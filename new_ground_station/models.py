from pydantic import BaseModel, Field, field_validator

from typing import Optional


class FlightComputerTelemetryData(BaseModel):
    """
    ERIS Delta flight computer telemetry data model.
    Decodes FlightStatus bitproto packets (telemetry_bp.FlightStatus).
    All values are stored in human units after conversion from the wire format.
    """

    # Time
    cur_time: int = Field(..., description="Milliseconds since launch")

    # GPS
    gps_lat: int = Field(..., description="Latitude in microdegrees (×10^6)")
    gps_lng: int = Field(..., description="Longitude in microdegrees (×10^6)")
    gps_alt: int = Field(..., description="GPS altitude in meters MSL")
    gps_sats_in_view: int = Field(..., description="GPS satellites in view")
    gps_fix_status: int = Field(
        ..., description="GPS fix status (0=no fix, 2=2D, 3=3D, 4=GNSS+DR)"
    )

    # Altitude and motion
    altitude: float = Field(..., description="Altitude MSL (meters)")
    velocity: float = Field(..., description="Velocity (m/s, from kalman)")
    acceleration: float = Field(..., description="Acceleration (m/s², from kalman)")
    vertical_velocity: float = Field(..., description="Fused vertical velocity (m/s)")

    # Control surfaces (0-100%)
    airbrake_deploy_pct: int = Field(..., description="Airbrake deployment percentage")
    canard_angle_pct: int = Field(..., description="Canard angle percentage")

    # Power
    battery_voltage: float = Field(..., description="Battery voltage (V)")

    # Environment
    temperature: float = Field(..., description="Temperature (°C)")

    # Cameras
    runcam_active: bool = Field(..., description="Runcam active")
    runcam_overcurrent: bool = Field(..., description="Runcam overcurrent")
    livecam_active: bool = Field(..., description="Live camera active")
    livecam_overcurrent: bool = Field(..., description="Live camera overcurrent")

    # Pyrotechnic continuity
    drogue_pyro_cont_1: bool = Field(
        ..., description="Drogue pyro channel 1 continuity"
    )
    drogue_pyro_cont_2: bool = Field(
        ..., description="Drogue pyro channel 2 continuity"
    )
    main_pyro_cont_1: bool = Field(..., description="Main pyro channel 1 continuity")
    main_pyro_cont_2: bool = Field(..., description="Main pyro channel 2 continuity")

    # Sensor health
    bmp1_ok: bool = Field(..., description="BMP1 barometer OK")
    bmp2_ok: bool = Field(..., description="BMP2 barometer OK")
    ext_barometer_ok: bool = Field(..., description="External barometer OK")
    bno_ok: bool = Field(..., description="BNO IMU OK")
    high_g_ok: bool = Field(..., description="High-G accelerometer OK")
    exernal_imu_ok: bool = Field(..., description="External IMU OK")

    # Filtered IMU
    roll: float = Field(..., description="Filtered roll rate (rad/s)")

    # Flight stage
    flight_stage: int = Field(..., description="Flight stage enum value")

    # Control enable flags
    canards_enabled: bool = Field(..., description="Canards enabled")
    airbrakes_enabled: bool = Field(..., description="Airbrakes enabled")

    # BNO raw acceleration Y-axis (m/s²)
    accel_y: float = Field(..., description="BNO accel Y (m/s²)")

    # High-G accelerometer Y-axis (m/s²)
    hg_accel_y: float = Field(..., description="High-G accel Y (m/s²)")

    # SD card logging enabled
    logging_enabled: bool = Field(..., description="SD card logging enabled")

    @field_validator("gps_lat", "gps_lng")
    @classmethod
    def validate_gps_coords(cls, v: int) -> int:
        """Validate GPS coordinates are within valid range."""
        # Microdegrees: lat ±90_000_000, lng ±180_000_000
        if abs(v) > 180_000_000:
            raise ValueError(f"GPS coordinate out of range: {v}")
        return v

    @classmethod
    def from_bitproto(cls, packet) -> "FlightComputerTelemetryData":
        """
        Create FlightComputerTelemetryData from a telemetry_bp.FlightStatus packet.

        Wire format conversions applied here:
          - altitude_msl_m / gps_altitude_msl_m: uint16 offset by +500 → subtract 500
          - velocity_mm_s: int20 in mm/s → divide by 1000 for m/s
          - acceleration_mss: int16 in cm/s² → divide by 100 for m/s²
          - vertical_velocity_cms: int32 in cm/s → divide by 100 for m/s
          - temperature_celsius: uint8, stored as round(°C × 2) → divide by 2
          - battery_voltage_mv: uint16 in mV → divide by 1000 for V
          - roll_filt: int16, rad/s × 100 → divide by 100
          - GPS: microdegrees (×10^6)
        """
        return cls(
            cur_time=packet.timestamp_ms,
            gps_lat=packet.gps_lat_microdeg,
            gps_lng=packet.gps_lng_microdeg,
            gps_alt=packet.gps_altitude_msl_m - 500,
            gps_sats_in_view=packet.gps_sats_in_view,
            gps_fix_status=packet.gps_fix_status,
            altitude=float(packet.altitude_msl_m - 500),
            velocity=packet.velocity_mm_s / 100.0,
            acceleration=packet.acceleration_mss / 100.0,
            vertical_velocity=packet.vertical_velocity_cms / 100.0,
            airbrake_deploy_pct=packet.airbrake_deploy_pct,
            canard_angle_pct=packet.canard_angle_pct,
            battery_voltage=packet.battery_voltage_mv / 1000.0,
            temperature=packet.temperature_celsius / 4.0,
            runcam_active=packet.runcam_active,
            runcam_overcurrent=packet.runcam_overcurrent,
            livecam_active=packet.livecam_active,
            livecam_overcurrent=packet.livecam_overcurrent,
            drogue_pyro_cont_1=packet.drogue_pyro_cont_1,
            drogue_pyro_cont_2=packet.drogue_pyro_cont_2,
            main_pyro_cont_1=packet.main_pyro_cont_1,
            main_pyro_cont_2=packet.main_pyro_cont_2,
            bmp1_ok=packet.bmp1_ok,
            bmp2_ok=packet.bmp2_ok,
            ext_barometer_ok=packet.ext_barometer_ok,
            bno_ok=packet.bno_ok,
            high_g_ok=packet.high_g_ok,
            exernal_imu_ok=packet.exernal_imu_ok,
            roll=packet.roll_filt / 100.0,
            flight_stage=int(packet.flight_stage),
            canards_enabled=packet.canards_enabled,
            airbrakes_enabled=packet.airbrakes_enabled,
            accel_y=packet.accel_y / 100.0,
            hg_accel_y=packet.hg_accel_y / 10.0,
            logging_enabled=packet.logging_enabled,
        )

    def get_gps_lat_degrees(self) -> float:
        """Convert microdegree latitude to degrees."""
        return self.gps_lat / 1_000_000.0

    def get_gps_lng_degrees(self) -> float:
        """Convert microdegree longitude to degrees."""
        return self.gps_lng / 1_000_000.0

    def get_gps_alt_meters(self) -> float:
        """GPS altitude in meters MSL."""
        return float(self.gps_alt)


