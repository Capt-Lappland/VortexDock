# includes/data_functions.py
from datetime import datetime, timedelta
from mysql.connector import Error
from typing import Dict, List, Union
from math import ceil

def get_tasks_progress(conn) -> List[Dict]:
    """获取所有任务进度数据"""
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, status, created_at FROM tasks ORDER BY created_at DESC")
        tasks = cursor.fetchall()
        result = []

        for task in tasks:
            task_id = task['id']
            task_data = {
                'id': task_id,
                'status': task['status'],
                'created_at': task['created_at'].isoformat() if task['created_at'] else None
            }

            # 获取总任务数
            cursor.execute(f"SELECT COUNT(*) as count FROM task_{task_id}_ligands")
            total = cursor.fetchone()['count']

            # 获取已完成数
            cursor.execute(f"SELECT COUNT(*) as count FROM task_{task_id}_ligands WHERE status = 'completed'")
            completed = cursor.fetchone()['count']

            # 计算进度
            progress = round((completed / total) * 100, 2) if total > 0 else 0

            # 计算处理速度
            five_min_ago = datetime.now() - timedelta(minutes=5)
            cursor.execute(f"""
                SELECT COUNT(*) as count 
                FROM task_{task_id}_ligands 
                WHERE status = 'completed' 
                AND last_updated >= %s
            """, (five_min_ago,))
            recent_completed = cursor.fetchone()['count']
            speed = recent_completed / 5  # 每分钟处理数量

            # 预估剩余时间
            remaining = total - completed
            estimated_minutes = ceil(remaining / speed) if speed > 0 else None
            estimated_time = format_estimated_time(estimated_minutes)

            task_data.update({
                'progress': progress,
                'total': total,
                'completed': completed,
                'estimated_time': estimated_time
            })
            result.append(task_data)

        return result

    except Error as e:
        print(f"获取任务进度错误: {str(e)}")
        return []
    finally:
        cursor.close()

def get_node_performance(conn) -> Dict[str, List]:
    """获取节点性能数据"""
    try:
        cursor = conn.cursor(dictionary=True)
        data = {'daily': [], 'hourly': [], 'minute': []}
        
        cursor.execute("SELECT id FROM tasks")
        tasks = cursor.fetchall()
        task_ids = [t['id'] for t in tasks]

        # 生成各时间粒度查询
        daily_queries = []
        hourly_queries = []
        minute_queries = []

        for task_id in task_ids:
            daily_queries.append(f"""
                SELECT DATE_FORMAT(last_updated, '%m-%d') as date, COUNT(*) as task_completed 
                FROM task_{task_id}_ligands 
                WHERE status = 'completed' 
                AND last_updated >= NOW() - INTERVAL 7 DAY
                GROUP BY DATE(last_updated)
            """)

            hourly_queries.append(f"""
                SELECT DATE_FORMAT(last_updated, '%H:00') as hour,
                       COUNT(*) as task_completed
                FROM task_{task_id}_ligands
                WHERE status = 'completed'
                AND last_updated >= NOW() - INTERVAL 24 HOUR
                GROUP BY hour
            """)

            minute_queries.append(f"""
                SELECT DATE_FORMAT(last_updated, '%H:%i') as minute,
                       COUNT(*) as task_completed
                FROM task_{task_id}_ligands
                WHERE status = 'completed'
                AND last_updated >= NOW() - INTERVAL 1 HOUR
                GROUP BY FLOOR(UNIX_TIMESTAMP(last_updated) / 300)
            """)

        # 合并查询
        if daily_queries:
            union_query = " UNION ALL ".join(daily_queries)
            cursor.execute(f"""
                SELECT date, SUM(task_completed) as completed_tasks 
                FROM ({union_query}) as daily_data 
                GROUP BY date 
                ORDER BY date DESC LIMIT 7
            """)
            data['daily'] = cursor.fetchall()

        if hourly_queries:
            union_query = " UNION ALL ".join(hourly_queries)
            cursor.execute(f"""
                SELECT hour, SUM(task_completed) as completed_tasks 
                FROM ({union_query}) as hourly_data 
                GROUP BY hour 
                ORDER BY hour ASC
            """)
            data['hourly'] = cursor.fetchall()

        if minute_queries:
            union_query = " UNION ALL ".join(minute_queries)
            cursor.execute(f"""
                SELECT minute, SUM(task_completed) as completed_tasks 
                FROM ({union_query}) as minute_data 
                GROUP BY minute 
                ORDER BY minute ASC
            """)
            data['minute'] = cursor.fetchall()

        return data

    except Error as e:
        print(f"获取节点性能错误: {str(e)}")
        return {'daily': [], 'hourly': [], 'minute': []}
    finally:
        cursor.close()

