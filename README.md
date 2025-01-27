# VortexDock: Distributed Molecular Docking System

This is a Python-based distributed molecular docking computation system, consisting of a distribution server and compute nodes. The system supports multiple compute nodes running simultaneously to improve the efficiency of molecular docking calculations.

## System Architecture

### Distribution Server

The distribution server is responsible for:

- Task management and distribution
- File storage and transfer
- Progress monitoring and status updates
- Providing HTTP and TCP services

Main Components:
- `server.py`: Core server program
- `cli.py`: Command-line tool
- `config.py`: Server configuration file

### Compute Node

The compute node is responsible for:

- Performing molecular docking calculations
- File download and upload
- Result submission
- Automatic task acquisition

Main Components:
- `client.py`: Compute node program
- `daemon.py`: Daemon process program
- `config.py`: Node configuration file
- `vina`: AutoDock Vina executable

## Installation Steps

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Distribution Server Configuration

1. Enter distribution_server directory
2. Modify config.py configuration:
   - Database connection information
   - Server ports
   - Other system parameters
3. Initialize database:
   ```bash
   python cli.py
   ```

### Compute Node Configuration

1. Enter compute_node directory
2. Modify config.py configuration:
   - Server connection information
   - Task parameters
   - System settings
3. Ensure vina program has execution permissions

## Usage

### Start Distribution Server

```bash
cd distribution_server
python server.py
```

### Task Management

Use command-line tool to manage tasks:

```bash
# List all tasks
python cli.py -ls

# Create new task
python cli.py -zip <task_file.zip> -name <task_name>

# Pause/Resume task
python cli.py -pause <task_id>

# Delete task
python cli.py -rm <task_id>
```

### Start Compute Node

The compute node supports two running modes:

1. Direct Running Mode:
```bash
cd compute_node
python client.py
```

2. Daemon Mode (Recommended):
```bash
cd compute_node
python daemon.py start  # Start daemon process
python daemon.py stop   # Stop daemon process
python daemon.py status # Check running status
```

Advantages of Daemon Mode:
- Runs in background, unaffected by terminal closure
- Automatic monitoring and restart of compute process
- Lower system resource usage
- Supports graceful shutdown and status query

## System Features

- Distributed Computing: Supports parallel computing across multiple nodes
- Automatic Load Balancing: Intelligent task distribution
- Breakpoint Resume: Supports task continuation after interruption
- Heartbeat Detection: Automatic node status detection
- Error Retry: Automatic handling of failed tasks
- File Management: Automatic cleanup of temporary files

## Important Notes

1. Ensure database service is running properly
2. Check network connection and firewall settings
3. Regularly check disk space
4. Clean up old task data in a timely manner