# 数据库配置
DB_CONFIG = {
    'host': 'captlappland.cn',
    'user': 'dock_server2',
    'password': 'WangRunZe2003@',
    'database': 'dock_server2',
    'pool_name': 'mypool',
    'pool_size': 5
}

# 服务器配置
SERVER_CONFIG = {
    'host': 'captlappland.cn',
    'http_port': 8000,
    'tcp_port': 10010
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

# 调试配置
DEBUG = True