/*
 * Mock Payload Telemetry Transceiver
 *
 * Demonstrates sending Bitproto payload telemetry over Serial with
 * Length-Prefix framing. Format: [Length (1 byte)] [Bitproto Payload (N bytes)]
 *
 * REQUIRES: Bitproto library (bitproto.h, bitproto.c)
 */

#include "bitproto.h"
#include "payload_bp.h"

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
  struct PayloadPacket message = {0};

  // 2. Populate fields with DYNAMIC data
  float t = millis() / 1000.0; // Time in seconds
  message.cur_time = millis();

  // GPS coordinates (Duke University area, slight drift)
  message.gps_lat = 359940330 + (long)(sin(t * 0.1) * 100);
  message.gps_lng = -788986220 + (long)(cos(t * 0.1) * 100);
  message.gps_alt = 150000 + (long)(sin(t * 0.2) * 5000); // 145-155m

  // DYNAMIC 1: Velocity (Sine Wave 0-10 m/s)
  float velocity = 5.0 + 5.0 * sin(t * 0.3);
  message.velocity = floatToUint32(velocity);

  // DYNAMIC 2: Acceleration (small random variations around gravity)
  float accel_x = (random(-100, 100) / 100.0);
  float accel_y = (random(-100, 100) / 100.0);
  float accel_z = 9.81 + (random(-50, 50) / 100.0);
  message.accel_x = floatToUint32(accel_x);
  message.accel_y = floatToUint32(accel_y);
  message.accel_z = floatToUint32(accel_z);

  // DYNAMIC 3: Distance to Target (decreasing over time, simulating approach)
  // Starts at 1000m and decreases, then resets
  float distance_cycle = fmod(t, 100.0); // 100 second cycle
  float distance_to_target = max(0.0f, 1000.0f - (distance_cycle * 10.0f));
  message.distance_to_target = floatToUint32(distance_to_target);

  // DYNAMIC 4: Destination Reached (true when distance < 50m)
  message.destination_reached = (distance_to_target < 50.0);

  // 3. Encode to Buffer using Bitproto
  // BYTES_LENGTH_PAYLOAD_PACKET is defined in payload_bp.h (37 bytes)
  uint8_t buffer[BYTES_LENGTH_PAYLOAD_PACKET];
  memset(buffer, 0, sizeof(buffer));

  int encoded_bytes = EncodePayloadPacket(&message, buffer);

  // 4. Send Framed Packet: [Sync1] [Sync2] [ID] + [Payload]
  uint8_t len = BYTES_LENGTH_PAYLOAD_PACKET;
  Serial.write(0xAA);        // Sync Byte 1
  Serial.write(0xBB);        // Sync Byte 2
  Serial.write(0x02);        // Type ID (Payload = 0x02)
  Serial.write(buffer, len); // Send Payload

  delay(500);
}
