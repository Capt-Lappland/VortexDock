<?php
// includes/data_functions.php

/**
 * Retrieve all task progress data
 */
function getTasksProgress($conn) {
    $data = [];
    $result = $conn->query('SELECT id, status, created_at FROM tasks ORDER BY created_at DESC');
    
    if ($result && $result->num_rows > 0) {
        while ($task = $result->fetch_assoc()) {
            $task_id = $task['id'];
            $total = $conn->query("SELECT COUNT(*) as count FROM task_{$task_id}_ligands")->fetch_assoc()['count'];
            $completed = $conn->query("SELECT COUNT(*) as count FROM task_{$task_id}_ligands WHERE status = 'completed'")->fetch_assoc()['count'];
            
            // Calculate progress
            $progress = $total > 0 ? round(($completed / $total) * 100, 2) : 0;
            
            // Calculate processing speed
            $recent_completed = $conn->query("SELECT COUNT(*) as count FROM task_{$task_id}_ligands 
                                            WHERE status = 'completed' 
                                            AND last_updated >= NOW() - INTERVAL 5 MINUTE")->fetch_assoc()['count'];
            $speed = $recent_completed / 5; // Number processed per minute
            
            // Estimate remaining time
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
 * Retrieve node performance data
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
        
        // Merge daily data queries
        if (!empty($daily_query)) {
            $daily_union = implode(' UNION ALL ', $daily_query);
            $result = $conn->query("SELECT date, SUM(task_completed) as completed_tasks 
                                  FROM ($daily_union) as daily_data 
                                  GROUP BY date 
                                  ORDER BY date DESC LIMIT 7");
            $data['daily'] = $result->fetch_all(MYSQLI_ASSOC);
        }
        
        // Merge hourly data queries
        if (!empty($hourly_query)) {
            $hourly_union = implode(' UNION ALL ', $hourly_query);
            $result = $conn->query("SELECT hour, SUM(task_completed) as completed_tasks 
                                  FROM ($hourly_union) as hourly_data 
                                  GROUP BY hour 
                                  ORDER BY hour ASC");
            $data['hourly'] = $result->fetch_all(MYSQLI_ASSOC);
        }
        
        // Merge minute data queries
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
 * Retrieve node status statistics
 */
function getNodeStats($conn) {
    $stats = ['total' => 0, 'online' => 0, 'offline' => 0, 'avg_cpu_usage' => 0];
    
    // Online nodes (heartbeat within the last 5 minutes)
    $result = $conn->query("SELECT COUNT(DISTINCT client_addr) as online_count 
                          FROM node_heartbeats 
                          WHERE last_heartbeat >= NOW() - INTERVAL 5 MINUTE");
    if ($result) $stats['online'] = (int)$result->fetch_assoc()['online_count'];
    
    // Total nodes
    $result = $conn->query("SELECT COUNT(DISTINCT client_addr) as total_count FROM node_heartbeats");
    if ($result) {
        $stats['total'] = (int)$result->fetch_assoc()['total_count'];
        $stats['offline'] = $stats['total'] - $stats['online'];
    }
    
    // Average CPU usage
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
 * Retrieve task queue status distribution
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
 * Retrieve task performance metrics
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
        
        // Calculate average processing time
        if (!empty($avg_time_queries)) {
            $query = "SELECT AVG(process_time) as avg_time 
                     FROM (".implode(" UNION ALL ", $avg_time_queries).") as tasks 
                     WHERE process_time > 0";
            $result = $conn->query($query);
            if ($result) $stats['avg_processing_time'] = round($result->fetch_assoc()['avg_time'] ?? 0, 1);
        }
        
        // Calculate success rate
        if (!empty($success_rate_queries)) {
            $query = "SELECT 
                     COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / 
                     NULLIF(COUNT(*), 0) as success_rate 
                     FROM (".implode(" UNION ALL ", $success_rate_queries).") as all_tasks";
            $result = $conn->query($query);
            if ($result) $stats['success_rate'] = round($result->fetch_assoc()['success_rate'] ?? 0, 1);
        }
        
        // Calculate throughput
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
 * Format estimated time (internal helper function)
 */
function formatEstimatedTime($minutes) {
    if (!$minutes) return null;
    $hours = floor($minutes / 60);
    $minutes = $minutes % 60;
    return ($hours > 0 ? $hours.' hours' : '').($minutes > 0 ? $minutes.' minutes' : '');
}

/**
 * Retrieve node CPU usage trend
 */
function getNodeCpuTrend($conn) {
    $data = [];
    
    // Retrieve CPU usage data for all nodes within the last hour
    $result = $conn->query("SELECT 
                            client_addr,
                            DATE_FORMAT(last_heartbeat, '%Y-%m-%d %H:%i') as minute,
                            cpu_usage
                          FROM node_heartbeats
                          WHERE last_heartbeat >= NOW() - INTERVAL 1 HOUR
                          ORDER BY last_heartbeat ASC");
    
    if ($result && $result->num_rows > 0) {
        $nodeData = [];
        while ($row = $result->fetch_assoc()) {
            $nodeData[$row['client_addr']][$row['minute']] = $row['cpu_usage'];
        }
        
        // Organize data for each node
        foreach ($nodeData as $node => $points) {
            $data[] = [
                'node' => $node,
                'data' => $points
            ];
        }
    }
    
    return $data;
}
?>