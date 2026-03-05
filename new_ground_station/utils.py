"""Utility functions for the ground station."""

import asyncio
import logging
import serial
from models import FlightComputerTelemetryData, PayloadTelemetryData
from typing import Optional, Dict

# Bitproto is required for serial data decoding
try:
    import telemetry_bp

    HAS_ERIS_BITPROTO = True
except ImportError as e:
    telemetry_bp = None
    HAS_ERIS_BITPROTO = False

try:
    import payload_bp

    HAS_PAYLOAD_BITPROTO = True
except ImportError:
    payload_bp = None
    HAS_PAYLOAD_BITPROTO = False

# Global Queues (passed in from main.py)
global_telemetry_queues = {}

# ── 3-Byte Synchronization Protocol Registry ──
SYNC_WORD = b"\xaa\xbb"

TELEMETRY_SOURCES = {}

if HAS_ERIS_BITPROTO:
    TELEMETRY_SOURCES[0x01] = {
        "name": "eris",
        "packet_class": telemetry_bp.FlightStatus,
        "data_model": FlightComputerTelemetryData,
        "queue_name": "eris",
    }

if HAS_PAYLOAD_BITPROTO:
    TELEMETRY_SOURCES[0x02] = {
        "name": "payload",
        "packet_class": payload_bp.PayloadPacket,
        "data_model": PayloadTelemetryData,
        "queue_name": "payload",
    }


logger = logging.getLogger(__name__)

# ── Command Uplink ──
# ACK/FAIL single-byte protocol: 0x00 = delivered, 0x01 = failed (not delivered)
# These never collide with valid bitproto length bytes (35 for eris/FlightStatus, 37 for payload).
COMMAND_ACK_BYTE = 0x00
COMMAND_FAIL_BYTE = 0x01

# Shared serial connections by page name, so the command endpoint can write to them
serial_connections: Dict[str, serial.Serial] = {}

# Queues for routing ACK/NAK responses back to the send_command() caller
command_ack_queues: Dict[str, asyncio.Queue] = {}


# ── Declarative field mappings: (frontend_name, attribute_or_callable) ──

ERIS_FIELDS = [
    ("cur_time", "cur_time"),
    ("altitude", "altitude"),
    ("velocity", "velocity"),
    ("acceleration", "acceleration"),
    ("vertical_velocity", "vertical_velocity"),
    ("battery_voltage", "battery_voltage"),
    ("temp", "temperature"),
    ("lat", "get_gps_lat_degrees"),
    ("long", "get_gps_lng_degrees"),
    ("gps_alt", "get_gps_alt_meters"),
    ("gps_sats", "gps_sats_in_view"),
    ("gps_fix", "gps_fix_status"),
    ("ab_servo", "airbrake_deploy_pct"),
    ("cnrd_servo", "canard_angle_pct"),
    ("drogue_cont_1", "drogue_pyro_cont_1"),
    ("drogue_cont_2", "drogue_pyro_cont_2"),
    ("main_cont_1", "main_pyro_cont_1"),
    ("main_cont_2", "main_pyro_cont_2"),
    ("runcam_active", "runcam_active"),
    ("runcam_overcurrent", "runcam_overcurrent"),
    ("livecam_active", "livecam_active"),
    ("livecam_overcurrent", "livecam_overcurrent"),
    ("bmp1_ok", "bmp1_ok"),
    ("bmp2_ok", "bmp2_ok"),
    ("ext_barometer_ok", "ext_barometer_ok"),
    ("bno_ok", "bno_ok"),
    ("high_g_ok", "high_g_ok"),
    ("exernal_imu_ok", "exernal_imu_ok"),
    ("roll", "roll"),
    ("flight_stage", "flight_stage"),
    ("canards_enabled", "canards_enabled"),
    ("airbrakes_enabled", "airbrakes_enabled"),
    ("accel_y", "accel_y"),
    ("hg_accel_y", "hg_accel_y"),
]

PAYLOAD_FIELDS = [
    ("cur_time", "cur_time"),
    ("lat", "get_gps_lat_degrees"),
    ("long", "get_gps_lng_degrees"),
    ("gps_alt", "get_gps_alt_meters"),
    ("velocity", "velocity"),
    ("accelx", "accel_x"),
    ("accely", "accel_y"),
    ("accelz", "accel_z"),
    ("distance_to_target", "distance_to_target"),
    ("destination_reached", "destination_reached"),
]


def _build_frontend_data(telemetry, fields, time):
    """Build frontend data list from a declarative field mapping."""
    result = []
    for source_name, attr in fields:
        val = getattr(telemetry, attr)
        if callable(val):
            val = val()
        if isinstance(val, bool):
            val = int(val)
        result.append({"time": time, "source": source_name, "value": val})
    return result


def _compute_time(cur_time_ms, takeoff_offset):
    """Convert millisecond boot time to seconds, applying optional takeoff offset."""
    time = cur_time_ms / 1000.0
    if takeoff_offset is not None:
        time = time - takeoff_offset
    return time


