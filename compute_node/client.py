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
        # Load configuration file
        import config
        self.debug = config.DEBUG  # Global debug switch
        self.receptor_cache_lock = threading.Lock()  # Global lock for receptor cache
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
        
        # Create necessary directories
        self.work_dir = Path('work_dir')
        self.work_dir.mkdir(exist_ok=True)
        
        # Create receptor cache directory
        self.receptor_cache_dir = Path('receptor_cache')
        self.receptor_cache_dir.mkdir(exist_ok=True)
        
        # Initialize SSL context and secure socket
        self.ssl_context = SSLContextManager().get_client_context()
        self.sock = None
        self.secure_sock = None
        
        # Initialize cache-related variables
        self.cache_lock = threading.Lock()
        self.sock_lock = threading.Lock()  # Add socket lock
        self.next_task = None
        self.next_task_files = {}
        
        # Connect and authenticate
        if not self.connect_tcp():
            raise ConnectionError("Unable to connect to server")
        
        # Start cleanup thread
        self._start_cleanup_thread()
        logger.info("DockingClient initialized successfully")
    
    def connect_tcp(self):
        """Connect to the TCP command server, supporting automatic reconnection"""
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
                
                # Create a new socket and establish a TLS connection
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
                    return False
                
                logger.info("Successfully connected and authenticated to TCP server")
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
        """Get task from server, supporting automatic reconnection"""
        try:
            # Check connection status and try to send data
            self.secure_sock.send_message({'type': 'get_task'})
            response = self.secure_sock.receive_message()
            if not response:
                # Only reconnect if the connection is actually lost
                if self.connect_tcp():
                    return self.get_task()
                return {'task_id': None}
            return response
        except Exception as e:
            logger.error(f"Error getting task: {e}")
            # Only attempt to reconnect if there is a connection error
            if self.connect_tcp():
                return self.get_task()
            return {'task_id': None}

    def download_input(self, task_id, filename):
        """Download input file, supporting automatic retry"""
        logger.info(f"Downloading input file: {filename} for task {task_id}")
        retries = 0
        
        # If it is a receptor file, check the cache first
        if filename == 'receptor.pdbqt':
            with self.receptor_cache_lock:  # Lock
                cached_receptor = self.receptor_cache_dir / f"{task_id}_receptor.pdbqt"
                if cached_receptor.exists():
                    logger.info(f"Using cached receptor file (Task ID: {task_id})")
                    task_dir = self.work_dir / str(task_id)
                    task_dir.mkdir(exist_ok=True)
                    receptor_dest = task_dir / filename
                    shutil.copy2(cached_receptor, receptor_dest)
                    return receptor_dest
        
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
                
                # If it is a receptor file, save it to the cache
                if filename == 'receptor.pdbqt':
                    with self.receptor_cache_lock:  # Lock
                        cached_receptor = self.receptor_cache_dir / f"{task_id}_receptor.pdbqt"
                        shutil.copy2(input_path, cached_receptor)
                        logger.info(f"Cached receptor file (Task ID: {task_id})")
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
        """Submit task result, supporting automatic retry"""
        retries = 0
        while retries < self.max_retries:
            try:
                if not output_file.exists():
                    logger.error(f"Error: Output file {output_file} does not exist")
                    return False
                
                # Upload result file
                with open(output_file, 'rb') as f:
                    files = {'file': f}
                    url = f'{self.http_base_url}/upload/result/{task_id}/{output_file.name}'
                    response = requests.post(url, files=files)
                    response.raise_for_status()
                
                # Update task status
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
                    # Only reconnect if the connection is actually lost
                    if not response and self.connect_tcp():
                        self.secure_sock.send_message(data)
                        response = self.secure_sock.receive_message()
                        return response and response.get('status') == 'ok'
                    return False
                except Exception as e:
                    logger.error(f"TCP communication error: {e}")
                    # Only attempt to reconnect if there is a connection error
                    if self.connect_tcp():
                        self.secure_sock.send_message(data)
                        response = self.secure_sock.receive_message()
                        return response and response.get('status') == 'ok'
                    return False
            
            except requests.exceptions.RequestException as e:
                retries += 1
                logger.error(f"HTTP upload attempt {retries} failed: {e}")
                if retries < self.max_retries:
                    logger.debug(f"Retrying upload in {self.retry_delay} seconds")
                    time.sleep(self.retry_delay)
        
        return False
    
    def run_vina(self, task_id, ligand_id, receptor_file, ligand_file, params):
        """Execute vina molecular docking command"""
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
            # Use Popen to get real-time output
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            # Process output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Parse progress information from output
                    if 'Writing output' in output:
                        logger.info(f"Task {task_id} ligand {ligand_id}: Docking completed, writing results")
                    elif 'Reading input' in output:
                        logger.info(f"Task {task_id} ligand {ligand_id}: Reading input files")
                    elif 'Performing search' in output:
                        logger.info(f"Task {task_id} ligand {ligand_id}: Performing docking search")
                    else:
                        logger.debug(output.strip())
            
            # Check process return value
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
    
    def _start_precache_thread(self):
        """Start precache thread to prefetch and download files for the next task"""
        def precache_worker():
            while True:
                try:
                    # Get the next task
                    with self.cache_lock:
                        if self.next_task is None:
                            next_task = self.get_task()
                            if next_task.get('task_id') is not None:
                                self.next_task = next_task
                                # Pre-download files
                                receptor_file = self.download_input(next_task['task_id'], 'receptor.pdbqt')
                                ligand_file = self.download_input(next_task['task_id'], next_task['ligand_file'])
                                if receptor_file and ligand_file:
                                    self.next_task_files = {
                                        'receptor_file': receptor_file,
                                        'ligand_file': ligand_file
                                    }
                                    logger.info(f"Precached files for next task {next_task['task_id']}")
                except Exception as e:
                    logger.error(f"Error in precache thread: {e}")
                time.sleep(5)

        # Create and start precache thread
        precache_thread = threading.Thread(target=precache_worker)
        precache_thread.daemon = True
        precache_thread.start()
        logger.info("Precache thread started")

    def run(self):
        """Run compute node main loop"""
        logger.info("Starting compute node...")
        
        # Ensure initial connection is established
        if not self.secure_sock or not self.connect_tcp():
            logger.error("Failed to establish initial connection to server")
            return
        
        while True:
            try:
                # Check if there is a precached task
                with self.cache_lock:
                    if self.next_task is not None:
                        task = self.next_task
                        files = self.next_task_files
                        self.next_task = None
                        self.next_task_files = {}
                    else:
                        task = self.get_task()
                        files = {}

                if task.get('task_id') is None:
                    time.sleep(5)
                    continue

                logger.info(f"Received task {task['task_id']}")

                # Use precached files or download required files
                receptor_file = files.get('receptor_file') or self.download_input(task['task_id'], 'receptor.pdbqt')
                ligand_file = files.get('ligand_file') or self.download_input(task['task_id'], task['ligand_file'])

                if not all([receptor_file, ligand_file]):
                    logger.error("Failed to download required files")
                    continue
                
                # Perform molecular docking
                output_path = self.run_vina(task['task_id'], task['ligand_id'],
                                          receptor_file, ligand_file, task['params'])
                if not output_path:
                    logger.error("Docking failed")
                    self._mark_ligand_failed(task['task_id'], task['ligand_id'])
                    continue
                
                # Submit result
                if self.submit_result(task['task_id'], task['ligand_id'], output_path):
                    logger.info(f"Task {task['task_id']} ligand {task['ligand_id']} completed successfully")
                else:
                    logger.info(f"Failed to submit results for task {task['task_id']} ligand {task['ligand_id']}")
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                self._mark_ligand_failed(task['task_id'], task['ligand_id'])
                # If an error occurs, try to re-establish the connection
                if not self.connect_tcp():
                    logger.error("Failed to reconnect to server, exiting...")
                    return
                time.sleep(self.retry_delay)


    
    def _start_cleanup_thread(self):
        """Start cleanup thread to periodically clean up expired work directory files"""
        def cleanup_worker():
            while True:
                try:
                    # Get current time
                    now = datetime.now()
                    # Traverse the work directory
                    for task_dir in self.work_dir.iterdir():
                        if task_dir.is_dir():
                            # Get the last modification time of the directory
                            mtime = datetime.fromtimestamp(task_dir.stat().st_mtime)
                            # If the directory exceeds the cleanup time threshold, delete it
                            if (now - mtime).total_seconds() > self.cleanup_age:
                                logger.info(f"Cleaning up expired task directory: {task_dir}")
                                shutil.rmtree(task_dir)
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")
                # Wait for the next cleanup
                time.sleep(self.cleanup_interval)
        
        # Create and start cleanup thread
        cleanup_thread = threading.Thread(target=cleanup_worker)
        cleanup_thread.daemon = True  # Set as daemon thread
        cleanup_thread.start()
        logger.info("Cleanup thread started")

    def _mark_ligand_failed(self, task_id, ligand_id):
        """Mark ligand as failed"""
        try:
            data = {
                'type': 'submit_result',
                'task_id': task_id,
                'ligand_id': ligand_id,
                'output_file': None,
                'status': 'failed'
            }
            self.secure_sock.send_message(data)
            response = self.secure_sock.receive_message()
            return response and response.get('status') == 'ok'
        except Exception as e:
            logger.error(f"Failed to mark ligand as failed: {e}")
            return False

if __name__ == '__main__':
    client = DockingClient()
    client.run()