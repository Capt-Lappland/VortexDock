# -*- coding: utf-8 -*-

import os
import json
import socket
import mysql.connector
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 全局调试开关
DEBUG = True

import sys
sys.path.append('..')
from config import DB_CONFIG
from utils.logger import logger
from utils.network import SSLContextManager, SecureSocket

# 导入连接池模块
from mysql.connector import pooling

# 任务超时时间（秒）
TASK_TIMEOUT = 3600

# 创建数据库连接池
connection_pool = None

def init_connection_pool():
    global connection_pool
    try:
        connection_pool = mysql.connector.pooling.MySQLConnectionPool(**DB_CONFIG)
        logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.critical(f"Failed to initialize database connection pool: {e}")
        sys.exit(1)

# 数据库连接函数
def get_db_connection():
    try:
        return connection_pool.get_connection()
    except Exception as e:
        logger.error(f"Failed to get database connection: {e}")
        return None

# 数据库初始化
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 创建计算节点心跳表
    c.execute('''
        CREATE TABLE IF NOT EXISTS node_heartbeats (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            client_addr VARCHAR(255) NOT NULL,
            cpu_usage FLOAT NOT NULL,
            last_heartbeat TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_client_addr (client_addr),
            INDEX idx_last_heartbeat (last_heartbeat)
        )
    ''')
    
    # 创建服务器认证表
    c.execute('''
        CREATE TABLE IF NOT EXISTS server_auth (
            id INT PRIMARY KEY AUTO_INCREMENT,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id VARCHAR(255) PRIMARY KEY,
            status VARCHAR(50),
            center_x FLOAT,
            center_y FLOAT,
            center_z FLOAT,
            size_x FLOAT,
            size_y FLOAT,
            size_z FLOAT,
            num_modes INT,
            energy_range FLOAT,
            cpu INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 获取所有任务并为每个任务创建配体表
    c.execute('SELECT id FROM tasks')
    tasks = c.fetchall()
    for task in tasks:
        task_id = task[0]
        c.execute(f'''
            CREATE TABLE IF NOT EXISTS task_{task_id}_ligands (
                ligand_id VARCHAR(255) PRIMARY KEY,
                ligand_file VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                output_file VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    conn.commit()
    conn.close()

# 检查并重置超时任务
def check_timeout_tasks():
    while True:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # 获取所有处理中的配体任务
            timeout_time = datetime.now() - timedelta(seconds=TASK_TIMEOUT)
            c.execute('SELECT id FROM tasks')
            tasks = c.fetchall()
            
            for task in tasks:
                task_id = task[0]
                # 检查超时的配体任务
                c.execute(f'''
                    SELECT ligand_id, status, COUNT(*) as retry_count
                    FROM task_{task_id}_ligands
                    WHERE status IN ('processing', 'failed')
                    AND last_updated < %s
                    GROUP BY ligand_id, status
                ''', (timeout_time,))
                
                for ligand in c.fetchall():
                    ligand_id, status, retry_count = ligand
                    new_status = 'failed' if retry_count >= 3 else 'pending'
                    logger.info(f"Task {task_id} ligand {ligand_id} {status} -> {new_status} (retries: {retry_count})")
                    
                    c.execute(f'''
                        UPDATE task_{task_id}_ligands
                        SET status = %s, last_updated = CURRENT_TIMESTAMP
                        WHERE ligand_id = %s
                    ''', (new_status, ligand_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error checking timeout tasks: {e}")
        
        # 每分钟检查一次
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
    def __init__(self, host='0.0.0.0', port=10020):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((host, port))
        self.sock.listen(5)
        self.ssl_context = SSLContextManager().get_server_context()
    
    def verify_password(self, password):
        """验证客户端提供的密码"""
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT password_hash FROM server_auth ORDER BY created_at DESC LIMIT 1')
            result = c.fetchone()
            conn.close()
            
            if not result:
                logger.warning("No server password set")
                return True
            
            import bcrypt
            stored_hash = result[0].encode() if isinstance(result[0], str) else result[0]
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
                            conn = get_db_connection()
                            c = conn.cursor()
                            
                            # 更新节点心跳和性能数据
                            c.execute('''
                                INSERT INTO node_heartbeats (client_addr, cpu_usage, last_heartbeat)
                                VALUES (%s, %s, CURRENT_TIMESTAMP)
                            ''', (addr[0], command.get('cpu_usage', 0)))
                            conn.commit()
                            conn.close()
                            
                            secure_sock.send_message({'status': 'ok'})
                        except Exception as e:
                            logger.error(f"Error updating node heartbeat: {e}")
                            secure_sock.send_message({'status': 'error'})
                        continue
                    elif command['type'] == 'get_task':
                        logger.debug(f"Client {addr} requesting task")
                        # 获取待处理任务
                        conn = get_db_connection()
                        c = conn.cursor()
                        
                        try:
                            # 开始事务
                            conn.start_transaction()
                            
                            # 首先获取一个待处理的任务，优先选择进行中的任务
                            c.execute('''
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
                                FOR UPDATE
                            ''')
                            task = c.fetchone()
                            
                            if task:
                                (task_id,
                                 center_x, center_y, center_z,
                                 size_x, size_y, size_z,
                                 num_modes, energy_range, cpu) = task
                                
                                # 从该任务的配体表中获取一个待处理的配体，使用行级锁
                                c.execute(f'''
                                    SELECT ligand_id, ligand_file 
                                    FROM task_{task_id}_ligands 
                                    WHERE status = 'pending' 
                                    ORDER BY created_at ASC LIMIT 1
                                    FOR UPDATE
                                ''')
                                ligand = c.fetchone()
                                
                                if ligand:
                                    ligand_id, ligand_file = ligand
                                    logger.info(f"Assigning task {task_id} ligand {ligand_id} to client {addr}")
                                    
                                    # 更新配体状态和时间戳
                                    c.execute(f'''
                                        UPDATE task_{task_id}_ligands 
                                        SET status = 'processing', last_updated = CURRENT_TIMESTAMP 
                                        WHERE ligand_id = %s
                                    ''', (ligand_id,))
                                    # 提交事务
                                    # 提交事务
                                    conn.commit()
                                    
                                    response = {
                                        'task_id': task_id,
                                        'ligand_id': ligand_id,
                                        'ligand_file': ligand_file,
                                        'params': {
                                            'center_x': center_x,
                                            'center_y': center_y,
                                            'center_z': center_z,
                                            'size_x': size_x,
                                            'size_y': size_y,
                                            'size_z': size_z,
                                            'num_modes': num_modes,
                                            'energy_range': energy_range,
                                            'cpu': cpu
                                        }
                                    }
                                else:
                                    logger.debug(f"No pending ligands for task {task_id}")
                                    # 如果该任务的所有配体都已处理完，将任务标记为已完成
                                    c.execute('UPDATE tasks SET status = %s WHERE id = %s',
                                            ('completed', task_id))
                                    # 提交事务
                                    # 提交事务
                                    conn.commit()
                                    response = {'task_id': None}
                            else:
                                logger.debug("No pending tasks available")
                                response = {'task_id': None}
                        finally:
                            conn.close()
                        
                        secure_sock.send_message(response)
                    
                    elif command['type'] == 'submit_result':
                        task_id = command['task_id']
                        ligand_id = command['ligand_id']
                        logger.info(f"Client {addr} submitting result for task {task_id} ligand {ligand_id}")
                        
                        try:
                            conn = get_db_connection()
                            c = conn.cursor()
                            
                            # 更新配体状态和结果
                            c.execute(f'''
                                UPDATE task_{task_id}_ligands 
                                SET status = %s, output_file = %s, last_updated = CURRENT_TIMESTAMP 
                                WHERE ligand_id = %s
                            ''', ('completed', os.path.join('results', str(task_id), command['output_file']), ligand_id))
                            conn.commit()
                            conn.close()
                            
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
            thread = threading.Thread(target=self.handle_client,
                                   args=(client, addr))
            thread.start()

if __name__ == '__main__':
    # 创建必要的目录
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('results', exist_ok=True)
    
    # 初始化数据库连接池
    init_connection_pool()
    
    # 初始化数据库
    init_db()
    
    # 启动任务超时检查线程
    timeout_thread = threading.Thread(target=check_timeout_tasks)
    timeout_thread.daemon = True
    timeout_thread.start()
    
    # 启动 TCP 服务器
    tcp_server = TCPServer()
    tcp_thread = threading.Thread(target=tcp_server.start)
    tcp_thread.start()
    
    # 启动 Flask 服务器
    app.run(host='0.0.0.0', port=9000)