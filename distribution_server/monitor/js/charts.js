// monitor/js/charts.js

// 严格模式
'use strict';

// 从DOM获取数据
const chartDataElement = document.getElementById('chart-data');
if (!chartDataElement) {
    console.error('无法找到chart-data元素');
    throw new Error('chart-data元素不存在');
}

// 存储图表实例
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
    console.error('解析图表数据失败:', error);
    throw error;
}

// Chart.js 全局配置
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial';
Chart.defaults.font.size = 12;
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(0, 0, 0, 0.8)';
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 6;

// 通用图表配置
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

// 初始化队列状态饼图
function initQueueStatusChart() {
    return new Chart(document.getElementById('queueStatusChart'), {
        type: 'pie',
        data: {
            labels: ['待处理', '处理中', '已完成', '失败'],
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

// 初始化吞吐量趋势图
function initThroughputChart() {
    if (chartData.throughput.length === 0) return null;

    return new Chart(document.getElementById('throughputChart'), {
        type: 'line',
        data: {
            labels: chartData.throughput.map(item => item.time_slot),
            datasets: [{
                label: '系统吞吐量',
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

// 初始化性能图表组
function initPerformanceCharts() {
    const charts = {
        daily: null,
        hourly: null,
        minute: null
    };

    // 每日性能柱状图
    if (chartData.daily.length > 0) {
        charts.daily = new Chart(document.getElementById('dailyPerformanceChart'), {
            type: 'bar',
            data: {
                labels: chartData.daily.map(item => item.date),
                datasets: [{
                    label: '每日完成任务数',
                    data: chartData.daily.map(item => item.completed_tasks),
                    backgroundColor: '#2196F3'
                }]
            },
            options: chartOptions
        });
    }

    // 每小时性能折线图
    if (chartData.hourly.length > 0) {
        charts.hourly = new Chart(document.getElementById('hourlyPerformanceChart'), {
            type: 'line',
            data: {
                labels: chartData.hourly.map(item => item.hour),
                datasets: [{
                    label: '每小时完成任务数',
                    data: chartData.hourly.map(item => item.completed_tasks),
                    borderColor: '#4CAF50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    fill: true
                }]
            },
            options: chartOptions
        });
    }

    // 每分钟性能折线图
    if (chartData.minute.length > 0) {
        charts.minute = new Chart(document.getElementById('minutePerformanceChart'), {
            type: 'line',
            data: {
                labels: chartData.minute.map(item => item.minute),
                datasets: [{
                    label: '每5分钟完成任务数',
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

// 预定义的高对比度颜色组合
const predefinedColors = [
    '#FF6B6B',  // 鲜红色
    '#4ECDC4',  // 青绿色
    '#45B7D1',  // 天蓝色
    '#96CEB4',  // 薄荷绿
    '#FFD93D',  // 明黄色
    '#6C5CE7',  // 靛蓝色
    '#A8E6CF',  // 浅绿色
    '#FF8B94',  // 粉红色
    '#A3A1FF',  // 淡紫色
    '#FFDAC1'   // 杏色
];

// 生成颜色
function generateColor(index) {
    return predefinedColors[index % predefinedColors.length];
}

// 绘制节点CPU使用率趋势图
function initNodeCpuTrendChart() {
    const chartElement = document.getElementById('nodeCpuTrendChart');
    if (!chartElement) return null;

    const cpuTrendData = chartData.cpuTrend;
    if (!cpuTrendData || cpuTrendData.length === 0) {
        console.warn('CPU趋势数据为空');
        return null;
    }

    // 准备数据集
    const datasets = cpuTrendData.map((node, index) => ({
        label: `节点 ${node.node}`,
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
                    text: '最近一小时CPU使用率趋势',
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
                        text: 'CPU使用率 (%)',
                        font: {
                            size: 12
                        }
                    }
                }
            }
        }
    });
}

// 页面加载初始化
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
        console.error('图表初始化失败:', error);
    }
});

// 更新图表数据
function updateCharts(data) {
    try {
        // 更新图表数据
        chartData = {
            queueStatus: data.queueStats || {},
            throughput: data.performanceStats.throughput || [],
            daily: data.nodePerformance.daily || [],
            hourly: data.nodePerformance.hourly || [],
            minute: data.nodePerformance.minute || [],
            cpuTrend: data.nodeCpuTrend || []
        };

        // 更新队列状态图表
        if (charts.queueStatus) {
            charts.queueStatus.data.datasets[0].data = [
                chartData.queueStatus.pending,
                chartData.queueStatus.processing,
                chartData.queueStatus.completed,
                chartData.queueStatus.failed
            ];
            charts.queueStatus.update('none');
        }

        // 更新吞吐量趋势图表
        if (charts.throughput && chartData.throughput.length > 0) {
            charts.throughput.data.labels = chartData.throughput.map(item => item.time_slot);
            charts.throughput.data.datasets[0].data = chartData.throughput.map(item => parseInt(item.total_count));
            charts.throughput.update('none');
        }

        // 更新每日性能图表
        if (charts.daily && chartData.daily.length > 0) {
            charts.daily.data.labels = chartData.daily.map(item => item.date);
            charts.daily.data.datasets[0].data = chartData.daily.map(item => item.completed_tasks);
            charts.daily.update('none');
        }

        // 更新每小时性能图表
        if (charts.hourly && chartData.hourly.length > 0) {
            charts.hourly.data.labels = chartData.hourly.map(item => item.hour);
            charts.hourly.data.datasets[0].data = chartData.hourly.map(item => item.completed_tasks);
            charts.hourly.update('none');
        }

        // 更新每分钟性能图表
        if (charts.minute && chartData.minute.length > 0) {
            charts.minute.data.labels = chartData.minute.map(item => item.minute);
            charts.minute.data.datasets[0].data = chartData.minute.map(item => item.completed_tasks);
            charts.minute.update('none');
        }

        // 更新CPU趋势图表
        if (charts.cpuTrend && chartData.cpuTrend.length > 0) {
            const datasets = chartData.cpuTrend.map((node, index) => ({
                label: `节点 ${node.node}`,
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
        console.error('更新图表数据失败:', error);
    }
}