def format_for_frontend(
    telemetry: FlightComputerTelemetryData, takeoff_offset: Optional[float] = None
) -> list:
    """Transform FlightComputerTelemetryData to frontend format."""
    time = _compute_time(telemetry.cur_time, takeoff_offset)
    return _build_frontend_data(telemetry, ERIS_FIELDS, time)


def format_payload_for_frontend(
    telemetry: PayloadTelemetryData, takeoff_offset: Optional[float] = None
) -> list:
    """Transform PayloadTelemetryData to frontend format."""
    time = _compute_time(telemetry.cur_time, takeoff_offset)
    return _build_frontend_data(telemetry, PAYLOAD_FIELDS, time)


async def _find_sync(ser, port_identity):
    """
    Slide bytes looking for the sync word (0xAA 0xBB).
    Also handles single-byte ACK/NAK responses for command uplink.
    Returns True if sync found, False if timed out.
    """
    window = b""
    while True:
        b = ser.read(1)
        if not b:
            await asyncio.sleep(0.01)
            return False

        # Handle single-byte Command ACK/NAK
        if port_identity and b[0] in (COMMAND_ACK_BYTE, COMMAND_FAIL_BYTE):
            status = "ack" if b[0] == COMMAND_ACK_BYTE else "fail"
            label = "delivered" if status == "ack" else "failed to deliver"
            logger.info(f"Command {label} to {port_identity}")
            if port_identity in command_ack_queues:
                await command_ack_queues[port_identity].put(status)
            continue

        window += b
        if len(window) > 2:
            window = window[1:]
        if window == SYNC_WORD:
            return True


async def _read_payload(ser, expected_size):
    """Read exactly expected_size bytes from serial, waiting as needed."""
    payload = b""
    while len(payload) < expected_size:
        chunk = ser.read(expected_size - len(payload))
        if chunk:
            payload += chunk
        else:
            await asyncio.sleep(0.005)
    return payload


async def unified_serial_producer(port: str, baudrate: int = 115200):
    """
    Read telemetry from an auto-discovered serial port.
    Uses a 3-byte custom framing protocol: [0xAA] [0xBB] [Source ID] [Bitproto Payload]
    Also maintains serial connection state for command uplink routing.
    """
    if not TELEMETRY_SOURCES:
        logger.error("No Bitproto libraries available. Cannot decode serial telemetry.")
        return

    logger.info(f"Starting UNIFIED serial producer on {port} @ {baudrate}")

    while True:
        try:
            with serial.Serial(port, baudrate, timeout=0.1) as ser:
                logger.info(f"Connected to unified port: {port}")
                ser.reset_input_buffer()
                port_identity = None

                try:
                    while True:
                        try:
                            # Wait for data
                            if ser.in_waiting < 1:
                                await asyncio.sleep(0.01)
                                continue

                            # 1. Find sync word
                            if not await _find_sync(ser, port_identity):
                                continue

                            # 2. Read identifier byte
                            while ser.in_waiting == 0:
                                await asyncio.sleep(0.001)
                            identifier = ser.read(1)[0]

                            # 3. Look up source
                            source = TELEMETRY_SOURCES.get(identifier)
                            if not source:
                                logger.warning(
                                    f"Unknown Sync ID: 0x{identifier:02X} on {port}"
                                )
                                continue

                            name = source["name"]

                            # Register port for command uplinks
                            if port_identity != name:
                                port_identity = name
                                serial_connections[name] = ser
                                command_ack_queues.setdefault(name, asyncio.Queue())
                                logger.info(
                                    f"Port {port} dynamically registered as '{name}' for command uplinks"
                                )

                            # 4. Read payload
                            expected_size = source["packet_class"].BYTES_LENGTH
                            payload = await _read_payload(ser, expected_size)

                            # 5. Decode and queue
                            packet = source["packet_class"]()
                            try:
                                packet.decode(bytearray(payload))
                                telemetry = source["data_model"].from_bitproto(packet)

                                target_queue = global_telemetry_queues.get(
                                    source["queue_name"]
                                )
                                if target_queue:
                                    await target_queue.put(telemetry)
                                else:
                                    logger.warning(
                                        f"Target queue '{source['queue_name']}' not found"
                                    )

                                logger.debug(f"Received {name} packet on {port}")
                            except Exception as e:
                                logger.warning(
                                    f"Failed to decode {name} packet on {port}: {e}"
                                )

                        except (OSError, serial.SerialException) as e:
                            logger.error(f"Serial read error on {port}: {e}")
                            break
                finally:
                    if port_identity:
                        serial_connections.pop(port_identity, None)

        except (OSError, serial.SerialException) as e:
            logger.error(f"Failed to connect to unified port {port}: {e}")
            logger.info(f"Retrying {port} in 2 seconds...")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Unexpected error in unified serial producer on {port}: {e}")
            await asyncio.sleep(2)


