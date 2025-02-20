import mysql.connector
from mysql.connector import Error

import sys
sys.path.append('..')
from config import DB_CONFIG
def get_db_connection():
    """创建并返回数据库连接对象"""
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database_mysql'],
            auth_plugin='mysql_native_password'  # 根据MySQL版本可能需要
        )
        return conn
    except Error as e:
        print(f"数据库连接失败: {str(e)}")
        raise  # 将异常抛给上层调用者处理

# 安全测试连接（可选）
if __name__ == "__main__":
    try:
        test_conn = get_db_connection()
        print("成功连接数据库！")
        test_conn.close()
    except Exception as e:
        print(f"连接测试失败: {e}")