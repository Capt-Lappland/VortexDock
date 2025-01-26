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

class DockingClient:
    def __init__(self):
        # 加载配置文件
        import config
        self.debug = config.DEBUG  # 全局调试开关
        logger.info("Initializing DockingClient")
        self.server_host = config.SERVER_CONFIG['host']
        self.http_port = config.SERVER_CONFIG['http_port']
        self.tcp_port = config.SERVER_CONFIG['tcp_port']
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
        self.sock = socket.socket()
        self.sock.connect((self.server_host, self.tcp_port))
        # 启动清理线程
        self._start_cleanup_thread()
        logger.info("DockingClient initialized successfully")
    
    def _start_cleanup_thread(self):
        """启动工作目录清理线程"""
        def cleanup_worker():
            while True:
                try:
                    self._cleanup_work_dir()
                except Exception as e:
                    logger.error(f"Error during cleanup: {e}")
                time.sleep(self.cleanup_interval)
        
        thread = threading.Thread(target=cleanup_worker, daemon=True)
        thread.start()
    
    def _cleanup_work_dir(self):
        """清理过期的工作目录"""
        now = datetime.now()
        for task_dir in self.work_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            try:
                # 检查目录的最后修改时间
                mtime = datetime.fromtimestamp(task_dir.stat().st_mtime)
                age = (now - mtime).total_seconds()
                
                if age > self.cleanup_age:
                    shutil.rmtree(task_dir)
                    logger.info(f"Cleaned up task directory: {task_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up {task_dir}: {e}")
    


    def connect_tcp(self):
        """连接到 TCP 命令服务器，支持自动重连"""
        logger.info("Attempting to connect to TCP server")
        retries = 0
        while retries < self.max_retries:
            try:
                if self.sock:
                    try:
                        self.sock.close()
                        logger.debug("Closed existing socket connection")
                    except Exception as e:
                        logger.debug(f"Error closing existing socket: {e}")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.server_host, self.tcp_port))
                logger.info("Successfully connected to TCP server")
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
            self.sock.send(json.dumps({'type': 'get_task'}).encode())
            data = self.sock.recv(1024)
            if not data:
                raise ConnectionError("服务器连接已断开")
            response = json.loads(data.decode())
            return response
        except (ConnectionError, json.JSONDecodeError, socket.error) as e:
            logger.error(f"Error getting task: {e}")
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
                    self.sock.send(json.dumps(data).encode())
                    response = json.loads(self.sock.recv(1024).decode())
                    return response['status'] == 'ok'
                except (socket.error, json.JSONDecodeError) as e:
                    logger.error(f"TCP communication error: {e}")
                    if self.connect_tcp():
                        # 重新发送任务状态
                        self.sock.send(json.dumps(data).encode())
                        response = json.loads(self.sock.recv(1024).decode())
                        return response['status'] == 'ok'
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
        
        while True:
            try:
                if not self.sock or not self.connect_tcp():
                    logger.warning("Failed to connect to server, retrying...")
                    time.sleep(self.retry_delay)
                    continue
                
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
                time.sleep(self.retry_delay)

if __name__ == '__main__':
    client = DockingClient()
    client.run()