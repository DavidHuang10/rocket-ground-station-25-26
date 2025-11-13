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

    def get_all_data(self, takeoff_offset: Optional[float] = None) -> List[Dict]:
        """
        Return all telemetry data formatted for frontend.

        Args:
            takeoff_offset: Optional offset in seconds for time adjustment

        Returns:
            List of dicts with {time, source, value} format
        """
        from utils import format_for_frontend

        result = []
        for telem in self.telemetry_buffer:
            result.extend(format_for_frontend(telem, takeoff_offset))
        return result

    def clear_buffer(self):
        """Clear in-memory telemetry buffer."""
        self.telemetry_buffer.clear()
        logger.info("Telemetry buffer cleared")

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

        # Create backups directory
        self.backups_dir = Path(log_dir).parent / "backups"
        self.backups_dir.mkdir(exist_ok=True)

        # Time tracking for takeoff offset
        self.takeoff_offset_time: Optional[float] = None  # seconds since boot
        self.takeoff_wall_time: Optional[datetime] = None  # wall clock time of takeoff
        self.last_telemetry_time: Optional[float] = None  # seconds since boot (from cur_time)

        # Backup existing current.csv if it exists
        current_csv = self.log_dir / "current.csv"
        if current_csv.exists():
            recovery_timestamp = self._generate_timestamp()
            recovery_path = self.backups_dir / f"recovery_{recovery_timestamp}.csv"
            shutil.move(str(current_csv), str(recovery_path))
            logger.info(f"Backed up existing current.csv to {recovery_path.name}")

        # Auto-start session on server boot
        self.current_session = FlightSession(self.log_dir)

        logger.info(f"Storage manager initialized: {self.log_dir}")
        logger.info(f"Backups directory: {self.backups_dir}")

    def add_telemetry(self, telemetry: TelemetryData):
        """
        Add telemetry packet to current session.

        Args:
            telemetry: Validated telemetry data
        """
        # Track last telemetry time (cur_time is in milliseconds)
        self.last_telemetry_time = telemetry.cur_time / 1000.0  # Convert to seconds

        self.current_session.add_telemetry(telemetry)

    def get_current_data(self) -> List[Dict]:
        """
        Get all telemetry data from current session with time adjustment applied.

        Returns:
            List of formatted telemetry data points (with adjusted times if takeoff occurred)
        """
        return self.current_session.get_all_data(self.takeoff_offset_time)

    def clear_data(self) -> Dict:
        """
        Clear charts and mark takeoff (T+0).
        Moves current.csv to backups/pre_flight_*.csv (NON-DESTRUCTIVE).
        Sets takeoff offset for time adjustment.

        Returns:
            Dict with status, backup filename, takeoff offset, and takeoff time
        """
        if self.last_telemetry_time is None:
            logger.warning("No telemetry received yet, cannot mark takeoff")
            return {
                "status": "error",
                "message": "No telemetry received yet"
            }

        # Generate timestamp
        timestamp = self._generate_timestamp()

        # Close current CSV file
        self.current_session.close()

        # Move current.csv to backups/pre_flight_*.csv (ONLY to backups, NOT flight_logs)
        src_path = self.log_dir / "current.csv"
        backup_path = self.backups_dir / f"pre_flight_{timestamp}.csv"
        self._move_file(src_path, backup_path)

        # Record takeoff offset (use last received telemetry time)
        self.takeoff_offset_time = self.last_telemetry_time
        self.takeoff_wall_time = datetime.now()

        # Create new session with fresh current.csv (old buffer discarded)
        self.current_session = FlightSession(self.log_dir)

        logger.info(f"Takeoff marked at T+0 (offset: {self.takeoff_offset_time:.3f}s)")

        return {
            "status": "success",
            "backup_filename": backup_path.name,
            "takeoff_offset": self.takeoff_offset_time,
            "takeoff_time": self.takeoff_wall_time.isoformat()
        }

    def save_flight(self) -> Dict:
        """
        Archive current.csv to timestamped file (keeps recording).
        Copies to BOTH backups/ and flight_logs/.

        Returns:
            Dict with status, filename, and save time
        """
        timestamp = self._generate_timestamp()

        # Ensure current data is flushed
        self.current_session.csv_file.flush()

        # Copy to backups (redundant backup)
        backup_path = self.backups_dir / f"flight_{timestamp}.csv"
        self._copy_file(self.current_session.csv_path, backup_path)

        # Copy to flight_logs (official save)
        archive_path = self.log_dir / f"flight_{timestamp}.csv"
        self._copy_file(self.current_session.csv_path, archive_path)

        logger.info(f"Flight saved: {archive_path.name}")

        return {
            "status": "success",
            "filename": archive_path.name,
            "saved_at": datetime.now().isoformat()
        }

    def save_and_clear(self) -> Dict:
        """
        Archive current flight and clear all data.
        This is the "end flight and start new" operation.
        Resets takeoff offset to None.

        Returns:
            Dict with status, filename, and save time
        """
        timestamp = self._generate_timestamp()

        # Ensure current data is flushed
        self.current_session.csv_file.flush()

        # Close current session
        self.current_session.close()

        # Copy to backups (redundant backup)
        src_path = self.log_dir / "current.csv"
        backup_path = self.backups_dir / f"flight_{timestamp}.csv"
        self._copy_file(src_path, backup_path)

        # Move to flight_logs (official save and remove from active)
        archive_path = self.log_dir / f"flight_{timestamp}.csv"
        self._move_file(src_path, archive_path)

        # Reset takeoff offset
        self.takeoff_offset_time = None
        self.takeoff_wall_time = None

        # Create new session with fresh current.csv (old buffer discarded)
        self.current_session = FlightSession(self.log_dir)

        logger.info(f"Flight saved and cleared: {archive_path.name}")

        return {
            "status": "success",
            "filename": archive_path.name,
            "saved_at": datetime.now().isoformat()
        }

    def get_session_info(self) -> Dict:
        """
        Get current session metadata including takeoff information.

        Returns:
            Dict with session start time, packet count, duration, and takeoff info
        """
        duration = (datetime.now() - self.current_session.start_time).total_seconds()
        return {
            "start_time": self.current_session.start_time.isoformat(),
            "packet_count": len(self.current_session.telemetry_buffer),
            "duration_seconds": duration,
            "takeoff_offset": self.takeoff_offset_time,
            "takeoff_time": self.takeoff_wall_time.isoformat() if self.takeoff_wall_time else None
        }

    def _generate_timestamp(self) -> str:
        """
        Generate timestamp string for filenames.

        Returns:
            Timestamp string in format: YYYY-MM-DD_HH-MM-SS
        """
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def _copy_file(self, src: Path, dest: Path):
        """
        Copy file from source to destination.

        Args:
            src: Source file path
            dest: Destination file path
        """
        shutil.copy(str(src), str(dest))
        logger.info(f"Copied {src.name} -> {dest.name}")

    def _move_file(self, src: Path, dest: Path):
        """
        Move file from source to destination.

        Args:
            src: Source file path
            dest: Destination file path
        """
        shutil.move(str(src), str(dest))
        logger.info(f"Moved {src.name} -> {dest.name}")

    def shutdown(self):
        """Clean shutdown - close CSV file."""
        self.current_session.close()
        logger.info("Storage manager shut down")
