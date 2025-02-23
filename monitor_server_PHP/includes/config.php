<?php

// 数据库配置
$DB_CONFIG = array(
    'host' => 'localhost',
    'user' => 'dock_server2',
    'password' => 'WangRunZe2003@',
    'database' => 'dock_server2',
    'pool_name' => 'mypool',
    'pool_size' => 5
);

// 服务器配置
$SERVER_CONFIG = array(
    'host' => 'localhost',
    'http_port' => 9000,  // HTTP服务器端口
    'tcp_port' => 10020,  // TCP命令服务器端口
    'password' => 'your_server_password'  // 服务器密码，通过 CLI 设置
);

// 任务配置
$TASK_CONFIG = array(
    'max_retries' => 5,  // 最大重试次数
    'retry_delay' => 5,  // 重试延迟（秒）
    'task_timeout' => 3600,  // 任务超时时间（秒）
    'cleanup_interval' => 3600,  // 清理间隔（秒）
    'cleanup_age' => 86400,  // 清理阈值（秒）
    'heartbeat_interval' => 30  // 心跳间隔（秒）
);

// 调试配置
$DEBUG = false;