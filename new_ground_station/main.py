from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
from typing import Set, Dict
import logging
import json
import os
from utils import (
    format_for_frontend,
    format_payload_for_frontend,
    mock_telemetry_producer,
    mock_payload_producer,
    unified_serial_producer,
    global_telemetry_queues,
    send_command,
)
import serial.tools.list_ports
from storage import StorageManager, PayloadStorageManager

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

connected_clients: Set[WebSocket] = set()

# Separate queues and storage for each source
eris_queue: asyncio.Queue = asyncio.Queue()
payload_queue: asyncio.Queue = asyncio.Queue()

# Storage managers per source (source name in filename)
eris_storage = StorageManager(log_dir="flight_logs/eris")
payload_storage = PayloadStorageManager(log_dir="flight_logs/payload")

storage_managers = {"eris": eris_storage, "payload": payload_storage}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown logic."""
    logger.info("Ground station server starting up...")

    # Start background broadcaster tasks (one per source)
    eris_broadcaster = asyncio.create_task(
        broadcast_telemetry("eris", eris_queue, eris_storage, format_for_frontend)
    )
    payload_broadcaster = asyncio.create_task(
        broadcast_telemetry(
            "payload", payload_queue, payload_storage, format_payload_for_frontend
        )
    )

    producer_tasks = []

    # Register queues for the unified parser
    global_telemetry_queues["eris"] = eris_queue
    global_telemetry_queues["payload"] = payload_queue

    # Auto-discover serial ports with retry (handles Pi boot race condition)
    active_ports = []
    max_retries = 3
    retry_delay = 3  # seconds

    for attempt in range(1, max_retries + 1):
        ports = serial.tools.list_ports.comports()
        active_ports = [
            p.device
            for p in ports
            if p.device and "Bluetooth" not in p.device and "BTH" not in p.device
        ]
        # active_ports = ["/dev/ttyACM1"]
        if active_ports:
            logger.info(f"Found serial ports on attempt {attempt}: {active_ports}")
            break
        logger.warning(
            f"No serial ports found (attempt {attempt}/{max_retries}), retrying in {retry_delay}s..."
        )
        await asyncio.sleep(retry_delay)

    if active_ports:
        logger.info(f"Starting UNIFIED mode with ports: {active_ports}")
        for port in active_ports:
            producer_tasks.append(asyncio.create_task(unified_serial_producer(port)))
    else:
        logger.info(
            "No serial ports found after retries. Starting in MOCK mode for both."
        )
        producer_tasks.append(asyncio.create_task(mock_telemetry_producer(eris_queue)))
        producer_tasks.append(asyncio.create_task(mock_payload_producer(payload_queue)))

    # If argument with serial port is provided, set active_ports = [arg_port]

    logger.info("Background tasks started")

    yield

    # Shutdown
    logger.info("Ground station server shutting down...")

    eris_broadcaster.cancel()
    payload_broadcaster.cancel()
    for task in producer_tasks:
        task.cancel()

    for client in connected_clients.copy():
        try:
            await client.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
    connected_clients.clear()

    logger.info("Shutdown complete")


app = FastAPI(
    title="ERIS Ground Station",
    description="Real-time telemetry receiver and dashboard for ERIS Delta",
    version="2.0.0",
    lifespan=lifespan,
)


async def _handle_ws_message(message: str):
    """Handle a single WebSocket message (ping or JSON command)."""
    if message == "ping":
        return "pong"

    msg = json.loads(message)
    if msg.get("type") == "command" and msg.get("page") and msg.get("command"):
        result = await send_command(msg["page"], msg["command"])
        return json.dumps(
            {
                "type": "command_ack",
                "page": msg["page"],
                "command": msg["command"],
                **result,
            }
        )
    return None


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming telemetry data to frontend clients."""
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info(f"WebSocket connected. Total clients: {len(connected_clients)}")

    try:
        while True:
            try:
                message = await websocket.receive_text()
                response = await _handle_ws_message(message)
                if response:
                    await websocket.send_text(response)
                    if response != "pong":
                        await broadcast_message(response)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error receiving WebSocket message: {e}")
                break
    finally:
        connected_clients.discard(websocket)
        logger.info(f"WebSocket disconnected. Total clients: {len(connected_clients)}")


async def broadcast_message(message: str):
    """Broadcast a message to all connected WebSocket clients."""
    if not connected_clients:
        return

    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send to client: {e}")
            disconnected.add(client)

    if disconnected:
        connected_clients.difference_update(disconnected)
        logger.info(f"Removed {len(disconnected)} disconnected clients")


async def broadcast_clear_signal(
    page: str, takeoff_offset: float = None, takeoff_time: str = None
):
    """Broadcast clear signal to all connected clients for a specific page."""
    message = {
        "type": "clear",
        "page": page,
        "takeoff_offset": takeoff_offset,
        "takeoff_time": takeoff_time,
    }
    message_json = json.dumps(message)
    await broadcast_message(message_json)
    logger.info(f"Broadcasted clear signal for {page} (offset={takeoff_offset})")


async def broadcast_telemetry(name, queue, storage, formatter):
    """Background task that processes telemetry from a queue and broadcasts."""
    logger.info(f"{name} telemetry broadcaster started")
    while True:
        try:
            telemetry = await queue.get()
            storage.add_telemetry(telemetry)
            message = json.dumps(
                {
                    "page": name,
                    "data": formatter(telemetry, storage.takeoff_offset_time),
                }
            )
            await broadcast_message(message)
            queue.task_done()
        except Exception as e:
            logger.error(f"Error in {name} broadcast loop: {e}")


# ── Command Uplink ──


class CommandRequest(BaseModel):
    command: str


@app.post("/command/{page}")
async def send_command_endpoint(page: str, req: CommandRequest):
    """Send a command to a transceiver and wait for ACK/NAK."""
    if page not in ("eris", "payload"):
        return {"status": "error", "message": f"Unknown page: {page}"}

    result = await send_command(page, req.command)

    # Broadcast result to all WebSocket clients
    ack_msg = json.dumps(
        {"type": "command_ack", "page": page, "command": req.command, **result}
    )
    await broadcast_message(ack_msg)

    return result


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "connected_clients": len(connected_clients),
        "eris_queue_size": eris_queue.qsize(),
        "payload_queue_size": payload_queue.qsize(),
    }


@app.get("/telemetry/current/{page}")
async def get_current_telemetry(page: str):
    """Get all telemetry from current session for a specific page."""
    storage = storage_managers.get(page)
    if not storage:
        return {"error": f"Unknown page: {page}"}
    return {"data": storage.get_current_data(), "session": storage.get_session_info()}


@app.post("/telemetry/clear/{page}")
async def clear_telemetry(page: str):
    """Clear charts and mark takeoff for a specific page."""
    storage = storage_managers.get(page)
    if not storage:
        return {"error": f"Unknown page: {page}"}

    result = storage.clear_data()
    if result.get("status") == "success":
        await broadcast_clear_signal(
            page=page,
            takeoff_offset=result.get("takeoff_offset"),
            takeoff_time=result.get("takeoff_time"),
        )
    return result


@app.post("/telemetry/save/{page}")
async def save_flight(page: str):
    """Archive current flight for a specific page."""
    storage = storage_managers.get(page)
    if not storage:
        return {"error": f"Unknown page: {page}"}
    return storage.save_flight()


# Mount static files last
app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
