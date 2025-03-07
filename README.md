<pre>
 __     __         _            ____             _    
 \ \   / /__  _ __| |_ _____  _|  _ \  ___   ___| | __
  \ \ / / _ \| '__| __/ _ \ \/ / | | |/ _ \ / __| |/ /
   \ V / (_) | |  | ||  __/>  <| |_| | (_) | (__|   < 
    \_/ \___/|_|   \__\___/_/\_\____/ \___/ \___|_|\_\
</pre>   
# VortexDock 分布式分子对接系统

VortexDock 是一个基于 Python 的分布式分子对接计算系统，由分发服务器、监控服务器和计算节点三部分组成。系统支持多个计算节点同时运行，运用空闲算力进行计算，大大提高了虚拟筛选的效率。目前对接软件只支持 AutoDock Vina，后续会增加对其他分子对接软件的支持。

## 系统架构

### 分发服务器 (Distribution Server)
维护任务数据库，存储并分发受体、配体和对接参数，获取并存储计算节点的对接结果(ligand_out.pdbqt)。

### 监控服务器（Monitoring Server）
监控任务数据库，总结并可视化对接任务的执行情况。

### 计算节点 (Compute Node)
执行分子对接计算的节点，主动从分发服务器获取任务，进行分子对接，将计算结果提交到分发服务器
 
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
### 启动监控服务器
监控服务器有两种形式，一种基于 Python ，另一种基于 PHP

基于 Python 的监控服务器启动使用下列指令
```bash

cd monitor_server
python app.py # 默认开放在 localhost:9000
```
启动基于 PHP 的监控服务器则将网站的根目录设置为 monitor_server_PHP
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
                                                