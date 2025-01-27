<?php
require_once __DIR__ . '/db_connect.php';
require_once __DIR__ . '/data_functions.php';

// 获取所有监控数据
$data = [
    'tasksProgress' => getTasksProgress($conn),
    'nodePerformance' => getNodePerformance($conn),
    'nodeStats' => getNodeStats($conn),
    'queueStats' => getTaskQueueStats($conn),
    'performanceStats' => getTaskPerformanceStats($conn),
    'nodeCpuTrend' => getNodeCpuTrend($conn)
];

$conn->close();

// 设置响应头为 JSON
header('Content-Type: application/json');
echo json_encode($data);