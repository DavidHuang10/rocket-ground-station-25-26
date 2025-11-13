"""
Telemetry data storage and session management.
Handles writing telemetry to disk and managing flight sessions.
"""

import csv
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from models import TelemetryData

logger = logging.getLogger(__name__)


class FlightSession:
    """
    Manages a single ongoing flight session.
    Data is stored in memory and written to current.csv in real-time.
    """

    def __init__(self, log_dir: Path):
        """
        Initialize flight session.

        Args:
            log_dir: Directory where CSV files will be stored
        """
        self.log_dir = log_dir
        self.start_time = datetime.now()
        self.telemetry_buffer: List[TelemetryData] = []

        # Always write to "current.csv"
        self.csv_path = log_dir / "current.csv"
        self.csv_file = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self._write_csv_header()

        logger.info(f"Flight session started: {self.csv_path}")

    def add_telemetry(self, telemetry: TelemetryData):
        """
        Add telemetry packet to session.
        Appends to in-memory buffer and writes to CSV file.

        Args:
            telemetry: Validated telemetry data packet
        """
        # Add to memory buffer
        self.telemetry_buffer.append(telemetry)

        # Write to CSV immediately
        self._append_csv_row(telemetry)
        self.csv_file.flush()  # Ensure data is written to disk

    def get_all_data(self) -> List[Dict]:
        """
        Return all telemetry data formatted for frontend.

        Returns:
            List of dicts with {time, source, value} format
        """
        from utils import format_for_frontend

        result = []
        for telem in self.telemetry_buffer:
            result.extend(format_for_frontend(telem))
        return result

    def clear_buffer(self):
        """Clear in-memory telemetry buffer."""
        self.telemetry_buffer.clear()
        logger.info("Telemetry buffer cleared")

    def reset_csv(self):
        """
        Truncate CSV file and restart with headers.
        Used when clearing charts.
        """
        # Close existing file
        self.csv_file.close()

        # Reopen in write mode (truncates)
        self.csv_file = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self._write_csv_header()

        logger.info("CSV file reset")

    def _write_csv_header(self):
        """Write CSV header row with all field names."""
        header = [
            "timestamp",
            "cur_time",
            "gps_lat",
            "gps_lng",
            "gps_alt",
            "accel_x",
            "accel_y",
            "accel_z",
            "gyro_x",
            "gyro_y",
            "gyro_z",
            "hg_accel",
            "altitude",
            "velocity",
            "smooth_vel",
            "pressure",
            "temperature",
            "launchsite_msl",
            "airbrake_cont",
            "ab_servo_pct",
            "cnrd_servo_pct",
            "drogue_pyro_cont_1",
            "drogue_pyro_cont_2",
            "main_pyro_cont_1",
            "main_pyro_cont_2",
            "flight_index",
            "ellipse_on",
            "cameras_on",
            "battery_voltage",
            "flight_stage"
        ]
        self.csv_writer.writerow(header)

    def _append_csv_row(self, telemetry: TelemetryData):
        """
        Append single telemetry packet as CSV row.

        Args:
            telemetry: Telemetry data to write
        """
        row = [
            datetime.now().isoformat(),
            telemetry.cur_time,
            telemetry.gps_lat,
            telemetry.gps_lng,
            telemetry.gps_alt,
            telemetry.accel_x,
            telemetry.accel_y,
            telemetry.accel_z,
            telemetry.gyro_x,
            telemetry.gyro_y,
            telemetry.gyro_z,
            telemetry.hg_accel,
            telemetry.altitude,
            telemetry.velocity,
            telemetry.smooth_vel,
            telemetry.pressure,
            telemetry.temperature,
            telemetry.launchsite_msl,
            int(telemetry.airbrake_cont),
            telemetry.ab_servo_pct,
            telemetry.cnrd_servo_pct,
            int(telemetry.drogue_pyro_cont_1),
            int(telemetry.drogue_pyro_cont_2),
            int(telemetry.main_pyro_cont_1),
            int(telemetry.main_pyro_cont_2),
            telemetry.flight_index,
            int(telemetry.ellipse_on),
            int(telemetry.cameras_on),
            telemetry.battery_voltage,
            telemetry.flight_stage
        ]
        self.csv_writer.writerow(row)

    def close(self):
        """Close CSV file cleanly."""
        if self.csv_file and not self.csv_file.closed:
            self.csv_file.close()
            logger.info("CSV file closed")


class StorageManager:
    """
    Manages single ongoing flight session with CSV logging.
    Session auto-starts on server boot.
    """

    def __init__(self, log_dir: str = "flight_logs"):
        """
        Initialize storage manager.

        Args:
            log_dir: Directory path for storing flight logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Auto-start session on server boot
        self.current_session = FlightSession(self.log_dir)

        logger.info(f"Storage manager initialized: {self.log_dir}")

    def add_telemetry(self, telemetry: TelemetryData):
        """
        Add telemetry packet to current session.

        Args:
            telemetry: Validated telemetry data
        """
        self.current_session.add_telemetry(telemetry)

    def get_current_data(self) -> List[Dict]:
        """
        Get all telemetry data from current session.

        Returns:
            List of formatted telemetry data points
        """
        return self.current_session.get_all_data()

    def clear_data(self):
        """
        Clear all data (memory buffer + CSV file).
        Charts will reset but session continues.
        """
        self.current_session.clear_buffer()
        self.current_session.reset_csv()
        logger.info("All data cleared")

    def save_flight(self) -> str:
        """
        Archive current.csv to timestamped file.
        Session continues running.

        Returns:
            Filename of archived flight
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_path = self.log_dir / f"flight_{timestamp}.csv"

        # Ensure current data is flushed
        self.current_session.csv_file.flush()

        # Copy current.csv to archive
        shutil.copy(self.current_session.csv_path, archive_path)

        logger.info(f"Flight archived: {archive_path.name}")
        return archive_path.name

    def save_and_clear(self) -> str:
        """
        Archive current flight and clear all data.
        This is the "end flight and start new" operation.

        Returns:
            Filename of archived flight
        """
        filename = self.save_flight()
        self.clear_data()
        logger.info(f"Flight saved and cleared: {filename}")
        return filename

    def get_session_info(self) -> Dict:
        """
        Get current session metadata.

        Returns:
            Dict with session start time, packet count, duration
        """
        duration = (datetime.now() - self.current_session.start_time).total_seconds()
        return {
            "start_time": self.current_session.start_time.isoformat(),
            "packet_count": len(self.current_session.telemetry_buffer),
            "duration_seconds": duration
        }

    def shutdown(self):
        """Clean shutdown - close CSV file."""
        self.current_session.close()
        logger.info("Storage manager shut down")
