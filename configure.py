import os
import json

def prompt_for_config(config_name, default_value):
    user_input = input(f"{config_name} [{default_value}]: ")
    return user_input if user_input else default_value

def configure():
    config = {}

    # Database configuration
    print("VortexDock Database Configuration:")
    config['DB_CONFIG'] = {
        'host': prompt_for_config('VortexDock Database Host', 'localhost'),
        'user': prompt_for_config('VortexDock Database User', 'vortexdock'),
        'password': prompt_for_config('VortexDock Database Password', 'password'),
        'database': prompt_for_config('VortexDock Database Name', 'vortexdock'),
        'pool_name': prompt_for_config('Connection Pool Name', 'mypool'),
        'pool_size': int(prompt_for_config('Connection Pool Size', 20)),
        'pool_reset_session': prompt_for_config('Reset Session State', 'True') == 'True',
        'connect_timeout': int(prompt_for_config('Connection Timeout (seconds)', 10))
    }

    # Server configuration
    print("\nVortexDock Server Configuration:")
    config['SERVER_CONFIG'] = {
        'host': prompt_for_config('VortexDock Server Host', 'localhost'),
        'http_port': int(prompt_for_config('VortexDock File Transfer Service Port', 9000)),
        'tcp_port': int(prompt_for_config('VortexDock Command Service Port', 10020)),
        'password': prompt_for_config('VortexDock Server Password', 'your_server_password')
    }

    # Task configuration
    print("\nTask Configuration:")
    config['TASK_CONFIG'] = {
        'max_retries': int(prompt_for_config('Maximum Retries', 5)),
        'retry_delay': int(prompt_for_config('Retry Delay (seconds)', 5)),
        'task_timeout': int(prompt_for_config('Task Timeout (seconds)', 3600)),
        'cleanup_interval': int(prompt_for_config('Cleanup Interval (seconds)', 3600)),
        'cleanup_age': int(prompt_for_config('Cleanup Threshold (seconds)', 86400)),
        'heartbeat_interval': int(prompt_for_config('Heartbeat Interval (seconds)', 30)),
        'heartbeat_retry_delay': int(prompt_for_config('Heartbeat retry delay (seconds)', 5))
    }

    # Process configuration
    print("\nProcess Configuration:")
    config['PROCESS_CONFIG'] = {
        'max_processes': int(prompt_for_config('Maximum number of processes', 2)),
        'process_start_interval': int(prompt_for_config('Process start interval (seconds)', 5)),
        'min_memory_per_process': int(prompt_for_config('Minimum memory per process (MB)', 100)),
        'max_cpu_per_process': int(prompt_for_config('Maximum CPU per process', 1))
    }

    # Debug configuration
    print("\nDebug Configuration:")
    config['DEBUG'] = prompt_for_config('Debug mode', 'False') == 'True'

    # Write configuration to config.py file
    with open('config.py', 'w', encoding='utf-8') as config_file:
        config_file.write("# -*- coding: utf-8 -*-\n\n")
        config_file.write("DB_CONFIG = " + json.dumps(config['DB_CONFIG'], indent=4, ensure_ascii=False) + "\n\n")
        config_file.write("SERVER_CONFIG = " + json.dumps(config['SERVER_CONFIG'], indent=4, ensure_ascii=False) + "\n\n")
        config_file.write("TASK_CONFIG = " + json.dumps(config['TASK_CONFIG'], indent=4, ensure_ascii=False) + "\n\n")
        config_file.write("PROCESS_CONFIG = " + json.dumps(config['PROCESS_CONFIG'], indent=4, ensure_ascii=False) + "\n\n")
        config_file.write("DEBUG = " + str(config['DEBUG']) + "\n")

    print("\nConfiguration has been saved to config.py file")

if __name__ == '__main__':
    print(r"""
 __     __         _            ____             _    
 \ \   / /__  _ __| |_ _____  _|  _ \  ___   ___| | __
  \ \ / / _ \| '__| __/ _ \ \/ / | | |/ _ \ / __| |/ /
   \ V / (_) | |  | ||  __/>  <| |_| | (_) | (__|   < 
    \_/ \___/|_|   \__\___/_/\_\____/ \___/ \___|_|\_\ 
""")
    configure()
