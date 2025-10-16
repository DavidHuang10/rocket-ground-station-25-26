# Implementation Plan: FastAPI Application Setup (Part 2)

## Overview
Create FastAPI application with WebSocket endpoint and static file serving on single port.

## Resources

### FastAPI WebSocket Pattern
From research notes (lines 116-126):
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/", StaticFiles(directory="public", html=True), name="public")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # WebSocket logic here
```

### Connection Management Pattern
From research notes (lines 83-87):
- Keep connected clients in `set()` for efficient add/remove
- Use try/finally blocks to ensure cleanup on disconnect
- Existing pattern: `ground_station/websocket.py:226-227`

### Error Handling
From research notes (lines 89-93):
- Wrap WebSocket receive loop in try/except for `WebSocketDisconnect`
- Clean up resources in finally block
- Use `connected_clients.discard(websocket)` to avoid errors

## Implementation

### File: `new_ground_station/main.py`

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import asyncio
from typing import Set
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="ERIS Ground Station",
    description="Real-time telemetry receiver and dashboard for ERIS Delta rocket",
    version="1.0.0"
)

# Global state
connected_clients: Set[WebSocket] = set()
telemetry_queue: asyncio.Queue = asyncio.Queue()


@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on server startup."""
    logger.info("Ground station server starting up...")
    # Background broadcaster task will be added in Part 3


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on server shutdown."""
    logger.info("Ground station server shutting down...")
    # Close all WebSocket connections
    for client in connected_clients.copy():
        try:
            await client.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
    connected_clients.clear()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for streaming telemetry data to frontend clients.

    Accepts connections, maintains them in the connected_clients set,
    and handles graceful disconnection.
    """
    # Validate Origin header for security
    origin = websocket.headers.get("origin", "")
    if origin and not _is_allowed_origin(origin):
        logger.warning(f"Rejected WebSocket connection from origin: {origin}")
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    # Accept the WebSocket connection
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info(f"WebSocket connected. Total clients: {len(connected_clients)}")

    try:
        # Keep connection alive and wait for client messages or disconnect
        while True:
            # Receive messages from client (ping/pong, etc.)
            try:
                message = await websocket.receive_text()
                # Handle ping/pong for heartbeat
                if message == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error receiving WebSocket message: {e}")
                break

    finally:
        # Remove client from connected set on disconnect
        connected_clients.discard(websocket)
        logger.info(f"WebSocket disconnected. Total clients: {len(connected_clients)}")


def _is_allowed_origin(origin: str) -> bool:
    """
    Validate WebSocket origin to prevent cross-site hijacking.

    For local ground station operations, only allow localhost origins.
    """
    allowed_origins = [
        "http://localhost",
        "https://localhost",
        "http://127.0.0.1",
        "https://127.0.0.1",
    ]
    return any(origin.startswith(allowed) for allowed in allowed_origins)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "connected_clients": len(connected_clients),
        "queue_size": telemetry_queue.qsize()
    }


# Mount static files last (acts as catch-all for frontend routes)
# This serves index.html, dash.html, and all static assets
app.mount("/", StaticFiles(directory="public", html=True), name="public")
```

