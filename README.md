# 分子对接分布式计算系统

这是一个基于 Python 的分布式分子对接计算系统，由分发服务器和计算节点两部分组成。系统支持多个计算节点同时运行，提高分子对接计算的效率。

## 系统架构

### 分发服务器 (Distribution Server)

分发服务器负责：
- 任务管理和分发
- 文件存储和传输
- 进度监控和状态更新
- 提供 HTTP 和 TCP 服务

主要组件：
- `server.py`: 核心服务器程序
- `cli.py`: 命令行工具
- `config.py`: 服务器配置文件

### 计算节点 (Compute Node)

计算节点负责：
- 执行分子对接计算
- 文件下载和上传
- 结果提交
- 自动任务获取

主要组件：
- `client.py`: 计算节点程序
- `config.py`: 节点配置文件
- `vina`: AutoDock Vina 可执行文件

## 安装步骤

1. 克隆代码仓库
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

### 分发服务器配置

1. 进入 distribution_server 目录
2. 修改 config.py 配置：
   - 数据库连接信息
   - 服务器端口
   - 其他系统参数
3. 初始化数据库：
   ```bash
   python cli.py
   ```

### 计算节点配置

1. 进入 compute_node 目录
2. 修改 config.py 配置：
   - 服务器连接信息
   - 任务参数
   - 系统设置
3. 确保 vina 程序有执行权限

## 使用方法

### 启动分发服务器

```bash
cd distribution_server
python server.py
```

### 任务管理

使用命令行工具管理任务：

```bash
# 列出所有任务
python cli.py -ls

# 创建新任务
python cli.py -zip <任务文件.zip> -name <任务名称>

# 暂停/恢复任务
python cli.py -pause <任务ID>

# 删除任务
python cli.py -rm <任务ID>
```

### 启动计算节点

```bash
cd compute_node
python client.py
```

## 系统特性

- 分布式计算：支持多节点并行计算
- 自动负载均衡：智能分配任务
- 断点续传：支持任务中断后继续
- 心跳检测：自动检测节点状态
- 错误重试：自动处理失败任务
- 文件管理：自动清理临时文件

## 注意事项

1. 确保数据库服务正常运行
2. 检查网络连接和防火墙设置
3. 定期检查磁盘空间
4. 及时清理旧任务数据