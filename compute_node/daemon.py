import curses
import sys
import time
import psutil
import threading
import subprocess
from datetime import datetime
from pathlib import Path

import sys
sys.path.append('..')
from config import PROCESS_CONFIG
from utils.logger import logger

class ProcessManager:
    def __init__(self):
        self.max_processes = PROCESS_CONFIG['max_processes']
        self.process_start_interval = PROCESS_CONFIG['process_start_interval']
        self.min_memory_per_process = PROCESS_CONFIG['min_memory_per_process']
        self.max_cpu_per_process = PROCESS_CONFIG['max_cpu_per_process']
        
        self.processes = {}
        self.process_outputs = {}
        self.process_lock = threading.Lock()
        
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
    
    def run(self):
        """运行守护进程主循环"""
        try:
            # 启动初始进程
            for i in range(min(5, self.max_processes)):
                if self.start_process(i):
                    time.sleep(self.process_start_interval)
            
            # 主循环
            while True:
                # 批量更新窗口，减少闪烁
                curses.update_lines_cols()
                self.update_daemon_status()
                self.update_process_status()
                self.check_and_restart_processes()
                curses.doupdate()  # 一次性刷新所有窗口
                time.sleep(0.5)  # 降低刷新频率
                time.sleep(1)
                
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