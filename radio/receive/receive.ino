/*
 * Ground Station LoRa Receiver + Command Uplink
 *
 * Receives LoRa telemetry from the flight computer and forwards
 * over serial to the Python backend.
 *
 * Command uplink: Uses RHReliableDatagram's sendtoWait() for automatic
 * ACK + retries. Returns 0x00 (delivered) or 0x01 (failed) to Python.
 *
 * Pair with send.ino on the flight computer side.
 */

#include <RHReliableDatagram.h>
#include <RH_RF95.h>
#include <SPI.h>

#define RFM95_CS 10
#define RFM95_RST 9
#define RFM95_INT 24 // 5, 24
#define LED 13

#define RF95_FREQ 915

// ── Addressing ──
#define FLIGHT_COMPUTER_ADDR 1
#define GROUND_STATION_ADDR 2

// #define DEBUG

RH_RF95 rf95(RFM95_CS, RFM95_INT);
RHReliableDatagram manager(rf95, GROUND_STATION_ADDR);

#define CMD_ACK 0x00
#define CMD_FAIL 0x01
String cmdBuffer = "";

void sendCommandOverLoRa(String cmd) {
  cmd.trim();
  if (cmd.length() == 0)
    return;

  uint8_t cmdBytes[RH_RF95_MAX_MESSAGE_LEN];
  uint8_t cmdLen = min((int)cmd.length(), RH_RF95_MAX_MESSAGE_LEN - 1);
  cmd.getBytes(cmdBytes, cmdLen + 1);

  // sendtoWait: sends command, waits for ACK with automatic retries
  bool delivered = manager.sendtoWait(cmdBytes, cmdLen, FLIGHT_COMPUTER_ADDR);

  // Forward result to Python backend over serial
  Serial.write(delivered ? CMD_ACK : CMD_FAIL);
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
  Serial.println("Ground Station LoRa RX + Command Uplink");
#endif

  // Manual radio reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  // Initialize reliable datagram manager (calls rf95.init() internally)
  while (!manager.init()) {
#ifdef DEBUG
    Serial.println("LoRa radio init failed");
#endif
    while (1)
      ;
  }
#ifdef DEBUG
  Serial.println("LoRa radio init OK!");
#endif

  if (!rf95.setFrequency(RF95_FREQ)) {
#ifdef DEBUG
    Serial.println("setFrequency failed");
#endif
    for (;;) {
    }
  }
#ifdef DEBUG
  Serial.print("Set Freq to: ");
  Serial.println(RF95_FREQ);
#endif

  rf95.setTxPower(23, false);
}

void loop() {
  // Receive telemetry (broadcast packets from flight computer)
  if (manager.available()) {
    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    memset(buf, 0, RH_RF95_MAX_MESSAGE_LEN);
    uint8_t len = sizeof(buf);
    uint8_t from;

    if (manager.recvfromAck(buf, &len, &from)) {
      Serial.write(0xAA); // Sync Byte 1
      Serial.write(0xBB); // Sync Byte 2
      Serial.write(0x01); // Type ID (Eris = 0x01)
      Serial.write((char *)buf, len);
    }
  }

  // Check for commands from Python backend over serial
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      sendCommandOverLoRa(cmdBuffer);
      cmdBuffer = "";
    } else if (c != '\r') {
      cmdBuffer += c;
    }
  }
}
