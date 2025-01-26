# -*- coding: utf-8 -*-

import os
import json
import time
import socket
import requests
import subprocess
import threading
import shutil
from datetime import datetime
from pathlib import Path

import sys
sys.path.append('..')
from utils.logger import logger
from utils.network import SSLContextManager, SecureSocket

class DockingClient:
    def __init__(self):
        # 加载配置文件
        import config
        self.debug = config.DEBUG  # 全局调试开关
        logger.info("Initializing DockingClient")
        self.server_host = config.SERVER_CONFIG['host']
        self.http_port = config.SERVER_CONFIG['http_port']
        self.tcp_port = config.SERVER_CONFIG['tcp_port']
        self.server_password = config.SERVER_CONFIG['password']
        self.http_base_url = f'http://{self.server_host}:{self.http_port}'
        self.max_retries = config.TASK_CONFIG['max_retries']
        self.retry_delay = config.TASK_CONFIG['retry_delay']
        self.task_timeout = config.TASK_CONFIG['task_timeout']
        self.cleanup_interval = config.TASK_CONFIG['cleanup_interval']
        self.cleanup_age = config.TASK_CONFIG['cleanup_age']
        self.heartbeat_interval = config.TASK_CONFIG['heartbeat_interval']
        
        # 创建必要的目录
        self.work_dir = Path('work_dir')
        self.work_dir.mkdir(exist_ok=True)
        
        # 初始化SSL上下文和安全套接字
        self.ssl_context = SSLContextManager().get_client_context()
        self.sock = None
        self.secure_sock = None
        
        # 连接并验证
        if not self.connect_tcp():
            raise ConnectionError("无法连接到服务器")
        
        # 启动清理线程
        self._start_cleanup_thread()
        logger.info("DockingClient initialized successfully")
    
    def connect_tcp(self):
        """连接到 TCP 命令服务器，支持自动重连"""
        logger.info("Attempting to connect to TCP server")
        retries = 0
        while retries < self.max_retries:
            try:
                if self.secure_sock:
                    try:
                        self.secure_sock.close()
                        logger.debug("Closed existing secure socket connection")
                    except Exception as e:
                        logger.debug(f"Error closing existing secure socket: {e}")
                
                # 创建新的套接字并建立TLS连接
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_sock.connect((self.server_host, self.tcp_port))
                self.secure_sock = SecureSocket(raw_sock, self.ssl_context)
                
                # 发送认证信息
                auth_data = {
                    'type': 'auth',
                    'password': self.server_password
                }
                self.secure_sock.send_message(auth_data)
                
                # 等待认证结果
                response = self.secure_sock.receive_message()
                if not response or response.get('status') != 'ok':
                    logger.error("Authentication failed")
                    return False
                
                logger.info("Successfully connected and authenticated to TCP server")
                # 发送初始心跳包
                self.secure_sock.send_message({'type': 'heartbeat'})
                response = self.secure_sock.receive_message()
                if not response or response.get('status') != 'ok':
                    logger.error("Initial heartbeat failed")
                    return False
                return True
            except Exception as e:
                retries += 1
                logger.warning(f"TCP connection attempt {retries} failed: {e}")
                if retries < self.max_retries:
                    logger.debug(f"Retrying in {self.retry_delay} seconds")
                    time.sleep(self.retry_delay)
        
        logger.error("Failed to connect to TCP server after maximum retries")
        return False
    
    def get_task(self):
        """从服务器获取任务，支持自动重连"""
        try:
            # 检查连接状态并尝试发送数据
            self.secure_sock.send_message({'type': 'get_task'})
            response = self.secure_sock.receive_message()
            if not response:
                # 只有在确实断开连接时才重连
                if self.connect_tcp():
                    return self.get_task()
                return {'task_id': None}
            return response
        except Exception as e:
            logger.error(f"Error getting task: {e}")
            # 只在连接出错时尝试重连
            if self.connect_tcp():
                return self.get_task()
            return {'task_id': None}

    def download_input(self, task_id, filename):
        """下载输入文件，支持自动重试"""
        logger.info(f"Downloading input file: {filename} for task {task_id}")
        retries = 0
        while retries < self.max_retries:
            try:
                task_dir = self.work_dir / str(task_id)
                task_dir.mkdir(exist_ok=True)
                logger.debug(f"Created task directory: {task_dir}")
                
                if filename == 'receptor.pdbqt':
                    file_dir = task_dir
                else:
                    ligand_dir = task_dir / 'ligands'
                    ligand_dir.mkdir(exist_ok=True)
                    file_dir = ligand_dir
                
                url = f'{self.http_base_url}/download/{task_id}/{filename}'
                input_path = file_dir / filename
                
                response = requests.get(url, stream=True)
                response.raise_for_status()
                
                with open(input_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return input_path
            
            except (requests.exceptions.RequestException, IOError) as e:
                retries += 1
                logger.warning(f"Download attempt {retries} failed: {e}")
                if retries < self.max_retries:
                    logger.debug(f"Retrying download in {self.retry_delay} seconds")
                    time.sleep(self.retry_delay)
                elif input_path.exists():
                    logger.debug(f"Cleaning up failed download: {input_path}")
                    input_path.unlink()
        
        return None
    
    def submit_result(self, task_id, ligand_id, output_file):
        """提交任务结果，支持自动重试"""
        retries = 0
        while retries < self.max_retries:
            try:
                if not output_file.exists():
                    logger.error(f"Error: Output file {output_file} does not exist")
                    return False
                
                # 上传结果文件
                with open(output_file, 'rb') as f:
                    files = {'file': f}
                    url = f'{self.http_base_url}/upload/result/{task_id}/{output_file.name}'
                    response = requests.post(url, files=files)
                    response.raise_for_status()
                
                # 更新任务状态
                data = {
                    'type': 'submit_result',
                    'task_id': task_id,
                    'ligand_id': ligand_id,
                    'output_file': output_file.name
                }
                try:
                    self.secure_sock.send_message(data)
                    response = self.secure_sock.receive_message()
                    if response and response.get('status') == 'ok':
                        return True
                    # 只在连接确实断开时才重连
                    if not response and self.connect_tcp():
                        self.secure_sock.send_message(data)
                        response = self.secure_sock.receive_message()
                        return response and response.get('status') == 'ok'
                    return False
                except Exception as e:
                    logger.error(f"TCP communication error: {e}")
                    # 只在连接出错时尝试重连
                    if self.connect_tcp():
                        self.secure_sock.send_message(data)
                        response = self.secure_sock.receive_message()
                        return response and response.get('status') == 'ok'
                    return False
            
            except requests.exceptions.RequestException as e:
                retries += 1
                logger.error(f"HTTP upload attempt {retries} failed: {e}")
                if retries < self.max_retries:
                    time.sleep(self.retry_delay)
        
        return False
    
    def run_vina(self, task_id, ligand_id, receptor_file, ligand_file, params):
        """执行 vina 分子对接命令"""
        logger.info(f"Starting Vina docking for task {task_id}, ligand {ligand_id}")
        task_dir = self.work_dir / str(task_id)
        output_file = f"{ligand_id}_out.pdbqt"
        output_path = task_dir / output_file
        logger.debug(f"Output will be saved to: {output_path}")
        
        vina_path = os.path.join(os.path.dirname(__file__), 'vina')
        cmd = [
            vina_path,
            '--receptor', str(receptor_file),
            '--ligand', str(ligand_file),
            '--center_x', str(params['center_x']),
            '--center_y', str(params['center_y']),
            '--center_z', str(params['center_z']),
            '--size_x', str(params['size_x']),
            '--size_y', str(params['size_y']),
            '--size_z', str(params['size_z']),
            '--num_modes', str(params['num_modes']),
            '--energy_range', str(params['energy_range']),
            '--cpu', str(params['cpu']),
            '--out', str(output_path)
        ]
        
        try:
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            # 实时处理输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # 解析输出中的进度信息
                    if 'Writing output' in output:
                        logger.info(f"Task {task_id} ligand {ligand_id}: Docking completed, writing results")
                    elif 'Reading input' in output:
                        logger.info(f"Task {task_id} ligand {ligand_id}: Reading input files")
                    elif 'Performing search' in output:
                        logger.info(f"Task {task_id} ligand {ligand_id}: Performing docking search")
                    else:
                        logger.debug(output.strip())
            
            # 检查进程返回值
            if process.returncode == 0:
                return output_path if output_path.exists() else None
            else:
                logger.error(f"Vina process failed with return code {process.returncode}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"Task {task_id} ligand {ligand_id} timed out after {self.task_timeout} seconds")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"Vina execution failed: {e}")
            return None
    
    def run(self):
        """运行计算节点主循环"""
        logger.info("Starting compute node...")
        
        # 确保初始连接建立
        if not self.secure_sock or not self.connect_tcp():
            logger.error("Failed to establish initial connection to server")
            return
        
        while True:
            try:
                # 获取任务
                task = self.get_task()
                if task.get('task_id') is None:
                    time.sleep(5)
                    continue
                
                logger.info(f"Received task {task['task_id']}")
                
                # 下载所需文件
                receptor_file = self.download_input(task['task_id'], 'receptor.pdbqt')
                ligand_file = self.download_input(task['task_id'], task['ligand_file'])
                
                if not all([receptor_file, ligand_file]):
                    logger.error("Failed to download required files")
                    continue
                
                # 执行分子对接
                output_path = self.run_vina(task['task_id'], task['ligand_id'],
                                          receptor_file, ligand_file, task['params'])
                if not output_path:
                    logger.error("Docking failed")
                    continue
                
                # 提交结果
                if self.submit_result(task['task_id'], task['ligand_id'], output_path):
                    logger.info(f"Task {task['task_id']} ligand {task['ligand_id']} completed successfully")
                else:
                    logger.info(f"Failed to submit results for task {task['task_id']} ligand {task['ligand_id']}")
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                # 如果发生错误，尝试重新建立连接
                if not self.connect_tcp():
                    logger.error("Failed to reconnect to server, exiting...")
                    return
                time.sleep(self.retry_delay)

    def _start_cleanup_thread(self):
        """启动清理线程，定期清理过期的工作目录文件"""
        def cleanup_worker():
            while True:
                try:
                    # 获取当前时间
                    now = datetime.now()
                    # 遍历工作目录
                    for task_dir in self.work_dir.iterdir():
                        if task_dir.is_dir():
                            # 获取目录的最后修改时间
                            mtime = datetime.fromtimestamp(task_dir.stat().st_mtime)
                            # 如果目录超过清理时间阈值，则删除
                            if (now - mtime).total_seconds() > self.cleanup_age:
                                logger.info(f"Cleaning up expired task directory: {task_dir}")
                                shutil.rmtree(task_dir)
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")
                # 等待下一次清理
                time.sleep(self.cleanup_interval)
        
        # 创建并启动清理线程
        cleanup_thread = threading.Thread(target=cleanup_worker)
        cleanup_thread.daemon = True  # 设置为守护线程
        cleanup_thread.start()
        logger.info("Cleanup thread started")

if __name__ == '__main__':
    client = DockingClient()
    client.run()