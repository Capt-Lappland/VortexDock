import os
import sys
import zipfile
import argparse
from pathlib import Path

sys.path.append('..')
from utils.db import execute_query, execute_update, get_db_connection

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create main task table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id VARCHAR(255) PRIMARY KEY,
            status VARCHAR(50),
            center_x FLOAT,
            center_y FLOAT,
            center_z FLOAT,
            size_x FLOAT,
            size_y FLOAT,
            size_z FLOAT,
            num_modes INT,
            energy_range FLOAT,
            cpu INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def list_tasks():
    tasks = execute_query('SELECT id, status, created_at FROM tasks')
    
    if not tasks:
        print("No tasks found")
    else:
        print("Task List:")
        print("ID\tStatus\tProgress\t\tSpeed (items/min)\tCreated At")
        for task in tasks:
            task_id = task['id']
            # Get the total number of ligands and completed ligands for the task
            total = execute_query(f'SELECT COUNT(*) as count FROM task_{task_id}_ligands', fetch_one=True)['count']
            completed = execute_query(f'SELECT COUNT(*) as count FROM task_{task_id}_ligands WHERE status = "completed"', fetch_one=True)['count']
            
            # Calculate progress percentage
            progress = completed / total if total > 0 else 0
            progress_bar = create_progress_bar(progress)
            
            # Calculate processing speed in the last 5 minutes
            recent_completed = execute_query(f'''
                SELECT COUNT(*) as count
                FROM task_{task_id}_ligands 
                WHERE status = 'completed' 
                AND last_updated >= NOW() - INTERVAL 5 MINUTE
            ''', fetch_one=True)['count']
            speed = recent_completed / 5 if recent_completed > 0 else 0
            
            print(f"{task_id}\t{task['status']}\t{progress_bar}\t{speed:.1f}\t\t{task['created_at']}")

def create_progress_bar(progress, width=20):
    # Generate a progress bar string
    filled = int(width * progress)
    empty = width - filled
    bar = '=' * filled + '>' + ' ' * empty if filled < width else '=' * width
    percentage = int(progress * 100)
    return f'[{bar}] {percentage}%'

