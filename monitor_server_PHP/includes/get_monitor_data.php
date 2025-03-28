<?php
require_once __DIR__ . '/db_connect.php';
require_once __DIR__ . '/data_functions.php';

// Retrieve all monitoring data
$data = [
    'tasksProgress' => getTasksProgress($conn),
    'nodePerformance' => getNodePerformance($conn),
    'nodeStats' => getNodeStats($conn),
    'queueStats' => getTaskQueueStats($conn),
    'performanceStats' => getTaskPerformanceStats($conn),
    'nodeCpuTrend' => getNodeCpuTrend($conn)
];

$conn->close();

// Set response header to JSON
header('Content-Type: application/json');
echo json_encode($data);
?>