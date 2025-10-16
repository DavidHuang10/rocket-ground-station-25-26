# ERIS Ground Station

Real-time telemetry receiver and dashboard for ERIS Delta rocket.

## What is Uvicorn?

Uvicorn is an ASGI (Asynchronous Server Gateway Interface) web server for Python. It's designed to run async Python web frameworks like FastAPI.

Key points:
- **Fast**: Built on `uvloop` and `httptools` for high performance
- **ASGI server**: Handles async/await code, WebSockets, and HTTP/2
- **Production-ready**: Can be used in development (with `--reload`) and production
- **Required for FastAPI**: FastAPI needs an ASGI server to run, and uvicorn is the recommended choice

When you run `uvicorn main:app`, it:
1. Imports the `app` object from `main.py`
2. Starts a web server on port 8000 (default)
3. Handles incoming HTTP and WebSocket connections
4. Routes them to your FastAPI application

## How to Run

1. **Install dependencies**:
   ```bash
   cd new_ground_station
   pip install -r requirements.txt
   ```

2. **Start the server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

3. **Open the dashboard**:
   - Navigate to http://localhost:8000 in your browser
   - The WebSocket connection will establish automatically

4. **Test the health endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```

## Features

- **WebSocket endpoint** (`/ws`) for real-time telemetry streaming
- **Health check endpoint** (`/health`) for monitoring
- **Connection management** with tracking of connected clients
- **Origin validation** for security
- **Ping/pong heartbeat** to maintain connections
- **Auto-reconnect** on connection loss
- **Graceful shutdown** handling
