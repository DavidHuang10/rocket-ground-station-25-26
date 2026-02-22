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
except ImportError:
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
SYNC_WORD = b'\xAA\xBB'

TELEMETRY_SOURCES = {}

if HAS_ERIS_BITPROTO:
    TELEMETRY_SOURCES[0x01] = {
        "name": "eris",
        "packet_class": telemetry_bp.TelemetryPacket,
        "data_model": FlightComputerTelemetryData,
        "queue_name": "eris"
    }

if HAS_PAYLOAD_BITPROTO:
    TELEMETRY_SOURCES[0x02] = {
        "name": "payload",
        "packet_class": payload_bp.PayloadPacket,
        "data_model": PayloadTelemetryData,
        "queue_name": "payload"
    }


logger = logging.getLogger(__name__)

# ── Command Uplink ──
# ACK/FAIL single-byte protocol: 0x00 = delivered, 0x01 = failed (not delivered)
# These never collide with valid bitproto length bytes (89 for eris, 37 for payload).
COMMAND_ACK_BYTE = 0x00
COMMAND_FAIL_BYTE = 0x01

# Shared serial connections by page name, so the command endpoint can write to them
serial_connections: Dict[str, serial.Serial] = {}

# Queues for routing ACK/NAK responses back to the send_command() caller
command_ack_queues: Dict[str, asyncio.Queue] = {}


def format_for_frontend(telemetry: FlightComputerTelemetryData, takeoff_offset: Optional[float] = None) -> list:
    """
    Transform FlightComputerTelemetryData to frontend format.

    Frontend expects: [{time, source, value}, ...]
    where time is in seconds.

    Args:
        telemetry: Telemetry data to format
        takeoff_offset: Optional offset in seconds. If provided, time will be adjusted
                        to flight time (T+0 = takeoff) instead of boot time.
    """
    time = telemetry.cur_time / 1000.0  # Convert ms to seconds

    # Apply takeoff offset if set (convert to flight time)
    if takeoff_offset is not None:
        time = time - takeoff_offset

    return [
        {"time": time, "source": "cur_time", "value": telemetry.cur_time},
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
        {"time": time, "source": "launchsite_msl", "value": telemetry.launchsite_msl},
        {"time": time, "source": "flight_index", "value": telemetry.flight_index},
        {"time": time, "source": "ellipse_on", "value": int(telemetry.ellipse_on)},
        {"time": time, "source": "cameras_on", "value": int(telemetry.cameras_on)},
    ]


