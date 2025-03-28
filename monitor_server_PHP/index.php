<?php
// monitor/index.php
require_once __DIR__ . '/includes/db_connect.php';
require_once __DIR__ . '/includes/data_functions.php';

// Retrieve all monitoring data
$tasksProgress = getTasksProgress($conn);
$nodePerformance = getNodePerformance($conn);
$nodeStats = getNodeStats($conn);
$queueStats = getTaskQueueStats($conn);
$performanceStats = getTaskPerformanceStats($conn);
$nodeCpuTrend = getNodeCpuTrend($conn);

$conn->close();
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VortexDock - Data Monitoring</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="css/styles.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container py-4">
        <h1 class="mb-4 text-primary">VortexDock Data Monitoring</h1>
        
        <!-- System Status Overview -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?= $nodeStats['online'] ?>/<?= $nodeStats['total'] ?></div>
                    <div class="stats-label">Online Nodes</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?= $nodeStats['avg_cpu_usage'] ?>%</div>
                    <div class="stats-label">Average CPU Usage</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?= $performanceStats['avg_processing_time'] ?> minutes</div>
                    <div class="stats-label">Average Processing Time</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?= $performanceStats['success_rate'] ?>%</div>
                    <div class="stats-label">Task Success Rate</div>
                </div>
            </div>
        </div>

        <!-- Task Progress Cards -->
        <div class="row">
            <div class="col-12 mb-4">
                <div class="card dashboard-card">
                    <div class="card-header bg-white">
                        <h5 class="card-title mb-0 text-primary">Task Progress</h5>
                    </div>
                    <div class="card-body">
                        <?php foreach ($tasksProgress as $task): ?>
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="fw-bold">Task <?= htmlspecialchars($task['id']) ?></span>
                                    <div class="text-end">
                                        <span class="text-muted"><?= $task['completed'] ?>/<?= $task['total'] ?></span>
                                        <?php if ($task['estimated_time']): ?>
                                            <span class="ms-2 text-info">Estimated completion in <?= $task['estimated_time'] ?></span>
                                        <?php endif; ?>
                                    </div>
                                </div>
                                <div class="progress">
                                    <div class="progress-bar" role="progressbar" 
                                         style="width: <?= $task['progress'] ?>%"
                                         aria-valuenow="<?= $task['progress'] ?>" 
                                         aria-valuemin="0" aria-valuemax="100">
                                        <?= $task['progress'] ?>%
                                    </div>
                                </div>
                            </div>
                        <?php endforeach; ?>
                    </div>
                </div>
            </div>

            <!-- Task Queue Status Distribution -->
            <div class="col-md-6 mb-4">
                <div class="card dashboard-card">
                    <div class="card-header bg-white">
                        <h5 class="card-title mb-0 text-primary">Task Queue Status Distribution</h5>
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="queueStatusChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <!-- System Throughput Trend -->
            <div class="col-md-6 mb-4">
                <div class="card dashboard-card">
                    <div class="card-header bg-white">
                        <h5 class="card-title mb-0 text-primary">System Throughput Trend</h5>
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="throughputChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Compute Node Performance -->
            <div class="col-12">
                <div class="card dashboard-card">
                    <div class="card-header bg-white">
                        <h5 class="card-title mb-0 text-primary">Compute Node Performance</h5>
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

            <!-- Node CPU Usage Trend -->
            <div class="col-12">
                <div class="card dashboard-card">
                    <div class="card-header bg-white">
                        <h5 class="card-title mb-0 text-primary">Node CPU Usage Trend</h5>
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="nodeCpuTrendChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Data Storage Element -->
    <div id="chart-data" 
         data-queue-status='<?= htmlspecialchars(json_encode($queueStats), ENT_QUOTES, 'UTF-8') ?>'
         data-throughput='<?= htmlspecialchars(json_encode($performanceStats['throughput']), ENT_QUOTES, 'UTF-8') ?>'
         data-daily='<?= htmlspecialchars(json_encode($nodePerformance['daily']), ENT_QUOTES, 'UTF-8') ?>'
         data-hourly='<?= htmlspecialchars(json_encode($nodePerformance['hourly']), ENT_QUOTES, 'UTF-8') ?>'
         data-minute='<?= htmlspecialchars(json_encode($nodePerformance['minute']), ENT_QUOTES, 'UTF-8') ?>'
         data-cpu-trend='<?= htmlspecialchars(json_encode($nodeCpuTrend), ENT_QUOTES, 'UTF-8') ?>'>
    </div>
    <!-- End of Data Storage Element -->

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/moment"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-moment"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="js/charts.js"></script>
    <script>
    $(document).ready(function() {
        function updateDashboard() {
            $.ajax({
                url: 'includes/get_monitor_data.php',
                method: 'GET',
                success: function(data) {
                    // Update statistics cards
                    $('.stats-value').eq(0).text(data.nodeStats.online + '/' + data.nodeStats.total);
                    $('.stats-value').eq(1).text(data.nodeStats.avg_cpu_usage + '%');
                    $('.stats-value').eq(2).text(data.performanceStats.avg_processing_time + ' minutes');
                    $('.stats-value').eq(3).text(data.performanceStats.success_rate + '%');

                    // Update task progress
                    let taskHtml = '';
                    data.tasksProgress.forEach(task => {
                        taskHtml += `
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="fw-bold">Task ${task.id}</span>
                                    <div class="text-end">
                                        <span class="text-muted">${task.completed}/${task.total}</span>
                                        ${task.estimated_time ? `<span class="ms-2 text-info">Estimated completion in ${task.estimated_time}</span>` : ''}
                                    </div>
                                </div>
                                <div class="progress">
                                    <div class="progress-bar" role="progressbar" 
                                         style="width: ${task.progress}%"
                                         aria-valuenow="${task.progress}" 
                                         aria-valuemin="0" aria-valuemax="100">
                                        ${task.progress}%
                                    </div>
                                </div>
                            </div>`;
                    });
                    $('.card-body').first().html(taskHtml);

                    // Update chart data
                    updateCharts(data);
                },
                error: function(xhr, status, error) {
                    console.error('Failed to fetch data:', error);
                }
            });
        }

        // Update data every 10 seconds
        setInterval(updateDashboard, 10000);
    });
    </script>
</body>
</html>