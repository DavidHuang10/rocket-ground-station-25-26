/*
 * Eris LoRa Transmitter (Flight Computer Simulator)
 *
 * Generates mock Eris telemetry, encodes it with Bitproto, and transmits
 * over LoRa RF95. Simulates what the real flight computer would send.
 *
 * Command uplink: Between telemetry transmissions, checks for incoming
 * LoRa command packets from the ground station (receive.ino). Recognized
 * commands trigger LED blinks; sends ACK/NAK response back over LoRa.
 *
 * Pair with receive.ino on the ground station side.
 *
 * REQUIRES:
 *   - RadioHead library (RH_RF95)
 *   - Bitproto files (bitproto.h/c, telemetry_bp.h/c)
 */

#include "bitproto.h"
#include "telemetry_bp.h"
#include <RH_RF95.h>
#include <SPI.h>

// ── Pin Definitions ──
#define RFM95_CS 10
#define RFM95_RST 9
#define RFM95_INT 24 // 5, 24
#define LED 13

// ── Radio Configuration ──
#define RF95_FREQ 915 // MHz — must match receive.ino

// #define DEBUG

// ── Radio Driver ──
RH_RF95 rf95(RFM95_CS, RFM95_INT);

// Helper to store float bits as uint32
union FloatUint32 {
  float f;
  uint32_t u;
};

inline uint32_t floatToUint32(float val) {
  union FloatUint32 converter;
  converter.f = val;
  return converter.u;
}

// ── Command Uplink ──
#define CMD_ACK 0x00
#define CMD_NAK 0x01

// Stateful telemetry fields that commands can toggle
bool drogue_cont_1 = true;
bool drogue_cont_2 = true;

// Check for incoming LoRa command, execute it, and send ACK/NAK back over LoRa.
void checkForLoRaCommand() {
  if (!rf95.available())
    return;

  uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
  uint8_t len = sizeof(buf);

  if (!rf95.recv(buf, &len) || len == 0)
    return;

  // Telemetry packets are BYTES_LENGTH_TELEMETRY_PACKET (89) bytes.
  // Commands are short ASCII strings (< 20 bytes). Use length to distinguish.
  if (len == BYTES_LENGTH_TELEMETRY_PACKET)
    return; // Not a command, ignore

  // Parse command string
  buf[len] = '\0'; // Null-terminate
  String cmd = String((char *)buf);
  cmd.trim();

  uint8_t response;

  if (cmd == "beep") {
    drogue_cont_1 = !drogue_cont_1;
    response = CMD_ACK;
  } else if (cmd == "beepbeep") {
    drogue_cont_2 = !drogue_cont_2;
    response = CMD_ACK;
  } else {
    response = CMD_NAK;
  }

  // Send ACK/NAK back over LoRa
  rf95.send(&response, 1);
  rf95.waitPacketSent();

#ifdef DEBUG
  Serial.print("CMD RX: ");
  Serial.print(cmd);
  Serial.print(" -> ");
  Serial.println(response == CMD_ACK ? "ACK" : "NAK");
#endif
}

void setup() {
  pinMode(LED, OUTPUT);
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  Serial.begin(115200);
  while (!Serial)
    ;
  delay(100);

#ifdef DEBUG
  Serial.println("Eris LoRa TX — Flight Computer Simulator");
#endif

  // Manual radio reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  // Initialize LoRa radio
  while (!rf95.init()) {
#ifdef DEBUG
    Serial.println("ERROR: LoRa radio init failed");
#endif
    while (1)
      ;
  }

  if (!rf95.setFrequency(RF95_FREQ)) {
#ifdef DEBUG
    Serial.println("ERROR: setFrequency failed");
#endif
    while (1)
      ;
  }

  rf95.setTxPower(23, false);

#ifdef DEBUG
  Serial.print("Freq: ");
  Serial.print(RF95_FREQ);
  Serial.println(" MHz — Transmitting telemetry...");
#endif
}

void loop() {
  // 1. Check for incoming LoRa commands from ground station
  checkForLoRaCommand();

  // 2. Build mock telemetry packet
  struct TelemetryPacket message = {0};
  float t = millis() / 1000.0;
  message.cur_time = millis();
  message.gps_lat = 359940330;
  message.gps_lng = -788986220;
  message.gps_alt = 150000;
  float alt_baro = 150.0 + 50.0 * sin(t * 0.5);
  message.alt_baro = floatToUint32(alt_baro);
  float vel_vertical = 25.0 * cos(t * 0.5);
  message.vel_vertical = floatToUint32(vel_vertical);
  message.smooth_vel = floatToUint32(vel_vertical);
  float press = 1013.25 - (alt_baro / 10.0);
  message.press = floatToUint32(press);
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
  message.drogue_pyro_cont_1 = drogue_cont_1;
  message.drogue_pyro_cont_2 = drogue_cont_2;
  message.main_pyro_cont_1 = false;
  message.main_pyro_cont_2 = false;
  message.flight_index = 0;
  message.ellipse_on = true;
  message.cameras_on = (millis() % 6000) < 3000;
  float battery_voltage = 12.6 - (millis() / 600000.0);
  message.battery_voltage = floatToUint32(battery_voltage);
  message.flight_stage = 2;

  // 3. Encode with Bitproto
  uint8_t buffer[BYTES_LENGTH_TELEMETRY_PACKET];
  memset(buffer, 0, sizeof(buffer));
  EncodeTelemetryPacket(&message, buffer);

  // 4. Send over LoRa
  rf95.send(buffer, BYTES_LENGTH_TELEMETRY_PACKET);
  rf95.waitPacketSent();

  // get ready to take it :o
  rf95.available();

#ifdef DEBUG
  Serial.print("TX t=");
  Serial.println(message.cur_time);
#endif

  delay(500); // Send at 2 Hz
}
