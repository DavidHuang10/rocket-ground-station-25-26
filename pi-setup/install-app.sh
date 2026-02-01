#!/bin/bash
# install-app.sh - Install ground station app only (no hotspot)

set -e

GROUND_STATION_DIR="/home/raspy/ground-station"
APP_DIR="$GROUND_STATION_DIR/new_ground_station"
SCRIPT_DIR="$GROUND_STATION_DIR/pi-setup"

echo "==========================================="
echo "  ERIS Ground Station - App Install"
echo "==========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./install-app.sh"
    exit 1
fi

# Check if ground station code exists
if [ ! -f "$APP_DIR/main.py" ]; then
    echo "ERROR: Ground station code not found at $GROUND_STATION_DIR"
    echo "Make sure you copied the repo to /home/raspy/ground-station/"
    exit 1
fi

echo "[1/4] Updating package lists..."
apt update

echo ""
echo "[2/4] Installing system dependencies..."
apt install -y python3-pip

echo ""
echo "[3/4] Installing Python packages..."
pip3 install --break-system-packages --ignore-installed -r "$APP_DIR/requirements.txt"

# Add raspy to dialout group for serial access
usermod -a -G dialout raspy 2>/dev/null || true

# Allow Python to bind to port 80 without root
PYTHON_PATH=$(which python3)
setcap 'cap_net_bind_service=+ep' "$PYTHON_PATH"

echo ""
echo "[4/4] Setting up auto-start service..."
cp "$SCRIPT_DIR/ground-station.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable ground-station
systemctl restart ground-station

echo ""
echo "==========================================="
echo "  App Install Complete!"
echo "==========================================="
echo ""
echo "Ground station is now running."
echo "Access at: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "To check status: sudo systemctl status ground-station"
echo "To view logs: sudo journalctl -u ground-station -f"
echo ""
echo "To also set up WiFi hotspot, run: sudo ./install-hotspot.sh"
