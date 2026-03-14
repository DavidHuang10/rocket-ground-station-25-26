"""
Telemetry data storage and session management.
Handles writing telemetry to disk and managing flight sessions.
Uses abstract base classes to support multiple telemetry types.
"""

import csv
import shutil
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, TypeVar, Generic
from models import FlightComputerTelemetryData, PayloadTelemetryData

logger = logging.getLogger(__name__)

# Generic type for telemetry data
T = TypeVar("T")


class BaseFlightSession(ABC, Generic[T]):
    """
    Abstract base class for flight sessions.
    Manages in-memory buffer and CSV logging for a single session.
    """

    def __init__(self, log_dir: Path, session_name: str = "Flight"):
        self.log_dir = log_dir
        self.start_time = datetime.now()
        self.telemetry_buffer: List[T] = []
        self.session_name = session_name

        self.csv_path = log_dir / "current.csv"
        self.csv_file = open(self.csv_path, "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self._write_csv_header()

        logger.info(f"{session_name} session started: {self.csv_path}")

    def add_telemetry(self, telemetry: T):
        """Add telemetry packet to session."""
        self.telemetry_buffer.append(telemetry)
        self._append_csv_row(telemetry)
        self.csv_file.flush()

    def get_all_data(self, takeoff_offset: Optional[float] = None) -> List[Dict]:
        """Return all telemetry data formatted for frontend."""
        result = []
        for telem in self.telemetry_buffer:
            result.extend(self._format_for_frontend(telem, takeoff_offset))
        return result

    def clear_buffer(self):
        """Clear in-memory telemetry buffer."""
        self.telemetry_buffer.clear()
        logger.info(f"{self.session_name} telemetry buffer cleared")

    def close(self):
        """Close CSV file cleanly."""
        if self.csv_file and not self.csv_file.closed:
            self.csv_file.close()
            logger.info(f"{self.session_name} CSV file closed")

    @abstractmethod
    def _write_csv_header(self):
        """Write CSV header row. Subclasses define their own columns."""
        pass

    @abstractmethod
    def _append_csv_row(self, telemetry: T):
        """Append telemetry packet as CSV row. Subclasses define their own format."""
        pass

    @abstractmethod
    def _format_for_frontend(
        self, telemetry: T, takeoff_offset: Optional[float]
    ) -> List[Dict]:
        """Format telemetry for frontend. Subclasses define their own format."""
        pass


class ErisFlightSession(BaseFlightSession[FlightComputerTelemetryData]):
    """Flight session for Eris flight computer telemetry."""

    def __init__(self, log_dir: Path):
        super().__init__(log_dir, "Eris")

    def _write_csv_header(self):
        header = [
            "timestamp",
            "cur_time",
            "gps_lat",
            "gps_lng",
            "gps_alt",
            "gps_sats_in_view",
            "gps_fix_status",
            "altitude",
            "velocity",
            "acceleration",
            "fused_baro_agl",
            "airbrake_deploy_pct",
            "canard_angle_pct",
            "battery_voltage",
            "temperature",
            "runcam_active",
            "runcam_overcurrent",
            "livecam_active",
            "livecam_overcurrent",
            "drogue_pyro_cont_1",
            "drogue_pyro_cont_2",
            "main_pyro_cont_1",
            "main_pyro_cont_2",
            "bmp1_ok",
            "bmp2_ok",
            "ext_barometer_ok",
            "bno_ok",
            "high_g_ok",
            "exernal_imu_ok",
            "roll",
            "flight_stage",
            "canards_enabled",
            "airbrakes_enabled",
            "accel_y",
            "hg_accel_y",
        ]
        self.csv_writer.writerow(header)

    def _append_csv_row(self, telemetry: FlightComputerTelemetryData):
        row = [
            datetime.now().isoformat(),
            telemetry.cur_time,
            telemetry.gps_lat,
            telemetry.gps_lng,
            telemetry.gps_alt,
            telemetry.gps_sats_in_view,
            telemetry.gps_fix_status,
            telemetry.altitude,
            telemetry.velocity,
            telemetry.acceleration,
            telemetry.fused_baro_agl,
            telemetry.airbrake_deploy_pct,
            telemetry.canard_angle_pct,
            telemetry.battery_voltage,
            telemetry.temperature,
            int(telemetry.runcam_active),
            int(telemetry.runcam_overcurrent),
            int(telemetry.livecam_active),
            int(telemetry.livecam_overcurrent),
            int(telemetry.drogue_pyro_cont_1),
            int(telemetry.drogue_pyro_cont_2),
            int(telemetry.main_pyro_cont_1),
            int(telemetry.main_pyro_cont_2),
            int(telemetry.bmp1_ok),
            int(telemetry.bmp2_ok),
            int(telemetry.ext_barometer_ok),
            int(telemetry.bno_ok),
            int(telemetry.high_g_ok),
            int(telemetry.exernal_imu_ok),
            telemetry.roll,
            telemetry.flight_stage,
            int(telemetry.canards_enabled),
            int(telemetry.airbrakes_enabled),
            telemetry.accel_y,
            telemetry.hg_accel_y,
        ]
        self.csv_writer.writerow(row)

    def _format_for_frontend(
        self, telemetry: FlightComputerTelemetryData, takeoff_offset: Optional[float]
    ) -> List[Dict]:
        from utils import format_for_frontend

        return format_for_frontend(telemetry, takeoff_offset)


class PayloadFlightSession(BaseFlightSession[PayloadTelemetryData]):
    """Flight session for payload telemetry."""

    def __init__(self, log_dir: Path):
        super().__init__(log_dir, "Payload")

    def _write_csv_header(self):
        header = [
            "timestamp",
            "cur_time",
            "gps_lat",
            "gps_lng",
            "gps_alt",
            "velocity",
            "accel_x",
            "accel_y",
            "accel_z",
            "distance_to_target",
            "destination_reached",
        ]
        self.csv_writer.writerow(header)

    def _append_csv_row(self, telemetry: PayloadTelemetryData):
        row = [
            datetime.now().isoformat(),
            telemetry.cur_time,
            telemetry.gps_lat,
            telemetry.gps_lng,
            telemetry.gps_alt,
            telemetry.velocity,
            telemetry.accel_x,
            telemetry.accel_y,
            telemetry.accel_z,
            telemetry.distance_to_target,
            int(telemetry.destination_reached),
        ]
        self.csv_writer.writerow(row)

    def _format_for_frontend(
        self, telemetry: PayloadTelemetryData, takeoff_offset: Optional[float]
    ) -> List[Dict]:
        from utils import format_payload_for_frontend

        return format_payload_for_frontend(telemetry, takeoff_offset)


class BaseStorageManager(ABC, Generic[T]):
    """
    Abstract base class for storage managers.
    Manages flight sessions with CSV logging and backup functionality.
    """

    def __init__(self, log_dir: str, backup_prefix: str = ""):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.backup_prefix = backup_prefix

        self.backups_dir = self.log_dir.parent / "backups"
        self.backups_dir.mkdir(exist_ok=True)

        self.takeoff_offset_time: Optional[float] = None
        self.takeoff_wall_time: Optional[datetime] = None
        self.last_telemetry_time: Optional[float] = None

        # Backup existing current.csv if it exists
        current_csv = self.log_dir / "current.csv"
        if current_csv.exists():
            recovery_timestamp = self._generate_timestamp()
            prefix = f"{backup_prefix}_" if backup_prefix else ""
            recovery_path = (
                self.backups_dir / f"{prefix}recovery_{recovery_timestamp}.csv"
            )
            shutil.move(str(current_csv), str(recovery_path))
            logger.info(f"Backed up existing current.csv to {recovery_path.name}")

        self.current_session = self._create_session()
        logger.info(f"Storage manager initialized: {self.log_dir}")

    @abstractmethod
    def _create_session(self) -> BaseFlightSession[T]:
        """Create a new flight session. Subclasses return their specific session type."""
        pass

    def add_telemetry(self, telemetry: T):
        """Add telemetry packet to current session."""
        self.last_telemetry_time = self._get_time_from_telemetry(telemetry)
        self.current_session.add_telemetry(telemetry)

    def _get_time_from_telemetry(self, telemetry: T) -> float:
        """Extract time (in seconds) from telemetry. Assumes cur_time in ms."""
        return telemetry.cur_time / 1000.0

    def get_current_data(self) -> List[Dict]:
        """Get all telemetry data from current session."""
        return self.current_session.get_all_data(self.takeoff_offset_time)

    def clear_data(self) -> Dict:
        """Clear charts and mark takeoff (T+0)."""
        if self.last_telemetry_time is None:
            logger.warning("No telemetry received yet, cannot mark takeoff")
            return {"status": "error", "message": "No telemetry received yet"}

        timestamp = self._generate_timestamp()
        self.current_session.close()

        src_path = self.log_dir / "current.csv"
        prefix = f"{self.backup_prefix}_" if self.backup_prefix else ""
        backup_path = self.backups_dir / f"{prefix}pre_flight_{timestamp}.csv"
        self._move_file(src_path, backup_path)

        self.takeoff_offset_time = self.last_telemetry_time
        self.takeoff_wall_time = datetime.now()

        self.current_session = self._create_session()

        logger.info(f"Takeoff marked at T+0 (offset: {self.takeoff_offset_time:.3f}s)")

        return {
            "status": "success",
            "backup_filename": backup_path.name,
            "takeoff_offset": self.takeoff_offset_time,
            "takeoff_time": self.takeoff_wall_time.isoformat(),
        }

    def save_flight(self) -> Dict:
        """Archive current flight to timestamped file."""
        timestamp = self._generate_timestamp()
        self.current_session.csv_file.flush()

        prefix = f"{self.backup_prefix}_" if self.backup_prefix else ""
        backup_path = self.backups_dir / f"{prefix}flight_{timestamp}.csv"
        self._copy_file(self.current_session.csv_path, backup_path)

        archive_path = self.log_dir / f"flight_{timestamp}.csv"
        self._copy_file(self.current_session.csv_path, archive_path)

        logger.info(f"Flight saved: {archive_path.name}")

        return {
            "status": "success",
            "filename": archive_path.name,
            "saved_at": datetime.now().isoformat(),
        }

    def get_session_info(self) -> Dict:
        """Get current session metadata."""
        duration = (datetime.now() - self.current_session.start_time).total_seconds()
        return {
            "start_time": self.current_session.start_time.isoformat(),
            "packet_count": len(self.current_session.telemetry_buffer),
            "duration_seconds": duration,
            "takeoff_offset": self.takeoff_offset_time,
            "takeoff_time": (
                self.takeoff_wall_time.isoformat() if self.takeoff_wall_time else None
            ),
        }

    def _generate_timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def _copy_file(self, src: Path, dest: Path):
        shutil.copy(str(src), str(dest))
        logger.info(f"Copied {src.name} -> {dest.name}")

    def _move_file(self, src: Path, dest: Path):
        shutil.move(str(src), str(dest))
        logger.info(f"Moved {src.name} -> {dest.name}")

    def shutdown(self):
        """Clean shutdown - close CSV file."""
        self.current_session.close()
        logger.info("Storage manager shut down")


class StorageManager(BaseStorageManager[FlightComputerTelemetryData]):
    """Storage manager for Eris flight computer telemetry."""

    def __init__(self, log_dir: str = "flight_logs/eris"):
        super().__init__(log_dir, backup_prefix="eris")

    def _create_session(self) -> ErisFlightSession:
        return ErisFlightSession(self.log_dir)


class PayloadStorageManager(BaseStorageManager[PayloadTelemetryData]):
    """Storage manager for payload telemetry."""

    def __init__(self, log_dir: str = "flight_logs/payload"):
        super().__init__(log_dir, backup_prefix="payload")

    def _create_session(self) -> PayloadFlightSession:
        return PayloadFlightSession(self.log_dir)
