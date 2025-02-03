# -*- coding: utf-8 -*-

import os
import time
import logging
import mysql.connector
from mysql.connector import pooling
from datetime import datetime, timedelta
from config import DB_CONFIG

# 初始化日志
logger = logging.getLogger('dock_server')

# 全局数据库连接池
connection_pool = None

def init_connection_pool():
    """初始化数据库连接池"""
    global connection_pool
    try:
        pool_name = DB_CONFIG.get('pool_name', 'mypool')  # 添加默认值
        pool_size = DB_CONFIG.get('pool_size', 10)  # 添加默认值
        connection_pool = pooling.MySQLConnectionPool(
            pool_name=pool_name,
            pool_size=pool_size,
            pool_reset_session=DB_CONFIG['pool_reset_session'],
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database_mysql'],
            connect_timeout=DB_CONFIG['connect_timeout']
        )
        logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.critical(f"Failed to initialize connection pool: {e}")
        raise

def get_db_connection():
    """从连接池获取数据库连接（带重试机制）"""
    if not connection_pool:
        init_connection_pool()
    
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            conn = connection_pool.get_connection()
            if conn.is_connected():
                return conn
        except (mysql.connector.Error, Exception) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Connection attempt {attempt+1} failed: {e}")
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"Failed to get connection after {max_retries} attempts")
                raise
    return None

def init_database():
    """初始化数据库表结构"""
    tables = [
        """
        CREATE TABLE IF NOT EXISTS node_heartbeats (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            client_addr VARCHAR(255) NOT NULL,
            cpu_usage FLOAT NOT NULL,
            memory_usage FLOAT NOT NULL,
            last_heartbeat TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_client_addr (client_addr),
            INDEX idx_last_heartbeat (last_heartbeat)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS server_auth (
            id INT PRIMARY KEY AUTO_INCREMENT,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id VARCHAR(255) PRIMARY KEY,
            status VARCHAR(50) DEFAULT 'pending',
            center_x FLOAT NOT NULL,
            center_y FLOAT NOT NULL,
            center_z FLOAT NOT NULL,
            size_x FLOAT NOT NULL,
            size_y FLOAT NOT NULL,
            size_z FLOAT NOT NULL,
            num_modes INT NOT NULL,
            energy_range FLOAT NOT NULL,
            cpu INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_status (status),
            INDEX idx_created_at (created_at)
        )
        """
    ]

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 创建基础表
        for table_sql in tables:
            cursor.execute(table_sql)
        
        # 动态创建任务相关表
        cursor.execute("SELECT id FROM tasks")
        tasks = cursor.fetchall()
        for (task_id,) in tasks:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS task_{task_id}_ligands (
                    ligand_id VARCHAR(255) PRIMARY KEY,
                    ligand_file VARCHAR(255) NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    retry_count INT DEFAULT 0,  # 新增重试计数字段
                    output_file VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_status (status)
                )
            """)
        
        conn.commit()
        logger.info("Database tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def execute_query(query, params=None, fetch_one=False):
    """执行查询语句"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        
        if fetch_one:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()
            
        conn.commit()
        return result
        
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def execute_update(query, params=None):
    """执行更新/插入语句"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        conn.commit()
        return cursor.rowcount
        
    except Exception as e:
        logger.error(f"Update execution failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# 初始化连接池和数据库
if __name__ == '__main__':
    init_connection_pool()
    init_database()