async def send_command(page: str, command: str) -> dict:
    """
    Send a command string to the transceiver over serial and wait for ACK/NAK.
    Returns {"status": "ack"}, {"status": "nak"}, {"status": "timeout"}, or {"status": "error", "message": ...}.
    """
    ser = serial_connections.get(page)
    if not ser:
        logger.warning(f"No serial connection for {page} (mock mode?)")
        return {"status": "error", "message": f"No serial connection for {page}"}

    ack_queue = command_ack_queues.get(page)
    if not ack_queue:
        return {"status": "error", "message": f"No ACK queue for {page}"}

    # Drain any stale ACK/NAK from previous commands
    while not ack_queue.empty():
        try:
            ack_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

    try:
        # Write command + newline to serial
        cmd_bytes = (command.strip() + "\n").encode("utf-8")
        ser.write(cmd_bytes)
        ser.flush()
        logger.info(f"Sent command to {page}: {command!r}")

        # Wait for ACK/NAK with timeout
        try:
            result = await asyncio.wait_for(ack_queue.get(), timeout=2.0)
            logger.info(f"Command response from {page}: {result}")
            return {"status": result}
        except asyncio.TimeoutError:
            logger.warning(f"Command ACK timeout for {page}")
            return {"status": "timeout"}

    except (OSError, serial.SerialException) as e:
        logger.error(f"Failed to send command to {page}: {e}")
        return {"status": "error", "message": str(e)}


async def mock_telemetry_producer(telemetry_queue: asyncio.Queue):
    """Mock telemetry data producer. Generates FlightComputerTelemetryData every 500ms."""
    import math

    logger.info("Mock telemetry producer started")

    flight_time = 0
    while True:
        t = flight_time / 1000.0

        altitude = 1500.0 + 50 * t - 2 * t**2
        velocity = 50.0 - 4 * t
        vertical_velocity = velocity + math.sin(t) * 2
        acceleration = 15.2 + math.sin(t * 2) * 5
        roll = 0.05 + math.sin(t) * 0.1
        ab_pct = int(45 + math.sin(t * 0.5) * 30)
        cnrd_pct = int(12 + math.cos(t * 0.7) * 10)
        battery = 12.6 - t * 0.01
        temp = 22.5 + t * 0.1

        telemetry = FlightComputerTelemetryData(
            cur_time=flight_time,
            gps_lat=40_123_456,
            gps_lng=-105_123_456,
            gps_alt=1523,
            gps_sats_in_view=8,
            gps_fix_status=3,
            altitude=altitude,
            velocity=velocity,
            acceleration=acceleration,
            vertical_velocity=vertical_velocity,
            airbrake_deploy_pct=max(0, min(100, ab_pct)),
            canard_angle_pct=max(0, min(100, cnrd_pct)),
            battery_voltage=battery,
            temperature=temp,
            runcam_active=True,
            runcam_overcurrent=False,
            livecam_active=False,
            livecam_overcurrent=False,
            drogue_pyro_cont_1=True,
            drogue_pyro_cont_2=True,
            main_pyro_cont_1=False,
            main_pyro_cont_2=False,
            bmp1_ok=True,
            bmp2_ok=True,
            ext_barometer_ok=True,
            bno_ok=True,
            high_g_ok=True,
            exernal_imu_ok=True,
            roll=roll,
            flight_stage=0,
            canards_enabled=True,
            airbrakes_enabled=True,
            accel_y=acceleration * math.cos(t * 0.3),
            hg_accel_y=acceleration * math.cos(t * 0.3) * 2.0,
        )

        await telemetry_queue.put(telemetry)
        flight_time += 500
        await asyncio.sleep(0.5)


async def mock_payload_producer(telemetry_queue: asyncio.Queue):
    """
    Mock payload telemetry producer for testing.
    Generates payload data with GPS, velocity, accel, plus distance_to_target and destination_reached.
    """
    import math
    import random

    logger.info("Mock payload producer started")

    flight_time = 0
    while True:
        t = flight_time / 1000.0

        # Shared fields (similar to rocket but slightly different trajectory)
        velocity = 30 - 2 * t
        accel_x = 5.0 + math.sin(t * 1.5) * 3
        accel_y = 0.2 + math.cos(t * 1.2) * 1
        accel_z = -9.8 + math.sin(t * 2) * 0.5

        # Payload-specific: distance decreases over time with random variation
        distance_to_target = max(0, 1000 - t * 50 + random.uniform(-20, 20))

        # Destination reached: flip every 10 seconds
        destination_reached = int(t / 10) % 2 == 1

        # Create PayloadTelemetryData object directly
        payload = PayloadTelemetryData(
            cur_time=flight_time,
            gps_lat=359940330,
            gps_lng=-788986220,
            gps_alt=150000 + int(t * 1000),
            velocity=velocity,
            accel_x=accel_x,
            accel_y=accel_y,
            accel_z=accel_z,
            distance_to_target=distance_to_target,
            destination_reached=destination_reached,
        )

        await telemetry_queue.put(payload)

        flight_time += 500
        await asyncio.sleep(0.5)
