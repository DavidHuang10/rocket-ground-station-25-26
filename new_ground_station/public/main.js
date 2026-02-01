/**
 * ERIS Ground Station Dashboard
 * 
 * Vue 3 application for real-time rocket telemetry visualization.
 * Connects via WebSocket for live data, fetches historical data on load,
 * and displays telemetry in configurable chart/indicator panels.
 */

import { ChartManager } from './js/managers/ChartManager.js';

const { createApp } = Vue;

createApp({
    data() {
        return {
            // Connection state
            ws: null,
            connected: false,
            heartbeatInterval: null,

            // Data management
            config: null,
            telemetryData: {},
            sessionInfo: null,
            packetCount: 0,
            
            // Buffering for race condition prevention: messages that arrive
            // before historical data loads are queued here
            historicalDataLoaded: false,
            messageBuffer: [],

            // Manual stopwatch timer (separate from telemetry time)
            manualTimer: 0,
            manualTimerRunning: false,
            manualTimerInterval: null,
            manualTimerEditing: false,

            // Expanded chart modal state
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
        // Charts stored outside Vue reactivity to prevent stack overflow
        // with Chart.js's complex object structure
        this._charts = {};
        this.chartManager = null;
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
        await this.loadConfig();
        this.initTelemetryData();
        await this.$nextTick();
        this.initCharts();
        this.chartManager = new ChartManager();
        this.connect();
    },

    beforeUnmount() {
        if (this.ws) this.ws.close();
        if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
    },

    methods: {
        /*
         * ============================================
         * CONFIGURATION & INITIALIZATION
         * ============================================
         */

        async loadConfig() {
            try {
                const response = await fetch('/config.json');
                this.config = await response.json();
                console.log('Configuration loaded:', this.config);
            } catch (e) {
                console.error('Failed to load configuration:', e);
                this.config = { panels: [], field_metadata: {} };
            }
        },

        initTelemetryData() {
            // Build empty arrays for each field defined in config panels
            const fields = new Set();
            this.config.panels.forEach(panel => {
                if (panel.fields) panel.fields.forEach(f => fields.add(f));
                if (panel.items) panel.items.forEach(item => { if (item.field) fields.add(item.field); });
            });
            fields.forEach(field => { this.telemetryData[field] = []; });
        },

        /*
         * ============================================
         * WEBSOCKET CONNECTION
         * 
         * On connect: fetch historical data FIRST, then process live messages.
         * Messages arriving during historical load are buffered to prevent
         * race conditions that cause chart artifacts.
         * ============================================
         */

        connect() {
            const wsUrl = `ws://${window.location.host}/ws`;
            console.log(`Connecting to ${wsUrl}...`);
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = async () => {
                console.log('WebSocket connected');
                this.connected = true;
                this.historicalDataLoaded = false;
                this.messageBuffer = [];

                try {
                    await this.loadCurrentSession();
                    this.historicalDataLoaded = true;

                    // Drain buffered messages that arrived during load
                    if (this.messageBuffer.length > 0) {
                        console.log(`📬 Processing ${this.messageBuffer.length} buffered messages`);
                        this.messageBuffer.forEach(msg => this.processTelemetry(msg));
                        this.messageBuffer = [];
                    }
                    this.updateCharts();
                } catch (e) {
                    console.error('Failed to load historical data:', e);
                    this.historicalDataLoaded = true;
                }

                this.heartbeatInterval = setInterval(() => {
                    if (this.ws.readyState === WebSocket.OPEN) this.ws.send('ping');
                }, 5000);
            };

            this.ws.onmessage = (event) => {
                if (event.data === 'pong') return;

                try {
                    const message = JSON.parse(event.data);

                    if (message.type === 'clear') {
                        this.handleClearSignal(message);
                        return;
                    }

                    if (Array.isArray(message)) {
                        if (!this.historicalDataLoaded) {
                            this.messageBuffer.push(message);
                        } else {
                            this.processTelemetry(message);
                        }
                    }
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.connected = false;
                if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
                setTimeout(() => this.connect(), 1000);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        },

        reconnect() {
            if (this.ws) this.ws.close();
            this.connect();
        },

        /*
         * ============================================
         * TELEMETRY DATA PROCESSING
         * ============================================
         */

        processTelemetry(telemetryArray) {
            // Each packet is an array of {time, source, value} objects
            this.packetCount++;
            for (const { time, source, value } of telemetryArray) {
                if (this.telemetryData.hasOwnProperty(source)) {
                    this.telemetryData[source].push({ time, value });
                }
            }
            this.updateCharts();
        },

        async loadCurrentSession() {
            console.log('🔄 Loading current session...');
            const response = await fetch('/telemetry/current');
            const result = await response.json();

            let loaded = 0;
            result.data.forEach(({ time, source, value }) => {
                if (this.telemetryData.hasOwnProperty(source)) {
                    this.telemetryData[source].push({ time, value });
                    loaded++;
                }
            });

            this.sessionInfo = result.session;
            this.packetCount = result.session?.packet_count || 0;
            console.log(`✅ Loaded ${loaded} data points`);

            this.$nextTick(() => this.updateCharts());
        },

        handleClearSignal(message) {
            // Clear all chart data and reset packet count
            for (const key in this.telemetryData) {
                this.telemetryData[key] = [];
            }
            this.packetCount = 0;
            this.updateCharts();

            if (message.takeoff_offset !== null) {
                console.log(`🚀 Takeoff! T+0 = ${message.takeoff_time}`);
            } else {
                console.log('📊 Charts cleared for new session');
            }
        },

        /*
         * ============================================
         * CHART MANAGEMENT
         * ============================================
         */

        initCharts() {
            this.config.panels.forEach(panel => {
                if (panel.type !== 'chart') return;

                const ctx = document.getElementById(`chart-${panel.id}`);
                if (!ctx) return;

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
            });
        },

        updateCharts() {
            this.config.panels.forEach(panel => {
                const chart = this._charts[panel.id];
                if (!chart) return;

                const field = panel.fields[0];
                const data = (this.telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));
                chart.data.datasets[0].data = data;
                chart.update('none');
            });

            // Keep modal chart in sync if open
            if (this.modalChart.visible && this.chartManager?.modalChart) {
                const panel = this.config.panels.find(p => p.id === this.modalChart.panelId);
                if (panel) {
                    this.chartManager.updateModalChart(this.telemetryData, panel.fields[0]);
                    this.modalChart.currentValue = this.getCurrentValue(panel.fields[0]);
                }
            }
        },

        getChartOptions(panel) {
            return {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: {
                        type: 'linear',
                        title: { display: true, text: 'Time (s)' },
                        ticks: { autoSkip: true, maxTicksLimit: 10 }
                    },
                    y: {
                        title: { display: true, text: `${panel.title} (${panel.unit || ''})` },
                        ticks: { autoSkip: true, maxTicksLimit: 8 }
                    }
                },
                plugins: { legend: { display: false } }
            };
        },

        /*
         * ============================================
         * SESSION ACTIONS (SAVE / CLEAR)
         * ============================================
         */

        async clearCharts() {
            if (!confirm('Clear charts and mark takeoff?\n\nPre-flight data will be backed up.')) return;

            try {
                const response = await fetch('/telemetry/clear', { method: 'POST' });
                const result = await response.json();
                if (result.status === 'success') {
                    console.log('✅ Takeoff marked, charts cleared');
                } else if (result.status === 'error') {
                    alert(result.message);
                }
            } catch (e) {
                alert(`Failed to clear charts: ${e.message}`);
            }
        },

        async saveFlight() {
            try {
                const response = await fetch('/telemetry/save', { method: 'POST' });
                const result = await response.json();
                if (result.status === 'success') {
                    alert(`Flight saved as ${result.filename}`);
                    console.log('✅ Flight saved:', result.filename);
                }
            } catch (e) {
                alert(`Failed to save flight: ${e.message}`);
            }
        },

        /*
         * ============================================
         * UTILITY METHODS
         * ============================================
         */

        getCurrentValue(source) {
            const data = this.telemetryData[source];
            return data && data.length > 0 ? data[data.length - 1].value : 0;
        },

        formatValue(value, precision) {
            if (value === null || value === undefined) return '0';
            return typeof value === 'number' ? value.toFixed(precision || 0) : value.toString();
        },

        formatTimer(ms) {
            if (!ms || ms < 0) return '00:00';
            const totalSec = Math.floor(ms / 1000);
            const h = Math.floor(totalSec / 3600);
            const m = Math.floor((totalSec % 3600) / 60);
            const s = totalSec % 60;
            const pad = n => n.toString().padStart(2, '0');
            return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
        },

        getStageName(stage) {
            const panel = this.config?.panels.find(p => p.id === 'flight_stage');
            return panel?.mapping?.[stage] || stage.toString();
        },

        getContinuityClass(source) {
            return this.getCurrentValue(source) === 1 ? 'good' : 'bad';
        },

        getCurrentTime() {
            for (const source in this.telemetryData) {
                const data = this.telemetryData[source];
                if (data && data.length > 0) return data[data.length - 1].time;
            }
            return 0;
        },

        hexToRgba(hex, alpha) {
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        },

        getTotalPackets() {
            return this.packetCount;
        },

        /*
         * ============================================
         * MANUAL TIMER (STOPWATCH)
         * 
         * Independent timer for manual timing during operations.
         * Click display to edit, supports MM:SS or HH:MM:SS input.
         * ============================================
         */

        toggleManualTimer() {
            this.manualTimerRunning ? this.pauseManualTimer() : this.startManualTimer();
        },

        startManualTimer() {
            if (this.manualTimerInterval) return;
            this.manualTimerRunning = true;
            this.manualTimerInterval = setInterval(() => { this.manualTimer += 100; }, 100);
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
            if (this.manualTimerRunning) this.pauseManualTimer();

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
            const parts = event.target.value.trim().split(':').map(p => parseInt(p.trim()));

            if (parts.length < 2 || parts.length > 3 || parts.some(n => isNaN(n) || n < 0)) {
                alert('Invalid format. Use MM:SS or HH:MM:SS');
                return;
            }

            if (parts.length === 2) {
                const [m, s] = parts;
                if (s >= 60) { alert('Seconds must be < 60'); return; }
                this.manualTimer = (m * 60 + s) * 1000;
            } else {
                const [h, m, s] = parts;
                if (m >= 60 || s >= 60) { alert('Minutes/seconds must be < 60'); return; }
                this.manualTimer = (h * 3600 + m * 60 + s) * 1000;
            }

            this.manualTimerEditing = false;
            if (this.wasRunning) this.startManualTimer();
        },

        cancelEditManualTimer(event) {
            if (event.relatedTarget?.classList.contains('timer-save-btn')) return;
            this.manualTimerEditing = false;
            if (this.wasRunning) this.startManualTimer();
        },

        /*
         * ============================================
         * MODAL CHART (EXPANDED VIEW)
         * 
         * Click any chart panel to open fullscreen with zoom/pan.
         * ============================================
         */

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
                if (this.chartManager) {
                    this.modalChart.instance = this.chartManager.createModalChart('modal-chart', panel, data);
                }
            });
            document.addEventListener('keydown', this.handleEscKey);
        },

        resetZoom() {
            if (this.chartManager) this.chartManager.resetModalZoom();
        },

        closeModal() {
            if (this.chartManager) this.chartManager.destroyModalChart();
            this.modalChart.instance = null;
            this.modalChart.visible = false;
            this.modalChart.panelId = null;
            document.removeEventListener('keydown', this.handleEscKey);
        },

        handleEscKey(event) {
            if (event.key === 'Escape' && this.modalChart.visible) this.closeModal();
        }
    }
}).mount('#app');
