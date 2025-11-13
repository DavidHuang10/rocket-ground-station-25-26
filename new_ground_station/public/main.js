const { createApp } = Vue;

createApp({
    data() {
        return {
            port: 8000,
            ws: null,
            connected: false,
            config: null,
            telemetryData: {},
            maxDataPoints: null,  // No limit - store all data
            heartbeatInterval: null,
            sessionInfo: null,
            // Manual timer
            manualTimer: 0,
            manualTimerRunning: false,
            manualTimerInterval: null,
            manualTimerEditing: false
        };
    },

    created() {
        // Store charts outside Vue's reactive system to avoid stack overflow
        this._charts = {};
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
            return this.config ? [...this.config.panels].sort((a, b) => a.order - b.order) : [];
        }
    },

    async mounted() {
        const urlParams = new URLSearchParams(window.location.search);
        const urlPort = urlParams.get('port');
        if (urlPort) {
            this.port = parseInt(urlPort);
        }

        await this.loadConfig();
        await this.loadCurrentSession();
        this.initTelemetryData();
        await this.$nextTick();
        this.initCharts();
        this.connect();
    },

    beforeUnmount() {
        if (this.ws) {
            this.ws.close();
        }
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }
    },

    methods: {
        async loadConfig() {
            try {
                const response = await fetch('/config.json');
                this.config = await response.json();
                console.log('Configuration loaded:', this.config);
            } catch (e) {
                console.error('Failed to load configuration:', e);
                // Fallback to empty config
                this.config = { panels: [], field_metadata: {} };
            }
        },

        initTelemetryData() {
            // Build telemetry data structure from all fields in config
            const fields = new Set();

            this.config.panels.forEach(panel => {
                if (panel.fields) {
                    panel.fields.forEach(f => fields.add(f));
                }
                if (panel.items) {
                    panel.items.forEach(item => {
                        if (item.field) fields.add(item.field);
                    });
                }
            });

            fields.forEach(field => {
                this.telemetryData[field] = [];
            });
        },

        connect() {
            const wsUrl = `ws://localhost:${this.port}/ws`;
            console.log(`Connecting to ${wsUrl}...`);

            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.connected = true;

                // Start heartbeat
                this.heartbeatInterval = setInterval(() => {
                    if (this.ws.readyState === WebSocket.OPEN) {
                        this.ws.send('ping');
                    }
                }, 5000);
            };

            this.ws.onmessage = (event) => {
                const data = event.data;

                // Handle pong
                if (data === 'pong') {
                    return;
                }

                // Process telemetry data
                try {
                    const telemetryArray = JSON.parse(data);
                    this.processTelemetry(telemetryArray);
                } catch (e) {
                    console.error('Failed to parse telemetry:', e);
                }
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.connected = false;

                if (this.heartbeatInterval) {
                    clearInterval(this.heartbeatInterval);
                }

                // Auto-reconnect after 1 second
                setTimeout(() => {
                    this.connect();
                }, 1000);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        },

        reconnect() {
            if (this.ws) {
                this.ws.close();
            }
            this.connect();
        },

        processTelemetry(telemetryArray) {
            // telemetryArray format: [{time, source, value}, ...]
            for (const item of telemetryArray) {
                const { time, source, value } = item;

                if (this.telemetryData.hasOwnProperty(source)) {
                    // Add data point (no trimming - store all data)
                    this.telemetryData[source].push({ time, value });
                }
            }

            // Update charts
            this.updateCharts();
        },

        initCharts() {
            this.config.panels.forEach(panel => {
                if (panel.type === 'chart') {
                    const canvasId = `chart-${panel.id}`;
                    const ctx = document.getElementById(canvasId);
                    if (ctx) {
                        this._charts[panel.id] = new Chart(ctx, {
                            type: 'line',
                            data: {
                                datasets: [{
                                    label: panel.title,
                                    data: [],
                                    borderColor: panel.chart_color || '#4caf50',
                                    backgroundColor: this.hexToRgba(panel.chart_color || '#4caf50', 0.1),
                                    tension: 0.4,
                                    pointRadius: 0
                                }]
                            },
                            options: this.getChartOptions(panel)
                        });
                    }
                }
            });
        },

        updateCharts() {
            this.config.panels.forEach(panel => {
                const chart = this._charts[panel.id];
                if (chart) {
                    const field = panel.fields[0];
                    const data = (this.telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));
                    chart.data.datasets[0].data = data;
                    chart.update('none');
                }
            });
        },

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
        },

        getCurrentValue(source) {
            const data = this.telemetryData[source];
            if (data && data.length > 0) {
                return data[data.length - 1].value;
            }
            return 0;
        },

        formatValue(value, precision) {
            if (value === null || value === undefined) return '0';
            if (typeof value === 'number') {
                return value.toFixed(precision || 0);
            }
            return value.toString();
        },

        formatTimer(milliseconds) {
            if (!milliseconds || milliseconds < 0) return '00:00';

            const totalSeconds = Math.floor(milliseconds / 1000);
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;

            if (hours > 0) {
                return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            }
            return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
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
            // Get the most recent time value from any telemetry source
            for (const source in this.telemetryData) {
                const data = this.telemetryData[source];
                if (data && data.length > 0) {
                    return data[data.length - 1].time;
                }
            }
            return 0;
        },

        hexToRgba(hex, alpha) {
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        },

        async loadCurrentSession() {
            try {
                const response = await fetch(`http://localhost:${this.port}/telemetry/current`);
                const result = await response.json();

                // Load all existing data from backend
                result.data.forEach(item => {
                    const { time, source, value } = item;
                    if (this.telemetryData.hasOwnProperty(source)) {
                        this.telemetryData[source].push({ time, value });
                    }
                });

                this.sessionInfo = result.session;
                console.log(`Loaded ${result.data.length} data points from session`);
            } catch (e) {
                console.error('Failed to load session:', e);
            }
        },

        async clearCharts() {
            if (!confirm('Clear all chart data?\n\nThis cannot be undone unless you save first.')) {
                return;
            }

            try {
                const response = await fetch(`http://localhost:${this.port}/telemetry/clear`, {
                    method: 'POST'
                });
                const result = await response.json();

                if (result.status === 'success') {
                    // Clear frontend data
                    for (const key in this.telemetryData) {
                        this.telemetryData[key] = [];
                    }
                    this.updateCharts();

                    console.log('✅ Charts cleared');
                }
            } catch (e) {
                alert(`Failed to clear charts: ${e.message}`);
            }
        },

        async saveFlight() {
            try {
                const response = await fetch(`http://localhost:${this.port}/telemetry/save`, {
                    method: 'POST'
                });
                const result = await response.json();

                if (result.status === 'success') {
                    alert(`Flight saved as ${result.filename}`);
                    console.log('✅ Flight saved:', result.filename);
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
                const response = await fetch(`http://localhost:${this.port}/telemetry/save-and-clear`, {
                    method: 'POST'
                });
                const result = await response.json();

                if (result.status === 'success') {
                    // Clear frontend data
                    for (const key in this.telemetryData) {
                        this.telemetryData[key] = [];
                    }
                    this.updateCharts();

                    alert(`Flight saved as ${result.filename}`);
                    console.log('✅ Flight saved and cleared:', result.filename);
                }
            } catch (e) {
                alert(`Failed to save and clear: ${e.message}`);
            }
        },

        getTotalPackets() {
            if (!this.sessionInfo) return 0;
            return this.sessionInfo.packet_count || 0;
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
            if (this.manualTimerInterval) return; // Prevent duplicate intervals
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
            // Pause timer while editing
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

            // Validate format
            if (parts.length !== 2 && parts.length !== 3) {
                alert('Invalid format. Use MM:SS or HH:MM:SS');
                return;
            }

            // Parse and validate numbers
            const numbers = parts.map(p => parseInt(p));
            if (numbers.some(n => isNaN(n) || n < 0)) {
                alert('Invalid time values. Use positive numbers only.');
                return;
            }

            // Validate ranges
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

            // Resume if it was running
            if (this.wasRunning) {
                this.startManualTimer();
            }
        },

        cancelEditManualTimer(event) {
            // Only cancel if not pressing Enter
            if (event.relatedTarget?.classList.contains('timer-save-btn')) {
                return;
            }
            this.manualTimerEditing = false;

            // Resume if it was running
            if (this.wasRunning) {
                this.startManualTimer();
            }
        }
    }
}).mount('#app');
