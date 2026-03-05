# Raspberry Pi Ground Station Setup

Sets up a Pi to host a telemetry dashboard accessible via WiFi hotspot.

## Quick Reference

| Item | Value |
|------|-------|
| Hostname | `raspy-ground-station` |
| Username | `raspy` |
| Hotspot SSID | `ground_station` |
| Hotspot Password | `31415926` |
| Hotspot Dashboard URL | `http://192.168.4.1` |
| Ethernet Dashboard URL | `http://192.168.1.1` (Pi acts as DHCP server, no manual IP needed) |

## Initial Setup

**1. Flash Pi** with Raspberry Pi Imager. Configure WiFi to your phone hotspot, enable SSH, set hostname/user above.

**2. Copy code** from your Mac:
```bash
scp -r /path/to/rocket-ground-station-25-26 raspy@raspy-ground-station.local:/home/raspy/ground-station
```

**3. Install app** (SSH into Pi):
```bash
cd /home/raspy/ground-station/pi-setup && chmod +x *.sh
sudo ./install-app.sh
```
This installs dependencies, sets up the systemd service, and grants port 80 access via `setcap`.

**4. (Optional) Install hotspot:**
```bash
sudo ./install-hotspot.sh   # Reboots into hotspot mode
```

## Switching Modes

| From | To | Command |
|------|----|---------|
| Phone WiFi | Hotspot | `sudo ./switch-to-hotspot.sh` |
| Hotspot | Phone WiFi | `sudo ./switch-to-wifi.sh "SSID" "password"` |

Both commands reboot the Pi.

## Useful Commands

```bash
sudo systemctl status ground-station    # Check service
sudo systemctl restart ground-station   # Restart service
sudo journalctl -u ground-station -f    # View logs
```

## Files

| File | Purpose |
|------|---------|
| `install-app.sh` | Install dashboard + systemd service |
| `install-hotspot.sh` | Configure WiFi hotspot (one-time) |
| `switch-to-hotspot.sh` | Switch to hotspot mode |
| `switch-to-wifi.sh` | Switch to client WiFi mode |
| `ground-station.service` | systemd service definition |
