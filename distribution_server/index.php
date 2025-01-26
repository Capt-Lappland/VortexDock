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
        
        // 计算最近5分钟的处理速度
        $recent_completed = $conn->query("SELECT COUNT(*) as count FROM task_{$task_id}_ligands WHERE status = 'completed' AND last_updated >= NOW() - INTERVAL 5 MINUTE")->fetch_assoc()['count'];
        $speed = $recent_completed > 0 ? $recent_completed / 5 : 0; // 每分钟处理数量
        
        // 计算预计完成时间
        $remaining = $total - $completed;
        $estimated_minutes = $speed > 0 ? ceil($remaining / $speed) : null;
        
        $estimated_time = null;
        if ($estimated_minutes !== null) {
            $hours = floor($estimated_minutes / 60);
            $minutes = $estimated_minutes % 60;
            $estimated_time = ($hours > 0 ? $hours . '小时' : '') . ($minutes > 0 ? $minutes . '分钟' : '');
        }
        
        $data[] = [
            'id' => $task_id,
            'status' => $task['status'],
            'progress' => $progress,
            'total' => $total,
            'completed' => $completed,
            'created_at' => $task['created_at'],
            'estimated_time' => $estimated_time
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
                         AND last_updated >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                         GROUP BY DATE(last_updated)";
        
        // 每小时数据查询
        $hourly_query[] = "SELECT DATE_FORMAT(last_updated, '%Y-%m-%d %H:00') as hour,
                          COUNT(*) as task_completed
                          FROM task_{$task_id}_ligands
                          WHERE status = 'completed'
                          AND last_updated >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                          GROUP BY hour";
        
        // 每五分钟数据查询
        $minute_query[] = "SELECT 
                            DATE_FORMAT(last_updated, '%Y-%m-%d %H:%i') as minute,
                            COUNT(*) as task_completed
                          FROM task_{$task_id}_ligands
                          WHERE status = 'completed'
                          AND last_updated >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
                          GROUP BY FLOOR(UNIX_TIMESTAMP(last_updated) / 300) * 300
                          ORDER BY minute ASC";
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
                              ORDER BY minute ASC");
        while ($row = $result->fetch_assoc()) {
            $data['minute'][] = $row;
        }
    }
    
    return $data;
}

// 获取计算节点状态统计
function getNodeStats($conn) {
    $stats = [
        'total' => 0,
        'online' => 0,
        'offline' => 0,
        'avg_cpu_usage' => 0
    ];
    
    // 获取最近5分钟内有心跳的节点数量
    $result = $conn->query("SELECT COUNT(DISTINCT client_addr) as online_count FROM node_heartbeats WHERE last_heartbeat >= NOW() - INTERVAL 5 MINUTE");
    if ($result) {
        $stats['online'] = $result->fetch_assoc()['online_count'];
    }
    
    // 获取所有节点数量
    $result = $conn->query("SELECT COUNT(DISTINCT client_addr) as total_count FROM node_heartbeats");
    if ($result) {
        $stats['total'] = $result->fetch_assoc()['total_count'];
        $stats['offline'] = $stats['total'] - $stats['online'];
    }
    
    // 获取平均CPU使用率
    $result = $conn->query("SELECT AVG(cpu_usage) as avg_cpu FROM node_heartbeats WHERE last_heartbeat >= NOW() - INTERVAL 5 MINUTE");
    if ($result) {
        $row = $result->fetch_assoc();
        $stats['avg_cpu_usage'] = round($row['avg_cpu'] ?? 0, 1);
    }
    
    return $stats;
}

// 获取任务队列状态分布
function getTaskQueueStats($conn) {
    $stats = [
        'pending' => 0,
        'processing' => 0,
        'completed' => 0,
        'failed' => 0
    ];
    
    // 获取所有任务的状态统计
    $tasks_result = $conn->query('SELECT id FROM tasks');
    if ($tasks_result) {
        while ($task = $tasks_result->fetch_assoc()) {
            $task_id = $task['id'];
            
            // 统计每个任务中各状态的配体数量
            $status_query = "SELECT status, COUNT(*) as count FROM task_{$task_id}_ligands GROUP BY status";
            $status_result = $conn->query($status_query);
            
            if ($status_result) {
                while ($row = $status_result->fetch_assoc()) {
                    $status = $row['status'];
                    if (isset($stats[$status])) {
                        $stats[$status] += (int)$row['count'];
                    }
                }
            }
        }
    }
    
    return $stats;
}