def format_payload_for_frontend(telemetry: PayloadTelemetryData, takeoff_offset: Optional[float] = None) -> list:
    """
    Transform PayloadTelemetryData to frontend format.

    Args:
        telemetry: Payload telemetry data to format
        takeoff_offset: Optional offset in seconds for time adjustment.
    """
    time = telemetry.cur_time / 1000.0

    if takeoff_offset is not None:
        time = time - takeoff_offset

    return [
        {"time": time, "source": "cur_time", "value": telemetry.cur_time},
        {"time": time, "source": "lat", "value": telemetry.get_gps_lat_degrees()},
        {"time": time, "source": "long", "value": telemetry.get_gps_lng_degrees()},
        {"time": time, "source": "gps_alt", "value": telemetry.get_gps_alt_meters()},
        {"time": time, "source": "velocity", "value": telemetry.velocity},
        {"time": time, "source": "accelx", "value": telemetry.accel_x},
        {"time": time, "source": "accely", "value": telemetry.accel_y},
        {"time": time, "source": "accelz", "value": telemetry.accel_z},
        {"time": time, "source": "distance_to_target", "value": telemetry.distance_to_target},
        {"time": time, "source": "destination_reached", "value": int(telemetry.destination_reached)},
    ]


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
                
                # We don't know the identity yet until we sync, but we map 
                # the connection for command uplinks globally. (Assuming 1 telemetry 
                # type per port predominantly, but we map on first received packet).
                port_identity = None 
                
                try:
                    while True:
                        try:
                            # 1. Slide window to find Sync Word: \xAA\xBB
                            if ser.in_waiting >= 1:
                                window = b''
                                while True:
                                    b = ser.read(1)
                                    if not b:
                                        await asyncio.sleep(0.01)
                                        break
                                    
                                    # Handle single-byte Command ACK/NAK from Command Uplink
                                    if b[0] == COMMAND_ACK_BYTE and port_identity:
                                        logger.info(f"Command delivered to {port_identity}")
                                        if port_identity in command_ack_queues:
                                            await command_ack_queues[port_identity].put("ack")
                                        continue
                                    elif b[0] == COMMAND_FAIL_BYTE and port_identity:
                                        logger.info(f"Command failed to deliver to {port_identity}")
                                        if port_identity in command_ack_queues:
                                            await command_ack_queues[port_identity].put("fail")
                                        continue

                                    window += b
                                    if len(window) > 2:
                                        window = window[1:] # slide
                                        
                                    if window == SYNC_WORD:
                                        break # Found!
                            else:
                                await asyncio.sleep(0.01)
                                continue

                            # Re-check if we broke out due to timeout vs sync
                            if window != SYNC_WORD:
                                continue

                            # 2. Sync found! Read the identity byte
                            # Wait briefly if it hasn't arrived over UART yet
                            while ser.in_waiting == 0:
                                await asyncio.sleep(0.001)
                                
                            identifier = ser.read(1)[0]
                            
                            # 3. Dynamic lookup!
                            source = TELEMETRY_SOURCES.get(identifier)
                            if not source:
                                logger.warning(f"Unknown Sync ID: 0x{identifier:02X} on {port}")
                                continue 
                                
                            expected_size = source["packet_class"].BYTES_LENGTH
                            name = source["name"]
                            
                            # Register this port for command uplinks if we haven't already
                            if port_identity != name:
                                port_identity = name
                                serial_connections[name] = ser
                                command_ack_queues.setdefault(name, asyncio.Queue())
                                logger.info(f"Port {port} dynamically registered as '{name}' for command uplinks")

                            # 4. Read the exact length required for the payload
                            payload = b""
                            while len(payload) < expected_size:
                                remaining = expected_size - len(payload)
                                chunk = ser.read(remaining)
                                if chunk:
                                    payload += chunk
                                else:
                                    await asyncio.sleep(0.005)
                            
                            if len(payload) == expected_size:
                                # 5. Decode Bitproto
                                packet = source["packet_class"]()
                                try:
                                    packet.decode(bytearray(payload))
                                    telemetry = source["data_model"].from_bitproto(packet)
                                    
                                    # Queue the telemetry
                                    target_queue = global_telemetry_queues.get(source["queue_name"])
                                    if target_queue:
                                        await target_queue.put(telemetry)
                                    else:
                                        logger.warning(f"Target queue '{source['queue_name']}' not found in global_telemetry_queues")
                                        
                                    logger.debug(f"Received {name} packet on {port}")
                                except Exception as e:
                                    logger.warning(f"Failed to decode {name} packet on {port}: {e}")
                                    
                        except (OSError, serial.SerialException) as e:
                            logger.error(f"Serial read error on {port}: {e}")
                            break
                finally:
                    # Unregister connection on disconnect
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
    """
    Mock telemetry data producer for testing.

    Generates sample CSV telemetry every 500ms.
    Replace this with actual serial data reading in the future.
    """
    import math
    logger.info("Mock telemetry producer started")

    flight_time = 0
    while True:
        # Simulate flight trajectory with time-varying values
        t = flight_time / 1000.0  # Convert to seconds

        # Simulate altitude increase then decrease (parabolic trajectory)
        altitude = 10 + 50 * t - 2 * t**2
        velocity = 50 - 4 * t
        smooth_vel = velocity + math.sin(t) * 2

        # Simulate IMU data with some variation
        accel_x = 15.2 + math.sin(t * 2) * 5
        accel_y = 0.3 + math.cos(t * 1.5) * 2
        accel_z = -9.8 + math.sin(t * 3) * 1
        gyro_x = 0.05 + math.sin(t) * 0.1
        gyro_y = -0.02 + math.cos(t * 1.2) * 0.08
        gyro_z = 0.1 + math.sin(t * 0.8) * 0.05

        # Simulate servo positions
        ab_servo = 45.5 + math.sin(t * 0.5) * 30
        cnrd_servo = 12.3 + math.cos(t * 0.7) * 10

        # Battery voltage slowly decreases
        battery = 12.6 - t * 0.01

        # Temperature increases slightly
        temp = 22.5 + t * 0.1

        # Generate mock CSV data
        csv_data = (
            f"{flight_time},"  # cur_time
            "401234567,-1051234567,1523000,"  # GPS (lat, lng, alt)
            f"{accel_x:.1f},{accel_y:.1f},{accel_z:.1f},"  # accel (x, y, z)
            f"{gyro_x:.2f},{gyro_y:.2f},{gyro_z:.2f},"  # gyro (x, y, z)
            "98.1,"  # hg_accel
            f"{altitude:.1f},{velocity:.1f},{smooth_vel:.1f},"  # altitude, velocity, smooth_vel
            f"1013.25,{temp:.1f},300.0,"  # pressure, temp, launchsite_msl
            f"1,{ab_servo:.1f},{cnrd_servo:.1f},"  # airbrake_cont, ab_servo_pct, cnrd_servo_pct
            "1,1,0,0,"  # drogue_cont_1, drogue_cont_2, main_cont_1, main_cont_2
            "1,1,0,"  # flight_index, ellipse_on, cameras_on
            f"{battery:.1f},2"  # battery_voltage, flight_stage
        )

        # Put data in queue
        await telemetry_queue.put(csv_data)

        # Increment time and wait 500ms
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
            destination_reached=destination_reached
        )

        await telemetry_queue.put(payload)

        flight_time += 500
        await asyncio.sleep(0.5)
