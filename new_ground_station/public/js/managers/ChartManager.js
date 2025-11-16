// Chart.js management

import { hexToRgba } from '../utils/formatters.js';

export class ChartManager {
    constructor() {
        this.charts = {};
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
}
