from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
from typing import Set
import logging
import json
from models import TelemetryData
from utils import format_for_frontend, mock_telemetry_producer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

connected_clients: Set[WebSocket] = set()
telemetry_queue: asyncio.Queue = asyncio.Queue()



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown logic."""
    # Startup
    logger.info("Ground station server starting up...")

    # Start background tasks
    broadcaster_task = asyncio.create_task(broadcast_telemetry())
    producer_task = asyncio.create_task(mock_telemetry_producer(telemetry_queue))

    logger.info("Background tasks started")

    yield

    # Shutdown
    logger.info("Ground station server shutting down...")

    # Cancel background tasks
    broadcaster_task.cancel()
    producer_task.cancel()

    # Close all WebSocket connections
    for client in connected_clients.copy():
        try:
            await client.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
    connected_clients.clear()

    logger.info("Shutdown complete")

app = FastAPI(
    title="ERIS Ground Station",
    description="Real-time telemetry receiver and dashboard for ERIS Gamma",
    version="1.0.0",
    lifespan=lifespan
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for streaming telemetry data to frontend clients.

    Accepts connections, maintains them in the connected_clients set,
    and handles graceful disconnection.
    """
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


async def broadcast_telemetry():
    """
    Background task that consumes telemetry from queue and broadcasts to all clients.

    Runs continuously, processing telemetry data from the queue, parsing it,
    and sending to all connected WebSocket clients.
    """
    logger.info("Telemetry broadcaster started")

    while True:
        try:
            # Get telemetry CSV string from queue
            csv_data = await telemetry_queue.get()

            # Parse and validate CSV data
            try:
                telemetry = TelemetryData.from_csv(csv_data)
            except (ValueError, Exception) as e:
                logger.error(f"Failed to parse telemetry: {e}")
                telemetry_queue.task_done()
                continue

            # Format data for frontend
            message_data = format_for_frontend(telemetry)
            message_json = json.dumps(message_data)

            # Broadcast to all connected clients
            if connected_clients:
                disconnected = set()

                for client in connected_clients:
                    try:
                        await client.send_text(message_json)
                    except Exception as e:
                        logger.warning(f"Failed to send to client: {e}")
                        disconnected.add(client)

                # Remove disconnected clients
                if disconnected:
                    connected_clients.difference_update(disconnected)
                    logger.info(f"Removed {len(disconnected)} disconnected clients")

            # Mark task as done
            telemetry_queue.task_done()

        except Exception as e:
            logger.error(f"Error in broadcast loop: {e}")
            # Continue running even if there's an error

#for testing
@app.post("/telemetry/inject")
async def inject_telemetry(csv_data: str):
    """
    Manual telemetry injection endpoint for testing.

    Allows posting CSV telemetry data directly to the queue.
    """
    try:
        # Validate the CSV can be parsed
        TelemetryData.from_csv(csv_data)
        # Add to queue
        await telemetry_queue.put(csv_data)
        return {"status": "success", "message": "Telemetry queued"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


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
