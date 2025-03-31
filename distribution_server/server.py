# -*- coding: utf-8 -*-

import os
import sys
import json
import socket
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, send_file
from werkzeug.utils import secure_filename

sys.path.append('..')
from utils.db import init_connection_pool, init_database, execute_query, execute_update, get_db_connection
from utils.logger import logger
from utils.network import SSLContextManager, SecureSocket
from config import SERVER_CONFIG, TASK_CONFIG, DB_CONFIG, DEBUG

app = Flask(__name__)

# 任务超时时间（秒）
TASK_TIMEOUT = 300

# 数据库连接状态
db_initialized = False

def init_db():
    """Initialize the database connection pool and table structure"""
    global db_initialized
    if not db_initialized:
        try:
            if DB_CONFIG['type'] == 'sqlite':
                init_database()  # SQLite does not use connection pooling
            else:
                init_connection_pool()
                init_database()
            db_initialized = True
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

# 检查并重置超时任务
def check_timeout_tasks():
    while True:
        try:
            timeout_time = datetime.now() - timedelta(seconds=TASK_TIMEOUT)
            
            # 获取所有未完成的任务
            tasks = execute_query("SELECT id FROM tasks WHERE status NOT IN ('completed', 'failed')")
            if not tasks:
                logger.debug("No tasks to check for timeout")
                time.sleep(60)
                continue
            
            for task in tasks:
                task_id = task[0] if DB_CONFIG['type'] == 'sqlite' else task['id']
                
                # 检查超时的配体（包含失败状态的配体）
                ligands = execute_query(f"""
                    SELECT ligand_id, status, retry_count
                    FROM task_{task_id}_ligands
                    WHERE status IN ('processing', 'failed')
                    AND last_updated < %s
                """, (timeout_time,))
                
                if not ligands:
                    logger.debug(f"No ligands to check for timeout in task {task_id}")
                    continue
                
                for ligand in ligands:
                    ligand_id = ligand[0] if DB_CONFIG['type'] == 'sqlite' else ligand['ligand_id']
                    status = ligand[1] if DB_CONFIG['type'] == 'sqlite' else ligand['status']
                    retry_count = ligand[2] if DB_CONFIG['type'] == 'sqlite' else ligand['retry_count']
                    
                    # 失败次数超过阈值则标记为最终失败
                    if retry_count >= TASK_CONFIG['max_retries']:
                        new_status = 'failed'
                    else:
                        new_status = 'pending'
                        retry_count += 1  # 增加重试计数

                    logger.info(f"Task {task_id} ligand {ligand_id} {status} -> {new_status} (retries: {retry_count})")
                    
                    execute_update(f"""
                        UPDATE task_{task_id}_ligands
                        SET status = %s,
                            retry_count = %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE ligand_id = %s
                    """, (new_status, retry_count, ligand_id))
                
                # 检查任务是否完全失败
                remaining = execute_query(f"""
                    SELECT COUNT(*) as count 
                    FROM task_{task_id}_ligands 
                    WHERE status NOT IN ('completed', 'failed')
                """, fetch_one=True)
                remaining = remaining[0] if DB_CONFIG['type'] == 'sqlite' else remaining.get('count', 0)
                
                if remaining == 0:
                    execute_update("UPDATE tasks SET status = 'completed' WHERE id = %s", (task_id,))
            
            # 提交事务（仅适用于 SQLite）
            if DB_CONFIG['type'] == 'sqlite':
                conn = get_db_connection()
                conn.commit()
                conn.close()

        except Exception as e:
            logger.error(f"Error checking timeout tasks: {e}")
        
        time.sleep(60)

