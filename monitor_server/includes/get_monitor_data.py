# 文件：app.py (新增路由部分)
from flask import jsonify
from includes.db_connect import get_db_connection
from includes.data_functions import (
    get_tasks_progress,
    get_node_performance,
    get_node_stats,
    get_task_queue_stats,
    get_task_performance_stats,
    get_node_cpu_trend
)

@app.route('/get_monitor_data')
def get_monitor_data():
    """监控数据接口"""
    try:
        conn = get_db_connection()
        
        data = {
            "tasksProgress": get_tasks_progress(conn),
            "nodePerformance": get_node_performance(conn),
            "nodeStats": get_node_stats(conn),
            "queueStats": get_task_queue_stats(conn),
            "performanceStats": get_task_performance_stats(conn),
            "nodeCpuTrend": get_node_cpu_trend(conn)
        }
        
        conn.close()
        return jsonify(data)
    
    except Exception as e:
        app.logger.error(f"数据接口错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

# 文件：includes/data_functions.py (示例函数实现)
def get_node_stats(conn):
    """获取节点统计信息"""
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                COUNT(*) AS total,
                SUM(status = 'online') AS online,
                ROUND(AVG(cpu_usage), 1) AS avg_cpu_usage
            FROM nodes
        """)
        return cursor.fetchone()
    finally:
        cursor.close()

def get_tasks_progress(conn):
    """获取任务进度"""
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                id,
                completed,
                total,
                ROUND((completed/total)*100) AS progress,
                estimated_time
            FROM tasks
            WHERE status = 'processing'
        """)
        return cursor.fetchall()
    finally:
        cursor.close()

# 其他函数实现类似模式