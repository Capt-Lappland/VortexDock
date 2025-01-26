<?php
require_once('../config.php');

// 创建数据库连接
$conn = new mysqli($DB_CONFIG['host'], $DB_CONFIG['user'], $DB_CONFIG['password'], $DB_CONFIG['database']);
if ($conn->connect_error) {
    die("数据库连接失败: " . $conn->connect_error);
}

// 获取所有任务的进度数据
function getTasksProgress($conn) {
    $data = [];
    $result = $conn->query('SELECT id, status, created_at FROM tasks');
    
    while ($task = $result->fetch_assoc()) {
        $task_id = $task['id'];
        // 获取该任务的配体总数和已完成数
        $total = $conn->query("SELECT COUNT(*) as count FROM task_{$task_id}_ligands")->fetch_assoc()['count'];
        $completed = $conn->query("SELECT COUNT(*) as count FROM task_{$task_id}_ligands WHERE status = 'completed'")->fetch_assoc()['count'];
        $progress = $total > 0 ? round(($completed / $total) * 100, 2) : 0;
        
        $data[] = [
            'id' => $task_id,
            'status' => $task['status'],
            'progress' => $progress,
            'total' => $total,
            'completed' => $completed,
            'created_at' => $task['created_at']
        ];
    }
    
    return $data;
}

// 获取计算节点性能数据
function getNodePerformance($conn) {
    $data = ['daily' => [], 'hourly' => [], 'minute' => []];
    
    // 获取所有任务ID
    $tasks_result = $conn->query('SELECT id FROM tasks');
    if (!$tasks_result || $tasks_result->num_rows == 0) {
        return $data;
    }
    
    // 构建UNION查询
    $daily_query = [];
    $hourly_query = [];
    $minute_query = [];
    
    while ($task = $tasks_result->fetch_assoc()) {
        $task_id = $task['id'];
        
        // 每日数据查询
        $daily_query[] = "SELECT DATE(last_updated) as date, COUNT(*) as task_completed 
                         FROM task_{$task_id}_ligands 
                         WHERE status = 'completed' 
                         GROUP BY DATE(last_updated)";
        
        // 每小时数据查询
        $hourly_query[] = "SELECT DATE_FORMAT(last_updated, '%Y-%m-%d %H:00') as hour,
                          COUNT(*) as task_completed
                          FROM task_{$task_id}_ligands
                          WHERE status = 'completed'
                          AND last_updated >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                          GROUP BY hour";
        
        // 每分钟数据查询
        $minute_query[] = "SELECT DATE_FORMAT(last_updated, '%Y-%m-%d %H:%i') as minute,
                          COUNT(*) as task_completed
                          FROM task_{$task_id}_ligands
                          WHERE status = 'completed'
                          AND last_updated >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
                          GROUP BY minute";
    }
    
    // 执行合并查询
    if (!empty($daily_query)) {
        $daily_union = implode(' UNION ALL ', $daily_query);
        $result = $conn->query("SELECT date, SUM(task_completed) as completed_tasks 
                              FROM ($daily_union) as daily_data 
                              GROUP BY date 
                              ORDER BY date DESC LIMIT 7");
        while ($row = $result->fetch_assoc()) {
            $data['daily'][] = $row;
        }
    }
    
    if (!empty($hourly_query)) {
        $hourly_union = implode(' UNION ALL ', $hourly_query);
        $result = $conn->query("SELECT hour, SUM(task_completed) as completed_tasks 
                              FROM ($hourly_union) as hourly_data 
                              GROUP BY hour 
                              ORDER BY hour ASC");
        while ($row = $result->fetch_assoc()) {
            $data['hourly'][] = $row;
        }
    }
    
    if (!empty($minute_query)) {
        $minute_union = implode(' UNION ALL ', $minute_query);
        $result = $conn->query("SELECT minute, SUM(task_completed) as completed_tasks 
                              FROM ($minute_union) as minute_data 
                              GROUP BY minute 
                              ORDER BY minute DESC");
        while ($row = $result->fetch_assoc()) {
            $data['minute'][] = $row;
        }
    }
    
    return $data;
}

$tasksProgress = getTasksProgress($conn);
$nodePerformance = getNodePerformance($conn);

$conn->close();
?>

<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VortexDock - 数据监控</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .dashboard-card {
            margin-bottom: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        .progress {
            height: 25px;
        }
    </style>
</head>
<body class="bg-light">
    <div class="container py-4">
        <h1 class="mb-4">VortexDock 数据监控</h1>
        
        <div class="row">
            <!-- 任务进度卡片 -->
            <div class="col-12 mb-4">
                <div class="card dashboard-card">
                    <div class="card-header">
                        <h5 class="card-title mb-0">任务进度</h5>
                    </div>
                    <div class="card-body">
                        <?php foreach ($tasksProgress as $task): ?>
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span>任务 <?php echo htmlspecialchars($task['id']); ?></span>
                                    <span><?php echo $task['completed']; ?>/<?php echo $task['total']; ?></span>
                                </div>
                                <div class="progress">
                                    <div class="progress-bar" role="progressbar" 
                                         style="width: <?php echo $task['progress']; ?>%"
                                         aria-valuenow="<?php echo $task['progress']; ?>" 
                                         aria-valuemin="0" aria-valuemax="100">
                                        <?php echo $task['progress']; ?>%
                                    </div>
                                </div>
                            </div>
                        <?php endforeach; ?>
                    </div>
                </div>
            </div>
            
            <!-- 性能图表卡片 -->
            <div class="col-12">
                <div class="card dashboard-card">
                    <div class="card-header">
                        <h5 class="card-title mb-0">计算节点性能</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-12 mb-4">
                                <canvas id="dailyPerformanceChart"></canvas>
                            </div>
                            <div class="col-12 mb-4">
                                <canvas id="hourlyPerformanceChart"></canvas>
                            </div>
                            <div class="col-12">
                                <canvas id="minutePerformanceChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 性能数据
        const performanceData = <?php echo json_encode($nodePerformance); ?>;

        // 每日性能图表
        const dailyDates = performanceData.daily.map(item => item.date);
        const dailyCompletedTasks = performanceData.daily.map(item => item.completed_tasks);
        new Chart(document.getElementById('dailyPerformanceChart'), {
            type: 'line',
            data: {
                labels: dailyDates,
                datasets: [{
                    label: '每日完成任务数',
                    data: dailyCompletedTasks,
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: '最近7天性能趋势'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: '完成任务数'
                        }
                    }
                }
            }
        });

        // 每小时性能图表
        const hourlyTimes = performanceData.hourly.map(item => item.hour);
        const hourlyCompletedTasks = performanceData.hourly.map(item => item.completed_tasks);
        new Chart(document.getElementById('hourlyPerformanceChart'), {
            type: 'line',
            data: {
                labels: hourlyTimes,
                datasets: [{
                    label: '每小时完成任务数',
                    data: hourlyCompletedTasks,
                    borderColor: 'rgb(255, 99, 132)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: '最近24小时性能趋势'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: '完成任务数'
                        }
                    }
                }
            }
        });

        // 每分钟性能图表
        const minuteTimes = performanceData.minute.map(item => item.minute);
        const minuteCompletedTasks = performanceData.minute.map(item => item.completed_tasks);
        new Chart(document.getElementById('minutePerformanceChart'), {
            type: 'line',
            data: {
                labels: minuteTimes,
                datasets: [{
                    label: '每分钟完成任务数',
                    data: minuteCompletedTasks,
                    borderColor: 'rgb(54, 162, 235)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: '最近1小时性能趋势'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: '完成任务数'
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>