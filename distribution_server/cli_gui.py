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
        self.daemon = True  # 设置为守护线程，随主线程退出

    def run(self):
        while self.running:
            try:
                tasks = get_tasks_progress(self.conn)
                self.data_queue.put(('tasks', tasks))
            except Exception as e:
                self.data_queue.put(('error', str(e)))
            threading.Event().wait(30)  # 每30秒刷新一次

    def stop(self):
        self.running = False

class VortexDockGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('VortexDock 监控系统')
        self.root.geometry('800x600')
        self.root.configure(bg='#f0f2f5')

        # 数据库连接
        try:
            self.conn = get_db_connection()
        except Exception as e:
            print(f'数据库连接失败: {str(e)}')
            sys.exit(1)

        # 初始化数据队列
        self.data_queue = Queue()

        # 创建主框架
        self.create_main_frame()
        
        # 初始化终端输出区域
        self.create_terminal()
        
        # 启动数据刷新线程
        self.start_refresh_thread()
        
        # 开始检查数据队列
        self.check_data_queue()

    def create_main_frame(self):
        # 创建任务列表面板
        self.create_task_list()

    def create_task_list(self):
        # 任务列表标题
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(title_frame, text='任务列表', font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        ttk.Button(title_frame, text='刷新', command=self.manual_refresh).pack(side=tk.RIGHT)

        # 任务列表
        self.task_tree = ttk.Treeview(self.root, columns=('ID', '状态', '进度', '预计剩余时间'),show='headings')
        self.task_tree.heading('ID', text='任务ID')
        self.task_tree.heading('状态', text='状态')
        self.task_tree.heading('进度', text='进度')
        self.task_tree.heading('预计剩余时间', text='预计剩余时间')
        self.task_tree.pack(fill=tk.BOTH, expand=True, padx=5)

        # 任务控制按钮
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(control_frame, text='暂停任务', command=self.pause_task).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text='继续任务', command=self.resume_task).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text='删除任务', command=self.delete_task).pack(side=tk.LEFT, padx=2)

    def create_terminal(self):
        # 终端输出区域
        terminal_frame = ttk.LabelFrame(self.root, text='终端输出')
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
                    self.log_to_terminal(f'刷新任务列表失败: {data}')
                elif msg_type == 'refresh':
                    # 处理手动刷新请求
                    try:
                        tasks = get_tasks_progress(self.conn)
                        self.update_task_list(tasks)
                    except Exception as e:
                        self.log_to_terminal(f'手动刷新任务列表失败: {str(e)}')
        except Exception as e:
            self.log_to_terminal(f'处理数据更新时出错: {str(e)}')
        finally:
            # 每100ms检查一次队列
            self.root.after(100, self.check_data_queue)

    def update_task_list(self, tasks):
        # 清空现有项
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        # 添加新数据
        for task in tasks:
            self.task_tree.insert('', 'end', values=(
                task['id'],
                task['status'],
                f"{task['progress']}%",
                task['estimated_time'] or '--'
            ))
        
        self.log_to_terminal('已刷新任务列表')

    def manual_refresh(self):
        try:
            # 将刷新请求发送到数据队列
            self.data_queue.put(('refresh', None))
            self.log_to_terminal('正在刷新任务列表...')
        except Exception as e:
            self.log_to_terminal(f'发送刷新请求失败: {str(e)}')

    def check_data_queue(self):
        try:
            while self.data_queue.qsize():
                msg_type, data = self.data_queue.get_nowait()
                if msg_type == 'tasks':
                    self.update_task_list(data)
                elif msg_type == 'error':
                    self.log_to_terminal(f'刷新任务列表失败: {data}')
                elif msg_type == 'refresh':
                    # 处理手动刷新请求
                    try:
                        tasks = get_tasks_progress(self.conn)
                        self.update_task_list(tasks)
                    except Exception as e:
                        self.log_to_terminal(f'手动刷新任务列表失败: {str(e)}')
        except Exception as e:
            self.log_to_terminal(f'处理数据更新时出错: {str(e)}')
        finally:
            # 每100ms检查一次队列
            self.root.after(100, self.check_data_queue)

    def pause_task(self):
        selected = self.task_tree.selection()
        if not selected:
            self.log_to_terminal('请先选择要暂停的任务')
            return
        
        task_id = self.task_tree.item(selected[0])['values'][0]
        try:
            # 检查任务是否存在
            task = execute_query('SELECT status FROM tasks WHERE id = %s', (task_id,), fetch_one=True)
            if not task:
                self.log_to_terminal(f'错误：找不到任务 {task_id}')
                return
            
            current_status = task['status']
            new_status = 'paused' if current_status == 'pending' else 'pending'
            
            # 更新任务状态
            execute_update('UPDATE tasks SET status = %s WHERE id = %s', (new_status, task_id))
            
            action = '暂停' if new_status == 'paused' else '恢复'
            self.log_to_terminal(f'成功{action}任务 {task_id}')
            
            # 刷新任务列表
            self.manual_refresh()
            
        except Exception as e:
            self.log_to_terminal(f'更新任务状态时出错：{str(e)}')

    def resume_task(self):
        selected = self.task_tree.selection()
        if not selected:
            self.log_to_terminal('请先选择要继续的任务')
            return
        
        task_id = self.task_tree.item(selected[0])['values'][0]
        # TODO: 实现任务继续逻辑
        self.log_to_terminal(f'已继续任务 {task_id}')

    def delete_task(self):
        selected = self.task_tree.selection()
        if not selected:
            self.log_to_terminal('请先选择要删除的任务')
            return
        
        task_id = self.task_tree.item(selected[0])['values'][0]
        # TODO: 实现任务删除逻辑
        self.log_to_terminal(f'已删除任务 {task_id}')

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