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
        # Process configuration
        self.max_processes = PROCESS_CONFIG['max_processes']
        self.process_start_interval = PROCESS_CONFIG['process_start_interval']
        self.min_memory_per_process = PROCESS_CONFIG['min_memory_per_process']
        self.max_cpu_per_process = PROCESS_CONFIG['max_cpu_per_process']
        
        # Server configuration
        self.server_host = SERVER_CONFIG['host']
        self.tcp_port = SERVER_CONFIG['tcp_port']
        self.server_password = SERVER_CONFIG['password']
        
        # Heartbeat configuration
        self.heartbeat_interval = TASK_CONFIG['heartbeat_interval']
        self.retry_delay = TASK_CONFIG['retry_delay']
        self.max_retries = TASK_CONFIG['max_retries']
        
        # Process management
        self.processes = {}
        self.process_outputs = {}
        self.process_lock = threading.Lock()
        
        # Network connection
        self.ssl_context = SSLContextManager().get_client_context()
        self.secure_sock = None
        self.sock_lock = threading.Lock()
        
        # Initialize curses
        self.screen = curses.initscr()
        curses.start_color()
        curses.use_default_colors()  # Use terminal default colors
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # -1 means use default background color
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)  # Hide cursor
        self.screen.keypad(True)
        
        # Get screen size
        self.height, self.width = self.screen.getmaxyx()
        
        # Create windows
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
        """Start a new client.py process"""
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
            
            # Start output monitoring thread
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
        """Monitor process output and update display"""
        process = self.processes[process_id]
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                with self.process_lock:
                    self.process_outputs[process_id].append(output.strip())
                    # Keep the latest 100 lines of output
                    if len(self.process_outputs[process_id]) > 100:
                        self.process_outputs[process_id].pop(0)
    
    def update_daemon_status(self):
        """Update daemon status display"""
        self.daemon_window.clear()
        self.daemon_window.box()
        self.daemon_window.addstr(0, 2, " Daemon Status ")
        
        # Display system resource usage
        cpu_percent = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        self.daemon_window.addstr(1, 2, f"CPU Usage: {cpu_percent}%")
        self.daemon_window.addstr(2, 2, f"Memory Usage: {mem.percent}%")
        self.daemon_window.addstr(3, 2, f"Running Processes: {len(self.processes)}")
        
        self.daemon_window.refresh()
    
    def update_process_status(self):
        """Update all process status display"""
        with self.process_lock:
            for process_id, window in self.process_windows.items():
                window.clear()
                window.box()
                
                process = self.processes.get(process_id)
                if process:
                    status = "Running" if process.poll() is None else "Stopped"
                    color = curses.color_pair(1) if status == "Running" else curses.color_pair(2)
                    window.addstr(0, 2, f" Process {process_id} (PID: {process.pid}) - {status} ", color)
                    
                    # Display process output
                    outputs = self.process_outputs.get(process_id, [])
                    max_lines = window.getmaxyx()[0] - 2
                    for i, line in enumerate(outputs[-max_lines:]):
                        try:
                            window.addstr(i + 1, 2, line[:self.width-4])
                        except curses.error:
                            pass
                else:
                    window.addstr(0, 2, f" Process {process_id} - Not Started ", curses.color_pair(3))
                
                window.refresh()
    
    def check_and_restart_processes(self):
        """Check process status and restart if needed"""
        with self.process_lock:
            for process_id, process in list(self.processes.items()):
                if process.poll() is not None:
                    logger.warning(f"Process {process_id} (PID: {process.pid}) has stopped, restarting...")
                    self.start_process(process_id)
    
    def connect_tcp(self):
        """Connect to TCP command server, support auto-reconnect"""
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
                
                # Create new socket and establish TLS connection
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_sock.settimeout(10)  # Set connection timeout
                raw_sock.connect((self.server_host, self.tcp_port))
                self.secure_sock = SecureSocket(raw_sock, self.ssl_context)
                
                # Send authentication information
                auth_data = {
                    'type': 'auth',
                    'password': self.server_password
                }
                self.secure_sock.send_message(auth_data)
                
                # Wait for authentication result
                response = self.secure_sock.receive_message()
                if not response or response.get('status') != 'ok':
                    logger.error("Authentication failed")
                    self.secure_sock.close()
                    retries += 1
                    if retries < self.max_retries:
                        time.sleep(min(self.retry_delay * (retries + 1), 30))  # Use exponential backoff strategy
                    continue
                
                logger.info("Successfully connected and authenticated to TCP server")
                # Send initial heartbeat
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
                        time.sleep(min(self.retry_delay * (retries + 1), 30))  # Use exponential backoff strategy
                    continue
                
                # Start heartbeat thread
                self._start_heartbeat_thread()
                return True
            except Exception as e:
                retries += 1
                logger.warning(f"TCP connection attempt {retries} failed: {e}")
                if self.secure_sock:
                    self.secure_sock.close()
                if retries < self.max_retries:
                    time.sleep(min(self.retry_delay * (retries + 1), 30))  # Use exponential backoff strategy
        
        logger.error("Failed to connect to TCP server after maximum retries")
        return False

    def _start_heartbeat_thread(self):
        """Start heartbeat thread, periodically send heartbeat and performance data"""
        def heartbeat_worker():
            consecutive_failures = 0
            max_failures = 3
            while True:
                try:
                    # Check connection status
                    if not self.secure_sock:
                        logger.warning("No active connection, attempting to reconnect...")
                        if not self.connect_tcp():
                            consecutive_failures += 1
                            if consecutive_failures >= max_failures:
                                logger.error("Maximum reconnection attempts reached")
                                time.sleep(self.retry_delay * 2)
                                consecutive_failures = 0
                            continue
                    
                    # Get system performance data
                    cpu_usage = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    # Send heartbeat
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
                            consecutive_failures = 0  # Reset failure count
                        except Exception as e:
                            logger.warning(f"Heartbeat failed: {e}, attempting to reconnect...")
                            self.secure_sock = None  # Mark connection as invalid
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
        
        # Create and start heartbeat thread
        heartbeat_thread = threading.Thread(target=heartbeat_worker)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()
        logger.info("Heartbeat thread started")

    def run(self):
        """Run daemon main loop"""
        try:
            # Establish connection to server
            if not self.connect_tcp():
                logger.error("Failed to connect to server")
                return
            # Start initial processes
            for i in range(min(5, self.max_processes)):
                if self.start_process(i):
                    time.sleep(self.process_start_interval)
            
            # Main loop
            while True:
                try:
                    # Batch update windows to reduce flicker
                    curses.update_lines_cols()
                    self.update_daemon_status()
                    self.update_process_status()
                    self.check_and_restart_processes()
                    curses.doupdate()  # Refresh all windows at once
                    time.sleep(1)  # Use a single delay time
                except curses.error as e:
                    logger.error(f"Curses error in main loop: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error in main loop: {e}")
                    time.sleep(1)  # Maintain delay even when an error occurs
                
        except KeyboardInterrupt:
            pass
        finally:
            # Clean up and restore terminal state
            curses.nocbreak()
            self.screen.keypad(False)
            curses.echo()
            curses.endwin()
            
            # Terminate all child processes
            for process in self.processes.values():
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    process.kill()

if __name__ == '__main__':
    manager = ProcessManager()
    manager.run()