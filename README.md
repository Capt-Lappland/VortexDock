# 分子对接分布式计算系统 (Distributed Molecular Docking System)

这是一个基于 Python 的分布式分子对接计算系统，由分发服务器和计算节点两部分组成。系统支持多个计算节点同时运行，提高分子对接计算的效率。

This is a Python-based distributed molecular docking computation system, consisting of a distribution server and compute nodes. The system supports multiple compute nodes running simultaneously to improve the efficiency of molecular docking calculations.

## 系统架构 (System Architecture)

### 分发服务器 (Distribution Server)

分发服务器负责：
The distribution server is responsible for:

- 任务管理和分发 (Task management and distribution)
- 文件存储和传输 (File storage and transfer)
- 进度监控和状态更新 (Progress monitoring and status updates)
- 提供 HTTP 和 TCP 服务 (Providing HTTP and TCP services)

主要组件 (Main Components)：
- `server.py`: 核心服务器程序 (Core server program)
- `cli.py`: 命令行工具 (Command-line tool)
- `config.py`: 服务器配置文件 (Server configuration file)

### 计算节点 (Compute Node)

计算节点负责：
The compute node is responsible for:

- 执行分子对接计算 (Performing molecular docking calculations)
- 文件下载和上传 (File download and upload)
- 结果提交 (Result submission)
- 自动任务获取 (Automatic task acquisition)

主要组件 (Main Components)：
- `client.py`: 计算节点程序 (Compute node program)
- `config.py`: 节点配置文件 (Node configuration file)
- `vina`: AutoDock Vina 可执行文件 (AutoDock Vina executable)

## 安装步骤 (Installation Steps)

1. 克隆代码仓库 (Clone the repository)
2. 安装依赖 (Install dependencies)：
   ```bash
   pip install -r requirements.txt
   ```

### 分发服务器配置 (Distribution Server Configuration)

1. 进入 distribution_server 目录 (Enter distribution_server directory)
2. 修改 config.py 配置 (Modify config.py configuration)：
   - 数据库连接信息 (Database connection information)
   - 服务器端口 (Server ports)
   - 其他系统参数 (Other system parameters)
3. 初始化数据库 (Initialize database)：
   ```bash
   python cli.py
   ```

### 计算节点配置 (Compute Node Configuration)

1. 进入 compute_node 目录 (Enter compute_node directory)
2. 修改 config.py 配置 (Modify config.py configuration)：
   - 服务器连接信息 (Server connection information)
   - 任务参数 (Task parameters)
   - 系统设置 (System settings)
3. 确保 vina 程序有执行权限 (Ensure vina program has execution permissions)

## 使用方法 (Usage)

### 启动分发服务器 (Start Distribution Server)

```bash
cd distribution_server
python server.py
```

### 任务管理 (Task Management)

使用命令行工具管理任务 (Use command-line tool to manage tasks)：

```bash
# 列出所有任务 (List all tasks)
python cli.py -ls

# 创建新任务 (Create new task)
python cli.py -zip <task_file.zip> -name <task_name>

# 暂停/恢复任务 (Pause/Resume task)
python cli.py -pause <task_id>

# 删除任务 (Delete task)
python cli.py -rm <task_id>
```

### 启动计算节点 (Start Compute Node)

```bash
cd compute_node
python client.py
```

## 系统特性 (System Features)

- 分布式计算 (Distributed Computing)：支持多节点并行计算 (Supports parallel computing across multiple nodes)
- 自动负载均衡 (Automatic Load Balancing)：智能分配任务 (Intelligent task distribution)
- 断点续传 (Breakpoint Resume)：支持任务中断后继续 (Supports task continuation after interruption)
- 心跳检测 (Heartbeat Detection)：自动检测节点状态 (Automatic node status detection)
- 错误重试 (Error Retry)：自动处理失败任务 (Automatic handling of failed tasks)
- 文件管理 (File Management)：自动清理临时文件 (Automatic cleanup of temporary files)

## 注意事项 (Important Notes)

1. 确保数据库服务正常运行 (Ensure database service is running properly)
2. 检查网络连接和防火墙设置 (Check network connection and firewall settings)
3. 定期检查磁盘空间 (Regularly check disk space)
4. 及时清理旧任务数据 (Clean up old task data in a timely manner)