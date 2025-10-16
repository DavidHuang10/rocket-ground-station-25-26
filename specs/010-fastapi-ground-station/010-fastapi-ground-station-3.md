# Implementation Plan: Telemetry Broadcasting System (Part 3)

## Overview
Implement queue-based telemetry broadcasting system that receives CSV data and streams to all connected WebSocket clients.

## Resources

### Producer-Consumer Pattern
From research notes (lines 131-147):
- Use `asyncio.Queue` for producer-consumer pattern
- Producer reads telemetry data and puts in queue
- WebSocket handler consumes from queue and broadcasts
- Decouple data acquisition from WebSocket broadcast

### Existing Broadcasting Pattern
From existing code `ground_station/websocket.py:236-247`:
- Iterate over clients, remove disconnected ones
- Use try/except for each client send
- Track disconnected clients in separate set

### Data Format for Frontend
From existing code `ground_station/public/main.js:124-156`:
- Frontend expects array of objects: `[{time, source, value}, ...]`
- Time in seconds (convert from milliseconds)
- Source is field name (e.g., "altitude", "battery_voltage")

## Implementation

### Update File: `new_ground_station/main.py`

Add the following to the existing `main.py` file:

```python
# Add these imports at the top
import json
from models import TelemetryData

# Add this function after the _is_allowed_origin function

def format_for_frontend(telemetry: TelemetryData) -> list:
    """
    Transform TelemetryData to frontend format.

    Frontend expects: [{time, source, value}, ...]
    where time is in seconds.
    """
    time = telemetry.cur_time / 1000.0  # Convert ms to seconds

    return [
        {"time": time, "source": "altitude", "value": telemetry.altitude},
        {"time": time, "source": "velocity", "value": telemetry.velocity},
        {"time": time, "source": "smooth_vel", "value": telemetry.smooth_vel},
        {"time": time, "source": "battery_voltage", "value": telemetry.battery_voltage},
        {"time": time, "source": "accelx", "value": telemetry.accel_x},
        {"time": time, "source": "accely", "value": telemetry.accel_y},
        {"time": time, "source": "accelz", "value": telemetry.accel_z},
        {"time": time, "source": "gyrox", "value": telemetry.gyro_x},
        {"time": time, "source": "gyroy", "value": telemetry.gyro_y},
        {"time": time, "source": "gyroz", "value": telemetry.gyro_z},
        {"time": time, "source": "hg_accel", "value": telemetry.hg_accel},
        {"time": time, "source": "temp", "value": telemetry.temperature},
        {"time": time, "source": "pressure", "value": telemetry.pressure},
        {"time": time, "source": "lat", "value": telemetry.get_gps_lat_degrees()},
        {"time": time, "source": "long", "value": telemetry.get_gps_lng_degrees()},
        {"time": time, "source": "gps_alt", "value": telemetry.get_gps_alt_meters()},
        {"time": time, "source": "stage", "value": telemetry.flight_stage},
        {"time": time, "source": "ab_servo", "value": telemetry.ab_servo_pct},
        {"time": time, "source": "cnrd_servo", "value": telemetry.cnrd_servo_pct},
        {"time": time, "source": "drogue_cont_1", "value": int(telemetry.drogue_pyro_cont_1)},
        {"time": time, "source": "drogue_cont_2", "value": int(telemetry.drogue_pyro_cont_2)},
        {"time": time, "source": "main_cont_1", "value": int(telemetry.main_pyro_cont_1)},
        {"time": time, "source": "main_cont_2", "value": int(telemetry.main_pyro_cont_2)},
        {"time": time, "source": "airbrake_cont", "value": int(telemetry.airbrake_cont)},
    ]


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


async def mock_telemetry_producer():
    """
    Mock telemetry data producer for testing.

    Generates sample CSV telemetry every 500ms.
    Replace this with actual serial data reading in the future.
    """
    logger.info("Mock telemetry producer started")

    flight_time = 0
    while True:
        # Generate mock CSV data
        csv_data = (
            f"{flight_time},"  # cur_time
            "401234567,-1051234567,1523000,"  # GPS (lat, lng, alt)
            "15.2,0.3,-9.8,"  # accel (x, y, z)
            "0.05,-0.02,0.1,"  # gyro (x, y, z)
            "98.1,"  # hg_accel
            "152.3,25.4,24.8,"  # altitude, velocity, smooth_vel
            "1013.25,22.5,300.0,"  # pressure, temp, launchsite_msl
            "1,45.5,12.3,"  # airbrake_cont, ab_servo_pct, cnrd_servo_pct
            "1,1,0,0,"  # drogue_cont_1, drogue_cont_2, main_cont_1, main_cont_2
            "1,1,0,"  # flight_index, ellipse_on, cameras_on
            "12.6,2"  # battery_voltage, flight_stage
        )

        # Put data in queue
        await telemetry_queue.put(csv_data)

        # Increment time and wait 500ms
        flight_time += 500
        await asyncio.sleep(0.5)


# Update the startup_event function
@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on server startup."""
    logger.info("Ground station server starting up...")

    # Start broadcaster task
    asyncio.create_task(broadcast_telemetry())

    # Start mock producer (for testing)
    asyncio.create_task(mock_telemetry_producer())

    logger.info("Background tasks started")
```