# HTTP 文件服务器
@app.route('/download/<task_id>/<filename>')
def download_file(task_id, filename):
    # 根据文件名判断文件类型和位置
    if filename == 'receptor.pdbqt':
        file_path = os.path.join('tasks', str(task_id), filename)
        if os.path.exists(file_path):
            return send_file(file_path)
    elif filename.endswith('.pdbqt'):
        file_path = os.path.join('tasks', str(task_id), 'ligands', filename)
        if os.path.exists(file_path):
            return send_file(file_path)
    return {'error': '文件不存在或不支持下载该类型的文件'}, 404

@app.route('/upload/result/<task_id>/<filename>', methods=['POST'])
def upload_result_file(task_id, filename):
    result_dir = os.path.join('results', str(task_id))
    os.makedirs(result_dir, exist_ok=True)
    file_path = os.path.join(result_dir, filename)
    request.files['file'].save(file_path)
    return json.dumps({'status': 'ok'})

# TCP 命令服务器
class TCPServer:
    def __init__(self, host='0.0.0.0', port=None, init_db_connection=True):
        if init_db_connection:
            init_db()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((host, port or SERVER_CONFIG['tcp_port']))
        self.sock.listen(5)
        self.ssl_context = SSLContextManager().get_server_context()
    
    def verify_password(self, password):
        """验证客户端提供的密码"""
        try:
            result = execute_query(
                'SELECT password_hash FROM server_auth ORDER BY created_at DESC LIMIT 1',
                fetch_one=True
            )
            
            if not result:
                logger.warning("No server password set")
                return True
            
            import bcrypt
            stored_hash = result['password_hash'].encode() if isinstance(result['password_hash'], str) else result['password_hash']
            return bcrypt.checkpw(password.encode(), stored_hash)
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
    
    def handle_client(self, client_sock, addr):
        logger.info(f"Client {addr} connected")
        
        # 将原始套接字包装为安全套接字
        secure_sock = SecureSocket(client_sock, self.ssl_context)
        
        try:
            # 等待客户端发送密码
            auth_data = secure_sock.receive_message()
            if not auth_data or auth_data.get('type') != 'auth' or not self.verify_password(auth_data.get('password', '')):
                logger.warning(f"Authentication failed for client {addr}")
                secure_sock.send_message({'status': 'error', 'message': '认证失败'})
                return
            
            secure_sock.send_message({'status': 'ok'})
            logger.info(f"Client {addr} authenticated successfully")
            
            while True:
                try:
                    command = secure_sock.receive_message()
                    if not command:
                        logger.info(f"Client {addr} disconnected")
                        break
                    
                    if command['type'] == 'heartbeat':
                        # 处理心跳消息和性能数据
                        try:
                            execute_update('''
                                INSERT INTO node_heartbeats (client_addr, cpu_usage, memory_usage, last_heartbeat)
                                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                            ''', (addr[0], command.get('cpu_usage', 0), command.get('memory_usage', 0)))
                            
                            secure_sock.send_message({'status': 'ok'})
                        except Exception as e:
                            logger.error(f"Error updating node heartbeat: {e}")
                            secure_sock.send_message({'status': 'error'})
                        continue
                    elif command['type'] == 'get_task':
                        logger.debug(f"Client {addr} requesting task")
                        # 获取待处理任务
                        try:
                            # 获取一个待处理的任务，优先选择进行中的任务
                            task = execute_query('''
                                SELECT id,
                                center_x, center_y, center_z,
                                size_x, size_y, size_z,
                                num_modes, energy_range, cpu
                                FROM tasks 
                                WHERE status IN ('pending', 'processing')
                                ORDER BY 
                                    CASE status
                                        WHEN 'processing' THEN 0
                                        WHEN 'pending' THEN 1
                                    END,
                                    created_at ASC LIMIT 1
                            ''', fetch_one=True)
                            
                            if task:
                                task_id = task['id']
                                
                                # 从该任务的配体表中获取一个待处理的配体
                                ligand = execute_query(f'''
                                    SELECT ligand_id, ligand_file 
                                    FROM task_{task_id}_ligands 
                                    WHERE status = 'pending' 
                                    ORDER BY created_at ASC LIMIT 1
                                ''', fetch_one=True)
                                
                                if ligand:
                                    ligand_id, ligand_file = ligand['ligand_id'], ligand['ligand_file']
                                    logger.info(f"Assigning task {task_id} ligand {ligand_id} to client {addr}")
                                    
                                    # 更新配体状态和时间戳
                                    execute_update(f'''
                                        UPDATE task_{task_id}_ligands 
                                        SET status = 'processing', last_updated = CURRENT_TIMESTAMP 
                                        WHERE ligand_id = %s
                                    ''', (ligand_id,))
                                    
                                    response = {
                                        'task_id': task_id,
                                        'ligand_id': ligand_id,
                                        'ligand_file': ligand_file,
                                        'params': {
                                            'center_x': task['center_x'],
                                            'center_y': task['center_y'],
                                            'center_z': task['center_z'],
                                            'size_x': task['size_x'],
                                            'size_y': task['size_y'],
                                            'size_z': task['size_z'],
                                            'num_modes': task['num_modes'],
                                            'energy_range': task['energy_range'],
                                            'cpu': task['cpu']
                                        }
                                    }
                                else:
                                    logger.debug(f"No pending ligands for task {task_id}")
                                    # 如果该任务的所有配体都已处理完，将任务标记为已完成
                                    execute_update('UPDATE tasks SET status = %s WHERE id = %s', ('completed', task_id))
                                    response = {'task_id': None}
                            else:
                                logger.debug("No pending tasks available")
                                response = {'task_id': None}
                            
                            secure_sock.send_message(response)
                        except Exception as e:
                            logger.error(f"Error getting task: {e}")
                            secure_sock.send_message({'status': 'error'})
                    
                    elif command['type'] == 'submit_result':
                        task_id = command['task_id']
                        ligand_id = command['ligand_id']
                        status = command.get('status', 'completed')  # 新增状态字段
                        
                        try:
                            # 根据提交状态更新
                            if status == 'completed':
                                update_sql = '''
                                    UPDATE task_{task_id}_ligands 
                                    SET status = %s, 
                                        output_file = %s, 
                                        last_updated = CURRENT_TIMESTAMP 
                                    WHERE ligand_id = %s
                                '''
                                params = ('completed', os.path.join('results', str(task_id), command['output_file']), ligand_id)
                            else:
                                update_sql = '''
                                    UPDATE task_{task_id}_ligands 
                                    SET status = 'failed',
                                        retry_count = retry_count + 1,
                                        last_updated = CURRENT_TIMESTAMP 
                                    WHERE ligand_id = %s
                                '''
                                params = (ligand_id,)
                            
                            execute_update(update_sql.format(task_id=task_id), params)
                            secure_sock.send_message({'status': 'ok'})
                        except Exception as e:
                            logger.error(f"Error updating task status: {e}")
                            secure_sock.send_message({'status': 'error'})
                
                except Exception as e:
                    logger.error(f"Unexpected error handling client {addr}: {e}")
                    break
        except Exception as e:
            logger.error(f"Error during authentication for client {addr}: {e}")
        finally:
            secure_sock.close()
    
    def start(self):
        while True:
            client, addr = self.sock.accept()
            logger.info(f"New connection from {addr}")
            thread = threading.Thread(target=self.handle_client, args=(client, addr))
            thread.start()

if __name__ == '__main__':
    # 创建必要的目录
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('results', exist_ok=True)
    
    # 启动任务超时检查线程
    timeout_thread = threading.Thread(target=check_timeout_tasks)
    timeout_thread.daemon = True
    timeout_thread.start()
    
    # 启动 TCP 服务器
    tcp_server = TCPServer()
    tcp_thread = threading.Thread(target=tcp_server.start)
    tcp_thread.start()
    
    # 启动 Flask 服务器
    app.run(host='0.0.0.0', port=SERVER_CONFIG['http_port'])