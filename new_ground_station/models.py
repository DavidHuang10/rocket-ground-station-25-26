from pydantic import BaseModel, Field, field_validator
from typing import Optional


class TelemetryData(BaseModel):
    """
    ERIS Delta flight computer telemetry data model.
    Parses 29-field CSV format transmitted at 2Hz (500ms interval).
    """

    # Time and position
    cur_time: int = Field(..., description="Milliseconds since boot")
    gps_lat: int = Field(..., description="Latitude in degrees × 10^7")
    gps_lng: int = Field(..., description="Longitude in degrees × 10^7")
    gps_alt: int = Field(..., description="GPS altitude in millimeters")

    # IMU - Accelerometer (m/s²)
    accel_x: float = Field(..., description="Acceleration X-axis (m/s²)")
    accel_y: float = Field(..., description="Acceleration Y-axis (m/s²)")
    accel_z: float = Field(..., description="Acceleration Z-axis (m/s²)")

    # IMU - Gyroscope (rad/s)
    gyro_x: float = Field(..., description="Gyroscope X-axis (rad/s)")
    gyro_y: float = Field(..., description="Gyroscope Y-axis (rad/s)")
    gyro_z: float = Field(..., description="Gyroscope Z-axis (rad/s)")

    # High-G accelerometer
    hg_accel: float = Field(..., description="High-G accelerometer (m/s²)")

    # Altimeter data
    altitude: float = Field(..., description="Altitude AGL (meters)")
    velocity: float = Field(..., description="Vertical velocity (m/s)")
    smooth_vel: float = Field(..., description="Smoothed velocity (m/s)")
    pressure: float = Field(..., description="Barometric pressure (hPa)")
    temperature: float = Field(..., description="Temperature (°C)")
    launchsite_msl: float = Field(..., description="Launch site MSL altitude (m)")

    # Airbrake system
    airbrake_cont: bool = Field(..., description="Airbrake continuity")
    ab_servo_pct: float = Field(..., description="Airbrake servo position (%)")
    cnrd_servo_pct: float = Field(..., description="Canard servo position (%)")

    # Pyrotechnic continuity
    drogue_pyro_cont_1: bool = Field(..., description="Drogue pyro channel 1 continuity")
    drogue_pyro_cont_2: bool = Field(..., description="Drogue pyro channel 2 continuity")
    main_pyro_cont_1: bool = Field(..., description="Main pyro channel 1 continuity")
    main_pyro_cont_2: bool = Field(..., description="Main pyro channel 2 continuity")

    # Flight metadata
    flight_index: int = Field(..., description="Flight index number")
    ellipse_on: bool = Field(..., description="Ellipse system status")
    cameras_on: bool = Field(..., description="Camera system status")
    battery_voltage: float = Field(..., description="Battery voltage (V)")
    flight_stage: int = Field(..., ge=0, le=6, description="Flight stage (0-6)")

    @field_validator('gps_lat', 'gps_lng')
    @classmethod
    def validate_gps_coords(cls, v: int) -> int:
        """Validate GPS coordinates are within valid range (before scaling)."""
        # Latitude: -90 to 90 degrees × 10^7 = -900000000 to 900000000
        # Longitude: -180 to 180 degrees × 10^7 = -1800000000 to 1800000000
        if abs(v) > 1800000000:
            raise ValueError(f"GPS coordinate out of range: {v}")
        return v

    @classmethod
    def from_csv(cls, csv_line: str) -> "TelemetryData":
        """
        Parse CSV line into TelemetryData model.

        Args:
            csv_line: Comma-separated string with 29 fields

        Returns:
            TelemetryData instance

        Raises:
            ValueError: If field count is incorrect or parsing fails
            pydantic.ValidationError: If data validation fails
        """
        fields = csv_line.strip().split(',')
        if len(fields) != 29:
            raise ValueError(f"Expected 29 fields, got {len(fields)}")

        try:
            return cls(
                cur_time=int(fields[0]),
                gps_lat=int(fields[1]),
                gps_lng=int(fields[2]),
                gps_alt=int(fields[3]),
                accel_x=float(fields[4]),
                accel_y=float(fields[5]),
                accel_z=float(fields[6]),
                gyro_x=float(fields[7]),
                gyro_y=float(fields[8]),
                gyro_z=float(fields[9]),
                hg_accel=float(fields[10]),
                altitude=float(fields[11]),
                velocity=float(fields[12]),
                smooth_vel=float(fields[13]),
                pressure=float(fields[14]),
                temperature=float(fields[15]),
                launchsite_msl=float(fields[16]),
                airbrake_cont=bool(int(fields[17])),
                ab_servo_pct=float(fields[18]),
                cnrd_servo_pct=float(fields[19]),
                drogue_pyro_cont_1=bool(int(fields[20])),
                drogue_pyro_cont_2=bool(int(fields[21])),
                main_pyro_cont_1=bool(int(fields[22])),
                main_pyro_cont_2=bool(int(fields[23])),
                flight_index=int(fields[24]),
                ellipse_on=bool(int(fields[25])),
                cameras_on=bool(int(fields[26])),
                battery_voltage=float(fields[27]),
                flight_stage=int(fields[28])
            )
        except (ValueError, IndexError) as e:
            raise ValueError(f"Failed to parse CSV: {e}") from e

    def get_gps_lat_degrees(self) -> float:
        """Convert scaled GPS latitude to degrees."""
        return self.gps_lat / 10_000_000.0

    def get_gps_lng_degrees(self) -> float:
        """Convert scaled GPS longitude to degrees."""
        return self.gps_lng / 10_000_000.0

    def get_gps_alt_meters(self) -> float:
        """Convert GPS altitude from millimeters to meters."""
        return self.gps_alt / 1000.0
