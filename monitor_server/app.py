from flask import Flask, render_template, jsonify
from includes.db_connect import get_db_connection
from includes.data_functions import (
    get_tasks_progress,
    get_node_performance,
    get_node_stats,
    get_task_queue_stats,
    get_task_performance_stats,
    get_node_cpu_trend
)

app = Flask(__name__)

@app.route('/')
def index():
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
    return render_template('index.html', **data)

@app.route('/get_monitor_data')
def get_monitor_data():
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

if __name__ == '__main__':
    app.run(debug=True, port=9000)