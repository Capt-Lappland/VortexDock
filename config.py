# 数据库配置
DB_CONFIG = {
    'host': 'captlappland.cn',
    'user': 'VortexDock',
    'password': 'WangRunZe2003@',
    'database': 'vortexdock',
    'pool_name': 'mypool',
    'pool_size': 5
}

# 服务器配置
SERVER_CONFIG = {
    'host': 'captlappland.cn',
    'http_port': 9000,
    'tcp_port': 10020,
    'password': 'Wg121212'  # 服务器密码，通过 CLI 设置
}

# 任务配置
TASK_CONFIG = {
    'max_retries': 5,
    'retry_delay': 5,
    'task_timeout': 3600,
    'cleanup_interval': 3600,
    'cleanup_age': 86400,
    'heartbeat_interval': 30
}

# 守护进程配置
PROCESS_CONFIG = {
    'max_processes': 2,
    'process_start_interval': 5,
    'min_memory_per_process': 100,
    'max_cpu_per_process': 1
}

# 调试配置
DEBUG = True