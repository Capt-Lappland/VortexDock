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

def init_connection_pool(config=None):
    """Initialize the database connection pool"""
    global connection_pool
    try:
        cfg = config if config is not None else DB_CONFIG
        if cfg['type'] == 'sqlite':
            connection_pool = None  # SQLite 不需要连接池
            logger.info("SQLite database configured successfully")
        elif cfg['type'] == 'mysql':
            # MySQL 连接池初始化
            pool_name = cfg.get('pool_name', 'mypool')
            pool_size = cfg.get('pool_size', 10)
            connection_pool = pooling.MySQLConnectionPool(
                pool_name=pool_name,
                pool_size=pool_size,
                pool_reset_session=cfg.get('pool_reset_session', True),
                host=cfg.get('host', 'localhost'),
                user=cfg.get('user', 'root'),
                password=cfg.get('password', ''),
                database=cfg.get('database', 'mysql'),
                connect_timeout=cfg.get('connect_timeout', 10)
            )
            logger.info("MySQL database connection pool initialized successfully")
        else:
            raise ValueError(f"Unsupported database type: {cfg['type']}")
    except Exception as e:
        logger.critical(f"Failed to initialize connection pool: {e}")
        raise

def get_db_connection():
    """Get a database connection (with retry mechanism)"""
    cfg = DB_CONFIG
    if cfg['type'] == 'sqlite':
        import sqlite3
        return sqlite3.connect(cfg['database'])
    
    if not connection_pool:
        init_connection_pool()
    
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            conn = connection_pool.get_connection()
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
    """Initialize database tables"""
    cfg = DB_CONFIG
    if cfg['type'] == 'sqlite':
        # SQLite-specific table creation
        tables = [
            """
            CREATE TABLE IF NOT EXISTS node_heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_addr TEXT NOT NULL,
                cpu_usage REAL NOT NULL,
                memory_usage REAL NOT NULL,
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS server_auth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                status TEXT DEFAULT 'pending',
                center_x REAL NOT NULL,
                center_y REAL NOT NULL,
                center_z REAL NOT NULL,
                size_x REAL NOT NULL,
                size_y REAL NOT NULL,
                size_z REAL NOT NULL,
                num_modes INTEGER NOT NULL,
                energy_range REAL NOT NULL,
                cpu INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
    else:
        # MySQL-specific table creation
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
        
        if cfg['type'] != 'sqlite':
            # 动态创建任务相关表
            cursor.execute("SELECT id FROM tasks")
            tasks = cursor.fetchall()
            for task in tasks:
                task_id = task[0] if cfg['type'] == 'sqlite' else task['id']
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS task_{task_id}_ligands (
                        ligand_id VARCHAR(255) PRIMARY KEY,
                        ligand_file VARCHAR(255) NOT NULL,
                        status VARCHAR(50) DEFAULT 'pending',
                        retry_count INT DEFAULT 0,
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
        if conn:
            cursor.close()
            conn.close()

def execute_query(query, params=None, fetch_one=False):
    """执行查询语句"""
    conn = None
    try:
        conn = get_db_connection()
        # 根据数据库类型动态设置游标返回类型
        cursor = conn.cursor() if DB_CONFIG['type'] == 'sqlite' else conn.cursor(dictionary=True)
        # 动态处理占位符
        query = query.replace('%s', '?') if DB_CONFIG['type'] == 'sqlite' else query
        cursor.execute(query, params or ())
        
        # 根据游标返回类型处理结果
        result = cursor.fetchone() if fetch_one else cursor.fetchall()
        if DB_CONFIG['type'] == 'sqlite' and result:
            # 将 SQLite 的元组结果转换为字典（仅在需要时）
            columns = [col[0] for col in cursor.description]
            if fetch_one:
                result = dict(zip(columns, result))
            else:
                result = [dict(zip(columns, row)) for row in result]
        
        if DB_CONFIG['type'] == 'sqlite':
            conn.commit()  # SQLite 需要显式提交
        return result
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cursor.close()
            conn.close()

def execute_update(query, params=None):
    """执行更新/插入语句"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 动态处理占位符
        query = query.replace('%s', '?') if DB_CONFIG['type'] == 'sqlite' else query
        cursor.execute(query, params or ())
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        logger.error(f"Update execution failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            cursor.close()
            conn.close()

# 初始化连接池和数据库
if __name__ == '__main__':
    init_connection_pool()
    init_database()