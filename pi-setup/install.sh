#!/bin/bash
# install.sh - Main setup script for Raspberry Pi Ground Station

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GROUND_STATION_DIR="/home/raspy/ground-station"

echo "==========================================="
echo "  ERIS Ground Station - Pi Setup"
echo "==========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./install.sh"
    exit 1
fi

# Check if ground station code exists
if [ ! -f "$GROUND_STATION_DIR/new_ground_station/main.py" ]; then
    echo "ERROR: Ground station code not found at $GROUND_STATION_DIR"
    echo "Make sure you copied the repo to /home/raspy/ground-station/"
    exit 1
fi

echo "[1/5] Updating package lists..."
apt update

echo ""
echo "[2/5] Installing dependencies..."
apt install -y python3 python3-pip python3-venv network-manager iw

# Install Python packages
echo ""
echo "[3/5] Installing Python packages..."
cd "$GROUND_STATION_DIR/new_ground_station"
pip3 install --break-system-packages --ignore-installed -r requirements.txt

echo ""
echo "[4/5] Setting up WiFi hotspot..."
chmod +x "$SCRIPT_DIR/hotspot-setup.sh"
"$SCRIPT_DIR/hotspot-setup.sh"

echo ""
echo "[5/5] Setting up auto-start service..."
cp "$SCRIPT_DIR/ground-station.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable ground-station

echo ""
echo "==========================================="
echo "  Setup Complete!"
echo "==========================================="
echo ""
echo "The Pi will now reboot."
echo ""
echo "After reboot:"
echo "  1. Connect to WiFi: ground_station (password: 31415926)"
echo "  2. Open browser: http://192.168.4.1"
echo ""
read -p "Press Enter to reboot (or Ctrl+C to cancel)..."

reboot