def create_task(zip_path, name):
    if not os.path.exists(zip_path):
        print(f"Error: File {zip_path} not found")
        return
    
    if execute_query('SELECT id FROM tasks WHERE id = %s', (name,), fetch_one=True):
        print(f"Error: Task name '{name}' already exists, please use a different name.")
        return
    
    # Create temporary directory to extract files
    temp_dir = Path('temp_extract')
    temp_dir.mkdir(exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Validate required files
        receptor_file = next(temp_dir.glob('**/receptor.pdbqt'), None)
        parameter_file = next(temp_dir.glob('**/parameter.txt'), None)
        ligand_files = list(temp_dir.glob('**/ligands/*.pdbqt'))
        
        if not (receptor_file and parameter_file and ligand_files):
            print("Error: ZIP file is missing required files (receptor.pdbqt, parameter.txt, ligands/ligand_*.pdbqt)")
            return
        
        # Move files to task directory
        task_dir = Path('tasks') / name
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Create ligands subdirectory
        ligands_dir = task_dir / 'ligands'
        ligands_dir.mkdir(exist_ok=True)
        
        receptor_dest = task_dir / 'receptor.pdbqt'
        parameter_dest = task_dir / 'parameter.txt'
        
        receptor_file.rename(receptor_dest)
        parameter_file.rename(parameter_dest)
        
        # Create database records
        conn = get_db_connection()
        c = conn.cursor()
        
        # Parse parameter file
        params = {}
        with open(parameter_dest, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=')
                    params[key.strip()] = value.strip()
        
        # Insert main task record
        execute_update('''
            INSERT INTO tasks (
                id, status,
                center_x, center_y, center_z,
                size_x, size_y, size_z,
                num_modes, energy_range, cpu
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            name, 'pending',
            float(params.get('center_x', 0)), float(params.get('center_y', 0)), float(params.get('center_z', 0)),
            float(params.get('size_x', 0)), float(params.get('size_y', 0)), float(params.get('size_z', 0)),
            int(params.get('num_modes', 9)), float(params.get('energy_range', 3)), int(params.get('cpu', 1))
        ))
        
        # Create task-specific ligand table
        execute_update(f'''
            CREATE TABLE IF NOT EXISTS task_{name}_ligands (
                ligand_id VARCHAR(255) PRIMARY KEY,
                ligand_file VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                output_file VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add ligand records
        for ligand_file in ligand_files:
            # Use file name (without extension) as ligand_id
            ligand_id = ligand_file.stem
            ligand_dest = ligands_dir / ligand_file.name
            ligand_file.rename(ligand_dest)
            
            execute_update(f'''
                INSERT INTO task_{name}_ligands (ligand_id, ligand_file)
                VALUES (%s, %s)
            ''', (ligand_id, ligand_file.name))
        
        conn.commit()
        conn.close()
        
        print(f"Task {name} created successfully")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Clean up temporary directory
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)

def remove_task(task_id):
    try:
        # Check if the task exists
        if not execute_query('SELECT id FROM tasks WHERE id = %s', (task_id,), fetch_one=True):
            print(f"Error: Task {task_id} not found")
            return
        
        # Delete task record
        execute_update('DELETE FROM tasks WHERE id = %s', (task_id,))
        
        # Delete task-specific ligand table
        execute_update(f'DROP TABLE IF EXISTS task_{task_id}_ligands')
        
        # Delete task-related files
        task_dir = Path('tasks') / task_id
        result_dir = Path('results') / task_id
        
        import shutil
        if task_dir.exists():
            shutil.rmtree(task_dir)
        if result_dir.exists():
            shutil.rmtree(result_dir)
            
        print(f"Task {task_id} deleted successfully")
        
    except Exception as e:
        print(f"Error deleting task: {str(e)}")

def pause_task(task_id):
    try:
        # Check if the task exists
        task = execute_query('SELECT status FROM tasks WHERE id = %s', (task_id,), fetch_one=True)
        if not task:
            print(f"Error: Task {task_id} not found")
            return
        
        current_status = task['status']
        new_status = 'paused' if current_status == 'pending' else 'pending'
        
        # Update task status
        execute_update('UPDATE tasks SET status = %s WHERE id = %s', (new_status, task_id))
        
        action = 'Paused' if new_status == 'paused' else 'Resumed'
        print(f"Task {task_id} {action} successfully")
        
    except Exception as e:
        print(f"Error updating task status: {str(e)}")

def set_server_password(password):
    try:
        # Generate password hash
        import bcrypt
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        
        # Clear old authentication information
        execute_update('DELETE FROM server_auth')
        
        # Insert new authentication information
        execute_update('''
            INSERT INTO server_auth (password_hash)
            VALUES (%s)
        ''', (password_hash.decode('utf-8'),))
        
        print("Server password set successfully")
        
    except Exception as e:
        print(f"Error setting password: {str(e)}")

def reset_node_heartbeats():
    try:
        # Drop and recreate node_heartbeats table
        execute_update('DROP TABLE IF EXISTS node_heartbeats')
        execute_update('''
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
        ''')
        print("Node heartbeats table reset successfully")
    except Exception as e:
        print(f"Error resetting node heartbeats table: {str(e)}")

def reset_processing_tasks():
    try:
        # Get all tasks
        tasks = execute_query('SELECT id FROM tasks')
        
        for task in tasks:
            task_id = task['id']
            # Update ligand table status from processing to pending
            execute_update(f'''
                UPDATE task_{task_id}_ligands 
                SET status = 'pending', 
                    last_updated = CURRENT_TIMESTAMP 
                WHERE status = 'processing'
            ''')
            
            # Update main task table status
            execute_update('''
                UPDATE tasks 
                SET status = 'pending', 
                    last_updated = CURRENT_TIMESTAMP 
                WHERE id = %s
            ''', (task_id,))
        
        print("All processing tasks reset to pending status")
        
    except Exception as e:
        print(f"Error resetting task status: {str(e)}")
        
def reset_failed_tasks():
    try:
        # Get all tasks
        tasks = execute_query('SELECT id FROM tasks')
        
        for task in tasks:
            task_id = task['id']
            # Update ligand table status from failed to pending
            execute_update(f'''
                UPDATE task_{task_id}_ligands 
                SET status = 'pending', 
                    last_updated = CURRENT_TIMESTAMP 
                WHERE status = 'failed'
            ''')
            
            # Update main task table status
            execute_update('''
                UPDATE tasks 
                SET status = 'pending', 
                    last_updated = CURRENT_TIMESTAMP 
                WHERE id = %s
            ''', (task_id,))
        
        print("All failed tasks reset to pending status")
        
    except Exception as e:
        print(f"Error resetting task status: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Molecular Docking Task Management Tool')
    parser.add_argument('-ls', action='store_true', help='List all tasks')
    parser.add_argument('-zip', help='Path to the task ZIP file to submit')
    parser.add_argument('-name', help='Task name')
    parser.add_argument('-rm', help='Delete specified task')
    parser.add_argument('-pause', help='Pause/Resume specified task')
    parser.add_argument('-set-password', help='Set server password')
    parser.add_argument('-reset-heartbeats', action='store_true', help='Reset node heartbeats table')
    parser.add_argument('-reset-processing', action='store_true', help='Reset all processing tasks to pending status')
    parser.add_argument('-reset-failed', action='store_true', help='Reset all failed tasks to pending status')
    
    args = parser.parse_args()
    
    # Ensure database and necessary directories exist
    init_db()
    os.makedirs('tasks', exist_ok=True)
    
    if args.ls:
        list_tasks()
    elif args.zip and args.name:
        create_task(args.zip, args.name)
    elif args.rm:
        remove_task(args.rm)
    elif args.pause:
        pause_task(args.pause)
    elif args.set_password:
        set_server_password(args.set_password)
    elif args.reset_heartbeats:
        reset_node_heartbeats()
    elif args.reset_processing:
        reset_processing_tasks()
    elif args.reset_failed:
        reset_failed_tasks()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()