# Implementation Plan: Frontend Integration (Part 4)

## Overview
Adapt existing Vue.js frontend from `ground_station/` to work with new FastAPI backend, maintaining all visualization features.

## Resources

### Existing Frontend Structure
From `ground_station/`:
- `public/index.html` - Main landing page with route links
- `public/dash.html` - Dashboard with charts and indicators
- `public/overlay.html` - Minimal overlay view
- `public/main.js` - Vue.js WebSocket client and data management
- `public/chart.js` - Chart.js integration for line charts
- `public/style.css` - Styling

### Frontend WebSocket Client Pattern
From `ground_station/public/main.js:108-166`:
- Connects to WebSocket with port from URL parameter
- Receives array format: `[{time, source, value}, ...]`
- Auto-reconnect with 1 second delay on disconnect
- Heartbeat ping/pong every 5 seconds
- Updates Vue reactive data store

### Data Sources Expected by Frontend
From `ground_station/public/main.js:124-156`:
- altitude, velocity, battery_voltage
- accelx, accely, accelz
- gyrox, gyroy, gyroz
- temp, pressure
- lat, long
- stage (flight stage)
- Various servo and continuity indicators

## Implementation

### File: `new_ground_station/public/dash.html`

Copy from existing `ground_station/public/dash.html` and adapt:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ERIS Ground Station - Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>ERIS Delta Ground Station</h1>
            <div class="connection-status" :class="connectionStatus">
                {{ connectionText }}
            </div>
        </header>

        <div class="controls">
            <label>
                WebSocket Port:
                <input type="number" v-model="port" min="1" max="65535">
            </label>
            <button @click="reconnect">Reconnect</button>
        </div>

        <div class="dashboard">
            <!-- Flight Stage Indicator -->
            <div class="panel">
                <h2>Flight Stage</h2>
                <div class="stage-indicator">
                    <div class="stage-value">{{ flightStage }}</div>
                    <div class="stage-name">{{ getStageName(flightStage) }}</div>
                </div>
            </div>

            <!-- Altitude Chart -->
            <div class="panel chart-panel">
                <h2>Altitude (m AGL)</h2>
                <canvas id="altitudeChart"></canvas>
                <div class="current-value">{{ getCurrentValue('altitude') }} m</div>
            </div>

            <!-- Velocity Chart -->
            <div class="panel chart-panel">
                <h2>Velocity (m/s)</h2>
                <canvas id="velocityChart"></canvas>
                <div class="current-value">{{ getCurrentValue('velocity') }} m/s</div>
            </div>

            <!-- Battery Voltage -->
            <div class="panel">
                <h2>Battery Voltage</h2>
                <div class="large-value">{{ getCurrentValue('battery_voltage') }} V</div>
            </div>

            <!-- GPS Coordinates -->
            <div class="panel">
                <h2>GPS Position</h2>
                <div class="gps-data">
                    <div>Lat: {{ getCurrentValue('lat').toFixed(7) }}°</div>
                    <div>Lng: {{ getCurrentValue('long').toFixed(7) }}°</div>
                    <div>Alt: {{ getCurrentValue('gps_alt').toFixed(1) }} m</div>
                </div>
            </div>

            <!-- Accelerometer Chart -->
            <div class="panel chart-panel">
                <h2>Acceleration (m/s²)</h2>
                <canvas id="accelChart"></canvas>
            </div>

            <!-- Gyroscope Chart -->
            <div class="panel chart-panel">
                <h2>Gyroscope (rad/s)</h2>
                <canvas id="gyroChart"></canvas>
            </div>

            <!-- Temperature and Pressure -->
            <div class="panel">
                <h2>Environmental</h2>
                <div class="env-data">
                    <div>Temp: {{ getCurrentValue('temp').toFixed(1) }} °C</div>
                    <div>Press: {{ getCurrentValue('pressure').toFixed(2) }} hPa</div>
                </div>
            </div>

            <!-- Servo Positions -->
            <div class="panel">
                <h2>Servo Positions</h2>
                <div class="servo-data">
                    <div>Airbrake: {{ getCurrentValue('ab_servo').toFixed(1) }}%</div>
                    <div>Canard: {{ getCurrentValue('cnrd_servo').toFixed(1) }}%</div>
                </div>
            </div>

            <!-- Pyro Continuity -->
            <div class="panel">
                <h2>Pyro Continuity</h2>
                <div class="continuity-grid">
                    <div :class="['continuity-indicator', getContinuityClass('drogue_cont_1')]">
                        Drogue 1
                    </div>
                    <div :class="['continuity-indicator', getContinuityClass('drogue_cont_2')]">
                        Drogue 2
                    </div>
                    <div :class="['continuity-indicator', getContinuityClass('main_cont_1')]">
                        Main 1
                    </div>
                    <div :class="['continuity-indicator', getContinuityClass('main_cont_2')]">
                        Main 2
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="main.js"></script>
</body>
</html>
```

### File: `new_ground_station/public/main.js`

```javascript
const { createApp } = Vue;

