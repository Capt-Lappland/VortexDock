<?php
require_once('config.php');

$conn = new mysqli(
    $DB_CONFIG['host'],
    $DB_CONFIG['user'],
    $DB_CONFIG['password'],
    $DB_CONFIG['database']
);

if ($conn->connect_error) {
    die("Database connection failed: " . $conn->connect_error);
}
?>