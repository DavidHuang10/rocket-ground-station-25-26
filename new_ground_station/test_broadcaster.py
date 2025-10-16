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
