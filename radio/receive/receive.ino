/*
 * Ground Station LoRa Receiver + Command Uplink
 *
 * Receives LoRa telemetry from the flight computer and forward
 * over serial to the Python backend.
 *
 * Command uplink: When the Python backend sends a command string over serial,
 * this sketch transmits it over LoRa to the flight computer (send.ino), waits
 * for a 1-byte ACK/NAK LoRa response, and forwards that byte over serial.
 *
 * Pair with send.ino on the flight computer side.
 *
 * ACK/NAK protocol (over LoRa AND serial):
 *   0x00 = ACK (command recognized and executed)
 *   0x01 = NAK (unknown command)
 */

#include <RH_RF95.h>
#include <SPI.h>

// ── Pin Definitions ──
#define RFM95_CS 10
#define RFM95_RST 9
#define RFM95_INT 5
#define LED 13

// ── Radio Configuration ──
#define RF95_FREQ 915

#define DEBUG

// ── Radio Driver ──
RH_RF95 rf95(RFM95_CS, RFM95_INT);

// ── Command Uplink ──
#define CMD_ACK 0x00
#define CMD_NAK 0x01
#define CMD_ACK_TIMEOUT_MS                                                     \
  1500 // How long to wait for LoRa ACK from flight computer
String cmdBuffer = "";

// Send a command over LoRa and wait for ACK/NAK response.
// Forwards the ACK/NAK byte (or nothing on timeout) to serial.
void sendCommandOverLoRa(String cmd) {
  cmd.trim();
  if (cmd.length() == 0)
    return;

  // Transmit command string over LoRa
  uint8_t cmdBytes[RH_RF95_MAX_MESSAGE_LEN];
  uint8_t cmdLen = min((int)cmd.length(), RH_RF95_MAX_MESSAGE_LEN - 1);
  cmd.getBytes(cmdBytes, cmdLen + 1);

  rf95.send(cmdBytes, cmdLen);
  rf95.waitPacketSent();

#ifdef DEBUG
  Serial.print("CMD TX: ");
  Serial.println(cmd);
#endif

  // Wait for ACK/NAK response from flight computer
  if (rf95.waitAvailableTimeout(CMD_ACK_TIMEOUT_MS)) {
    uint8_t respBuf[RH_RF95_MAX_MESSAGE_LEN];
    uint8_t respLen = sizeof(respBuf);

    if (rf95.recv(respBuf, &respLen) && respLen >= 1) {
      // Forward ACK/NAK byte to Python backend over serial
      Serial.write(respBuf[0]);
#ifdef DEBUG
      Serial.print("CMD RESP: ");
      Serial.println(respBuf[0] == CMD_ACK ? "ACK" : "NAK");
#endif
      return;
    }
  }

  // Timeout — Python backend's own 2s timeout will handle this
#ifdef DEBUG
  Serial.println("CMD RESP: TIMEOUT");
#endif
}

void setup() {
  pinMode(LED, OUTPUT);
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  while (!Serial)
    ;
  Serial.begin(115200);
  delay(100);

#ifdef DEBUG
  Serial.println("Ground Station LoRa RX + Command Uplink");
#endif

  // Manual radio reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  while (!rf95.init()) {
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
  if (rf95.available()) {
    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    memset(buf, 0, RH_RF95_MAX_MESSAGE_LEN);
    uint8_t len = sizeof(buf);

    if (rf95.recv(buf, &len)) {
      Serial.write(len);
      Serial.write((char *)buf, len);
    }
  }

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
