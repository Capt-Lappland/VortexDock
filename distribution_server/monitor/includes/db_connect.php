<?php
require_once('config.php');

$conn = new mysqli(
    $DB_CONFIG['host'],
    $DB_CONFIG['user'],
    $DB_CONFIG['password'],
    $DB_CONFIG['database']
);

if ($conn->connect_error) {
    die("数据库连接失败: " . $conn->connect_error);
}
?>