createApp({
    data() {
        return {
            port: 8000,
            ws: null,
            connected: false,
            telemetryData: {
                altitude: [],
                velocity: [],
                smooth_vel: [],
                battery_voltage: [],
                accelx: [],
                accely: [],
                accelz: [],
                gyrox: [],
                gyroy: [],
                gyroz: [],
                hg_accel: [],
                temp: [],
                pressure: [],
                lat: [],
                long: [],
                gps_alt: [],
                stage: [],
                ab_servo: [],
                cnrd_servo: [],
                drogue_cont_1: [],
                drogue_cont_2: [],
                main_cont_1: [],
                main_cont_2: [],
                airbrake_cont: []
            },
            charts: {},
            maxDataPoints: 100,
            heartbeatInterval: null
        };
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
            return stageData.length > 0 ? stageData[stageData.length - 1].value : 0;
        }
    },

    mounted() {
        // Get port from URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        const urlPort = urlParams.get('port');
        if (urlPort) {
            this.port = parseInt(urlPort);
        }

        // Initialize charts
        this.initCharts();

        // Connect to WebSocket
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
            // Altitude chart
            const altCtx = document.getElementById('altitudeChart');
            if (altCtx) {
                this.charts.altitude = new Chart(altCtx, {
                    type: 'line',
                    data: {
                        datasets: [{
                            label: 'Altitude',
                            data: [],
                            borderColor: '#4caf50',
                            backgroundColor: 'rgba(76, 175, 80, 0.1)',
                            tension: 0.4
                        }]
                    },
                    options: this.getChartOptions('Time (s)', 'Altitude (m)')
                });
            }

            // Velocity chart
            const velCtx = document.getElementById('velocityChart');
            if (velCtx) {
                this.charts.velocity = new Chart(velCtx, {
                    type: 'line',
                    data: {
                        datasets: [{
                            label: 'Velocity',
                            data: [],
                            borderColor: '#2196f3',
                            backgroundColor: 'rgba(33, 150, 243, 0.1)',
                            tension: 0.4
                        }]
                    },
                    options: this.getChartOptions('Time (s)', 'Velocity (m/s)')
                });
            }

            // Accelerometer chart (3 axes)
            const accelCtx = document.getElementById('accelChart');
            if (accelCtx) {
                this.charts.accel = new Chart(accelCtx, {
                    type: 'line',
                    data: {
                        datasets: [
                            {
                                label: 'X',
                                data: [],
                                borderColor: '#f44336',
                                tension: 0.4
                            },
                            {
                                label: 'Y',
                                data: [],
                                borderColor: '#4caf50',
                                tension: 0.4
                            },
                            {
                                label: 'Z',
                                data: [],
                                borderColor: '#2196f3',
                                tension: 0.4
                            }
                        ]
                    },
                    options: this.getChartOptions('Time (s)', 'Accel (m/s²)')
                });
            }

            // Gyroscope chart (3 axes)
            const gyroCtx = document.getElementById('gyroChart');
            if (gyroCtx) {
                this.charts.gyro = new Chart(gyroCtx, {
                    type: 'line',
                    data: {
                        datasets: [
                            {
                                label: 'X',
                                data: [],
                                borderColor: '#f44336',
                                tension: 0.4
                            },
                            {
                                label: 'Y',
                                data: [],
                                borderColor: '#4caf50',
                                tension: 0.4
                            },
                            {
                                label: 'Z',
                                data: [],
                                borderColor: '#2196f3',
                                tension: 0.4
                            }
                        ]
                    },
                    options: this.getChartOptions('Time (s)', 'Gyro (rad/s)')
                });
            }
        },

        updateCharts() {
            // Update altitude chart
            if (this.charts.altitude) {
                this.charts.altitude.data.datasets[0].data = this.telemetryData.altitude.map(
                    d => ({ x: d.time, y: d.value })
                );
                this.charts.altitude.update('none');
            }

            // Update velocity chart
            if (this.charts.velocity) {
                this.charts.velocity.data.datasets[0].data = this.telemetryData.velocity.map(
                    d => ({ x: d.time, y: d.value })
                );
                this.charts.velocity.update('none');
            }

            // Update accelerometer chart
            if (this.charts.accel) {
                this.charts.accel.data.datasets[0].data = this.telemetryData.accelx.map(
                    d => ({ x: d.time, y: d.value })
                );
                this.charts.accel.data.datasets[1].data = this.telemetryData.accely.map(
                    d => ({ x: d.time, y: d.value })
                );
                this.charts.accel.data.datasets[2].data = this.telemetryData.accelz.map(
                    d => ({ x: d.time, y: d.value })
                );
                this.charts.accel.update('none');
            }

            // Update gyroscope chart
            if (this.charts.gyro) {
                this.charts.gyro.data.datasets[0].data = this.telemetryData.gyrox.map(
                    d => ({ x: d.time, y: d.value })
                );
                this.charts.gyro.data.datasets[1].data = this.telemetryData.gyroy.map(
                    d => ({ x: d.time, y: d.value })
                );
                this.charts.gyro.data.datasets[2].data = this.telemetryData.gyroz.map(
                    d => ({ x: d.time, y: d.value })
                );
                this.charts.gyro.update('none');
            }
        },

        getChartOptions(xLabel, yLabel) {
            return {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: {
                        type: 'linear',
                        title: {
                            display: true,
                            text: xLabel
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: yLabel
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true
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

        getStageName(stage) {
            const stages = [
                'Standby',
                'Armed',
                'Boost',
                'Coast',
                'Drogue',
                'Main',
                'Landed'
            ];
            return stages[stage] || 'Unknown';
        },

        getContinuityClass(source) {
            const value = this.getCurrentValue(source);
            return value === 1 ? 'good' : 'bad';
        }
    }
}).mount('#app');
```

### File: `new_ground_station/public/style.css`

```css
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background-color: #0a0a0a;
    color: #ffffff;
    line-height: 1.6;
}

header {
    background-color: #1a1a1a;
    padding: 20px;
    border-bottom: 2px solid #333;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

h1 {
    font-size: 24px;
    font-weight: 600;
}

h2 {
    font-size: 16px;
    font-weight: 500;
    margin-bottom: 15px;
    color: #aaa;
}

.connection-status {
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: 500;
}

.connection-status.connected {
    background-color: #1b5e20;
    border: 1px solid #4caf50;
}

.connection-status.disconnected {
    background-color: #5c1010;
    border: 1px solid #f44336;
}

.controls {
    background-color: #1a1a1a;
    padding: 15px 20px;
    border-bottom: 1px solid #333;
    display: flex;
    gap: 15px;
    align-items: center;
}

.controls label {
    display: flex;
    align-items: center;
    gap: 10px;
}

.controls input {
    background-color: #2a2a2a;
    border: 1px solid #444;
    color: #fff;
    padding: 6px 10px;
    border-radius: 4px;
    width: 100px;
}

.controls button {
    background-color: #2196f3;
    color: white;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
}

.controls button:hover {
    background-color: #1976d2;
}

.dashboard {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    padding: 20px;
}

.panel {
    background-color: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 20px;
}

.chart-panel {
    min-height: 300px;
}

.chart-panel canvas {
    max-height: 250px;
}

.current-value {
    text-align: center;
    font-size: 20px;
    font-weight: 600;
    margin-top: 10px;
    color: #4caf50;
}

.large-value {
    font-size: 48px;
    font-weight: 700;
    text-align: center;
    color: #2196f3;
}

.stage-indicator {
    text-align: center;
}

.stage-value {
    font-size: 72px;
    font-weight: 700;
    color: #ff9800;
}

.stage-name {
    font-size: 24px;
    color: #aaa;
    margin-top: 10px;
}

.gps-data, .env-data, .servo-data {
    font-size: 18px;
    line-height: 2;
}

.continuity-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}

.continuity-indicator {
    padding: 15px;
    text-align: center;
    border-radius: 4px;
    font-weight: 600;
}

.continuity-indicator.good {
    background-color: #1b5e20;
    border: 2px solid #4caf50;
}

.continuity-indicator.bad {
    background-color: #5c1010;
    border: 2px solid #f44336;
}
```

## Testing

### Manual Test Steps

1. **Copy frontend files**:
   ```bash
   # Ensure files are in new_ground_station/public/
   ```

2. **Start server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

3. **Open dashboard**:
   - Navigate to `http://localhost:8000/dash.html`

4. **Verify connection**:
   - Connection status should show "Connected"
   - Should see "Connected" in green in header

5. **Verify charts updating**:
   - Altitude chart should show line graph updating
   - Velocity chart should update
   - Accelerometer chart should show 3 lines (X, Y, Z)
   - Gyroscope chart should show 3 lines

6. **Verify data displays**:
   - Flight stage should show number and name
   - Battery voltage should display
   - GPS coordinates should display
   - Temperature and pressure should display
   - Servo positions should display
   - Continuity indicators should be colored (green/red)

7. **Test port parameter**:
   - Navigate to `http://localhost:8000/dash.html?port=8000`
   - Should connect to specified port

8. **Test reconnection**:
   - Stop server while connected
   - Status should show "Disconnected"
   - Restart server
   - Should auto-reconnect and show "Connected"

## Verification Steps

1. Create all frontend files in `public/` directory
2. Follow manual test steps
3. Verify all visualizations work correctly
4. Test with mock telemetry data

## Success Criteria

- ✅ Dashboard loads and displays correctly
- ✅ WebSocket connection established automatically
- ✅ All charts render and update in real-time
- ✅ Current values display correctly
- ✅ Flight stage indicator works
- ✅ GPS coordinates display with 7 decimal precision
- ✅ Continuity indicators show correct colors
- ✅ Auto-reconnect works after disconnect
- ✅ Port parameter works from URL
- ✅ Reconnect button works manually
- ✅ Charts trim to max 100 data points
- ✅ Multiple browser tabs can view simultaneously

## Notes

- Charts use Chart.js CDN (no local install needed)
- Vue 3 loaded from CDN
- All styling in single CSS file
- Responsive grid layout adapts to screen size
- Charts update with `'none'` mode for performance (no animation)
