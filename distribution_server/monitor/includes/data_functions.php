<?php
// includes/data_functions.php

/**
 * 获取所有任务进度数据
 */
function getTasksProgress($conn) {
    $data = [];
    $result = $conn->query('SELECT id, status, created_at FROM tasks ORDER BY created_at DESC');
    
    if ($result && $result->num_rows > 0) {
        while ($task = $result->fetch_assoc()) {
            $task_id = $task['id'];
            $total = $conn->query("SELECT COUNT(*) as count FROM task_{$task_id}_ligands")->fetch_assoc()['count'];
            $completed = $conn->query("SELECT COUNT(*) as count FROM task_{$task_id}_ligands WHERE status = 'completed'")->fetch_assoc()['count'];
            
            // 处理进度计算
            $progress = $total > 0 ? round(($completed / $total) * 100, 2) : 0;
            
            // 计算处理速度
            $recent_completed = $conn->query("SELECT COUNT(*) as count FROM task_{$task_id}_ligands 
                                            WHERE status = 'completed' 
                                            AND last_updated >= NOW() - INTERVAL 5 MINUTE")->fetch_assoc()['count'];
            $speed = $recent_completed / 5; // 每分钟处理数量
            
            // 预估剩余时间
            $remaining = $total - $completed;
            $estimated_minutes = $speed > 0 ? ceil($remaining / $speed) : null;
            $estimated_time = formatEstimatedTime($estimated_minutes);
            
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
    }
    return $data;
}

/**
 * 获取节点性能数据
 */
function getNodePerformance($conn) {
    $data = ['daily' => [], 'hourly' => [], 'minute' => []];
    $tasks_result = $conn->query('SELECT id FROM tasks');
    
    if ($tasks_result && $tasks_result->num_rows > 0) {
        $daily_query = $hourly_query = $minute_query = [];
        
        while ($task = $tasks_result->fetch_assoc()) {
            $task_id = $task['id'];
            
            $daily_query[] = "SELECT DATE(last_updated) as date, COUNT(*) as task_completed 
                             FROM task_{$task_id}_ligands 
                             WHERE status = 'completed' 
                             AND last_updated >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                             GROUP BY DATE(last_updated)";
            
            $hourly_query[] = "SELECT DATE_FORMAT(last_updated, '%Y-%m-%d %H:00') as hour,
                              COUNT(*) as task_completed
                              FROM task_{$task_id}_ligands
                              WHERE status = 'completed'
                              AND last_updated >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                              GROUP BY hour";
            
            $minute_query[] = "SELECT DATE_FORMAT(last_updated, '%Y-%m-%d %H:%i') as minute,
                              COUNT(*) as task_completed
                              FROM task_{$task_id}_ligands
                              WHERE status = 'completed'
                              AND last_updated >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
                              GROUP BY FLOOR(UNIX_TIMESTAMP(last_updated) / 300)";
        }
        
        // 合并查询每日数据
        if (!empty($daily_query)) {
            $daily_union = implode(' UNION ALL ', $daily_query);
            $result = $conn->query("SELECT date, SUM(task_completed) as completed_tasks 
                                  FROM ($daily_union) as daily_data 
                                  GROUP BY date 
                                  ORDER BY date DESC LIMIT 7");
            $data['daily'] = $result->fetch_all(MYSQLI_ASSOC);
        }
        
        // 合并查询每小时数据
        if (!empty($hourly_query)) {
            $hourly_union = implode(' UNION ALL ', $hourly_query);
            $result = $conn->query("SELECT hour, SUM(task_completed) as completed_tasks 
                                  FROM ($hourly_union) as hourly_data 
                                  GROUP BY hour 
                                  ORDER BY hour ASC");
            $data['hourly'] = $result->fetch_all(MYSQLI_ASSOC);
        }
        
        // 合并查询每分钟数据
        if (!empty($minute_query)) {
            $minute_union = implode(' UNION ALL ', $minute_query);
            $result = $conn->query("SELECT minute, SUM(task_completed) as completed_tasks 
                                  FROM ($minute_union) as minute_data 
                                  GROUP BY minute 
                                  ORDER BY minute ASC");
            $data['minute'] = $result->fetch_all(MYSQLI_ASSOC);
        }
    }
    return $data;
}

/**
 * 获取节点状态统计
 */
function getNodeStats($conn) {
    $stats = ['total' => 0, 'online' => 0, 'offline' => 0, 'avg_cpu_usage' => 0];
    
    // 在线节点数（最近5分钟有心跳）
    $result = $conn->query("SELECT COUNT(DISTINCT client_addr) as online_count 
                          FROM node_heartbeats 
                          WHERE last_heartbeat >= NOW() - INTERVAL 5 MINUTE");
    if ($result) $stats['online'] = (int)$result->fetch_assoc()['online_count'];
    
    // 总节点数
    $result = $conn->query("SELECT COUNT(DISTINCT client_addr) as total_count FROM node_heartbeats");
    if ($result) {
        $stats['total'] = (int)$result->fetch_assoc()['total_count'];
        $stats['offline'] = $stats['total'] - $stats['online'];
    }
    
    // 平均CPU使用率
    $result = $conn->query("SELECT AVG(cpu_usage) as avg_cpu 
                          FROM node_heartbeats 
                          WHERE last_heartbeat >= NOW() - INTERVAL 5 MINUTE");
    if ($result) {
        $row = $result->fetch_assoc();
        $stats['avg_cpu_usage'] = round($row['avg_cpu'] ?? 0, 1);
    }
    
    return $stats;
}

/**
 * 获取任务队列状态分布
 */
function getTaskQueueStats($conn) {
    $stats = ['pending' => 0, 'processing' => 0, 'completed' => 0, 'failed' => 0];
    $tasks_result = $conn->query('SELECT id FROM tasks');
    
    if ($tasks_result && $tasks_result->num_rows > 0) {
        while ($task = $tasks_result->fetch_assoc()) {
            $task_id = $task['id'];
            $result = $conn->query("SELECT status, COUNT(*) as count 
                                   FROM task_{$task_id}_ligands 
                                   GROUP BY status");
            
            if ($result) {
                while ($row = $result->fetch_assoc()) {
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

/**
 * 获取任务性能指标
 */
function getTaskPerformanceStats($conn) {
    $stats = ['avg_processing_time' => 0, 'success_rate' => 0, 'throughput' => []];
    $tasks_result = $conn->query('SELECT id FROM tasks');
    
    if ($tasks_result && $tasks_result->num_rows > 0) {
        $avg_time_queries = $success_rate_queries = $throughput_queries = [];
        
        while ($task = $tasks_result->fetch_assoc()) {
            $task_id = $task['id'];
            
            $avg_time_queries[] = "SELECT TIMESTAMPDIFF(MINUTE, created_at, last_updated) as process_time 
                                  FROM task_{$task_id}_ligands 
                                  WHERE status = 'completed'";
            
            $success_rate_queries[] = "SELECT status FROM task_{$task_id}_ligands";
            
            $throughput_queries[] = "SELECT DATE_FORMAT(last_updated, '%Y-%m-%d %H:%i:00') as time_slot, 
                                    COUNT(*) as count 
                                    FROM task_{$task_id}_ligands 
                                    WHERE status = 'completed' 
                                    AND last_updated >= NOW() - INTERVAL 24 HOUR 
                                    GROUP BY time_slot";
        }
        
        // 计算平均处理时间
        if (!empty($avg_time_queries)) {
            $query = "SELECT AVG(process_time) as avg_time 
                     FROM (".implode(" UNION ALL ", $avg_time_queries).") as tasks 
                     WHERE process_time > 0";
            $result = $conn->query($query);
            if ($result) $stats['avg_processing_time'] = round($result->fetch_assoc()['avg_time'] ?? 0, 1);
        }
        
        // 计算成功率
        if (!empty($success_rate_queries)) {
            $query = "SELECT 
                     COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / 
                     NULLIF(COUNT(*), 0) as success_rate 
                     FROM (".implode(" UNION ALL ", $success_rate_queries).") as all_tasks";
            $result = $conn->query($query);
            if ($result) $stats['success_rate'] = round($result->fetch_assoc()['success_rate'] ?? 0, 1);
        }
        
        // 计算吞吐量
        if (!empty($throughput_queries)) {
            $query = "SELECT 
                     DATE_FORMAT(DATE_SUB(time_slot, INTERVAL MINUTE(time_slot) % 30 MINUTE), 
                                '%Y-%m-%d %H:%i:00') as time_slot,
                     SUM(count) as total_count 
                     FROM (".implode(" UNION ALL ", $throughput_queries).") as stats 
                     GROUP BY DATE_FORMAT(DATE_SUB(time_slot, INTERVAL MINUTE(time_slot) % 30 MINUTE), 
                                '%Y-%m-%d %H:%i:00')
                     ORDER BY time_slot";
            $result = $conn->query($query);
            $stats['throughput'] = $result->fetch_all(MYSQLI_ASSOC);
        }
    }
    return $stats;
}

/**
 * 格式化预估时间（内部辅助函数）
 */
function formatEstimatedTime($minutes) {
    if (!$minutes) return null;
    $hours = floor($minutes / 60);
    $minutes = $minutes % 60;
    return ($hours > 0 ? $hours.'小时' : '').($minutes > 0 ? $minutes.'分钟' : '');
}
?>