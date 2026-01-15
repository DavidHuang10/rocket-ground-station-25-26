/*
 * Mock Arduino Telemetry Transceiver
 * 
 * Demonstrates sending Protobuf telemetry over Serial with Length-Prefix framing.
 * Format: [Length (1 byte)] [Protobuf Payload (N bytes)]
 * 
 * REQUIRES: nanopb library
 */

#include "telemetry.pb.h" // You must generate this
#include "pb_encode.h"
#include "pb_common.h"

void setup() {
  Serial.begin(115200);
  while (!Serial); 
}

void loop() {
  // 1. Initialize message
  rocket_telemetry_TelemetryPacket message = rocket_telemetry_TelemetryPacket_init_zero;

  // 2. Populate fields with DYNAMIC data
  float t = millis() / 1000.0; // Time in seconds
  message.cur_time = millis();
  
  message.gps_lat = 359940330; 
  message.gps_lng = -788986220;
  message.gps_alt = 150000;

  // DYNAMIC 1: Altitude (Sine Wave 100-200m)
  message.alt_baro = 150.0 + 50.0 * sin(t * 0.5);

  // DYNAMIC 2: Vertical Velocity (Cosine)
  message.vel_vertical = 25.0 * cos(t * 0.5);
  message.smooth_vel = message.vel_vertical;

  // DYNAMIC 3: Pressure (Inverse of Alt)
  message.press = 1013.25 - (message.alt_baro / 10.0);

  // DYNAMIC 4: Accel Z (Gravity + Noise)
  message.accel_z = 9.81 + (random(-50, 50) / 100.0);
  message.hg_accel = 9.80;

  message.accel_x = 0.5;
  message.accel_y = 0.12;
  message.gyro_x = 0.01;
  message.gyro_y = -0.02;
  message.gyro_z = 0.00;
  
  message.temp = 25.4;
  message.launchsite_msl = 30.0;
  
  // Boolean flags 
  message.airbrake_cont = true;
  message.ab_servo_pct = 45.0;
  message.cnrd_servo_pct = 0.0;
  
  message.drogue_pyro_cont_1 = true;
  message.drogue_pyro_cont_2 = true;
  message.main_pyro_cont_1 = false;
  message.main_pyro_cont_2 = false;
  
  message.flight_index = 0;
  message.ellipse_on = true;

  // DYNAMIC 5 (Binary): Cameras - Toggle every 3s
  message.cameras_on = (millis() % 6000) < 3000;

  // DYNAMIC 6: Battery - Slow Drain
  message.battery_voltage = 12.6 - (millis() / 600000.0);

  message.flight_stage = 2; // Burn state

  // 3. Encode to Buffer
  uint8_t buffer[256];
  pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
  
  bool status = pb_encode(&stream, rocket_telemetry_TelemetryPacket_fields, &message);

  if (!status) {
    Serial.println("Encoding failed!");
    return;
  }

  // 4. Send Framed Packet: [Length Byte] + [Payload]
  // Note: Only works if packet size < 255 bytes.
  
  uint8_t len = (uint8_t)stream.bytes_written;
  Serial.write(len);                 // Send Length
  Serial.write(buffer, len);         // Send Payload
  
  delay(500);
}
