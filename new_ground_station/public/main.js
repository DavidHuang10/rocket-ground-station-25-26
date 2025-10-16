const { createApp } = Vue;

createApp({
    data() {
        return {
            port: 8000,
            ws: null,
            connected: false,
            config: null,
            telemetryData: {},
            maxDataPoints: 100,
            heartbeatInterval: null
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
                    // Add data point
                    this.telemetryData[source].push({ time, value });

                    // Trim to max data points
                    if (this.telemetryData[source].length > this.maxDataPoints) {
                        this.telemetryData[source].shift();
                    }
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
        }
    }
}).mount('#app');
