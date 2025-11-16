// Telemetry data storage and processing

export class DataManager {
    constructor() {
        this.telemetryData = {};
        this.sessionInfo = null;
        this.packetCount = 0;
    }

    init(fields) {
        fields.forEach(field => {
            this.telemetryData[field] = [];
        });
    }

    processTelemetry(telemetryArray) {
        // Each array represents one telemetry packet
        this.packetCount++;
        
        for (const item of telemetryArray) {
            const { time, source, value } = item;
            if (this.telemetryData.hasOwnProperty(source)) {
                this.telemetryData[source].push({ time, value });
            }
        }
    }

    async loadCurrentSession() {
        try {
            console.log('Loading current session');
            const response = await fetch('/telemetry/current');
            const result = await response.json();

            let loaded = 0;

            result.data.forEach(item => {
                const { time, source, value } = item;
                if (this.telemetryData.hasOwnProperty(source)) {
                    this.telemetryData[source].push({ time, value });
                    loaded++;
                }
            });

            this.sessionInfo = result.session;
            // Initialize packet count from session info
            this.packetCount = result.session?.packet_count || 0;
            if (loaded > 0) {
                console.log(`Loaded ${loaded} data points`);
            }

            return result;
        } catch (e) {
            console.error('Failed to load session:', e);
            return null;
        }
    }

    clear() {
        for (const key in this.telemetryData) {
            this.telemetryData[key] = [];
        }
        // Reset packet count on clear
        this.packetCount = 0;
    }

    getCurrentValue(source) {
        const data = this.telemetryData[source];
        if (data && data.length > 0) {
            return data[data.length - 1].value;
        }
        return 0;
    }

    getCurrentTime() {
        for (const source in this.telemetryData) {
            const data = this.telemetryData[source];
            if (data && data.length > 0) {
                return data[data.length - 1].time;
            }
        }
        return 0;
    }

    getPacketCount() {
        return this.packetCount;
    }
}