### Update File: `new_ground_station/main.py` - Add Queue Status Endpoint

Add this endpoint before the `/health` endpoint:

```python
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
```

## Testing

### Test File: `new_ground_station/test_broadcaster.py`

```python
import pytest
import asyncio
from main import format_for_frontend, broadcast_telemetry, connected_clients, telemetry_queue
from models import TelemetryData


def test_format_for_frontend():
    """Test telemetry data formatting for frontend."""
    csv = "12000,401234567,-1051234567,1523000,15.2,0.3,-0.1,0.05,-0.02,0.1,98.1,152.3,25.4,24.8,1013.25,22.5,300.0,1,45.5,12.3,1,1,0,0,1,1,0,12.6,2"
    telemetry = TelemetryData.from_csv(csv)

    result = format_for_frontend(telemetry)

    # Check it's a list of dicts
    assert isinstance(result, list)
    assert all(isinstance(item, dict) for item in result)

    # Check time conversion (12000ms -> 12.0s)
    assert result[0]["time"] == 12.0

    # Check specific fields
    altitude_data = next(item for item in result if item["source"] == "altitude")
    assert altitude_data["value"] == 152.3

    battery_data = next(item for item in result if item["source"] == "battery_voltage")
    assert battery_data["value"] == 12.6

    # Check GPS coordinate conversion
    lat_data = next(item for item in result if item["source"] == "lat")
    assert abs(lat_data["value"] - 40.1234567) < 0.0000001

    stage_data = next(item for item in result if item["source"] == "stage")
    assert stage_data["value"] == 2


@pytest.mark.asyncio
async def test_queue_processing():
    """Test that telemetry can be queued and processed."""
    csv = "12000,401234567,-1051234567,1523000,15.2,0.3,-0.1,0.05,-0.02,0.1,98.1,152.3,25.4,24.8,1013.25,22.5,300.0,1,45.5,12.3,1,1,0,0,1,1,0,12.6,2"

    # Clear queue
    while not telemetry_queue.empty():
        await telemetry_queue.get()

    # Put data in queue
    await telemetry_queue.put(csv)

    # Verify queue has data
    assert telemetry_queue.qsize() == 1

    # Get and verify data
    data = await telemetry_queue.get()
    assert data == csv

    telemetry_queue.task_done()
```

### Manual Testing Steps

1. **Start server with mock producer**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

2. **Open browser to** `http://localhost:8000`

3. **Verify telemetry streaming**:
   - Should see JSON data updating every 500ms
   - Time field should increment by 0.5 each update
   - All 24+ data fields should be present

4. **Test with multiple clients**:
   - Open 3 browser tabs to `http://localhost:8000`
   - All should receive same telemetry data
   - Check server logs: should show 3 connected clients

5. **Test disconnection handling**:
   - Close one browser tab
   - Server logs should show client disconnected
   - Other tabs should continue receiving data

6. **Test manual injection**:
   ```bash
   curl -X POST http://localhost:8000/telemetry/inject \
     -H "Content-Type: application/json" \
     -d '"12000,401234567,-1051234567,1523000,15.2,0.3,-0.1,0.05,-0.02,0.1,98.1,152.3,25.4,24.8,1013.25,22.5,300.0,1,45.5,12.3,1,1,0,0,1,1,0,12.6,2"'
   ```
   Expected: `{"status":"success","message":"Telemetry queued"}`

7. **Test invalid data handling**:
   ```bash
   curl -X POST http://localhost:8000/telemetry/inject \
     -H "Content-Type: application/json" \
     -d '"invalid,data,here"'
   ```
   Expected: Error message about field count

8. **Check health endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```
   Should show queue_size and connected_clients count

## Verification Steps

1. Update `main.py` with all code above
2. Run pytest: `pytest test_broadcaster.py -v`
3. Follow manual testing steps
4. Verify all tests pass

## Success Criteria

- ✅ Background broadcaster task starts on server startup
- ✅ Mock producer generates telemetry every 500ms
- ✅ CSV data parsed correctly into TelemetryData
- ✅ Data formatted correctly for frontend
- ✅ All connected clients receive broadcast
- ✅ Disconnected clients removed from set
- ✅ Server continues running even with parse errors
- ✅ Manual injection endpoint works
- ✅ Invalid data returns error without crashing
- ✅ Queue size visible in health endpoint
- ✅ No data loss when multiple clients connected

## Notes

**Future Enhancement**: Replace `mock_telemetry_producer()` with serial port reading:
```python
async def serial_telemetry_producer(port: str, baudrate: int):
    """Read telemetry from serial port."""
    import serial_asyncio
    reader, writer = await serial_asyncio.open_serial_connection(
        url=port, baudrate=baudrate
    )
    while True:
        line = await reader.readline()
        csv_data = line.decode('utf-8').strip()
        await telemetry_queue.put(csv_data)
```
