import tkinter as tk
from tkinter import ttk, scrolledtext
import mysql.connector
from datetime import datetime
import sys
import os
import threading
from queue import Queue

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import execute_query, execute_update, get_db_connection
from monitor_server.includes.data_functions import (
    get_tasks_progress, get_node_performance,
    get_node_stats, get_task_queue_stats,
    get_task_performance_stats, get_node_cpu_trend
)

class DataRefreshThread(threading.Thread):
    def __init__(self, conn, data_queue):
        super().__init__()
        self.conn = conn
        self.data_queue = data_queue
        self.running = True
        self.daemon = True  # Set as a daemon thread, exits with the main thread

    def run(self):
        while self.running:
            try:
                tasks = get_tasks_progress(self.conn)
                self.data_queue.put(('tasks', tasks))
            except Exception as e:
                self.data_queue.put(('error', str(e)))
            threading.Event().wait(30)  # Refresh every 30 seconds

    def stop(self):
        self.running = False

class VortexDockGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('VortexDock Monitoring System')
        self.root.geometry('800x600')
        self.root.configure(bg='#f0f2f5')

        # Database connection
        try:
            self.conn = get_db_connection()
        except Exception as e:
            print(f'Database connection failed: {str(e)}')
            sys.exit(1)

        # Initialize data queue
        self.data_queue = Queue()

        # Create main frame
        self.create_main_frame()
        
        # Initialize terminal output area
        self.create_terminal()
        
        # Start data refresh thread
        self.start_refresh_thread()
        
        # Start checking the data queue
        self.check_data_queue()

    def create_main_frame(self):
        # Create task list panel
        self.create_task_list()

    def create_task_list(self):
        # Task list title
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(title_frame, text='Task List', font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        ttk.Button(title_frame, text='Refresh', command=self.manual_refresh).pack(side=tk.RIGHT)

        # Task list
        self.task_tree = ttk.Treeview(self.root, columns=('ID', 'Status', 'Progress', 'Estimated Remaining Time'), show='headings')
        self.task_tree.heading('ID', text='Task ID')
        self.task_tree.heading('Status', text='Status')
        self.task_tree.heading('Progress', text='Progress')
        self.task_tree.heading('Estimated Remaining Time', text='Estimated Remaining Time')
        self.task_tree.pack(fill=tk.BOTH, expand=True, padx=5)

        # Task control buttons
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(control_frame, text='Pause Task', command=self.pause_task).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text='Resume Task', command=self.resume_task).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text='Delete Task', command=self.delete_task).pack(side=tk.LEFT, padx=2)

    def create_terminal(self):
        # Terminal output area
        terminal_frame = ttk.LabelFrame(self.root, text='Terminal Output')
        terminal_frame.pack(fill=tk.BOTH, padx=10, pady=5)

        self.terminal = scrolledtext.ScrolledText(terminal_frame, height=8)
        self.terminal.pack(fill=tk.BOTH, expand=True)

    def log_to_terminal(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.terminal.insert(tk.END, f'[{timestamp}] {message}\n')
        self.terminal.see(tk.END)

    def start_refresh_thread(self):
        self.refresh_thread = DataRefreshThread(self.conn, self.data_queue)
        self.refresh_thread.start()

    def check_data_queue(self):
        try:
            while self.data_queue.qsize():
                msg_type, data = self.data_queue.get_nowait()
                if msg_type == 'tasks':
                    self.update_task_list(data)
                elif msg_type == 'error':
                    self.log_to_terminal(f'Failed to refresh task list: {data}')
                elif msg_type == 'refresh':
                    # Handle manual refresh request
                    try:
                        tasks = get_tasks_progress(self.conn)
                        self.update_task_list(tasks)
                    except Exception as e:
                        self.log_to_terminal(f'Failed to manually refresh task list: {str(e)}')
        except Exception as e:
            self.log_to_terminal(f'Error processing data updates: {str(e)}')
        finally:
            # Check the queue every 100ms
            self.root.after(100, self.check_data_queue)

    def update_task_list(self, tasks):
        # Clear existing items
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        # Add new data
        for task in tasks:
            self.task_tree.insert('', 'end', values=(
                task['id'],
                task['status'],
                f"{task['progress']}%",
                task['estimated_time'] or '--'
            ))
        
        self.log_to_terminal('Task list refreshed')

    def manual_refresh(self):
        try:
            # Send refresh request to the data queue
            self.data_queue.put(('refresh', None))
            self.log_to_terminal('Refreshing task list...')
        except Exception as e:
            self.log_to_terminal(f'Failed to send refresh request: {str(e)}')

    def pause_task(self):
        selected = self.task_tree.selection()
        if not selected:
            self.log_to_terminal('Please select a task to pause first')
            return
        
        task_id = self.task_tree.item(selected[0])['values'][0]
        try:
            # Check if the task exists
            task = execute_query('SELECT status FROM tasks WHERE id = %s', (task_id,), fetch_one=True)
            if not task:
                self.log_to_terminal(f'Error: Task {task_id} not found')
                return
            
            current_status = task['status']
            new_status = 'paused' if current_status == 'pending' else 'pending'
            
            # Update task status
            execute_update('UPDATE tasks SET status = %s WHERE id = %s', (new_status, task_id))
            
            action = 'paused' if new_status == 'paused' else 'resumed'
            self.log_to_terminal(f'Successfully {action} task {task_id}')
            
            # Refresh task list
            self.manual_refresh()
            
        except Exception as e:
            self.log_to_terminal(f'Error updating task status: {str(e)}')

    def resume_task(self):
        selected = self.task_tree.selection()
        if not selected:
            self.log_to_terminal('Please select a task to resume first')
            return
        
        task_id = self.task_tree.item(selected[0])['values'][0]
        # TODO: Implement task resume logic
        self.log_to_terminal(f'Task {task_id} resumed')

    def delete_task(self):
        selected = self.task_tree.selection()
        if not selected:
            self.log_to_terminal('Please select a task to delete first')
            return
        
        task_id = self.task_tree.item(selected[0])['values'][0]
        # TODO: Implement task delete logic
        self.log_to_terminal(f'Task {task_id} deleted')

    def __del__(self):
        if hasattr(self, 'refresh_thread'):
            self.refresh_thread.stop()
        if hasattr(self, 'conn') and self.conn.is_connected():
            self.conn.close()

def main():
    root = tk.Tk()
    app = VortexDockGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()