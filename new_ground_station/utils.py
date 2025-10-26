"""Utility functions for the ground station."""
import asyncio
import logging
from models import TelemetryData
# from config import load_config, TelemetryConfig
from typing import Optional

logger = logging.getLogger(__name__)

# # Global config cache
# _config_cache: Optional[TelemetryConfig] = None

# Wasn't used, config is handled with frontend.
# def get_config() -> TelemetryConfig:
#     """Get cached telemetry configuration."""
#     global _config_cache
#     if _config_cache is None:
#         _config_cache = load_config()
#     return _config_cache


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
