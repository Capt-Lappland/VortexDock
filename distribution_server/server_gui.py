import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import json
import os
import sys
from datetime import datetime
import psutil
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import init_connection_pool, init_database, execute_query, get_db_connection
from utils.logger import logger
from server import TCPServer, app

class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('VortexDock 服务器控制面板')
        self.root.geometry('1400x900')  # 增加默认窗口大小
        self.root.configure(bg='#f0f2f5')
        
        # 初始化服务器状态
        self.server_running = False
        self.tcp_server = None
        self.flask_thread = None
        
        # 加载配置文件
        self.load_config()
        
        # 创建主框架
        self.create_main_frame()
        
        # 启动性能监控
        self.start_performance_monitor()
    
    def load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.py')
        if not os.path.exists(config_path):
            config_path = config_path + '.example'
        
        with open(config_path, 'r') as f:
            content = f.read()
            # 使用exec执行配置文件内容
            exec(content, globals())
        
        # 将配置保存到实例变量
        self.db_config = globals().get('DB_CONFIG', {})
        self.server_config = globals().get('SERVER_CONFIG', {})
        self.task_config = globals().get('TASK_CONFIG', {})
        self.process_config = globals().get('PROCESS_CONFIG', {})
        self.debug = globals().get('DEBUG', False)
    
    def create_main_frame(self):
        # 创建左侧控制面板
        left_frame = ttk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # 服务器控制区域
        control_frame = ttk.LabelFrame(left_frame, text='服务器控制')
        control_frame.pack(fill=tk.X, pady=5)
        
        # 添加数据库连接按钮
        self.db_connect_btn = ttk.Button(control_frame, text='连接数据库', command=self.test_db_connection)
        self.db_connect_btn.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_btn = ttk.Button(control_frame, text='启动服务器', command=self.start_server, state=tk.DISABLED)
        self.start_btn.pack(fill=tk.X, padx=5, pady=5)
        
        self.stop_btn = ttk.Button(control_frame, text='停止服务器', command=self.stop_server, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, padx=5, pady=5)
        
        # 配置管理区域
        self.create_config_section(left_frame)
        
        # 创建右侧主区域
        right_frame = ttk.Frame(self.root)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 系统监控区域
        monitor_frame = ttk.LabelFrame(right_frame, text='系统监控')
        monitor_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建性能图表
        self.create_performance_charts(monitor_frame)
        
        # 创建状态指示器
        status_frame = ttk.Frame(monitor_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.create_status_indicator(status_frame, 'TCP服务器', 0)
        self.create_status_indicator(status_frame, 'HTTP服务器', 1)
        self.create_status_indicator(status_frame, '数据库连接', 2)
        
        # 终端输出区域
        terminal_frame = ttk.LabelFrame(right_frame, text='终端输出')
        terminal_frame.pack(fill=tk.BOTH, expand=True)
        
        self.terminal = scrolledtext.ScrolledText(terminal_frame, height=10)
        self.terminal.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def create_config_section(self, parent):
        # 创建配置管理区域
        config_frame = ttk.LabelFrame(parent, text='配置管理')
        config_frame.pack(fill=tk.X, pady=5)
        
        # 创建选项卡
        notebook = ttk.Notebook(config_frame)
        notebook.pack(fill=tk.X, padx=5, pady=5)
        
        # 数据库配置
        db_frame = ttk.Frame(notebook)
        notebook.add(db_frame, text='数据库配置')
        self.create_db_config(db_frame)
        
        # 服务器配置
        server_frame = ttk.Frame(notebook)
        notebook.add(server_frame, text='服务器配置')
        self.create_server_config(server_frame)
        
        # 任务配置
        task_frame = ttk.Frame(notebook)
        notebook.add(task_frame, text='任务配置')
        self.create_task_config(task_frame)
        
        # 进程配置
        process_frame = ttk.Frame(notebook)
        notebook.add(process_frame, text='进程配置')
        self.create_process_config(process_frame)
        
        
        # 保存按钮
        ttk.Button(config_frame, text='保存所有配置', command=self.save_all_config).pack(fill=tk.X, padx=5, pady=5)
    
    def create_db_config(self, parent):
        self.db_entries = {}
        for key, value in self.db_config.items():
            ttk.Label(parent, text=f'{key}:').pack(padx=5, pady=2)
            entry = ttk.Entry(parent)
            entry.insert(0, str(value))
            entry.pack(fill=tk.X, padx=5, pady=2)
            self.db_entries[key] = entry
        
        # 添加数据库连接测试按钮
        ttk.Button(parent, text='测试连接', command=self.test_db_connection).pack(fill=tk.X, padx=5, pady=5)
    
    def test_db_connection(self):
        # 禁用连接按钮，避免重复点击
        self.db_connect_btn.config(state=tk.DISABLED)
        self.log_message('正在连接数据库...')
        
        # 获取当前输入的数据库配置
        config = {k: self.get_entry_value(v) for k, v in self.db_entries.items()}
        # 确保配置中包含database_mysql字段
        if 'database' in config:
            config['database_mysql'] = config.pop('database')
        
        def connect_thread():
            try:
                # 尝试建立连接
                init_connection_pool(config)
                # 测试连接是否成功
                conn = get_db_connection()
                if conn:
                    conn.close()
                    # 使用after方法在主线程中更新UI
                    self.root.after(0, lambda: [
                        messagebox.showinfo('成功', '数据库连接成功！'),
                        self.update_status_light('数据库连接', True),
                        self.log_message('数据库连接成功'),
                        self.start_btn.config(state=tk.NORMAL),
                        self.db_connect_btn.config(state=tk.NORMAL)
                    ])
            except Exception as e:
                # 使用after方法在主线程中更新UI
                self.root.after(0, lambda: [
                    messagebox.showerror('错误', f'数据库连接失败：{str(e)}'),
                    self.update_status_light('数据库连接', False),
                    self.log_message(f'数据库连接测试失败: {str(e)}'),
                    self.start_btn.config(state=tk.DISABLED),
                    self.db_connect_btn.config(state=tk.NORMAL)
                ])
        
        # 启动连接线程
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def create_server_config(self, parent):
        self.server_entries = {}
        for key, value in self.server_config.items():
            ttk.Label(parent, text=f'{key}:').pack(padx=5, pady=2)
            entry = ttk.Entry(parent)
            entry.insert(0, str(value))
            entry.pack(fill=tk.X, padx=5, pady=2)
            self.server_entries[key] = entry
            
            # 特殊处理端口配置，将其设置为类属性
            if key == 'tcp_port':
                self.tcp_port = entry
            elif key == 'http_port':
                self.http_port = entry
    
    def create_task_config(self, parent):
        self.task_entries = {}
        for key, value in self.task_config.items():
            ttk.Label(parent, text=f'{key}:').pack(padx=5, pady=2)
            entry = ttk.Entry(parent)
            entry.insert(0, str(value))
            entry.pack(fill=tk.X, padx=5, pady=2)
            self.task_entries[key] = entry
    
    def create_process_config(self, parent):
        self.process_entries = {}
        for key, value in self.process_config.items():
            ttk.Label(parent, text=f'{key}:').pack(padx=5, pady=2)
            entry = ttk.Entry(parent)
            entry.insert(0, str(value))
            entry.pack(fill=tk.X, padx=5, pady=2)
            self.process_entries[key] = entry
    
    def create_debug_config(self, parent):
        self.debug_var = tk.BooleanVar(value=self.debug)
        ttk.Checkbutton(parent, text='启用调试模式', variable=self.debug_var).pack(padx=5, pady=5)
    
    def save_all_config(self):
        try:
            # 收集所有配置
            config = {
                'DB_CONFIG': {k: self.get_entry_value(v) for k, v in self.db_entries.items()},
                'SERVER_CONFIG': {k: self.get_entry_value(v) for k, v in self.server_entries.items()},
                'TASK_CONFIG': {k: self.get_entry_value(v) for k, v in self.task_entries.items()},
                'PROCESS_CONFIG': {k: self.get_entry_value(v) for k, v in self.process_entries.items()},
                'DEBUG': self.debug_var.get()
            }
            
            # 生成配置文件内容
            config_content = '# 数据库配置\nDB_CONFIG = ' + json.dumps(config['DB_CONFIG'], indent=4, ensure_ascii=False)
            config_content += '\n\n# 服务器配置\nSERVER_CONFIG = ' + json.dumps(config['SERVER_CONFIG'], indent=4, ensure_ascii=False)
            config_content += '\n\n# 任务配置\nTASK_CONFIG = ' + json.dumps(config['TASK_CONFIG'], indent=4, ensure_ascii=False)
            config_content += '\n\n# 守护进程配置\nPROCESS_CONFIG = ' + json.dumps(config['PROCESS_CONFIG'], indent=4, ensure_ascii=False)
            config_content += f'\n\n# 调试配置\nDEBUG = {str(config["DEBUG"])}'
            
            # 保存到文件
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.py')
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            self.log_message('配置保存成功')
            messagebox.showinfo('成功', '配置保存成功')
            
            # 重新加载配置
            self.load_config()
        except Exception as e:
            self.log_message(f'保存配置失败: {str(e)}')
            messagebox.showerror('错误', f'保存配置失败: {str(e)}')
    
    def get_entry_value(self, entry):
        value = entry.get()
        try:
            # 尝试转换为数字
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            # 如果不是数字，返回字符串
            return value
    
    def create_performance_charts(self, parent):
        # 创建图表框架，设置更大的尺寸
        chart_frame = ttk.Frame(parent)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # CPU使用率图表
        self.cpu_figure = Figure(figsize=(6, 3), dpi=100)
        self.cpu_plot = self.cpu_figure.add_subplot(111)
        self.cpu_plot.set_title('CPU使用率')
        self.cpu_canvas = FigureCanvasTkAgg(self.cpu_figure, master=chart_frame)
        self.cpu_canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 内存使用率图表
        self.mem_figure = Figure(figsize=(6, 3), dpi=100)
        self.mem_plot = self.mem_figure.add_subplot(111)
        self.mem_plot.set_title('内存使用率')
        self.mem_canvas = FigureCanvasTkAgg(self.mem_figure, master=chart_frame)
        self.mem_canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 初始化数据
        self.cpu_data = [0] * 60
        self.mem_data = [0] * 60
    
    def create_status_indicator(self, parent, text, column):
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, padx=15, pady=5, sticky='nsew')
        
        canvas = tk.Canvas(frame, width=20, height=20)
        canvas.create_oval(3, 3, 17, 17, fill='red', tags='light')
        canvas.pack(side=tk.LEFT, padx=5, pady=2)
        
        ttk.Label(frame, text=text).pack(side=tk.LEFT)
        
        setattr(self, f'{text.lower()}_light', canvas)
    
    def update_status_light(self, name, status):
        light = getattr(self, f'{name.lower()}_light')
        color = 'green' if status else 'red'
        light.itemconfig('light', fill=color)
    
    def start_performance_monitor(self):
        def update():
            # 更新CPU和内存数据
            cpu_percent = psutil.cpu_percent()
            mem_percent = psutil.virtual_memory().percent
            
            self.cpu_data.pop(0)
            self.cpu_data.append(cpu_percent)
            self.mem_data.pop(0)
            self.mem_data.append(mem_percent)
            
            # 更新图表
            self.cpu_plot.clear()
            self.cpu_plot.plot(self.cpu_data)
            self.cpu_plot.set_ylim(0, 100)
            self.cpu_plot.set_title(f'CPU使用率: {cpu_percent}%', fontfamily='Arial Unicode MS')
            
            self.mem_plot.clear()
            self.mem_plot.plot(self.mem_data)
            self.mem_plot.set_ylim(0, 100)
            self.mem_plot.set_title(f'内存使用率: {mem_percent}%', fontfamily='Arial Unicode MS')
            
            self.cpu_canvas.draw()
            self.mem_canvas.draw()
            
            # 每秒更新一次
            self.root.after(1000, update)
        
        update()
    
    def start_server(self):
        try:
            # 获取配置
            tcp_port = int(self.tcp_port.get())
            http_port = int(self.http_port.get())
            
            # 启动TCP服务器，不自动初始化数据库连接
            self.tcp_server = TCPServer(port=tcp_port, init_db_connection=False)
            self.tcp_thread = threading.Thread(target=self.tcp_server.start)
            self.tcp_thread.daemon = True
            self.tcp_thread.start()
            
            # 启动Flask服务器
            self.flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=http_port))
            self.flask_thread.daemon = True
            self.flask_thread.start()
            
            self.server_running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            
            self.update_status_light('TCP服务器', True)
            self.update_status_light('HTTP服务器', True)
            
            self.log_message('服务器启动成功')
        except Exception as e:
            self.log_message(f'服务器启动失败: {str(e)}')
            messagebox.showerror('错误', f'服务器启动失败: {str(e)}')
    
    def stop_server(self):
        try:
            # 停止服务器
            if self.tcp_server:
                self.tcp_server.sock.close()
            
            self.server_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            
            self.update_status_light('TCP服务器', False)
            self.update_status_light('HTTP服务器', False)
            
            self.log_message('服务器已停止')
        except Exception as e:
            self.log_message(f'停止服务器时出错: {str(e)}')
            messagebox.showerror('错误', f'停止服务器时出错: {str(e)}')
    
    def save_config(self):
        try:
            config = {
                'tcp_port': int(self.tcp_port.get()),
                'http_port': int(self.http_port.get()),
                'max_retries': int(self.max_retries.get())
            }
            
            # 保存配置到文件
            with open('server_config.json', 'w') as f:
                json.dump(config, f, indent=4)
            
            self.log_message('配置保存成功')
            messagebox.showinfo('成功', '配置保存成功')
        except Exception as e:
            self.log_message(f'保存配置失败: {str(e)}')
            messagebox.showerror('错误', f'保存配置失败: {str(e)}')
    
    def log_message(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.terminal.insert(tk.END, f'[{timestamp}] {message}\n')
        self.terminal.see(tk.END)

def main():
    root = tk.Tk()
    app = ServerGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()