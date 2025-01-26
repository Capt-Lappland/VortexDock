<?php
// monitor/index.php
require_once __DIR__ . '/includes/db_connect.php';
require_once __DIR__ . '/includes/data_functions.php';

// 获取所有监控数据
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
    <link href="css/styles.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container py-4">
        <h1 class="mb-4 text-primary">VortexDock 数据监控</h1>
        
        <!-- 系统状态概览 -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?= $nodeStats['online'] ?>/<?= $nodeStats['total'] ?></div>
                    <div class="stats-label">在线节点数</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?= $nodeStats['avg_cpu_usage'] ?>%</div>
                    <div class="stats-label">平均CPU使用率</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?= $performanceStats['avg_processing_time'] ?>分钟</div>
                    <div class="stats-label">平均处理时间</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card text-center">
                    <div class="stats-value"><?= $performanceStats['success_rate'] ?>%</div>
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
                                    <span class="fw-bold">任务 <?= htmlspecialchars($task['id']) ?></span>
                                    <div class="text-end">
                                        <span class="text-muted"><?= $task['completed'] ?>/<?= $task['total'] ?></span>
                                        <?php if ($task['estimated_time']): ?>
                                            <span class="ms-2 text-info">预计<?= $task['estimated_time'] ?>后完成</span>
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

    <!-- 数据存储元素 -->
    <div id="chart-data" 
         data-queue-status='<?= htmlspecialchars(json_encode($queueStats), ENT_QUOTES, 'UTF-8') ?>'
         data-throughput='<?= htmlspecialchars(json_encode($performanceStats['throughput']), ENT_QUOTES, 'UTF-8') ?>'
         data-daily='<?= htmlspecialchars(json_encode($nodePerformance['daily']), ENT_QUOTES, 'UTF-8') ?>'
         data-hourly='<?= htmlspecialchars(json_encode($nodePerformance['hourly']), ENT_QUOTES, 'UTF-8') ?>'
         data-minute='<?= htmlspecialchars(json_encode($nodePerformance['minute']), ENT_QUOTES, 'UTF-8') ?>'>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="js/charts.js"></script>
</body>
</html>