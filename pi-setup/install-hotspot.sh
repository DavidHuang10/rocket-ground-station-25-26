#!/bin/bash
# install-hotspot.sh - Set up WiFi hotspot (run after install-app.sh)

set -e

GROUND_STATION_DIR="/home/raspy/ground-station"
SCRIPT_DIR="$GROUND_STATION_DIR/pi-setup"

echo "==========================================="
echo "  ERIS Ground Station - Hotspot Setup"
echo "==========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./install-hotspot.sh"
    exit 1
fi

echo "[1/2] Installing NetworkManager..."
apt install -y network-manager iw

echo ""
echo "[2/2] Configuring WiFi hotspot..."
chmod +x "$SCRIPT_DIR/hotspot-setup.sh"
"$SCRIPT_DIR/hotspot-setup.sh"

echo ""
echo "==========================================="
echo "  Hotspot Setup Complete!"
echo "==========================================="
echo ""
echo "Hotspot will start on reboot."
echo ""
echo "  SSID: ground_station"
echo "  Password: 31415926"
echo "  Dashboard: http://192.168.4.1"
echo ""
read -p "Press Enter to reboot (or Ctrl+C to cancel)..."

reboot
