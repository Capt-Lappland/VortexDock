// monitor/js/charts.js

// Strict mode
'use strict';

// Get data from DOM
const chartDataElement = document.getElementById('chart-data');
if (!chartDataElement) {
    console.error('Cannot find chart-data element');
    throw new Error('chart-data element does not exist');
}

// Store chart instances
let charts = {
    queueStatus: null,
    throughput: null,
    daily: null,
    hourly: null,
    minute: null,
    cpuTrend: null
};

let chartData;
try {
    chartData = {
        queueStatus: JSON.parse(chartDataElement.dataset.queueStatus || '{}'),
        throughput: JSON.parse(chartDataElement.dataset.throughput || '[]'),
        daily: JSON.parse(chartDataElement.dataset.daily || '[]'),
        hourly: JSON.parse(chartDataElement.dataset.hourly || '[]'),
        minute: JSON.parse(chartDataElement.dataset.minute || '[]'),
        cpuTrend: JSON.parse(chartDataElement.dataset.cpuTrend || '[]')
    };
} catch (error) {
    console.error('Failed to parse chart data:', error);
    throw error;
}

// Chart.js global configuration
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial';
Chart.defaults.font.size = 12;
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(0, 0, 0, 0.8)';
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 6;

// General chart configuration
const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'top',
            labels: {
                padding: 20,
                usePointStyle: true,
                pointStyle: 'circle',
                font: { size: 12 }
            }
        },
        tooltip: {
            mode: 'index',
            intersect: false,
            titleFont: { size: 14 },
            bodyFont: { size: 13 }
        }
    },
    scales: {
        y: {
            beginAtZero: true,
            grid: { color: 'rgba(0, 0, 0, 0.1)', drawBorder: false },
            ticks: {
                padding: 10,
                font: { size: 12 },
                callback: value => value.toLocaleString()
            }
        },
        x: {
            grid: { display: false },
            ticks: {
                maxRotation: 45,
                minRotation: 45,
                padding: 10,
                font: { size: 11 }
            }
        }
    },
    elements: {
        line: { tension: 0.4, borderWidth: 2 },
        point: { radius: 3, hitRadius: 10, hoverRadius: 5 }
    }
};

// Initialize queue status pie chart
function initQueueStatusChart() {
    return new Chart(document.getElementById('queueStatusChart'), {
        type: 'pie',
        data: {
            labels: ['Pending', 'Processing', 'Completed', 'Failed'],
            datasets: [{
                data: [
                    chartData.queueStatus.pending,
                    chartData.queueStatus.processing,
                    chartData.queueStatus.completed,
                    chartData.queueStatus.failed
                ],
                backgroundColor: ['#2196F3', '#FFC107', '#4CAF50', '#F44336']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right' }
            }
        }
    });
}

// Initialize throughput trend chart
function initThroughputChart() {
    if (chartData.throughput.length === 0) return null;

    return new Chart(document.getElementById('throughputChart'), {
        type: 'line',
        data: {
            labels: chartData.throughput.map(item => item.time_slot),
            datasets: [{
                label: 'System Throughput',
                data: chartData.throughput.map(item => parseInt(item.total_count)),
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: context => {
                    const chart = context.chart;
                    const { ctx, chartArea } = chart;
                    if (!chartArea) return null;
                    const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
                    gradient.addColorStop(0, 'rgba(75, 192, 192, 0.1)');
                    gradient.addColorStop(1, 'rgba(75, 192, 192, 0.4)');
                    return gradient;
                },
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            ...chartOptions,
            scales: {
                ...chartOptions.scales,
                x: {
                    ...chartOptions.scales.x,
                    ticks: {
                        ...chartOptions.scales.x.ticks,
                        callback: (value, index, values) => {
                            const time = new Date(chartData.throughput[index].time_slot);
                            return `${time.getHours()}:${String(time.getMinutes()).padStart(2, '0')}`;
                        }
                    }
                }
            }
        }
    });
}

// Initialize performance charts group
function initPerformanceCharts() {
    const charts = {
        daily: null,
        hourly: null,
        minute: null
    };

    // Daily performance bar chart
    if (chartData.daily.length > 0) {
        charts.daily = new Chart(document.getElementById('dailyPerformanceChart'), {
            type: 'bar',
            data: {
                labels: chartData.daily.map(item => item.date),
                datasets: [{
                    label: 'Tasks Completed Daily',
                    data: chartData.daily.map(item => item.completed_tasks),
                    backgroundColor: '#2196F3'
                }]
            },
            options: chartOptions
        });
    }

    // Hourly performance line chart
    if (chartData.hourly.length > 0) {
        charts.hourly = new Chart(document.getElementById('hourlyPerformanceChart'), {
            type: 'line',
            data: {
                labels: chartData.hourly.map(item => item.hour),
                datasets: [{
                    label: 'Tasks Completed Hourly',
                    data: chartData.hourly.map(item => item.completed_tasks),
                    borderColor: '#4CAF50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    fill: true
                }]
            },
            options: chartOptions
        });
    }

    // Minute performance line chart
    if (chartData.minute.length > 0) {
        charts.minute = new Chart(document.getElementById('minutePerformanceChart'), {
            type: 'line',
            data: {
                labels: chartData.minute.map(item => item.minute),
                datasets: [{
                    label: 'Tasks Completed Every 5 Minutes',
                    data: chartData.minute.map(item => item.completed_tasks),
                    borderColor: '#FF9800',
                    backgroundColor: 'rgba(255, 152, 0, 0.1)',
                    fill: true
                }]
            },
            options: chartOptions
        });
    }

    return charts;
}

// Predefined high-contrast color combinations
const predefinedColors = [
    '#FF6B6B',  // Bright Red
    '#4ECDC4',  // Aqua Green
    '#45B7D1',  // Sky Blue
    '#96CEB4',  // Mint Green
    '#FFD93D',  // Bright Yellow
    '#6C5CE7',  // Indigo
    '#A8E6CF',  // Light Green
    '#FF8B94',  // Pink
    '#A3A1FF',  // Light Purple
    '#FFDAC1'   // Apricot
];

// Generate color
function generateColor(index) {
    return predefinedColors[index % predefinedColors.length];
}

// Draw node CPU usage trend chart
function initNodeCpuTrendChart() {
    const chartElement = document.getElementById('nodeCpuTrendChart');
    if (!chartElement) return null;

    const cpuTrendData = chartData.cpuTrend;
    if (!cpuTrendData || cpuTrendData.length === 0) {
        console.warn('CPU trend data is empty');
        return null;
    }

    // Prepare datasets
    const datasets = cpuTrendData.map((node, index) => ({
        label: `Node ${node.node}`,
        data: Object.entries(node.data).map(([time, value]) => ({
            x: new Date(time).getTime(),
            y: parseFloat(value)
        })),
        borderColor: generateColor(index),
        backgroundColor: 'transparent',
        tension: 0.4,
        borderWidth: 2
    }));

    return new Chart(chartElement, {
        type: 'line',
        data: {
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            },
            plugins: {
                title: {
                    display: true,
                    text: 'CPU Usage Trend in the Last Hour',
                    font: {
                        size: 14
                    }
                },
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 15
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        displayFormats: {
                            minute: 'HH:mm'
                        }
                    },
                    grid: {
                        display: false
                    },
                    ticks: {
                        maxRotation: 0
                    }
                },
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'CPU Usage (%)',
                        font: {
                            size: 12
                        }
                    }
                }
            }
        }
    });
}

