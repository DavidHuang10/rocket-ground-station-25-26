#!/usr/bin/env python3
import serial.tools.list_ports
import os

def get_serial_ports():
    return list(serial.tools.list_ports.comports())

def select_port(ports, prompt):
    print(f"\n{prompt}")
    for i, p in enumerate(ports):
        print(f"[{i}] {p.device} - {p.description} ({p.manufacturer})")
    print(f"[{len(ports)}] Skip/None")
    
    while True:
        try:
            selection = int(input("Select port number: "))
            if 0 <= selection < len(ports):
                return ports[selection].device
            elif selection == len(ports):
                return None
            else:
                print("Invalid selection.")
        except ValueError:
            print("Please enter a number.")

def main():
    print("===========================================")
    print("  Ground Station Port Configuration")
    print("===========================================")
    
    ports = get_serial_ports()
    
    if not ports:
        print("No serial ports found!")
        return

    print(f"Found {len(ports)} devices.")

    # Select Eris Port
    eris_port = select_port(ports, "Select ERIS (Rocket) Transceiver Port:")
    
    # Select Payload Port
    payload_port = select_port(ports, "Select PAYLOAD Transceiver Port:")

    # Generate env file content
    env_content = ""
    if eris_port:
        env_content += f"ERIS_SERIAL={eris_port}\n"
    if payload_port:
        env_content += f"PAYLOAD_SERIAL={payload_port}\n"

    env_path = os.path.expanduser("~/ground-station/ground-station.env")
    
    print(f"\nWriting configuration to {env_path}...")
    print("-" * 20)
    print(env_content.strip())
    print("-" * 20)
    
    with open(env_path, "w") as f:
        f.write(env_content)
    
    print("Configuration saved!")
    print("\nPlease restart the service to apply changes:")
    print("sudo systemctl restart ground-station")

if __name__ == "__main__":
    main()