// 获取任务处理性能指标
function getTaskPerformanceStats($conn) {
    $stats = [
        'avg_processing_time' => 0,
        'success_rate' => 0,
        'throughput' => []
    ];
    
    // 获取所有任务ID
    $tasks_result = $conn->query('SELECT id FROM tasks');
    if (!$tasks_result || $tasks_result->num_rows == 0) {
        return $stats;
    }
    
    // 构建UNION ALL查询
    $avg_time_queries = [];
    $success_rate_queries = [];
    $throughput_queries = [];
    
    while ($task = $tasks_result->fetch_assoc()) {
        $task_id = $task['id'];
        
        // 平均处理时间查询（仅计算已完成的任务）
        $avg_time_queries[] = "SELECT TIMESTAMPDIFF(MINUTE, created_at, last_updated) as process_time FROM task_{$task_id}_ligands WHERE status = 'completed'";
        
        // 成功率查询（所有状态的任务）
        $success_rate_queries[] = "SELECT status FROM task_{$task_id}_ligands";
        
        // 吞吐量查询（按10分钟间隔统计最近24小时）
        $throughput_queries[] = "SELECT DATE_FORMAT(last_updated, '%Y-%m-%d %H:%i:00') as time_slot, COUNT(*) as count FROM task_{$task_id}_ligands WHERE status = 'completed' AND last_updated >= NOW() - INTERVAL 24 HOUR GROUP BY time_slot";
    }
    
    // 计算平均处理时间
    if (!empty($avg_time_queries)) {
        $avg_time_query = "SELECT AVG(process_time) as avg_time FROM (" . implode(" UNION ALL ", $avg_time_queries) . ") as completed_tasks WHERE process_time > 0";
        $result = $conn->query($avg_time_query);
        if ($result) {
            $row = $result->fetch_assoc();
            $stats['avg_processing_time'] = round($row['avg_time'] ?? 0, 1);
        }
    }
    
    // 计算成功率
    if (!empty($success_rate_queries)) {
        $success_rate_query = "SELECT 
            COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as success_rate 
            FROM (" . implode(" UNION ALL ", $success_rate_queries) . ") as all_tasks";
        $result = $conn->query($success_rate_query);
        if ($result) {
            $row = $result->fetch_assoc();
            $stats['success_rate'] = round($row['success_rate'] ?? 0, 1);
        }
    }
    
    // 计算吞吐量趋势（每30分钟一个数据点，最近24小时）
    if (!empty($throughput_queries)) {
        $throughput_query = "SELECT 
            DATE_FORMAT(DATE_SUB(time_slot, INTERVAL MINUTE(time_slot) % 30 MINUTE), '%Y-%m-%d %H:%i:00') as time_slot,
            SUM(count) as total_count 
            FROM (" . implode(" UNION ALL ", $throughput_queries) . 
            ") as hourly_stats 
            WHERE time_slot >= NOW() - INTERVAL 24 HOUR
            GROUP BY DATE_FORMAT(DATE_SUB(time_slot, INTERVAL MINUTE(time_slot) % 30 MINUTE), '%Y-%m-%d %H:%i:00')
            ORDER BY time_slot";
        $result = $conn->query($throughput_query);
        if ($result) {
            while ($row = $result->fetch_assoc()) {
                $stats['throughput'][] = [
                    'time' => $row['time_slot'],
                    'count' => (int)$row['total_count']
                ];
            }
        }
    }
    
    return $stats;
}

$tasksProgress = getTasksProgress($conn);
$nodePerformance = getNodePerformance($conn);
$nodeStats = getNodeStats($conn);
$queueStats = getTaskQueueStats($conn);
$performanceStats = getTaskPerformanceStats($conn);

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
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-radius: 8px;
            border: none;
        }
        .progress {
            height: 25px;
            border-radius: 6px;
            overflow: hidden;
        }
        .progress-bar {
            transition: width 0.6s ease;
            background: linear-gradient(45deg, #2196F3, #00BCD4);
        }
        .chart-container {
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.05);
            height: 400px;
            margin-bottom: 20px;
        }
        .stats-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stats-value {
            font-size: 24px;
            font-weight: bold;
            color: #2196F3;
        }
        .stats-label {
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body class="bg-light">
    <div class="container py-4">
        <h1 class="mb-4 text-primary">VortexDock 数据监控</h1>
        
        <!-- 系统状态概览 -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?php echo $nodeStats['online']; ?>/<?php echo $nodeStats['total']; ?></div>
                    <div class="stats-label">在线节点数</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?php echo $nodeStats['avg_cpu_usage']; ?>%</div>
                    <div class="stats-label">平均CPU使用率</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?php echo $performanceStats['avg_processing_time']; ?>分钟</div>
                    <div class="stats-label">平均处理时间</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?php echo $performanceStats['success_rate']; ?>%</div>
                    <div class="stats-label">任务成功率</div>
                </div>
            </div>
        </div>

        <!-- 任务进度卡片 -->
        <div class="row">
            <div class="col-12 mb-4">
                <div class="card dashboard-card">
                    <div class="card-header bg-white">
                        <h5 class="card-title mb-0 text-primary">任务进度</h5>
                    </div>
                    <div class="card-body">
                        <?php foreach ($tasksProgress as $task): ?>
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="fw-bold">任务 <?php echo htmlspecialchars($task['id']); ?></span>
                                    <div class="text-end">
                                        <span class="text-muted"><?php echo $task['completed']; ?>/<?php echo $task['total']; ?></span>
                                        <?php if ($task['estimated_time']): ?>
                                            <span class="ms-2 text-info">预计<?php echo $task['estimated_time']; ?>后完成</span>
                                        <?php endif; ?>
                                    </div>
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

            <!-- 任务队列状态分布 -->
            <div class="col-md-6 mb-4">
                <div class="card dashboard-card">
                    <div class="card-header bg-white">
                        <h5 class="card-title mb-0 text-primary">任务队列状态分布</h5>
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="queueStatusChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 系统吞吐量趋势 -->
            <div class="col-md-6 mb-4">
                <div class="card dashboard-card">
                    <div class="card-header bg-white">
                        <h5 class="card-title mb-0 text-primary">系统吞吐量趋势</h5>
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="throughputChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 计算节点性能 -->
            <div class="col-12">
                <div class="card dashboard-card">
                    <div class="card-header bg-white">
                        <h5 class="card-title mb-0 text-primary">计算节点性能</h5>
                    </div>
                    <div class="card-body">
                        <div class="row g-4">
                            <div class="col-12 col-lg-4">
                                <div class="chart-container">
                                    <canvas id="dailyPerformanceChart"></canvas>
                                </div>
                            </div>
                            <div class="col-12 col-lg-4">
                                <div class="chart-container">
                                    <canvas id="hourlyPerformanceChart"></canvas>
                                </div>
                            </div>
                            <div class="col-12 col-lg-4">
                                <div class="chart-container">
                                    <canvas id="minutePerformanceChart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Chart.js 全局配置
        Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial';
        Chart.defaults.font.size = 12;
        Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        Chart.defaults.plugins.tooltip.padding = 10;
        Chart.defaults.plugins.tooltip.cornerRadius = 6;
        
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            aspectRatio: 1.5,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    titleFont: {
                        size: 14
                    },
                    bodyFont: {
                        size: 13
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)',
                        drawBorder: false
                    },
                    ticks: {
                        padding: 10,
                        font: {
                            size: 12
                        },
                        callback: function(value) {
                            return value.toLocaleString();
                        }
                    },
                    title: {
                        display: true,
                        text: '完成任务数',
                        font: {
                            size: 13
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        padding: 10,
                        font: {
                            size: 11
                        },
                        callback: function(value, index, values) {
                            const label = this.getLabelForValue(value);
                            if (label.includes(' ')) {
                                const [date, time] = label.split(' ');
                                return [date, time];
                            }
                            return label;
                        }
                    }
                }
            },
            elements: {
                line: {
                    tension: 0.4,
                    borderWidth: 2
                },
                point: {
                    radius: 3,
                    hitRadius: 10,
                    hoverRadius: 5
                }
            }
        };

        // 任务队列状态分布图
        const queueStatusData = <?php echo json_encode($queueStats); ?>;
        new Chart(document.getElementById('queueStatusChart'), {
            type: 'pie',
            data: {
                labels: ['待处理', '处理中', '已完成', '失败'],
                datasets: [{
                    data: [
                        queueStatusData.pending,
                        queueStatusData.processing,
                        queueStatusData.completed,
                        queueStatusData.failed
                    ],
                    backgroundColor: [
                        '#2196F3',
                        '#FFC107',
                        '#4CAF50',
                        '#F44336'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right'
                    }
                }
            }
        });

        // 系统吞吐量趋势图
        const throughputData = <?php echo json_encode($performanceStats['throughput']); ?>;
        if (throughputData && throughputData.length > 0) {
            new Chart(document.getElementById('throughputChart'), {
                type: 'line',
                data: {
                    labels: throughputData.map(item => item.time),
                    datasets: [{
                        label: '系统吞吐量',
                        data: throughputData.map(item => item.count),
                        borderColor: 'rgba(75, 192, 192, 1)',
                        backgroundColor: (context) => {
                            const chart = context.chart;
                            const {ctx, chartArea} = chart;
                            if (!chartArea) return null;
                            const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
                            gradient.addColorStop(0, 'rgba(75, 192, 192, 0.1)');
                            gradient.addColorStop(1, 'rgba(75, 192, 192, 0.4)');
                            return gradient;
                        },
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        pointBackgroundColor: 'rgba(75, 192, 192, 1)',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointHoverRadius: 5,
                        pointHoverBackgroundColor: 'rgba(75, 192, 192, 1)',
                        pointHoverBorderColor: '#fff',
                        pointHoverBorderWidth: 2
                    }]
                },
                options: {
                    ...chartOptions,
                    plugins: {
                        ...chartOptions.plugins,
                        legend: {
                            display: true,
                            position: 'top',
                            labels: {
                                font: {
                                    size: 14,
                                    weight: 'bold'
                                },
                                padding: 20,
                                usePointStyle: true
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleFont: {
                                size: 14,
                                weight: 'bold'
                            },
                            bodyFont: {
                                size: 13
                            },
                            padding: 12,
                            displayColors: false
                        }
                    },
                    scales: {
                        y: {
                            grid: {
                                color: 'rgba(0, 0, 0, 0.05)',
                                drawBorder: false
                            },
                            ticks: {
                                padding: 10,
                                font: {
                                    size: 12
                                },
                                callback: function(value) {
                                    return value;
                                }
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45,
                                padding: 10,
                                font: {
                                    size: 11
                                },
                                callback: function(value, index, values) {
                                    const label = this.getLabelForValue(value);
                                    const time = new Date(label);
                                    return time.getHours() + ':' + String(time.getMinutes()).padStart(2, '0');
                                }
                            }
                        }
                    }
                }
            });
        }

        // 计算节点性能图表
        const dailyData = <?php echo json_encode($nodePerformance['daily']); ?>;
        if (dailyData && dailyData.length > 0) {
            new Chart(document.getElementById('dailyPerformanceChart'), {
                type: 'bar',
                data: {
                    labels: dailyData.map(item => item.date),
                    datasets: [{
                        label: '每日完成任务数',
                        data: dailyData.map(item => item.completed_tasks),
                        backgroundColor: '#2196F3'
                    }]
                },
                options: chartOptions
            });
        }

        const hourlyData = <?php echo json_encode($nodePerformance['hourly']); ?>;
        if (hourlyData && hourlyData.length > 0) {
            new Chart(document.getElementById('hourlyPerformanceChart'), {
                type: 'line',
                data: {
                    labels: hourlyData.map(item => item.hour),
                    datasets: [{
                        label: '每小时完成任务数',
                        data: hourlyData.map(item => item.completed_tasks),
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        fill: true
                    }]
                },
                options: chartOptions
            });
        }

        const minuteData = <?php echo json_encode($nodePerformance['minute']); ?>;
        if (minuteData && minuteData.length > 0) {
            new Chart(document.getElementById('minutePerformanceChart'), {
                type: 'line',
                data: {
                    labels: minuteData.map(item => item.minute),
                    datasets: [{
                        label: '每5分钟完成任务数',
                        data: minuteData.map(item => item.completed_tasks),
                        borderColor: '#FF9800',
                        backgroundColor: 'rgba(255, 152, 0, 0.1)',
                        fill: true
                    }]
                },
                options: chartOptions
            });
        }
    </script>
</body>
</html>