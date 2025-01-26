import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

class Logger:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.logger = logging.getLogger('dock_server')
        self.logger.setLevel(logging.DEBUG)

        # 创建日志目录
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)

        # 配置文件处理器
        log_file = os.path.join(log_dir, 'dock_server.log')
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)

        # 配置控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        # 设置日志格式
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def debug(self, message):
        """调试信息，用于开发调试"""
        self.logger.debug(message)

    def info(self, message):
        """一般信息，用于记录正常的操作流程"""
        self.logger.info(message)

    def warning(self, message):
        """警告信息，用于可能的问题或异常情况"""
        self.logger.warning(message)

    def error(self, message):
        """错误信息，用于操作失败或异常情况"""
        self.logger.error(message)

    def critical(self, message):
        """严重错误，用于影响系统运行的致命错误"""
        self.logger.critical(message)

# 全局日志实例
logger = Logger()