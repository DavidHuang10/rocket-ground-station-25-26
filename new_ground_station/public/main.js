/**
 * ERIS Ground Station Dashboard
 * 
 * Vue 3 application for real-time Eris telemetry visualization.
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
            currentPage: 'eris',  // Default page
            pageData: {},           // Telemetry data per page: {eris: {...}, payload: {...}}
            sessionInfo: {},        // Session info per page
            packetCount: {},        // Packet count per page
            
            // Buffering for race condition prevention: messages that arrive
            // before historical data loads are queued here
            historicalDataLoaded: {},
            messageBuffer: {},

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
        // Current page's telemetry data
        telemetryData() {
            return this.pageData[this.currentPage] || {};
        },
        flightStage() {
            const stageData = this.telemetryData.stage;
            return stageData && stageData.length > 0 ? stageData[stageData.length - 1].value : 0;
        },
        // Get current page's panels from config.pages
        currentPageConfig() {
            if (!this.config?.pages) return null;
            return this.config.pages.find(p => p.id === this.currentPage);
        },
        sortedPanels() {
            if (!this.currentPageConfig) return [];
            return [...this.currentPageConfig.panels].sort((a, b) => a.order - b.order);
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
            // Build empty arrays for each field per page
            if (!this.config?.pages) return;
            
            this.config.pages.forEach(page => {
                this.pageData[page.id] = {};
                this.packetCount[page.id] = 0;
                this.historicalDataLoaded[page.id] = false;
                this.messageBuffer[page.id] = [];
                
                const fields = new Set();
                page.panels.forEach(panel => {
                    if (panel.fields) panel.fields.forEach(f => fields.add(f));
                    if (panel.items) panel.items.forEach(item => { if (item.field) fields.add(item.field); });
                });
                fields.forEach(field => { this.pageData[page.id][field] = []; });
            });
        },
        
        switchPage(pageId) {
            this.currentPage = pageId;
            this.$nextTick(() => {
                this.initCharts();
                this.updateCharts();
            });
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
                
                // Reset per-page buffers
                if (this.config?.pages) {
                    this.config.pages.forEach(page => {
                        this.historicalDataLoaded[page.id] = false;
                        this.messageBuffer[page.id] = [];
                    });
                }

                try {
                    await this.loadCurrentSession();
                    
                    // Mark all pages as loaded and drain buffers
                    if (this.config?.pages) {
                        this.config.pages.forEach(page => {
                            this.historicalDataLoaded[page.id] = true;
                            const buffer = this.messageBuffer[page.id] || [];
                            if (buffer.length > 0) {
                                console.log(`Processing ${buffer.length} buffered messages for ${page.id}`);
                                buffer.forEach(msg => this.processTelemetry(page.id, msg));
                                this.messageBuffer[page.id] = [];
                            }
                        });
                    }
                    this.updateCharts();
                } catch (e) {
                    console.error('Failed to load historical data:', e);
                    if (this.config?.pages) {
                        this.config.pages.forEach(page => {
                            this.historicalDataLoaded[page.id] = true;
                        });
                    }
                }

                this.heartbeatInterval = setInterval(() => {
                    if (this.ws.readyState === WebSocket.OPEN) this.ws.send('ping');
                }, 5000);
            };

            this.ws.onmessage = (event) => {
                if (event.data === 'pong') return;

                try {
                    const message = JSON.parse(event.data);

                    // Handle clear signal with page
                    if (message.type === 'clear') {
                        this.handleClearSignal(message);
                        return;
                    }

                    // Handle page-tagged telemetry: {page: 'eris', data: [...]}
                    if (message.page && message.data) {
                        const pageId = message.page;
                        if (!this.historicalDataLoaded[pageId]) {
                            this.messageBuffer[pageId] = this.messageBuffer[pageId] || [];
                            this.messageBuffer[pageId].push(message.data);
                        } else {
                            this.processTelemetry(pageId, message.data);
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
            if (this.ws) {
                // Remove onclose listener to prevent auto-reconnect trigger
                this.ws.onclose = null;
                this.ws.close();
            }
            this.connected = false;
            this.connect();
        },

        /*
         * ============================================
         * TELEMETRY DATA PROCESSING
         * ============================================
         */

        processTelemetry(pageId, telemetryArray) {
            // Each packet is an array of {time, source, value} objects for a specific page
            this.packetCount[pageId] = (this.packetCount[pageId] || 0) + 1;
            const pageData = this.pageData[pageId];
            if (!pageData) return;
            
            for (const { time, source, value } of telemetryArray) {
                if (pageData.hasOwnProperty(source)) {
                    pageData[source].push({ time, value });
                }
            }
            
            // Only update charts if this is the current page
            if (pageId === this.currentPage) {
                this.updateCharts();
            }
        },

        async loadCurrentSession() {
            console.log('Loading current session for all pages...');
            
            if (!this.config?.pages) return;
            
            // Load data for each page
            for (const page of this.config.pages) {
                const pageId = page.id;
                
                // Clear existing data
                for (const key in this.pageData[pageId]) {
                    this.pageData[pageId][key] = [];
                }
                this.packetCount[pageId] = 0;
                
                try {
                    const response = await fetch(`/telemetry/current/${pageId}`);
                    const result = await response.json();
                    
                    if (result.data) {
                        let loaded = 0;
                        result.data.forEach(({ time, source, value }) => {
                            if (this.pageData[pageId].hasOwnProperty(source)) {
                                this.pageData[pageId][source].push({ time, value });
                                loaded++;
                            }
                        });
                        
                        this.sessionInfo[pageId] = result.session;
                        this.packetCount[pageId] = result.session?.packet_count || 0;
                        console.log(`Loaded ${loaded} data points for ${pageId}`);
                    }
                } catch (e) {
                    console.error(`Failed to load session for ${pageId}:`, e);
                }
            }
            
            this.$nextTick(() => this.updateCharts());
        },

        handleClearSignal(message) {
            // Clear chart data for specific page
            const pageId = message.page;
            if (!pageId || !this.pageData[pageId]) return;
            
            for (const key in this.pageData[pageId]) {
                this.pageData[pageId][key] = [];
            }
            this.packetCount[pageId] = 0;
            
            if (pageId === this.currentPage) {
                this.updateCharts();
            }

            if (message.takeoff_offset !== null) {
                console.log(`Takeoff for ${pageId}! T+0 = ${message.takeoff_time}`);
            } else {
                console.log(`Charts cleared for ${pageId}`);
            }
        },

        /*
         * ============================================
         * CHART MANAGEMENT
         * ============================================
         */

        initCharts() {
            // Destroy existing charts first
            Object.values(this._charts).forEach(chart => {
                if (chart) chart.destroy();
            });
            this._charts = {};
            
            // Create charts for current page panels only
            if (!this.currentPageConfig) return;
            
            this.currentPageConfig.panels.forEach(panel => {
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
            if (!this.currentPageConfig) return;
            
            this.currentPageConfig.panels.forEach(panel => {
                const chart = this._charts[panel.id];
                if (!chart) return;

                const field = panel.fields[0];
                const data = (this.telemetryData[field] || []).map(d => ({ x: d.time, y: d.value }));
                chart.data.datasets[0].data = data;
                chart.update('none');
            });

            // Keep modal chart in sync if open
            if (this.modalChart.visible && this.chartManager?.modalChart) {
                const panel = this.currentPageConfig.panels.find(p => p.id === this.modalChart.panelId);
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
            if (!confirm(`Clear ${this.currentPage} charts and mark takeoff?\n\nPre-flight data will be backed up.`)) return;

            try {
                const response = await fetch(`/telemetry/clear/${this.currentPage}`, { method: 'POST' });
                const result = await response.json();
                if (result.status === 'success') {
                    console.log(`${this.currentPage} takeoff marked, charts cleared`);
                } else if (result.status === 'error') {
                    alert(result.message);
                }
            } catch (e) {
                alert(`Failed to clear charts: ${e.message}`);
            }
        },

        async saveFlight() {
            try {
                const response = await fetch(`/telemetry/save/${this.currentPage}`, { method: 'POST' });
                const result = await response.json();
                if (result.status === 'success') {
                    alert(`${this.currentPage} flight saved as ${result.filename}`);
                    console.log('Flight saved:', result.filename);
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
            const panel = this.currentPageConfig?.panels.find(p => p.id === 'flight_stage' || p.id === 'destination_status');
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
            return this.packetCount[this.currentPage] || 0;
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
