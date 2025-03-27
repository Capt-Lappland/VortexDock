<pre>
 __     __         _            ____             _    
 \ \   / /__  _ __| |_ _____  _|  _ \  ___   ___| | __
  \ \ / / _ \| '__| __/ _ \ \/ / | | |/ _ \ / __| |/ /
   \ V / (_) | |  | ||  __/>  <| |_| | (_) | (__|   < 
    \_/ \___/|_|   \__\___/_/\_\____/ \___/ \___|_|\_\
</pre>   
# VortexDock: Distributed Molecular Docking System

VortexDock is a Python-based distributed molecular docking system consisting of a distribution server, a monitoring server, and compute nodes. It supports parallel computation across multiple nodes, utilizing idle resources to improve virtual screening efficiency. Currently, it supports AutoDock Vina, with plans to add more docking software.

## Architecture

### Distribution Server
Manages the task database, distributes receptor, ligand, and docking parameters, and collects docking results (ligand_out.pdbqt) from compute nodes.

### Monitoring Server
Monitors the task database and visualizes task execution status.

### Compute Node
Fetches tasks from the distribution server, performs docking, and submits results back to the server.

## Installation

1. Clone the repository.
2. Install MySQL (current must, but we'll support SQLite soon)
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Distribution Server Setup

1. Navigate to the `distribution_server` directory.
2. Edit `config.py`:
   - Database connection
   - Server port
   - Other parameters
3. Initialize the database:
   ```bash
   python cli.py
   ```

### Compute Node Setup

1. Navigate to the `compute_node` directory.
2. Edit `config.py`:
   - Server connection
   - Task parameters
   - System settings
3. Ensure the `vina` program has execution permissions.

## Usage

### Start Distribution Server

```bash
cd distribution_server
python server.py
```

### Task Management

```bash
# List all tasks
python cli.py -ls

# Create a new task
python cli.py -zip <task_file.zip> -name <task_name>

# Pause/Resume a task
python cli.py -pause <task_id>

# Delete a task
python cli.py -rm <task_id>
```

### Start Monitoring Server

Python-based monitoring server:
```bash
cd monitor_server
python app.py  # Default: localhost:9000
```

PHP-based monitoring server:
Set the web root to `monitor_server_PHP`.

### Start Compute Node

```bash
cd compute_node
python client.py
```

## Features

- Distributed computation with multi-node support
- Task resumption after interruption
- Node heartbeat detection
- Automatic retry for failed tasks
- Temporary file management
