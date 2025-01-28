import os
import json

def prompt_for_config(config_name, default_value):
    user_input = input(f"{config_name} [{default_value}]: ")
    return user_input if user_input else default_value

def configure():
    config = {}

    # 数据库配置
    print("VortexDock 数据库配置:")
    config['DB_CONFIG'] = {
        'host': prompt_for_config('VortexDock 数据库主机', 'localhost'),
        'user': prompt_for_config('VortexDock 数据库用户', 'vortexdock'),
        'password': prompt_for_config('VortexDock 数据库密码', 'password'),
        'database': prompt_for_config('VortexDock 数据库名称', 'vortexdock'),
        'pool_name': prompt_for_config('连接池名称', 'mypool'),
        'pool_size': int(prompt_for_config('连接池大小', 20)),
        'pool_reset_session': prompt_for_config('重置会话状态', 'True') == 'True',
        'connect_timeout': int(prompt_for_config('连接超时时间（秒）', 10))
    }

    # 服务器配置
    print("\nVortexDock 分发服务器配置:")
    config['SERVER_CONFIG'] = {
        'host': prompt_for_config('VortexDock 分发服务器主机', 'localhost'),
        'http_port': int(prompt_for_config('VortexDock 文件传输服务端口', 9000)),
        'tcp_port': int(prompt_for_config('VortexDock 命令服务端口', 10020)),
        'password': prompt_for_config('VortexDock 分发服务器密码', 'your_server_password')
    }

    # 任务配置
    print("\n计算节点配置:")
    config['TASK_CONFIG'] = {
        'max_retries': int(prompt_for_config('最大重试次数', 5)),
        'retry_delay': int(prompt_for_config('重试延迟（秒）', 5)),
        'task_timeout': int(prompt_for_config('任务超时时间（秒）', 3600)),
        'cleanup_interval': int(prompt_for_config('清理间隔（秒）', 3600)),
        'cleanup_age': int(prompt_for_config('清理阈值（秒）', 86400)),
        'heartbeat_interval': int(prompt_for_config('心跳间隔（秒）', 30)),
        'heartbeat_retry_delay': int(prompt_for_config('心跳重试延迟（秒）', 5))
    }

    # 守护进程配置
    print("\n守护进程配置:")
    config['PROCESS_CONFIG'] = {
        'max_processes': int(prompt_for_config('最大进程数', 2)),
        'process_start_interval': int(prompt_for_config('进程启动间隔（秒）', 5)),
        'min_memory_per_process': int(prompt_for_config('每个进程的最小内存（MB）', 100)),
        'max_cpu_per_process': int(prompt_for_config('每个进程的最大CPU数', 1))
    }

    # 调试配置
    print("\n调试配置:")
    config['DEBUG'] = prompt_for_config('调试模式', 'False') == 'True'

    # 将配置写入 config.py 文件
    with open('config.py', 'w', encoding='utf-8') as config_file:
        config_file.write("# -*- coding: utf-8 -*-\n\n")
        config_file.write("DB_CONFIG = " + json.dumps(config['DB_CONFIG'], indent=4, ensure_ascii=False) + "\n\n")
        config_file.write("SERVER_CONFIG = " + json.dumps(config['SERVER_CONFIG'], indent=4, ensure_ascii=False) + "\n\n")
        config_file.write("TASK_CONFIG = " + json.dumps(config['TASK_CONFIG'], indent=4, ensure_ascii=False) + "\n\n")
        config_file.write("PROCESS_CONFIG = " + json.dumps(config['PROCESS_CONFIG'], indent=4, ensure_ascii=False) + "\n\n")
        config_file.write("DEBUG = " + str(config['DEBUG']) + "\n")

    print("\n配置已保存到 config.py 文件中")

if __name__ == '__main__':
    print(r"""
 __     __         _            ____             _    
 \ \   / /__  _ __| |_ _____  _|  _ \  ___   ___| | __
  \ \ / / _ \| '__| __/ _ \ \/ / | | |/ _ \ / __| |/ /
   \ V / (_) | |  | ||  __/>  <| |_| | (_) | (__|   < 
    \_/ \___/|_|   \__\___/_/\_\____/ \___/ \___|_|\_\ 
""")
    configure()
