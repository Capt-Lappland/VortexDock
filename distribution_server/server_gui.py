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
        self.root.title('VortexDock Server Control Panel')
        self.root.geometry('1400x900')  # Increase default window size
        self.root.configure(bg='#f0f2f5')
        
        # Initialize server status
        self.server_running = False
        self.tcp_server = None
        self.flask_thread = None
        
        # Load configuration file
        self.load_config()
        
        # Create main frame
        self.create_main_frame()
        
        # Start performance monitoring
        self.start_performance_monitor()
    
    def load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.py')
        if not os.path.exists(config_path):
            config_path = config_path + '.example'
        
        with open(config_path, 'r') as f:
            content = f.read()
            # Use exec to execute the configuration file content
            exec(content, globals())
        
        # Save the configuration to instance variables
        self.db_config = globals().get('DB_CONFIG', {})
        self.server_config = globals().get('SERVER_CONFIG', {})
        self.task_config = globals().get('TASK_CONFIG', {})
        self.process_config = globals().get('PROCESS_CONFIG', {})
        self.debug = globals().get('DEBUG', False)
    
    def create_main_frame(self):
        # Create left control panel
        left_frame = ttk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # Server control area
        control_frame = ttk.LabelFrame(left_frame, text='Server Control')
        control_frame.pack(fill=tk.X, pady=5)
        
        # Add database connection button
        self.db_connect_btn = ttk.Button(control_frame, text='Connect to Database', command=self.test_db_connection)
        self.db_connect_btn.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_btn = ttk.Button(control_frame, text='Start Server', command=self.start_server, state=tk.DISABLED)
        self.start_btn.pack(fill=tk.X, padx=5, pady=5)
        
        self.stop_btn = ttk.Button(control_frame, text='Stop Server', command=self.stop_server, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, padx=5, pady=5)
        
        # Configuration management area
        self.create_config_section(left_frame)
        
        # Create right main area
        right_frame = ttk.Frame(self.root)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # System monitoring area
        monitor_frame = ttk.LabelFrame(right_frame, text='System Monitoring')
        monitor_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create performance charts
        self.create_performance_charts(monitor_frame)
        
        # Create status indicators
        status_frame = ttk.Frame(monitor_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.create_status_indicator(status_frame, 'TCP Server', 0)
        self.create_status_indicator(status_frame, 'HTTP Server', 1)
        self.create_status_indicator(status_frame, 'Database Connection', 2)
        
        # Terminal output area
        terminal_frame = ttk.LabelFrame(right_frame, text='Terminal Output')
        terminal_frame.pack(fill=tk.BOTH, expand=True)
        
        self.terminal = scrolledtext.ScrolledText(terminal_frame, height=10)
        self.terminal.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def create_config_section(self, parent):
        # Create configuration management area
        config_frame = ttk.LabelFrame(parent, text='Configuration Management')
        config_frame.pack(fill=tk.X, pady=5)
        
        # Create tabs
        notebook = ttk.Notebook(config_frame)
        notebook.pack(fill=tk.X, padx=5, pady=5)
        
        # Database configuration
        db_frame = ttk.Frame(notebook)
        notebook.add(db_frame, text='Database Configuration')
        self.create_db_config(db_frame)
        
        # Server configuration
        server_frame = ttk.Frame(notebook)
        notebook.add(server_frame, text='Server Configuration')
        self.create_server_config(server_frame)
        
        # Task configuration
        task_frame = ttk.Frame(notebook)
        notebook.add(task_frame, text='Task Configuration')
        self.create_task_config(task_frame)
        
        # Process configuration
        process_frame = ttk.Frame(notebook)
        notebook.add(process_frame, text='Process Configuration')
        self.create_process_config(process_frame)
        
        
        # Save button
        ttk.Button(config_frame, text='Save All Configurations', command=self.save_all_config).pack(fill=tk.X, padx=5, pady=5)
    
    def create_db_config(self, parent):
        self.db_entries = {}
        for key, value in self.db_config.items():
            ttk.Label(parent, text=f'{key}:').pack(padx=5, pady=2)
            entry = ttk.Entry(parent)
            entry.insert(0, str(value))
            entry.pack(fill=tk.X, padx=5, pady=2)
            self.db_entries[key] = entry
        
        # Add database connection test button
        ttk.Button(parent, text='Test Connection', command=self.test_db_connection).pack(fill=tk.X, padx=5, pady=5)
    
    def test_db_connection(self):
        # Disable the connect button to avoid repeated clicks
        self.db_connect_btn.config(state=tk.DISABLED)
        self.log_message('Connecting to database...')
        
        # Get the current database configuration
        config = {k: self.get_entry_value(v) for k, v in self.db_entries.items()}
        # Ensure the configuration includes the database_mysql field
        if 'database' in config:
            config['database_mysql'] = config.pop('database')
        
        def connect_thread():
            try:
                # Try to establish a connection
                init_connection_pool(config)
                # Test if the connection is successful
                conn = get_db_connection()
                if conn:
                    conn.close()
                    # Use the after method to update the UI in the main thread
                    self.root.after(0, lambda: [
                        messagebox.showinfo('Success', 'Database connection successful!'),
                        self.update_status_light('Database Connection', True),
                        self.log_message('Database connection successful'),
                        self.start_btn.config(state=tk.NORMAL),
                        self.db_connect_btn.config(state=tk.NORMAL)
                    ])
            except Exception as e:
                # Use the after method to update the UI in the main thread
                self.root.after(0, lambda: [
                    messagebox.showerror('Error', f'Database connection failed: {str(e)}'),
                    self.update_status_light('Database Connection', False),
                    self.log_message(f'Database connection test failed: {str(e)}'),
                    self.start_btn.config(state=tk.DISABLED),
                    self.db_connect_btn.config(state=tk.NORMAL)
                ])
        
        # Start the connection thread
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def create_server_config(self, parent):
        self.server_entries = {}
        for key, value in self.server_config.items():
            ttk.Label(parent, text=f'{key}:').pack(padx=5, pady=2)
            entry = ttk.Entry(parent)
            entry.insert(0, str(value))
            entry.pack(fill=tk.X, padx=5, pady=2)
            self.server_entries[key] = entry
            
            # Special handling for port configuration, set as class attributes
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
        ttk.Checkbutton(parent, text='Enable Debug Mode', variable=self.debug_var).pack(padx=5, pady=5)
    
    def save_all_config(self):
        try:
            # Collect all configurations
            config = {
                'DB_CONFIG': {k: self.get_entry_value(v) for k, v in self.db_entries.items()},
                'SERVER_CONFIG': {k: self.get_entry_value(v) for k, v in self.server_entries.items()},
                'TASK_CONFIG': {k: self.get_entry_value(v) for k, v in self.task_entries.items()},
                'PROCESS_CONFIG': {k: self.get_entry_value(v) for k, v in self.process_entries.items()},
                'DEBUG': self.debug_var.get()
            }
            
            # Generate configuration file content
            config_content = '# Database Configuration\nDB_CONFIG = ' + json.dumps(config['DB_CONFIG'], indent=4, ensure_ascii=False)
            config_content += '\n\n# Server Configuration\nSERVER_CONFIG = ' + json.dumps(config['SERVER_CONFIG'], indent=4, ensure_ascii=False)
            config_content += '\n\n# Task Configuration\nTASK_CONFIG = ' + json.dumps(config['TASK_CONFIG'], indent=4, ensure_ascii=False)
            config_content += '\n\n# Process Configuration\nPROCESS_CONFIG = ' + json.dumps(config['PROCESS_CONFIG'], indent=4, ensure_ascii=False)
            config_content += f'\n\n# Debug Configuration\nDEBUG = {str(config["DEBUG"])}'
            
            # Save to file
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.py')
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            self.log_message('Configuration saved successfully')
            messagebox.showinfo('Success', 'Configuration saved successfully')
            
            # Reload configuration
            self.load_config()
        except Exception as e:
            self.log_message(f'Failed to save configuration: {str(e)}')
            messagebox.showerror('Error', f'Failed to save configuration: {str(e)}')
    
    def get_entry_value(self, entry):
        value = entry.get()
        try:
            # Try to convert to a number
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            # If not a number, return as a string
            return value
    
    def create_performance_charts(self, parent):
        # Create chart frame with larger size
        chart_frame = ttk.Frame(parent)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # CPU usage chart
        self.cpu_figure = Figure(figsize=(6, 3), dpi=100)
        self.cpu_plot = self.cpu_figure.add_subplot(111)
        self.cpu_plot.set_title('CPU Usage')
        self.cpu_canvas = FigureCanvasTkAgg(self.cpu_figure, master=chart_frame)
        self.cpu_canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Memory usage chart
        self.mem_figure = Figure(figsize=(6, 3), dpi=100)
        self.mem_plot = self.mem_figure.add_subplot(111)
        self.mem_plot.set_title('Memory Usage')
        self.mem_canvas = FigureCanvasTkAgg(self.mem_figure, master=chart_frame)
        self.mem_canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Initialize data
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
            # Update CPU and memory data
            cpu_percent = psutil.cpu_percent()
            mem_percent = psutil.virtual_memory().percent
            
            self.cpu_data.pop(0)
            self.cpu_data.append(cpu_percent)
            self.mem_data.pop(0)
            self.mem_data.append(mem_percent)
            
            # Update charts
            self.cpu_plot.clear()
            self.cpu_plot.plot(self.cpu_data)
            self.cpu_plot.set_ylim(0, 100)
            self.cpu_plot.set_title(f'CPU Usage: {cpu_percent}%', fontfamily='Arial Unicode MS')
            
            self.mem_plot.clear()
            self.mem_plot.plot(self.mem_data)
            self.mem_plot.set_ylim(0, 100)
            self.mem_plot.set_title(f'Memory Usage: {mem_percent}%', fontfamily='Arial Unicode MS')
            
            self.cpu_canvas.draw()
            self.mem_canvas.draw()
            
            # Update every second
            self.root.after(1000, update)
        
        update()
    
    def start_server(self):
        try:
            # Get configuration
            tcp_port = int(self.tcp_port.get())
            http_port = int(self.http_port.get())
            
            # Start TCP server without automatically initializing database connection
            self.tcp_server = TCPServer(port=tcp_port, init_db_connection=False)
            self.tcp_thread = threading.Thread(target=self.tcp_server.start)
            self.tcp_thread.daemon = True
            self.tcp_thread.start()
            
            # Start Flask server
            self.flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=http_port))
            self.flask_thread.daemon = True
            self.flask_thread.start()
            
            self.server_running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            
            self.update_status_light('TCP Server', True)
            self.update_status_light('HTTP Server', True)
            
            self.log_message('Server started successfully')
        except Exception as e:
            self.log_message(f'Failed to start server: {str(e)}')
            messagebox.showerror('Error', f'Failed to start server: {str(e)}')
    
    def stop_server(self):
        try:
            # Stop the server
            if self.tcp_server:
                self.tcp_server.sock.close()
            
            self.server_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            
            self.update_status_light('TCP Server', False)
            self.update_status_light('HTTP Server', False)
            
            self.log_message('Server stopped')
        except Exception as e:
            self.log_message(f'Error stopping server: {str(e)}')
            messagebox.showerror('Error', f'Error stopping server: {str(e)}')
    
    def save_config(self):
        try:
            config = {
                'tcp_port': int(self.tcp_port.get()),
                'http_port': int(self.http_port.get()),
                'max_retries': int(self.max_retries.get())
            }
            
            # Save configuration to file
            with open('server_config.json', 'w') as f:
                json.dump(config, f, indent=4)
            
            self.log_message('Configuration saved successfully')
            messagebox.showinfo('Success', 'Configuration saved successfully')
        except Exception as e:
            self.log_message(f'Failed to save configuration: {str(e)}')
            messagebox.showerror('Error', f'Failed to save configuration: {str(e)}')
    
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