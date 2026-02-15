from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
from typing import Set, Dict
import logging
import json
import os
from models import FlightComputerTelemetryData, PayloadTelemetryData
from utils import (
    format_for_frontend, 
    format_payload_for_frontend,
    mock_telemetry_producer, 
    mock_payload_producer,
    serial_telemetry_producer,
    payload_serial_producer,
    send_command
)
from storage import StorageManager, PayloadStorageManager

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

connected_clients: Set[WebSocket] = set()

# Separate queues and storage for each source
eris_queue: asyncio.Queue = asyncio.Queue()
payload_queue: asyncio.Queue = asyncio.Queue()

# Storage managers per source (source name in filename)
eris_storage = StorageManager(log_dir="flight_logs/eris")
payload_storage = PayloadStorageManager(log_dir="flight_logs/payload")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown logic."""
    logger.info("Ground station server starting up...")

    # Start background broadcaster tasks (one per source)
    eris_broadcaster = asyncio.create_task(broadcast_eris_telemetry())
    payload_broadcaster = asyncio.create_task(broadcast_payload_telemetry())
    
    producer_tasks = []
    
    # Check for eris serial port
    eris_serial = os.environ.get("ERIS_SERIAL")
    if eris_serial:
        logger.info(f"Starting ERIS in REAL mode: {eris_serial}")
        producer_tasks.append(asyncio.create_task(
            serial_telemetry_producer(eris_queue, eris_serial)
        ))
    else:
        logger.info("Starting ERIS in MOCK mode")
        producer_tasks.append(asyncio.create_task(
            mock_telemetry_producer(eris_queue)
        ))
    
    # Check for payload serial port
    payload_serial = os.environ.get("PAYLOAD_SERIAL")
    if payload_serial:
        logger.info(f"Starting PAYLOAD in REAL mode: {payload_serial}")
        producer_tasks.append(asyncio.create_task(
            payload_serial_producer(payload_queue, payload_serial)
        ))
    else:
        logger.info("Starting PAYLOAD in MOCK mode")
        producer_tasks.append(asyncio.create_task(
            mock_payload_producer(payload_queue)
        ))

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
    lifespan=lifespan
)


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
                if message == "ping":
                    await websocket.send_text("pong")
                else:
                    # Try to parse as JSON command from frontend
                    try:
                        msg = json.loads(message)
                        if msg.get("type") == "command" and msg.get("page") and msg.get("command"):
                            result = await send_command(msg["page"], msg["command"])
                            ack_msg = json.dumps({
                                "type": "command_ack",
                                "page": msg["page"],
                                "command": msg["command"],
                                **result
                            })
                            await broadcast_message(ack_msg)
                    except (json.JSONDecodeError, Exception):
                        pass
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


async def broadcast_clear_signal(page: str, takeoff_offset: float = None, takeoff_time: str = None):
    """Broadcast clear signal to all connected clients for a specific page."""
    message = {
        "type": "clear",
        "page": page,
        "takeoff_offset": takeoff_offset,
        "takeoff_time": takeoff_time
    }
    message_json = json.dumps(message)
    await broadcast_message(message_json)
    logger.info(f"Broadcasted clear signal for {page} (offset={takeoff_offset})")


async def broadcast_eris_telemetry():
    """Background task that processes Eris telemetry and broadcasts with page tag."""
    logger.info("Eris telemetry broadcaster started")

    while True:
        try:
            data = await eris_queue.get()

            try:
                if isinstance(data, str):
                    telemetry = FlightComputerTelemetryData.from_csv(data)
                elif isinstance(data, FlightComputerTelemetryData):
                    telemetry = data
                else:
                    logger.warning(f"Unknown Eris data type: {type(data)}")
                    eris_queue.task_done()
                    continue
            except (ValueError, Exception) as e:
                logger.error(f"Failed to parse Eris telemetry: {e}")
                eris_queue.task_done()
                continue

            eris_storage.add_telemetry(telemetry)

            # Format with page tag
            message_data = {
                "page": "eris",
                "data": format_for_frontend(telemetry, eris_storage.takeoff_offset_time)
            }
            message_json = json.dumps(message_data)

            await broadcast_message(message_json)
            eris_queue.task_done()

        except Exception as e:
            logger.error(f"Error in Eris broadcast loop: {e}")


async def broadcast_payload_telemetry():
    """Background task that processes payload telemetry and broadcasts with page tag."""
    logger.info("Payload telemetry broadcaster started")

    while True:
        try:
            data = await payload_queue.get()

            try:
                if isinstance(data, PayloadTelemetryData):
                    telemetry = data
                else:
                    logger.warning(f"Unknown payload data type: {type(data)}")
                    payload_queue.task_done()
                    continue
            except (ValueError, Exception) as e:
                logger.error(f"Failed to parse payload telemetry: {e}")
                payload_queue.task_done()
                continue

            # Store payload telemetry (handles CSV writing and time tracking)
            payload_storage.add_telemetry(telemetry)

            # Format with page tag
            message_data = {
                "page": "payload",
                "data": format_payload_for_frontend(telemetry, payload_storage.takeoff_offset_time)
            }
            message_json = json.dumps(message_data)

            await broadcast_message(message_json)
            payload_queue.task_done()

        except Exception as e:
            logger.error(f"Error in payload broadcast loop: {e}")


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
    ack_msg = json.dumps({
        "type": "command_ack",
        "page": page,
        "command": req.command,
        **result
    })
    await broadcast_message(ack_msg)
    
    return result


# Testing endpoint
@app.post("/telemetry/inject")
async def inject_telemetry(csv_data: str):
    """Manual telemetry injection endpoint for testing (Eris only)."""
    try:
        FlightComputerTelemetryData.from_csv(csv_data)
        await eris_queue.put(csv_data)
        return {"status": "success", "message": "Telemetry queued"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "connected_clients": len(connected_clients),
        "eris_queue_size": eris_queue.qsize(),
        "payload_queue_size": payload_queue.qsize()
    }


@app.get("/telemetry/current/{page}")
async def get_current_telemetry(page: str):
    """Get all telemetry from current session for a specific page."""
    if page == "eris":
        return {
            "data": eris_storage.get_current_data(),
            "session": eris_storage.get_session_info()
        }
    elif page == "payload":
        return {
            "data": payload_storage.get_current_data(),
            "session": payload_storage.get_session_info()
        }
    else:
        return {"error": f"Unknown page: {page}"}


@app.post("/telemetry/clear/{page}")
async def clear_telemetry(page: str):
    """Clear charts and mark takeoff for a specific page."""
    if page == "eris":
        result = eris_storage.clear_data()
    elif page == "payload":
        result = payload_storage.clear_data()
    else:
        return {"error": f"Unknown page: {page}"}

    if result.get("status") == "success":
        await broadcast_clear_signal(
            page=page,
            takeoff_offset=result.get("takeoff_offset"),
            takeoff_time=result.get("takeoff_time")
        )

    return result


@app.post("/telemetry/save/{page}")
async def save_flight(page: str):
    """Archive current flight for a specific page."""
    if page == "eris":
        result = eris_storage.save_flight()
    elif page == "payload":
        result = payload_storage.save_flight()
    else:
        return {"error": f"Unknown page: {page}"}
    
    return result


# Mount static files last
app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