class PayloadTelemetryData(BaseModel):
    """
    Payload telemetry data model.
    Contains subset of flight computer fields plus payload-specific fields.
    """

    # Time
    cur_time: int = Field(..., description="Milliseconds since boot")

    # GPS (shared with flight computer)
    gps_lat: int = Field(..., description="Latitude in degrees × 10^7")
    gps_lng: int = Field(..., description="Longitude in degrees × 10^7")
    gps_alt: int = Field(..., description="GPS altitude in millimeters")

    # Motion (subset of flight computer)
    velocity: float = Field(..., description="Velocity (m/s)")
    accel_x: float = Field(..., description="Acceleration X-axis (m/s²)")
    accel_y: float = Field(..., description="Acceleration Y-axis (m/s²)")
    accel_z: float = Field(..., description="Acceleration Z-axis (m/s²)")

    # Payload-specific fields
    distance_to_target: float = Field(..., description="Distance to target (meters)")
    destination_reached: bool = Field(
        ..., description="Whether destination has been reached"
    )

    @field_validator("gps_lat", "gps_lng")
    @classmethod
    def validate_gps_coords(cls, v: int) -> int:
        """Validate GPS coordinates are within valid range."""
        if abs(v) > 1800000000:
            raise ValueError(f"GPS coordinate out of range: {v}")
        return v

    @classmethod
    def from_bitproto(cls, packet) -> "PayloadTelemetryData":
        """
        Create PayloadTelemetryData from a Bitproto packet.

        Args:
            packet: payload_bp.PayloadPacket instance
        """
        return cls(
            cur_time=packet.cur_time,
            gps_lat=packet.gps_lat,
            gps_lng=packet.gps_lng,
            gps_alt=packet.gps_alt,
            velocity=uint32_to_float(packet.velocity),
            accel_x=uint32_to_float(packet.accel_x),
            accel_y=uint32_to_float(packet.accel_y),
            accel_z=uint32_to_float(packet.accel_z),
            distance_to_target=uint32_to_float(packet.distance_to_target),
            destination_reached=packet.destination_reached,
        )

    def get_gps_lat_degrees(self) -> float:
        """Convert scaled GPS latitude to degrees."""
        return self.gps_lat / 10_000_000.0

    def get_gps_lng_degrees(self) -> float:
        """Convert scaled GPS longitude to degrees."""
        return self.gps_lng / 10_000_000.0

    def get_gps_alt_meters(self) -> float:
        """Convert GPS altitude from millimeters to meters."""
        return self.gps_alt / 1000.0
