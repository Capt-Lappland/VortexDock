import os
import json

def prompt_for_config(config_name, default_value, validator=None):
    while True:
        user_input = input(f"{config_name} [{default_value}]: ")
        user_input = user_input if user_input else default_value
        if validator:
            try:
                if validator(user_input):
                    return user_input
            except Exception as e:
                print(f"Invalid input: {e}")
        else:
            return user_input

def int_validator(value, min_value=None, max_value=None):
    value = int(value)
    if (min_value is not None and value < min_value) or (max_value is not None and value > max_value):
        raise ValueError(f"Value must be between {min_value} and {max_value}")
    return True

def bool_validator(value):
    if value.lower() not in ['true', 'false']:
        raise ValueError("Value must be 'True' or 'False'")
    return True

def choice_validator(value, choices):
    if value not in choices:
        raise ValueError(f"Value must be one of {choices}")
    return True

def configure():
    config = {}

    # Database configuration
    print("VortexDock Database Configuration:")
    db_type = prompt_for_config('Database Type (mysql/sqlite)', 'sqlite', lambda v: choice_validator(v, ['mysql', 'sqlite']))
    config['DB_CONFIG'] = {'type': db_type}

    if db_type == 'mysql':
        config['DB_CONFIG'].update({
            'host': prompt_for_config('VortexDock Database Host', 'localhost'),
            'user': prompt_for_config('VortexDock Database User', 'vortexdock'),
            'password': prompt_for_config('VortexDock Database Password', 'password'),
            'database': prompt_for_config('VortexDock Database Name', 'vortexdock'),
            'pool_name': prompt_for_config('Connection Pool Name', 'mypool'),
            'pool_size': int(prompt_for_config('Connection Pool Size', 20, lambda v: int_validator(v, 1, 100))),
            'pool_reset_session': prompt_for_config('Reset Session State', 'True', lambda v: choice_validator(v.lower(), ['true', 'false'])).lower() == 'true',
            'connect_timeout': int(prompt_for_config('Connection Timeout (seconds)', 10, lambda v: int_validator(v, 1, 300)))
        })
    elif db_type == 'sqlite':
        config['DB_CONFIG']['database'] = prompt_for_config('SQLite Database File Path', 'vortexdock.db')

    # Server configuration
    print("\nVortexDock Server Configuration:")
    config['SERVER_CONFIG'] = {
        'host': prompt_for_config('VortexDock Server Host', 'localhost'),
        'http_port': int(prompt_for_config('VortexDock File Transfer Service Port', 9000, lambda v: int_validator(v, 1, 65535))),
        'tcp_port': int(prompt_for_config('VortexDock Command Service Port', 10020, lambda v: int_validator(v, 1, 65535))),
        'password': prompt_for_config('VortexDock Server Password', 'your_server_password')
    }

    # Task configuration
    print("\nTask Configuration:")
    config['TASK_CONFIG'] = {
        'max_retries': int(prompt_for_config('Maximum Retries', 5, lambda v: int_validator(v, 0, 100))),
        'retry_delay': int(prompt_for_config('Retry Delay (seconds)', 5, lambda v: int_validator(v, 1, 3600))),
        'task_timeout': int(prompt_for_config('Task Timeout (seconds)', 3600, lambda v: int_validator(v, 1, 86400))),
        'cleanup_interval': int(prompt_for_config('Cleanup Interval (seconds)', 3600, lambda v: int_validator(v, 1, 86400))),
        'cleanup_age': int(prompt_for_config('Cleanup Threshold (seconds)', 86400, lambda v: int_validator(v, 1, 31536000))),
        'heartbeat_interval': int(prompt_for_config('Heartbeat Interval (seconds)', 30, lambda v: int_validator(v, 1, 3600))),
        'heartbeat_retry_delay': int(prompt_for_config('Heartbeat retry delay (seconds)', 5, lambda v: int_validator(v, 1, 3600)))
    }

    # Process configuration
    print("\nProcess Configuration:")
    config['PROCESS_CONFIG'] = {
        'max_processes': int(prompt_for_config('Maximum number of processes', 2, lambda v: int_validator(v, 1, 100))),
        'process_start_interval': int(prompt_for_config('Process start interval (seconds)', 5, lambda v: int_validator(v, 1, 3600))),
        'min_memory_per_process': int(prompt_for_config('Minimum memory per process (MB)', 100, lambda v: int_validator(v, 1, 65536))),
        'max_cpu_per_process': int(prompt_for_config('Maximum CPU per process', 1, lambda v: int_validator(v, 1, 64)))
    }

    # Debug configuration
    print("\nDebug Configuration:")
    config['DEBUG'] = prompt_for_config('Debug mode', 'False', lambda v: choice_validator(v.lower(), ['true', 'false'])).lower() == 'true'

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
