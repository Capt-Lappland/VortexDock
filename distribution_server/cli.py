import os
import sys
import zipfile
import mysql.connector
import argparse
from pathlib import Path

import sys
sys.path.append('..')
from config import DB_CONFIG

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        print(f"数据库连接失败: {e}")
        return None

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 创建主任务表
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
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT id, status, created_at FROM tasks')
    tasks = c.fetchall()
    
    if not tasks:
        print("没有找到任务")
    else:
        print("任务列表:")
        print("ID\t状态\t进度\t\t速度(个/分钟)\t创建时间")
        for task in tasks:
            task_id = task[0]
            # 获取该任务的配体总数和已完成数
            c.execute(f'SELECT COUNT(*) FROM task_{task_id}_ligands')
            total = c.fetchone()[0]
            c.execute(f'SELECT COUNT(*) FROM task_{task_id}_ligands WHERE status = "completed"')
            completed = c.fetchone()[0]
            
            # 计算进度百分比
            progress = completed / total if total > 0 else 0
            progress_bar = create_progress_bar(progress)
            
            # 计算最近5分钟的处理速度
            c.execute(f'''
                SELECT COUNT(*) 
                FROM task_{task_id}_ligands 
                WHERE status = 'completed' 
                AND last_updated >= NOW() - INTERVAL 5 MINUTE
            ''')
            recent_completed = c.fetchone()[0]
            speed = recent_completed / 5 if recent_completed > 0 else 0
            
            print(f"{task_id}\t{task[1]}\t{progress_bar}\t{speed:.1f}\t\t{task[2]}")
    
    conn.close()

def create_progress_bar(progress, width=20):
    filled = int(width * progress)
    empty = width - filled
    bar = '=' * filled + '>' + ' ' * empty if filled < width else '=' * width
    percentage = int(progress * 100)
    return f'[{bar}] {percentage}%'
    
    conn.close()

