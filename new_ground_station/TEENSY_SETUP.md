# Teensy & Arduino Setup Guide

## 1. Quick Overview: What is the Arduino IDE?
The **Arduino IDE** is the software used to write code for your Teensy (and other microcontrollers), compile it, and upload it to the board.
- **Sketch**: A program written for Arduino (files ending in `.ino`).
- **Library**: Pre-written code packages (like `Nanopb`) you can include in your sketch.
- **Serial Monitor**: A built-in tool to see what your Teensy is sending over the USB cable (useful for debugging).

## 2. Using Protobuf on Teensy
To use Protobuf (Protocol Buffers) on a microcontroller, we use a library called **Nanopb**. Standard Protobuf is too heavy; Nanopb is designed for small devices.

### Step 1: Install Nanopb Library
1. Open Arduino IDE.
2. Go to `Sketch` -> `Include Library` -> `Manage Libraries...`.
3. Search for `Nanopb`.
4. Click **Install** (by Petteri Aimonen).

### Step 2: Generate C Code
You need to convert our `telemetry.proto` definition into C code (`.c` and `.h` files) that the Arduino understands.
1. Make sure you have the `nanopb_generator` usage enabled (requires Python).
2. Run the generator:
   ```sh
   # If you have the full protobuf stack
   python3 -m grpc_tools.protoc --nanopb_out=. telemetry.proto
   
   # OR if you just have the generator script
   python3 path/to/nanopb/generator/nanopb_generator.py telemetry.proto
   ```
3. This creates `telemetry.pb.c` and `telemetry.pb.h`.
4. **Copy these two files** into the same folder as your `mock_arduino_transceiver.ino` sketch.

### Step 3: Why the "Length Byte"?
You might notice the Arduino code does this:
```cpp
Serial.write(len);
Serial.write(buffer, len);
```
**Why?**
- **Text (CSV)**: We used `\n` (newline) to mark the end of a packet.
- **Binary (Protobuf)**: A protobuf packet might *contain* the byte for newline (`0x0A`) as part of a number! If we just looked for newlines, we'd get confused.
- **Solution**: We send the **Length** first. If the length is 50, the receiver knows to read exactly 50 bytes. This is called "Framing".

## 3. Uploading the Mock Sketch
1. Open `mock_arduino_transceiver.ino` in Arduino IDE.
2. Select your board (Teensy 4.1) and Port.
3. Click "Upload" (Right Arrow icon).
4. The Teensy will start sending fake telemetry.
