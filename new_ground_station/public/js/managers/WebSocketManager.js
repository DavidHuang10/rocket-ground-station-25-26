// WebSocket connection management

export class WebSocketManager {
    constructor(onMessage, onConnectionChange, onConnected = null) {
        this.ws = null;
        this.connected = false;
        this.heartbeatInterval = null;
        this.onMessage = onMessage;
        this.onConnectionChange = onConnectionChange;
        this.onConnected = onConnected;
    }

    connect() {
        const wsUrl = `ws://${window.location.host}/ws`;
        console.log(`Connecting to ${wsUrl}...`);

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = async () => {
            console.log('WebSocket connected');
            this.connected = true;
            this.onConnectionChange(true);

            if (this.onConnected) {
                try {
                    await this.onConnected();
                } catch (e) {
                    console.error('Error in onConnected callback:', e);
                }
            }

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

            // Process messages
            try {
                const message = JSON.parse(data);
                this.onMessage(message);
            } catch (e) {
                console.error('Failed to parse message:', e);
            }
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.connected = false;
            this.onConnectionChange(false);

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
    }

    reconnect() {
        if (this.ws) {
            this.ws.close();
        }
        this.connect();
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }
    }
}
