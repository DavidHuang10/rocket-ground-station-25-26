from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
from typing import Set
import logging
import json
from models import TelemetryData
from utils import format_for_frontend, mock_telemetry_producer
from storage import StorageManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

connected_clients: Set[WebSocket] = set()
telemetry_queue: asyncio.Queue = asyncio.Queue()
storage_manager = StorageManager(log_dir="flight_logs")



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


async def broadcast_message(message: str):
    """
    Broadcast a message to all connected WebSocket clients.

    Args:
        message: JSON string to broadcast
    """
    if not connected_clients:
        return

    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send to client: {e}")
            disconnected.add(client)

    # Remove disconnected clients
    if disconnected:
        connected_clients.difference_update(disconnected)
        logger.info(f"Removed {len(disconnected)} disconnected clients")


async def broadcast_clear_signal(takeoff_offset: float = None, takeoff_time: str = None):
    """
    Broadcast clear signal to all connected clients.

    Args:
        takeoff_offset: Takeoff offset in seconds (None if not a takeoff clear)
        takeoff_time: ISO timestamp of takeoff (None if not a takeoff clear)
    """
    message = {
        "type": "clear",
        "takeoff_offset": takeoff_offset,
        "takeoff_time": takeoff_time
    }
    message_json = json.dumps(message)
    await broadcast_message(message_json)
    logger.info(f"Broadcasted clear signal (offset={takeoff_offset})")


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

            # Save to storage
            storage_manager.add_telemetry(telemetry)

            # Format data for frontend (with time adjustment if takeoff has occurred)
            message_data = format_for_frontend(telemetry, storage_manager.takeoff_offset_time)
            message_json = json.dumps(message_data)

            # Broadcast to all connected clients
            await broadcast_message(message_json)

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


@app.get("/telemetry/current")
async def get_current_telemetry():
    """Get all telemetry from current session."""
    return {
        "data": storage_manager.get_current_data(),
        "session": storage_manager.get_session_info()
    }


@app.post("/telemetry/clear")
async def clear_telemetry():
    """
    Clear charts and mark takeoff (T+0).
    Backs up pre-flight data to backups/pre_flight_*.csv.
    Broadcasts clear signal to all connected clients.
    """
    result = storage_manager.clear_data()

    # Broadcast clear signal to all connected clients
    if result.get("status") == "success":
        await broadcast_clear_signal(
            takeoff_offset=result.get("takeoff_offset"),
            takeoff_time=result.get("takeoff_time")
        )

    return result


@app.post("/telemetry/save")
async def save_flight():
    """
    Archive current flight to timestamped CSV file.
    Copies to both backups/ and flight_logs/.
    Recording continues.
    """
    result = storage_manager.save_flight()
    return result


@app.post("/telemetry/save-and-clear")
async def save_and_clear():
    """
    Archive current flight and clear all data.
    Resets takeoff offset for new session.
    Broadcasts clear signal to all connected clients.
    """
    result = storage_manager.save_and_clear()

    # Broadcast clear signal to all connected clients (with null offset)
    if result.get("status") == "success":
        await broadcast_clear_signal(
            takeoff_offset=None,
            takeoff_time=None
        )

    return result


# Mount static files last (acts as catch-all for frontend routes)
# This serves index.html, dash.html, and all static assets
app.mount("/", StaticFiles(directory="public", html=True), name="public")
