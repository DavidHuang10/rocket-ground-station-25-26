// Chart.js management

import { hexToRgba } from '../utils/formatters.js';

export class ChartManager {
    constructor() {
        this.charts = {};
        this.modalChart = null;
    }

    init(panels) {
        panels.forEach(panel => {
            if (panel.type === 'chart') {
                const canvasId = `chart-${panel.id}`;
                const ctx = document.getElementById(canvasId);
                if (ctx) {
                    this.charts[panel.id] = new Chart(ctx, {
                        type: 'line',
                        data: {
                            datasets: [{
                                label: panel.title,
                                data: [],
                                borderColor: panel.chart_color || '#4caf50',
                                backgroundColor: hexToRgba(panel.chart_color || '#4caf50', 0.1),
                                tension: 0.4,
                                pointRadius: 0
                            }]
                        },
                        options: this.getChartOptions(panel)
                    });
                }
            }
        });
    }

    update(panels, telemetryData) {
        panels.forEach(panel => {
            const chart = this.charts[panel.id];
            if (chart) {
                const field = panel.fields[0];
                const data = (telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));
                chart.data.datasets[0].data = data;
                chart.update('none');
            }
        });
    }

    getChartOptions(panel) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                x: {
                    type: 'linear',
                    title: {
                        display: true,
                        text: 'Time (s)'
                    },
                    ticks: {
                        autoSkip: true,
                        maxTicksLimit: 10
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: `${panel.title} (${panel.unit || ''})`
                    },
                    ticks: {
                        autoSkip: true,
                        maxTicksLimit: 8
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        };
    }

    destroy(panelId) {
        if (this.charts[panelId]) {
            this.charts[panelId].destroy();
            delete this.charts[panelId];
        }
    }

    destroyAll() {
        Object.keys(this.charts).forEach(id => this.destroy(id));
    }

    // Modal chart methods
    createModalChart(canvasId, panel, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        this.modalChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: panel.title,
                    data: data,
                    borderColor: panel.chart_color || '#4caf50',
                    backgroundColor: hexToRgba(panel.chart_color || '#4caf50', 0.1),
                    tension: 0.4,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }]
            },
            options: this.getModalChartOptions(panel)
        });

        return this.modalChart;
    }

    updateModalChart(telemetryData, field) {
        if (this.modalChart) {
            const data = (telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));
            this.modalChart.data.datasets[0].data = data;
            this.modalChart.update('none');
        }
    }

    resetModalZoom() {
        if (this.modalChart) {
            this.modalChart.resetZoom();
        }
    }

    destroyModalChart() {
        if (this.modalChart) {
            this.modalChart.destroy();
            this.modalChart = null;
        }
    }

    getModalChartOptions(panel) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            },
            scales: this.getModalScales(panel),
            plugins: {
                legend: {
                    display: false
                },
                tooltip: this.getModalTooltipConfig(panel),
                zoom: this.getZoomConfig()
            }
        };
    }

    getModalScales(panel) {
        return {
            x: {
                type: 'linear',
                title: {
                    display: true,
                    text: 'Time (s)',
                    color: '#fff',
                    font: { size: 14 }
                },
                ticks: {
                    color: '#aaa',
                    autoSkip: true,
                    maxTicksLimit: 12
                },
                grid: {
                    color: '#333'
                }
            },
            y: {
                title: {
                    display: true,
                    text: `${panel.title} (${panel.unit || ''})`,
                    color: '#fff',
                    font: { size: 14 }
                },
                ticks: {
                    color: '#aaa',
                    autoSkip: true,
                    maxTicksLimit: 10
                },
                grid: {
                    color: '#333'
                }
            }
        };
    }

    getModalTooltipConfig(panel) {
        return {
            enabled: true,
            mode: 'nearest',
            intersect: false,
            backgroundColor: 'rgba(0, 0, 0, 0.9)',
            titleColor: '#fff',
            bodyColor: '#fff',
            borderColor: panel.chart_color || '#4caf50',
            borderWidth: 2,
            padding: 12,
            displayColors: false,
            callbacks: {
                title: (items) => {
                    if (items.length > 0) {
                        return `Time: ${items[0].parsed.x.toFixed(3)}s`;
                    }
                    return '';
                },
                label: (item) => {
                    const value = item.parsed.y;
                    const precision = panel.precision !== undefined ? panel.precision : 2;
                    return `${panel.title}: ${value.toFixed(precision)} ${panel.unit || ''}`;
                },
                afterLabel: (item) => {
                    const precision = panel.precision !== undefined ? panel.precision : 2;
                    return `Coordinates: (${item.parsed.x.toFixed(3)}, ${item.parsed.y.toFixed(precision)})`;
                }
            }
        };
    }

    getZoomConfig() {
        return {
            pan: {
                enabled: true,
                mode: 'xy',
                modifierKey: null
            },
            zoom: {
                wheel: {
                    enabled: true,
                    speed: 0.1
                },
                pinch: {
                    enabled: true
                },
                drag: {
                    enabled: true,
                    modifierKey: 'ctrl'
                },
                mode: 'xy'
            },
            limits: {
                x: { min: 'original', max: 'original' },
                y: { min: 'original', max: 'original' }
            }
        };
    }
}
