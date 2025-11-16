// Main application entry point

import { ConfigManager } from './managers/ConfigManager.js';
import { ChartManager } from './managers/ChartManager.js';
import { WebSocketManager } from './managers/WebSocketManager.js';
import { DataManager } from './managers/DataManager.js';
import { formatValue, formatTimer, hexToRgba } from './utils/formatters.js';

const { createApp } = Vue;

createApp({
    data() {
        return {
            port: 8000,
            connected: false,
            config: null,
            telemetryData: {},
            // Manual timer
            manualTimer: 0,
            manualTimerRunning: false,
            manualTimerInterval: null,
            manualTimerEditing: false,
            // Modal chart
            modalChart: {
                visible: false,
                instance: null,
                panelId: null,
                title: '',
                unit: '',
                precision: 0,
                currentValue: 0
            }
        };
    },

    created() {
        // Initialize managers
        this.configManager = new ConfigManager();
        this.chartManager = new ChartManager();
        this.dataManager = new DataManager();
        // WebSocketManager will be initialized in mounted() with historical data callback
    },

    computed: {
        connectionStatus() {
            return this.connected ? 'connected' : 'disconnected';
        },

        connectionText() {
            return this.connected ? 'Connected' : 'Disconnected';
        },

        flightStage() {
            const stageData = this.telemetryData.stage;
            return stageData && stageData.length > 0 ? stageData[stageData.length - 1].value : 0;
        },

        sortedPanels() {
            return this.configManager?.sortedPanels || [];
        }
    },

    async mounted() {
        const urlParams = new URLSearchParams(window.location.search);
        const urlPort = urlParams.get('port');
        if (urlPort) {
            this.port = parseInt(urlPort);
        }

        await this.configManager.load();
        this.config = this.configManager.config;

        this.dataManager.init(this.configManager.getAllFields());
        this.telemetryData = this.dataManager.telemetryData;

        await this.$nextTick();
        this.chartManager.init(this.configManager.panels);

        // Pass async callback to load historical data after WebSocket connects
        this.wsManager = new WebSocketManager(
            this.handleWebSocketMessage.bind(this),
            this.handleConnectionChange.bind(this),
            this.loadHistoricalDataAfterConnection.bind(this)
        );
        this.wsManager.connect();
    },

    beforeUnmount() {
        this.wsManager.disconnect();
    },

    methods: {
        // WebSocket handlers
        handleWebSocketMessage(message) {
            if (message.type === 'clear') {
                this.handleClearSignal(message);
                return;
            }

            if (Array.isArray(message)) {
                this.dataManager.processTelemetry(message);
                this.chartManager.update(this.configManager.panels, this.telemetryData);
                this.updateModalChart();
            }
        },

        handleConnectionChange(connected) {
            this.connected = connected;
        },

        async loadHistoricalDataAfterConnection() {
            // Fetch historical data NOW (includes all data up to this moment)
            // This ensures no gap between historical and live data
            try {
                await this.dataManager.loadCurrentSession();
                this.chartManager.update(this.configManager.panels, this.telemetryData);
            } catch (e) {
                console.error('Failed to load historical data after connection:', e);
            }
        },

        reconnect() {
            this.wsManager.reconnect();
        },

        handleClearSignal(message) {
            this.dataManager.clear();
            this.chartManager.update(this.configManager.panels, this.telemetryData);

            if (message.takeoff_offset !== null) {
                console.log(`Takeoff marked: T+0 = ${message.takeoff_time}`);
            }
        },

        // Formatting utilities (passed through to utils)
        getCurrentValue(source) {
            return this.dataManager.getCurrentValue(source);
        },

        formatValue(value, precision) {
            return formatValue(value, precision);
        },

        formatTimer(milliseconds) {
            return formatTimer(milliseconds);
        },

        getStageName(stage) {
            const panel = this.config?.panels.find(p => p.id === 'flight_stage');
            if (panel && panel.mapping) {
                return panel.mapping[stage] || 'Unknown';
            }
            return stage.toString();
        },

        getContinuityClass(source) {
            const value = this.getCurrentValue(source);
            return value === 1 ? 'good' : 'bad';
        },

        getCurrentTime() {
            return this.dataManager.getCurrentTime();
        },

        getTotalPackets() {
            return this.dataManager.getPacketCount();
        },

        // API calls
        async clearCharts() {
            if (!confirm('Clear charts and mark takeoff?\n\nPre-flight data will be backed up.')) {
                return;
            }

            try {
                const response = await fetch('/telemetry/clear', {
                    method: 'POST'
                });
                const result = await response.json();

                if (result.status === 'error') {
                    alert(result.message);
                }
            } catch (e) {
                alert(`Failed to clear charts: ${e.message}`);
            }
        },

        async saveFlight() {
            try {
                const response = await fetch('/telemetry/save', {
                    method: 'POST'
                });
                const result = await response.json();

                if (result.status === 'success') {
                    alert(`Flight saved as ${result.filename}`);
                }
            } catch (e) {
                alert(`Failed to save flight: ${e.message}`);
            }
        },

        async saveAndClear() {
            if (!confirm('Save current flight and clear charts?')) {
                return;
            }

            try {
                const response = await fetch('/telemetry/save-and-clear', {
                    method: 'POST'
                });
                const result = await response.json();

                if (result.status === 'success') {
                    alert(`Flight saved as ${result.filename}`);
                }
            } catch (e) {
                alert(`Failed to save and clear: ${e.message}`);
            }
        },

        // Manual timer methods
        toggleManualTimer() {
            if (this.manualTimerRunning) {
                this.pauseManualTimer();
            } else {
                this.startManualTimer();
            }
        },

        startManualTimer() {
            if (this.manualTimerInterval) return;
            this.manualTimerRunning = true;
            this.manualTimerInterval = setInterval(() => {
                this.manualTimer += 100;
            }, 100);
        },

        pauseManualTimer() {
            this.manualTimerRunning = false;
            if (this.manualTimerInterval) {
                clearInterval(this.manualTimerInterval);
                this.manualTimerInterval = null;
            }
        },

        resetManualTimer() {
            this.pauseManualTimer();
            this.manualTimer = 0;
        },

        editManualTimer() {
            this.wasRunning = this.manualTimerRunning;
            if (this.manualTimerRunning) {
                this.pauseManualTimer();
            }

            this.manualTimerEditing = true;
            this.$nextTick(() => {
                const input = document.getElementById('manual-timer-input');
                if (input) {
                    input.value = this.formatTimer(this.manualTimer);
                    input.focus();
                    input.select();
                }
            });
        },

        saveManualTimer(event) {
            const value = event.target.value.trim();
            const parts = value.split(':').map(p => p.trim());

            if (parts.length !== 2 && parts.length !== 3) {
                alert('Invalid format. Use MM:SS or HH:MM:SS');
                return;
            }

            const numbers = parts.map(p => parseInt(p));
            if (numbers.some(n => isNaN(n) || n < 0)) {
                alert('Invalid time values. Use positive numbers only.');
                return;
            }

            if (parts.length === 2) {
                const [minutes, seconds] = numbers;
                if (seconds >= 60) {
                    alert('Seconds must be less than 60');
                    return;
                }
                this.manualTimer = (minutes * 60 + seconds) * 1000;
            } else if (parts.length === 3) {
                const [hours, minutes, seconds] = numbers;
                if (minutes >= 60 || seconds >= 60) {
                    alert('Minutes and seconds must be less than 60');
                    return;
                }
                this.manualTimer = (hours * 3600 + minutes * 60 + seconds) * 1000;
            }

            this.manualTimerEditing = false;

            if (this.wasRunning) {
                this.startManualTimer();
            }
        },

        cancelEditManualTimer(event) {
            if (event.relatedTarget?.classList.contains('timer-save-btn')) {
                return;
            }
            this.manualTimerEditing = false;

            if (this.wasRunning) {
                this.startManualTimer();
            }
        },

        // Modal methods
        openModal(panel) {
            const field = panel.fields[0];
            const data = (this.telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));

            this.modalChart.panelId = panel.id;
            this.modalChart.title = panel.title;
            this.modalChart.unit = panel.unit || '';
            this.modalChart.precision = panel.precision || 0;
            this.modalChart.currentValue = this.getCurrentValue(field);
            this.modalChart.visible = true;

            this.$nextTick(() => {
                const ctx = document.getElementById('modal-chart');
                if (ctx) {
                    this.modalChart.instance = new Chart(ctx, {
                        type: 'line',
                        data: {
                            datasets: [{
                                label: panel.title,
                                data: data,
                                borderColor: panel.chart_color || '#4caf50',
                                backgroundColor: hexToRgba(panel.chart_color || '#4caf50', 0.1),
                                tension: 0.4,
                                pointRadius: 3,
                                pointHoverRadius: 5
                            }]
                        },
                        options: this.getModalChartOptions(panel)
                    });
                }
            });

            document.addEventListener('keydown', this.handleEscKey);
        },

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
                scales: {
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
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: true,
                        mode: 'nearest',
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: panel.chart_color || '#4caf50',
                        borderWidth: 1,
                        padding: 10,
                        displayColors: false,
                        callbacks: {
                            title: (items) => {
                                return `Time: ${items[0].parsed.x.toFixed(3)}s`;
                            },
                            label: (item) => {
                                return `${panel.title}: ${item.parsed.y.toFixed(panel.precision || 2)} ${panel.unit || ''}`;
                            }
                        }
                    },
                    zoom: {
                        pan: {
                            enabled: true,
                            mode: 'xy',
                            modifierKey: null  // No modifier key required - just drag to pan
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
                                enabled: false  // Disable drag-to-zoom box
                            },
                            mode: 'xy'
                        },
                        limits: {
                            x: { min: 'original', max: 'original' },
                            y: { min: 'original', max: 'original' }
                        }
                    }
                }
            };
        },

        updateModalChart() {
            if (this.modalChart.visible && this.modalChart.instance) {
                const panel = this.config.panels.find(p => p.id === this.modalChart.panelId);
                if (panel) {
                    const field = panel.fields[0];
                    const data = (this.telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));
                    this.modalChart.instance.data.datasets[0].data = data;
                    // Update without animation to preserve zoom state
                    this.modalChart.instance.update('none');
                    this.modalChart.currentValue = this.getCurrentValue(field);
                }
            }
        },

        resetZoom() {
            if (this.modalChart.instance) {
                this.modalChart.instance.resetZoom();
            }
        },

        closeModal() {
            if (this.modalChart.instance) {
                this.modalChart.instance.destroy();
                this.modalChart.instance = null;
            }
            this.modalChart.visible = false;
            this.modalChart.panelId = null;

            document.removeEventListener('keydown', this.handleEscKey);
        },

        handleEscKey(event) {
            if (event.key === 'Escape' && this.modalChart.visible) {
                this.closeModal();
            }
        }
    }
}).mount('#app');
