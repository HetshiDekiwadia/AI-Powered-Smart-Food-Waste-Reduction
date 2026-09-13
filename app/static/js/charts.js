/**
 * EcoPlate AI - Chart.js Visualization Module
 */

function initWasteCategoryChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    // Prevent canvas reuse collisions
    const existingChart = Chart.getChart(canvasId);
    if (existingChart) {
        existingChart.destroy();
    }

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#ef4444', // Plate Waste (Red)
                    '#f59e0b', // Prep Waste (Amber)
                    '#8b5cf6', // Spoilage (Purple)
                    '#3b82f6', // Buffet Leftover (Blue)
                    '#10b981'  // Other (Green)
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        font: { family: "'Plus Jakarta Sans', sans-serif", size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return ` ${context.label}: ${context.raw} kg`;
                        }
                    }
                }
            },
            cutout: '70%'
        }
    });
}

function initForecastComparisonChart(canvasId, traditionalKg, optimizedKg, traditionalPortions, optimizedPortions) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    // Prevent canvas reuse collisions on dynamic recalculation
    const existingChart = Chart.getChart(canvasId);
    if (existingChart) {
        existingChart.destroy();
    }

    const portionsData = [
        traditionalPortions !== undefined ? traditionalPortions : null,
        optimizedPortions !== undefined ? optimizedPortions : null
    ];

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Traditional Cooking (Uncalibrated)', 'EcoPlate AI Optimized Batch'],
            datasets: [{
                label: 'Prepared Food Quantity (kg)',
                data: [traditionalKg, optimizedKg],
                backgroundColor: ['#94a3b8', '#10b981'],
                borderRadius: 8,
                barThickness: 45
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const idx = context.dataIndex;
                            const kgVal = context.raw;
                            const portions = portionsData[idx];
                            if (portions !== null && portions !== undefined) {
                                return ` ${kgVal} kg (${portions} portions)`;
                            }
                            return ` ${kgVal} kg prepared`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Total Food Prepared (kg)'
                    },
                    grid: { color: '#f1f5f9' }
                },
                x: {
                    grid: { display: false }
                }
            }
        }
    });
}
