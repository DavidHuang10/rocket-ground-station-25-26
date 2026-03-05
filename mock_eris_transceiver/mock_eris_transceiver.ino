/*
 * Mock Arduino Telemetry Transceiver
 *
 * Demonstrates sending Bitproto telemetry over Serial with Length-Prefix
 * framing. Format: [Length (1 byte)] [Bitproto Payload (N bytes)]
 *
 * REQUIRES: Bitproto library (bitproto.h, bitproto.c)
 */

#include "bitproto.h"
#include "telemetry_bp.h"

// Helper to convert float to uint32 (preserves IEEE 754 bits)
union FloatUint32 {
  float f;
  uint32_t u;
};

inline uint32_t floatToUint32(float val) {
  union FloatUint32 converter;
  converter.f = val;
  return converter.u;
}

void setup() {
  Serial.begin(115200);
  while (!Serial)
    ;
}

void loop() {
  // 1. Initialize message
  struct TelemetryPacket message = {0};

  // 2. Populate fields with DYNAMIC data
  float t = millis() / 1000.0; // Time in seconds
  message.cur_time = millis();

  message.gps_lat = 359940330;
  message.gps_lng = -788986220;
  message.gps_alt = 150000;

  // DYNAMIC 1: Altitude (Sine Wave 100-200m)
  float alt_baro = 150.0 + 50.0 * sin(t * 0.5);
  message.alt_baro = floatToUint32(alt_baro);

  // DYNAMIC 2: Vertical Velocity (Cosine)
  float vel_vertical = 25.0 * cos(t * 0.5);
  message.vel_vertical = floatToUint32(vel_vertical);
  message.smooth_vel = floatToUint32(vel_vertical);

  // DYNAMIC 3: Pressure (Inverse of Alt)
  float press = 1013.25 - (alt_baro / 10.0);
  message.press = floatToUint32(press);

  // DYNAMIC 4: Accel Z (Gravity + Noise)
  float accel_z = 9.81 + (random(-50, 50) / 100.0);
  message.accel_z = floatToUint32(accel_z);
  message.hg_accel = floatToUint32(9.80);

  message.accel_x = floatToUint32(0.5);
  message.accel_y = floatToUint32(0.12);
  message.gyro_x = floatToUint32(0.01);
  message.gyro_y = floatToUint32(-0.02);
  message.gyro_z = floatToUint32(0.00);
  message.temp = floatToUint32(25.4);
  message.launchsite_msl = floatToUint32(30.0);
  message.airbrake_cont = true;
  message.ab_servo_pct = floatToUint32(45.0);
  message.cnrd_servo_pct = floatToUint32(0.0);

  message.drogue_pyro_cont_1 = true;
  message.drogue_pyro_cont_2 = true;
  message.main_pyro_cont_1 = false;
  message.main_pyro_cont_2 = false;

  message.flight_index = 0;
  message.ellipse_on = true;

  // DYNAMIC 5 (Binary): Cameras - Toggle every 3s
  message.cameras_on = (millis() % 6000) < 3000;

  // DYNAMIC 6: Battery - Slow Drain
  float battery_voltage = 12.6 - (millis() / 600000.0);
  message.battery_voltage = floatToUint32(battery_voltage);

  message.flight_stage = 2; // Burn state

  // 3. Encode to Buffer using Bitproto
  // BYTES_LENGTH_TELEMETRY_PACKET is defined in telemetry_bp.h (89 bytes)
  uint8_t buffer[BYTES_LENGTH_TELEMETRY_PACKET];
  memset(buffer, 0, sizeof(buffer));

  int encoded_bytes = EncodeTelemetryPacket(&message, buffer);

  // 4. Send Framed Packet: [Sync1] [Sync2] [ID] + [Payload]
  // Note: Bitproto produces fixed-size output (BYTES_LENGTH_TELEMETRY_PACKET)
  uint8_t len = BYTES_LENGTH_TELEMETRY_PACKET;
  Serial.write(0xAA);        // Sync Byte 1
  Serial.write(0xBB);        // Sync Byte 2
  Serial.write(0x01);        // Type ID (Eris = 0x01)
  Serial.write(buffer, len); // Send Payload

  delay(500);
}
