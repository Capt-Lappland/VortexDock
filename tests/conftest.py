#import sys
#import pytest
#import shutil
#from pathlib import Path
#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#from utils.db import init_connection_pool, init_database, get_db_connection

#@pytest.fixture(scope="session", autouse=True)
#def setup_test_environment():
#    """全局测试环境配置"""
#    # 使用测试数据库配置
#    import config
#    config.DB_CONFIG['database_mysql'] = 'vortexdock'
    
#    # 初始化测试数据库
#    init_connection_pool()
#   init_database()
#    
    # 创建测试目录
#    Path("tests/data").mkdir(parents=True, exist_ok=True)
    
#    yield  # 测试执行
    
    # 测试后清理
#    conn = get_db_connection()
#    conn.cursor().execute("DROP DATABASE test_vortexdock")
#    shutil.rmtree("tests/data", ignore_errors=True)