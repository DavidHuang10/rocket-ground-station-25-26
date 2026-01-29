# Raspberry Pi Ground Station Setup

Configures a Raspberry Pi to:
1. Broadcast a WiFi hotspot (`ground_station`)
2. Auto-start the ground station dashboard on boot
3. Allow phones to connect and view telemetry at `http://192.168.4.1`

## Pi Details

- **Hostname**: raspy-ground-station
- **Username**: raspy
- **WiFi SSID**: ground_station
- **WiFi Password**: 31415926
- **Dashboard URL**: http://192.168.4.1 (after hotspot is running)

## Prerequisites

- Raspberry Pi with Debian Trixie (or newer Raspberry Pi OS)
- Initial network connection (phone hotspot or ethernet) for setup
- Ground station code at `/home/raspy/ground-station/`

## Setup Instructions

### 1. Connect to Pi via SSH

First, connect your Pi to a network (phone hotspot works). Find its IP address, then:

```bash
ssh raspy@<PI_IP_ADDRESS>
```

### 2. Copy Files to Pi (from your local machine)

```bash
scp -r /path/to/rocket-ground-station-25-26 raspy@<PI_IP>:/home/raspy/ground-station
```

### 3. Run the Install Script (on the Pi)

```bash
cd /home/raspy/ground-station/pi-setup
chmod +x install.sh
sudo ./install.sh
```

This will:
- Install Python dependencies
- Set up the WiFi hotspot
- Configure auto-start on boot
- Reboot the Pi

### 4. Connect to Ground Station

After reboot:
1. On your phone, connect to WiFi network `ground_station` (password: `31415926`)
2. Open browser and go to `http://192.168.4.1`
3. Dashboard should load

## Manual Commands

### Check service status
```bash
sudo systemctl status ground-station
```

### View logs
```bash
sudo journalctl -u ground-station -f
```

### Restart service
```bash
sudo systemctl restart ground-station
```

### Stop/start hotspot
```bash
sudo nmcli connection down ground_station_hotspot
sudo nmcli connection up ground_station_hotspot
```

## Troubleshooting

### Can't connect to hotspot
```bash
# Check if hotspot is active
nmcli connection show --active

# Restart hotspot
sudo nmcli connection down ground_station_hotspot
sudo nmcli connection up ground_station_hotspot
```

### Dashboard not loading
```bash
# Check if service is running
sudo systemctl status ground-station

# Check logs for errors
sudo journalctl -u ground-station -n 50

# Try running manually
cd /home/raspy/ground-station/new_ground_station
python3 -m uvicorn main:app --host 0.0.0.0 --port 80
```

### Need to reconnect Pi to regular WiFi
```bash
# Disable hotspot temporarily
sudo nmcli connection down ground_station_hotspot

# Connect to regular WiFi
sudo nmcli device wifi connect "YourWiFiName" password "YourPassword"
```

## File Overview

| File | Purpose |
|------|---------|
| `install.sh` | Main setup script (run once) |
| `hotspot-setup.sh` | Configures WiFi access point |
| `ground-station.service` | systemd service for auto-start |
| `README.md` | This file |