def get_node_stats(conn) -> Dict[str, Union[int, float]]:
    """获取节点状态统计"""
    try:
        cursor = conn.cursor(dictionary=True)
        stats = {'total': 0, 'online': 0, 'offline': 0, 'avg_cpu_usage': 0.0}

        # 在线节点数
        five_min_ago = datetime.now() - timedelta(minutes=5)
        cursor.execute("""
            SELECT COUNT(DISTINCT client_addr) as online_count 
            FROM node_heartbeats 
            WHERE last_heartbeat >= %s
        """, (five_min_ago,))
        stats['online'] = cursor.fetchone()['online_count']

        # 总节点数
        cursor.execute("SELECT COUNT(DISTINCT client_addr) as total_count FROM node_heartbeats")
        result = cursor.fetchone()
        if result:
            stats['total'] = result['total_count']
            stats['offline'] = stats['total'] - stats['online']

        # 平均CPU使用率
        cursor.execute("""
            SELECT AVG(cpu_usage) as avg_cpu 
            FROM node_heartbeats 
            WHERE last_heartbeat >= %s
        """, (five_min_ago,))
        avg_cpu = cursor.fetchone()['avg_cpu']
        stats['avg_cpu_usage'] = round(avg_cpu, 1) if avg_cpu else 0.0

        return stats

    except Error as e:
        print(f"获取节点统计错误: {str(e)}")
        return stats
    finally:
        cursor.close()

def get_task_queue_stats(conn) -> Dict[str, int]:
    """获取任务队列状态分布"""
    try:
        cursor = conn.cursor(dictionary=True)
        stats = {'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0}
        
        cursor.execute("SELECT id FROM tasks")
        tasks = cursor.fetchall()

        for task in tasks:
            task_id = task['id']
            cursor.execute(f"""
                SELECT status, COUNT(*) as count 
                FROM task_{task_id}_ligands 
                GROUP BY status
            """)
            
            for row in cursor:
                status = row['status']
                if status in stats:
                    stats[status] += row['count']

        return stats

    except Error as e:
        print(f"获取队列统计错误: {str(e)}")
        return stats
    finally:
        cursor.close()

def get_task_performance_stats(conn) -> Dict:
    """获取任务性能指标"""
    try:
        cursor = conn.cursor(dictionary=True)
        stats = {'avg_processing_time': 0.0, 'success_rate': 0.0, 'throughput': []}
        
        cursor.execute("SELECT id FROM tasks")
        tasks = cursor.fetchall()
        task_ids = [t['id'] for t in tasks]

        # 计算平均处理时间
        avg_queries = []
        for task_id in task_ids:
            avg_queries.append(f"""
                SELECT TIMESTAMPDIFF(MINUTE, created_at, last_updated) as process_time 
                FROM task_{task_id}_ligands 
                WHERE status = 'completed'
            """)
        
        if avg_queries:
            union_query = " UNION ALL ".join(avg_queries)
            cursor.execute(f"""
                SELECT AVG(process_time) as avg_time 
                FROM ({union_query}) as tasks 
                WHERE process_time > 0
            """)
            avg_time = cursor.fetchone()['avg_time']
            stats['avg_processing_time'] = round(avg_time, 1) if avg_time else 0.0

        # 计算成功率
        success_queries = []
        for task_id in task_ids:
            success_queries.append(f"SELECT status FROM task_{task_id}_ligands")
        
        if success_queries:
            union_query = " UNION ALL ".join(success_queries)
            cursor.execute(f"""
                SELECT 
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0) as success_rate 
                FROM ({union_query}) as all_tasks
            """)
            success_rate = cursor.fetchone()['success_rate']
            stats['success_rate'] = round(success_rate, 1) if success_rate else 0.0

        # 计算吞吐量
        throughput_queries = []
        for task_id in task_ids:
            throughput_queries.append(f"""
                SELECT 
                    DATE_FORMAT(last_updated, '%Y-%m-%d %H:%i:00') as time_slot,
                    COUNT(*) as count
                FROM task_{task_id}_ligands
                WHERE status = 'completed'
                AND last_updated >= NOW() - INTERVAL 1 HOUR
                GROUP BY FLOOR(UNIX_TIMESTAMP(last_updated) / 60)
            """)
        
        if throughput_queries:
            union_query = " UNION ALL ".join(throughput_queries)
            cursor.execute(f"""
                SELECT 
                    time_slot,
                    SUM(count) as total_count
                FROM ({union_query}) as stats
                GROUP BY time_slot
                ORDER BY time_slot ASC
            """)
            stats['throughput'] = cursor.fetchall()

        return stats

    except Error as e:
        print(f"获取性能统计错误: {str(e)}")
        return stats
    finally:
        cursor.close()

def get_node_cpu_trend(conn) -> List[Dict]:
    """获取节点CPU使用率趋势"""
    try:
        cursor = conn.cursor(dictionary=True)
        data = []
        
        one_hour_ago = datetime.now() - timedelta(hours=1)
        cursor.execute("""
            SELECT 
                client_addr,
                DATE_FORMAT(last_heartbeat, '%Y-%m-%d %H:%i') as minute,
                cpu_usage
            FROM node_heartbeats
            WHERE last_heartbeat >= %s
            ORDER BY last_heartbeat ASC
        """, (one_hour_ago,))

        node_data = {}
        for row in cursor:
            node = row['client_addr']
            if node not in node_data:
                node_data[node] = {}
            node_data[node][row['minute']] = row['cpu_usage']

        for node, points in node_data.items():
            data.append({
                'node': node,
                'data': points
            })

        return data

    except Error as e:
        print(f"获取CPU趋势错误: {str(e)}")
        return []
    finally:
        cursor.close()

def format_estimated_time(minutes: int) -> str:
    """格式化预估时间"""
    if not minutes:
        return None
    hours, mins = divmod(minutes, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if mins > 0:
        parts.append(f"{mins}分钟")
    return "".join(parts) if parts else None