def create_task(zip_path, name):
    if not os.path.exists(zip_path):
        print(f"错误：找不到文件 {zip_path}")
        return
    
    # 创建临时目录解压文件
    temp_dir = Path('temp_extract')
    temp_dir.mkdir(exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # 验证必要文件
        receptor_file = next(temp_dir.glob('**/receptor.pdbqt'), None)
        parameter_file = next(temp_dir.glob('**/parameter.txt'), None)
        ligand_files = list(temp_dir.glob('**/ligands/*.pdbqt'))
        
        if not (receptor_file and parameter_file and ligand_files):
            print("错误：ZIP文件缺少必要的文件（receptor.pdbqt、parameter.txt、ligands/ligand_*.pdbqt）")
            return
        
        # 将文件移动到任务目录
        task_dir = Path('tasks') / name
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建 ligands 子目录
        ligands_dir = task_dir / 'ligands'
        ligands_dir.mkdir(exist_ok=True)
        
        receptor_dest = task_dir / 'receptor.pdbqt'
        parameter_dest = task_dir / 'parameter.txt'
        
        receptor_file.rename(receptor_dest)
        parameter_file.rename(parameter_dest)
        
        # 创建数据库记录
        conn = get_db_connection()
        c = conn.cursor()
        
        # 解析参数文件
        params = {}
        with open(parameter_dest, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=')
                    params[key.strip()] = value.strip()
        
        # 插入主任务记录
        c.execute('''
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
        
        # 创建任务特定的配体表
        c.execute(f'''
            CREATE TABLE IF NOT EXISTS task_{name}_ligands (
                ligand_id VARCHAR(255) PRIMARY KEY,
                ligand_file VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                output_file VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 添加配体记录
        for ligand_file in ligand_files:
            # 直接使用文件名（不含扩展名）作为 ligand_id
            ligand_id = ligand_file.stem
            ligand_dest = ligands_dir / ligand_file.name
            ligand_file.rename(ligand_dest)
            
            c.execute(f'''
                INSERT INTO task_{name}_ligands (ligand_id, ligand_file)
                VALUES (%s, %s)
            ''', (ligand_id, ligand_file.name))
        
        conn.commit()
        conn.close()
        
        print(f"成功创建任务 {name}")
        
    except Exception as e:
        print(f"错误：{str(e)}")
    finally:
        # 清理临时目录
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)

def remove_task(task_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 检查任务是否存在
        c.execute('SELECT id FROM tasks WHERE id = %s', (task_id,))
        if not c.fetchone():
            print(f"错误：找不到任务 {task_id}")
            return
        
        # 删除任务记录
        c.execute('DELETE FROM tasks WHERE id = %s', (task_id,))
        
        # 删除任务的配体表
        c.execute(f'DROP TABLE IF EXISTS task_{task_id}_ligands')
        
        conn.commit()
        
        # 删除任务相关文件
        task_dir = Path('tasks') / task_id
        result_dir = Path('results') / task_id
        
        import shutil
        if task_dir.exists():
            shutil.rmtree(task_dir)
        if result_dir.exists():
            shutil.rmtree(result_dir)
            
        print(f"成功删除任务 {task_id}")
        
    except Exception as e:
        print(f"删除任务时出错：{str(e)}")
        conn.rollback()
    finally:
        conn.close()

def pause_task(task_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 检查任务是否存在
        c.execute('SELECT status FROM tasks WHERE id = %s', (task_id,))
        task = c.fetchone()
        if not task:
            print(f"错误：找不到任务 {task_id}")
            return
        
        current_status = task[0]
        new_status = 'paused' if current_status == 'pending' else 'pending'
        
        # 更新任务状态
        c.execute('UPDATE tasks SET status = %s WHERE id = %s', (new_status, task_id))
        conn.commit()
        
        action = '暂停' if new_status == 'paused' else '恢复'
        print(f"成功{action}任务 {task_id}")
        
    except Exception as e:
        print(f"更新任务状态时出错：{str(e)}")
        conn.rollback()
    finally:
        conn.close()

def set_server_password(password):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 生成密码哈希
        import bcrypt
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        
        # 清除旧的认证信息
        c.execute('DELETE FROM server_auth')
        
        # 插入新的认证信息
        c.execute('''
            INSERT INTO server_auth (password_hash)
            VALUES (%s)
        ''', (password_hash.decode('utf-8'),))
        
        conn.commit()
        print("服务器密码设置成功")
        
    except Exception as e:
        print(f"设置密码时出错：{str(e)}")
        conn.rollback()
    finally:
        conn.close()

def reset_node_heartbeats():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 删除并重新创建node_heartbeats表
    c.execute('DROP TABLE IF EXISTS node_heartbeats')
    c.execute('''
        CREATE TABLE IF NOT EXISTS node_heartbeats (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            client_addr VARCHAR(255) NOT NULL,
            cpu_usage FLOAT NOT NULL,
            last_heartbeat TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_client_addr (client_addr),
            INDEX idx_last_heartbeat (last_heartbeat)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("计算节点心跳表已重置")

def reset_processing_tasks():
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 获取所有任务
        c.execute('SELECT id FROM tasks')
        tasks = c.fetchall()
        
        for task in tasks:
            task_id = task[0]
            # 更新配体表中的处理中状态为待处理
            c.execute(f'''
                UPDATE task_{task_id}_ligands 
                SET status = 'pending', 
                    last_updated = CURRENT_TIMESTAMP 
                WHERE status = 'processing'
            ''')
            
            # 更新主任务表中的状态
            c.execute('''
                UPDATE tasks 
                SET status = 'pending', 
                    last_updated = CURRENT_TIMESTAMP 
                WHERE id = %s AND status = 'processing'
            ''', (task_id,))
        
        conn.commit()
        print("已将所有处理中的任务重置为待处理状态")
        
    except Exception as e:
        print(f"重置任务状态时出错：{str(e)}")
        conn.rollback()
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='分子对接任务管理工具')
    parser.add_argument('-ls', action='store_true', help='列出所有任务')
    parser.add_argument('-zip', help='要提交的任务ZIP文件路径')
    parser.add_argument('-name', help='任务名称')
    parser.add_argument('-rm', help='删除指定的任务')
    parser.add_argument('-pause', help='暂停/恢复指定的任务')
    parser.add_argument('-set-password', help='设置服务器密码')
    parser.add_argument('-reset-heartbeats', action='store_true', help='重置计算节点心跳表')
    parser.add_argument('-reset-processing', action='store_true', help='将所有处理中的任务重置为待处理状态')
    
    args = parser.parse_args()
    
    # 确保数据库和必要目录存在
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
    else:
        parser.print_help()

if __name__ == '__main__':
    main()