# db.py
import os
import time
import logging
from pathlib import Path
from typing import Optional, Union
import sqlite3
import mysql.connector
from mysql.connector import pooling

from config import DB_TYPE, DB_CONFIG
from utils.logger import logger

# 统一连接类型
Connection = Union[
    sqlite3.Connection,
    pooling.PooledMySQLConnection
]

class DatabaseManager:
    def __init__(self):
        self.db_type = DB_TYPE.lower()
        self.mysql_pool = None
        self._init_database()

    def _init_database(self):
        """根据配置初始化数据库连接"""
        if self.db_type == 'mysql':
            self._init_mysql_pool()
        elif self.db_type == 'sqlite':
            self._init_sqlite_db()
        else:
            raise ValueError(f"不支持的数据库类型: {self.db_type}")

    def _init_mysql_pool(self):
        """初始化MySQL连接池"""
        mysql_config = DB_CONFIG['mysql'].copy()
        try:
            self.mysql_pool = pooling.MySQLConnectionPool(
                pool_name=mysql_config.pop('pool_name'),
                pool_size=mysql_config.pop('pool_size'),
                **mysql_config
            )
            logger.info(f"Initialized MySQL pool with {mysql_config['pool_size']} connections")
        except Exception as e:
            logger.critical(f"MySQL连接池初始化失败: {e}")
            raise

    def _init_sqlite_db(self):
        """初始化SQLite数据库"""
        sqlite_config = DB_CONFIG['sqlite']
        db_path = Path(sqlite_config['database'])
        
        # 创建数据库目录
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 测试连接
        try:
            conn = sqlite3.connect(
                database=db_path,
                check_same_thread=sqlite_config['check_same_thread']
            )
            conn.close()
            logger.info(f"SQLite数据库已就绪: {db_path}")
        except Exception as e:
            logger.critical(f"SQLite连接失败: {e}")
            raise

    def get_connection(self) -> Connection:
        """获取数据库连接（自动适配类型）"""
        if self.db_type == 'mysql':
            return self._get_mysql_connection()
        return self._get_sqlite_connection()

    def _get_mysql_connection(self) -> pooling.PooledMySQLConnection:
        """获取MySQL连接（带重试）"""
        for attempt in range(1, 4):
            try:
                conn = self.mysql_pool.get_connection()
                if conn.is_connected():
                    return conn
            except Exception as e:
                logger.warning(f"MySQL连接尝试 {attempt}/3 失败: {e}")
                time.sleep(1)
        raise ConnectionError("无法获取MySQL连接")

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        """获取SQLite连接"""
        return sqlite3.connect(
            database=DB_CONFIG['sqlite']['database'],
            check_same_thread=DB_CONFIG['sqlite']['check_same_thread']
        )

    class DBCursor:
        """上下文管理器统一处理连接"""
        def __init__(self, db_manager):
            self.db_manager = db_manager
            self.conn = None
            self.cursor = None

        def __enter__(self):
            self.conn = self.db_manager.get_connection()
            self.cursor = self.conn.cursor()
            return self.cursor

        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
            finally:
                self.cursor.close()
                self.conn.close()

# 单例实例
db_manager = DatabaseManager()

def execute_sql(sql: str, params: tuple = (), fetch: bool = False):
    """通用SQL执行方法"""
    with db_manager.DBCursor(db_manager) as cursor:
        try:
            cursor.execute(sql, params)
            if fetch:
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"SQL执行失败: {e}\nSQL: {sql}\nParams: {params}")
            raise

def init_tables():
    """初始化所有数据库表结构（兼容 MySQL 和 SQLite）"""
    try:
        # 计算节点心跳表
        execute_sql('''
            CREATE TABLE IF NOT EXISTS node_heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_addr TEXT NOT NULL,
                cpu_usage REAL NOT NULL,
                memory_usage REAL NOT NULL,
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        execute_sql('CREATE INDEX IF NOT EXISTS idx_client_addr ON node_heartbeats (client_addr)')
        execute_sql('CREATE INDEX IF NOT EXISTS idx_last_heartbeat ON node_heartbeats (last_heartbeat)')

        # 服务器认证表
        execute_sql('''
            CREATE TABLE IF NOT EXISTS server_auth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 主任务表
        execute_sql('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                status TEXT,
                center_x REAL,
                center_y REAL,
                center_z REAL,
                size_x REAL,
                size_y REAL,
                size_z REAL,
                num_modes INTEGER,
                energy_range REAL,
                cpu INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        execute_sql('CREATE INDEX IF NOT EXISTS idx_status ON tasks (status)')

        # 动态创建任务配体表
        tasks = execute_sql('SELECT id FROM tasks', fetch=True)
        for task in tasks:
            task_id = task['id']
            execute_sql(f'''
                CREATE TABLE IF NOT EXISTS task_{task_id}_ligands (
                    ligand_id TEXT PRIMARY KEY,
                    ligand_file TEXT,
                    status TEXT DEFAULT 'pending',
                    output_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        logger.info("数据库表结构初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise