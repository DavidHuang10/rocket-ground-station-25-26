# Teensy Bridge Configuration

The Ground Station makes the following assumptions about the Teensy (or any serial device) connected to the Raspberry Pi.

## 1. Serial Settings
*   **Baud Rate**: `115200`
*   **Data Bits**: 8
*   **Parity**: None
*   **Stop Bits**: 1

## 2. Data Format
The Teensy **MUST** output data as a single line of text ending with a newline character (`\n`).
*   **Format**: `12345,40.123,-105.123,...` (Standard CSV)
*   **Encoding**: ASCII or UTF-8

## 3. Example Teensy Code
```cpp
void setup() {
    Serial.begin(115200); // CRITICAL: Match this speed
}

void loop() {
    if (radio_received) {
        // ... (receive packet into buffer) ...
        Serial.println((char*)buffer); // CRITICAL: println adds the newline
    }
}
```
