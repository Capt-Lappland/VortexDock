import curses
import sys
import time
import psutil
import threading
import subprocess
import socket
from datetime import datetime
from pathlib import Path

import sys
sys.path.append('..')
from config import PROCESS_CONFIG, SERVER_CONFIG, TASK_CONFIG
from utils.logger import logger
from utils.network import SSLContextManager, SecureSocket

class ProcessManager:
    def __init__(self):
        # 进程配置
        self.max_processes = PROCESS_CONFIG['max_processes']
        self.process_start_interval = PROCESS_CONFIG['process_start_interval']
        self.min_memory_per_process = PROCESS_CONFIG['min_memory_per_process']
        self.max_cpu_per_process = PROCESS_CONFIG['max_cpu_per_process']
        
        # 服务器配置
        self.server_host = SERVER_CONFIG['host']
        self.tcp_port = SERVER_CONFIG['tcp_port']
        self.server_password = SERVER_CONFIG['password']
        
        # 心跳配置
        self.heartbeat_interval = TASK_CONFIG['heartbeat_interval']
        self.retry_delay = TASK_CONFIG['retry_delay']
        self.max_retries = TASK_CONFIG['max_retries']
        
        # 进程管理
        self.processes = {}
        self.process_outputs = {}
        self.process_lock = threading.Lock()
        
        # 网络连接
        self.ssl_context = SSLContextManager().get_client_context()
        self.secure_sock = None
        self.sock_lock = threading.Lock()
        
        # 初始化curses
        self.screen = curses.initscr()
        curses.start_color()
        curses.use_default_colors()  # 使用终端默认颜色
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # -1表示使用默认背景色
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)  # 隐藏光标
        self.screen.keypad(True)
        
        # 获取屏幕尺寸
        self.height, self.width = self.screen.getmaxyx()
        
        # 创建窗口
        self.daemon_window = curses.newwin(5, self.width, 0, 0)
        self.process_windows = {}
        process_height = (self.height - 5) // 5
        for i in range(5):
            self.process_windows[i] = curses.newwin(
                process_height,
                self.width,
                5 + i * process_height,
                0
            )
    
    def start_process(self, process_id):
        """启动一个新的client.py进程"""
        try:
            process = subprocess.Popen(
                [sys.executable, 'client.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            with self.process_lock:
                self.processes[process_id] = process
                self.process_outputs[process_id] = []
            
            # 启动输出监控线程
            threading.Thread(
                target=self.monitor_process_output,
                args=(process_id,),
                daemon=True
            ).start()
            
            logger.info(f"Started process {process_id} with PID {process.pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to start process {process_id}: {e}")
            return False
    
    def monitor_process_output(self, process_id):
        """监控进程输出并更新显示"""
        process = self.processes[process_id]
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                with self.process_lock:
                    self.process_outputs[process_id].append(output.strip())
                    # 保持最新的100行输出
                    if len(self.process_outputs[process_id]) > 100:
                        self.process_outputs[process_id].pop(0)
    
    def update_daemon_status(self):
        """更新守护进程状态显示"""
        self.daemon_window.clear()
        self.daemon_window.box()
        self.daemon_window.addstr(0, 2, " 守护进程状态 ")
        
        # 显示系统资源使用情况
        cpu_percent = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        self.daemon_window.addstr(1, 2, f"CPU使用率: {cpu_percent}%")
        self.daemon_window.addstr(2, 2, f"内存使用: {mem.percent}%")
        self.daemon_window.addstr(3, 2, f"运行进程数: {len(self.processes)}")
        
        self.daemon_window.refresh()
    
    def update_process_status(self):
        """更新所有进程状态显示"""
        with self.process_lock:
            for process_id, window in self.process_windows.items():
                window.clear()
                window.box()
                
                process = self.processes.get(process_id)
                if process:
                    status = "运行中" if process.poll() is None else "已停止"
                    color = curses.color_pair(1) if status == "运行中" else curses.color_pair(2)
                    window.addstr(0, 2, f" 进程 {process_id} (PID: {process.pid}) - {status} ", color)
                    
                    # 显示进程输出
                    outputs = self.process_outputs.get(process_id, [])
                    max_lines = window.getmaxyx()[0] - 2
                    for i, line in enumerate(outputs[-max_lines:]):
                        try:
                            window.addstr(i + 1, 2, line[:self.width-4])
                        except curses.error:
                            pass
                else:
                    window.addstr(0, 2, f" 进程 {process_id} - 未启动 ", curses.color_pair(3))
                
                window.refresh()
    
    def check_and_restart_processes(self):
        """检查进程状态并在需要时重启"""
        with self.process_lock:
            for process_id, process in list(self.processes.items()):
                if process.poll() is not None:
                    logger.warning(f"Process {process_id} (PID: {process.pid}) has stopped, restarting...")
                    self.start_process(process_id)
    
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
                raw_sock.settimeout(10)  # 设置连接超时时间
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
                    self.secure_sock.close()
                    retries += 1
                    if retries < self.max_retries:
                        time.sleep(min(self.retry_delay * (retries + 1), 30))  # 使用指数退避策略
                    continue
                
                logger.info("Successfully connected and authenticated to TCP server")
                # 发送初始心跳包
                cpu_usage = psutil.cpu_percent(interval=1)
                self.secure_sock.send_message({
                    'type': 'heartbeat',
                    'cpu_usage': cpu_usage
                })
                response = self.secure_sock.receive_message()
                if not response or response.get('status') != 'ok':
                    logger.error("Initial heartbeat failed")
                    self.secure_sock.close()
                    retries += 1
                    if retries < self.max_retries:
                        time.sleep(min(self.retry_delay * (retries + 1), 30))  # 使用指数退避策略
                    continue
                
                # 启动心跳线程
                self._start_heartbeat_thread()
                return True
            except Exception as e:
                retries += 1
                logger.warning(f"TCP connection attempt {retries} failed: {e}")
                if self.secure_sock:
                    self.secure_sock.close()
                if retries < self.max_retries:
                    time.sleep(min(self.retry_delay * (retries + 1), 30))  # 使用指数退避策略
        
        logger.error("Failed to connect to TCP server after maximum retries")
        return False

    def _start_heartbeat_thread(self):
        """启动心跳线程，定期发送心跳包和性能数据"""
        def heartbeat_worker():
            consecutive_failures = 0
            max_failures = 3
            while True:
                try:
                    # 检查连接状态
                    if not self.secure_sock:
                        logger.warning("No active connection, attempting to reconnect...")
                        if not self.connect_tcp():
                            consecutive_failures += 1
                            if consecutive_failures >= max_failures:
                                logger.error("Maximum reconnection attempts reached")
                                time.sleep(self.retry_delay * 2)
                                consecutive_failures = 0
                            continue
                    
                    # 获取系统性能数据
                    cpu_usage = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    # 发送心跳包
                    with self.sock_lock:
                        try:
                            self.secure_sock.send_message({
                                'type': 'heartbeat',
                                'cpu_usage': cpu_usage,
                                'memory_usage': memory.percent
                            })
                            response = self.secure_sock.receive_message()
                            if not response or response.get('status') != 'ok':
                                raise ConnectionError("Invalid heartbeat response")
                            consecutive_failures = 0  # 重置失败计数
                        except Exception as e:
                            logger.warning(f"Heartbeat failed: {e}, attempting to reconnect...")
                            self.secure_sock = None  # 标记连接为无效
                            consecutive_failures += 1
                            if consecutive_failures >= max_failures:
                                logger.error("Maximum reconnection attempts reached")
                                time.sleep(self.retry_delay * 2)
                                consecutive_failures = 0
                except Exception as e:
                    logger.error(f"Error in heartbeat thread: {e}")
                    time.sleep(self.retry_delay)
                finally:
                    time.sleep(self.heartbeat_interval)
        
        # 创建并启动心跳线程
        heartbeat_thread = threading.Thread(target=heartbeat_worker)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()
        logger.info("Heartbeat thread started")

    def run(self):
        """运行守护进程主循环"""
        try:
            # 建立与服务器的连接
            if not self.connect_tcp():
                logger.error("Failed to connect to server")
                return
            # 启动初始进程
            for i in range(min(5, self.max_processes)):
                if self.start_process(i):
                    time.sleep(self.process_start_interval)
            
            # 主循环
            while True:
                try:
                    # 批量更新窗口，减少闪烁
                    curses.update_lines_cols()
                    self.update_daemon_status()
                    self.update_process_status()
                    self.check_and_restart_processes()
                    curses.doupdate()  # 一次性刷新所有窗口
                    time.sleep(1)  # 使用单一的延迟时间
                except curses.error as e:
                    logger.error(f"Curses error in main loop: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error in main loop: {e}")
                    time.sleep(1)  # 发生错误时也保持延迟
                
        except KeyboardInterrupt:
            pass
        finally:
            # 清理并恢复终端状态
            curses.nocbreak()
            self.screen.keypad(False)
            curses.echo()
            curses.endwin()
            
            # 终止所有子进程
            for process in self.processes.values():
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    process.kill()

if __name__ == '__main__':
    manager = ProcessManager()
    manager.run()