# VortexDock 分子对接分布式计算系统

这是一个基于 Python 的分布式分子对接计算系统，由分发服务器和计算节点两部分组成。系统目前支持 AutoDock Vina 分子对接软件，可通过多个计算节点同时运行，提高分子对接计算的效率。未来计划支持更多分子对接软件。

## 系统架构

### 分发服务器

分发服务器负责：

- 任务管理和分发
- 文件存储和传输
- 进度监控和状态更新
- 提供 HTTP 和 TCP 服务

主要组件：
- `server.py`: 核心服务器程序
- `cli.py`: 命令行工具
- `config.py`: 服务器配置文件

### 计算节点

计算节点负责：

- 执行分子对接计算
- 文件下载和上传
- 结果提交
- 自动任务获取

主要组件：
- `client.py`: 计算节点程序
- `daemon.py`: 守护进程程序
- `config.py`: 节点配置文件
- `vina`: AutoDock Vina 可执行文件

## 系统要求

### AutoDock Vina

1. 安装 AutoDock Vina：
   - 从官方网站下载对应系统版本的 AutoDock Vina
   - 确保 vina 程序在系统 PATH 中或放置在 compute_node 目录下
   - 验证安装：在终端运行 `vina --help` 确认可正常使用

2. 准备输入文件：
   - 受体（蛋白质）结构文件（PDBQT 格式）
   - 配体（小分子）结构文件（PDBQT 格式）
   - 对接配置文件（包含搜索空间等参数）

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
python cli.py -zip <task_file.zip> -name <task_name>

# 暂停/恢复任务
python cli.py -pause <task_id>

# 删除任务
python cli.py -rm <task_id>
```

### 任务文件准备

创建任务前需要准备以下文件并打包为 ZIP 格式：

1. 受体文件：
   - 文件名：`receptor.pdbqt`
   - 格式：PDBQT
   - 说明：已处理好的蛋白质结构文件

2. 配体文件：
   - 文件名：`ligands.pdbqt`
   - 格式：PDBQT
   - 说明：包含一个或多个小分子的结构文件

3. 配置文件：
   - 文件名：`config.txt`
   - 格式：文本文件
   - 内容示例：
     ```
     receptor = receptor.pdbqt
     ligand = ligands.pdbqt
     center_x = 0.0
     center_y = 0.0
     center_z = 0.0
     size_x = 20.0
     size_y = 20.0
     size_z = 20.0
     exhaustiveness = 8
     num_modes = 9
     energy_range = 3
     ```

### 启动计算节点

计算节点支持两种运行模式：

1. 直接运行模式：
```bash
cd compute_node
python client.py
```

2. 守护进程模式（推荐）：
```bash
cd compute_node
python daemon.py # 以守护进程方式启动
```

守护进程模式的优势：
- 后台运行，不受终端关闭影响
- 自动监控和重启计算进程
- 系统资源占用更少
- 支持优雅关闭和状态查询


## 注意事项

1. 确保数据库服务正常运行
2. 检查网络连接和防火墙设置
3. 定期检查磁盘空间
4. 及时清理旧任务数据
5. 确保 AutoDock Vina 配置正确且可用