### File: `new_ground_station/public/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ERIS Ground Station</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #1a1a1a;
            color: #ffffff;
        }
        .status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
        }
        .connected {
            background-color: #2d5016;
            border: 1px solid #4caf50;
        }
        .disconnected {
            background-color: #5c1010;
            border: 1px solid #f44336;
        }
        .data {
            font-family: monospace;
            background-color: #2a2a2a;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            max-height: 400px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <h1>ERIS Ground Station</h1>

    <div id="status" class="status disconnected">
        Status: <span id="status-text">Disconnected</span>
    </div>

    <div>
        <label for="port-input">WebSocket Port:</label>
        <input type="number" id="port-input" value="8000" min="1" max="65535">
        <button id="connect-btn">Connect</button>
    </div>

    <h2>Telemetry Data</h2>
    <div id="telemetry-data" class="data">
        Waiting for data...
    </div>

    <script>
        let ws = null;
        const statusDiv = document.getElementById('status');
        const statusText = document.getElementById('status-text');
        const telemetryDiv = document.getElementById('telemetry-data');
        const portInput = document.getElementById('port-input');
        const connectBtn = document.getElementById('connect-btn');

        // Get port from URL parameter if present
        const urlParams = new URLSearchParams(window.location.search);
        const urlPort = urlParams.get('port');
        if (urlPort) {
            portInput.value = urlPort;
        }

        function connect() {
            const port = portInput.value;
            const wsUrl = `ws://localhost:${port}/ws`;

            console.log(`Connecting to ${wsUrl}...`);

            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                console.log('WebSocket connected');
                statusDiv.className = 'status connected';
                statusText.textContent = 'Connected';
                connectBtn.textContent = 'Disconnect';

                // Start heartbeat
                heartbeatInterval = setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send('ping');
                    }
                }, 5000);
            };

            ws.onmessage = (event) => {
                const data = event.data;

                // Handle pong response
                if (data === 'pong') {
                    console.log('Heartbeat: pong received');
                    return;
                }

                // Display telemetry data
                try {
                    const telemetry = JSON.parse(data);
                    displayTelemetry(telemetry);
                } catch (e) {
                    console.error('Failed to parse telemetry:', e);
                }
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected');
                statusDiv.className = 'status disconnected';
                statusText.textContent = 'Disconnected';
                connectBtn.textContent = 'Connect';

                if (heartbeatInterval) {
                    clearInterval(heartbeatInterval);
                }

                // Auto-reconnect after 1 second
                setTimeout(() => {
                    if (connectBtn.textContent === 'Connect') {
                        connect();
                    }
                }, 1000);
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }

        function disconnect() {
            if (ws) {
                ws.close();
                ws = null;
            }
        }

        function displayTelemetry(data) {
            const timestamp = new Date().toLocaleTimeString();
            const dataStr = JSON.stringify(data, null, 2);
            telemetryDiv.innerHTML = `<pre>[${timestamp}]\n${dataStr}</pre>`;
        }

        connectBtn.addEventListener('click', () => {
            if (connectBtn.textContent === 'Connect') {
                connect();
            } else {
                disconnect();
            }
        });

        let heartbeatInterval = null;

        // Auto-connect on page load
        connect();
    </script>
</body>
</html>
```

### File: `new_ground_station/requirements.txt`

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
websockets>=12.0
pydantic>=2.0.0
python-multipart>=0.0.6
```

### File: `new_ground_station/.gitignore`

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
dist/
*.egg-info/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
htmlcov/
.coverage
```

## Testing

### Manual Test Steps

1. **Install dependencies**:
   ```bash
   cd new_ground_station
   pip install -r requirements.txt
   ```

2. **Create public directory**:
   ```bash
   mkdir -p public
   # Move index.html to public/
   ```

3. **Start server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

4. **Test health endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```
   Expected: `{"status":"healthy","connected_clients":0,"queue_size":0}`

5. **Test static file serving**:
   - Open browser to `http://localhost:8000`
   - Should see ERIS Ground Station page

6. **Test WebSocket connection**:
   - Click "Connect" button
   - Status should change to "Connected"
   - Check server logs for "WebSocket connected" message

7. **Test heartbeat**:
   - Wait 5 seconds
   - Check browser console for "Heartbeat: pong received"

8. **Test disconnection**:
   - Click "Disconnect" button
   - Status should change to "Disconnected"
   - Check server logs for "WebSocket disconnected" message

9. **Test auto-reconnect**:
   - Stop server while connected
   - Status should show "Disconnected"
   - Restart server
   - Should auto-reconnect within 1 second

## Verification Steps

1. Create all files as specified above
2. Follow manual test steps
3. Verify all tests pass
4. Check logs show proper connection/disconnection events

## Success Criteria

- ✅ FastAPI server starts on specified port
- ✅ Health endpoint returns correct status
- ✅ Static files (index.html) served correctly
- ✅ WebSocket endpoint accepts connections
- ✅ Connected clients tracked in global set
- ✅ Heartbeat ping/pong works
- ✅ Graceful disconnection and cleanup
- ✅ Auto-reconnect on connection loss
- ✅ Origin validation prevents cross-site connections
- ✅ Multiple clients can connect simultaneously
