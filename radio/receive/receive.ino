#include <RH_RF95.h>
#include <SPI.h>

#define RFM95_CS 10
#define RFM95_RST 9
#define RFM95_INT 5

#define RF95_FREQ 915

#define DEBUG

// Singleton instance of the radio driver
RH_RF95 rf95(RFM95_CS, RFM95_INT);
// Blinky on receipt
#define LED 13

void setup() {
  pinMode(LED, OUTPUT);
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  while (!Serial)
    ;
  Serial.begin(115200);
  delay(100);

#ifdef DEBUG
  Serial.println("Arduino LoRa RX Test!");
#endif

  // manual reset
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

  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
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
    // Should be a message for us now
    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    memset(buf, 0, RH_RF95_MAX_MESSAGE_LEN);
    uint8_t len = sizeof(buf);

    if (rf95.recv(buf, &len)) {
      Serial.write(len);
      Serial.write((char *)buf, len);
    }
  }
}