// Page load initialization
document.addEventListener('DOMContentLoaded', () => {
    try {
        charts.queueStatus = initQueueStatusChart();
        charts.throughput = initThroughputChart();
        const performanceCharts = initPerformanceCharts();
        charts.daily = performanceCharts.daily;
        charts.hourly = performanceCharts.hourly;
        charts.minute = performanceCharts.minute;
        charts.cpuTrend = initNodeCpuTrendChart();
    } catch (error) {
        console.error('Failed to initialize charts:', error);
    }
});

// Update chart data
function updateCharts(data) {
    try {
        // Update chart data
        chartData = {
            queueStatus: data.queueStats || {},
            throughput: data.performanceStats.throughput || [],
            daily: data.nodePerformance.daily || [],
            hourly: data.nodePerformance.hourly || [],
            minute: data.nodePerformance.minute || [],
            cpuTrend: data.nodeCpuTrend || []
        };

        // Update queue status chart
        if (charts.queueStatus) {
            charts.queueStatus.data.datasets[0].data = [
                chartData.queueStatus.pending,
                chartData.queueStatus.processing,
                chartData.queueStatus.completed,
                chartData.queueStatus.failed
            ];
            charts.queueStatus.update('none');
        }

        // Update throughput trend chart
        if (charts.throughput && chartData.throughput.length > 0) {
            charts.throughput.data.labels = chartData.throughput.map(item => item.time_slot);
            charts.throughput.data.datasets[0].data = chartData.throughput.map(item => parseInt(item.total_count));
            charts.throughput.update('none');
        }

        // Update daily performance chart
        if (charts.daily && chartData.daily.length > 0) {
            charts.daily.data.labels = chartData.daily.map(item => item.date);
            charts.daily.data.datasets[0].data = chartData.daily.map(item => item.completed_tasks);
            charts.daily.update('none');
        }

        // Update hourly performance chart
        if (charts.hourly && chartData.hourly.length > 0) {
            charts.hourly.data.labels = chartData.hourly.map(item => item.hour);
            charts.hourly.data.datasets[0].data = chartData.hourly.map(item => item.completed_tasks);
            charts.hourly.update('none');
        }

        // Update minute performance chart
        if (charts.minute && chartData.minute.length > 0) {
            charts.minute.data.labels = chartData.minute.map(item => item.minute);
            charts.minute.data.datasets[0].data = chartData.minute.map(item => item.completed_tasks);
            charts.minute.update('none');
        }

        // Update CPU trend chart
        if (charts.cpuTrend && chartData.cpuTrend.length > 0) {
            const datasets = chartData.cpuTrend.map((node, index) => ({
                label: `Node ${node.node}`,
                data: Object.entries(node.data).map(([time, value]) => ({
                    x: new Date(time).getTime(),
                    y: parseFloat(value)
                })),
                borderColor: generateColor(index),
                backgroundColor: 'transparent',
                tension: 0.4,
                borderWidth: 2
            }));
            charts.cpuTrend.data.datasets = datasets;
            charts.cpuTrend.update('none');
        }
    } catch (error) {
        console.error('Failed to update chart data:', error);
    }
}