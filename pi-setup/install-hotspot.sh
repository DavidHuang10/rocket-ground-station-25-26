#!/bin/bash
# install-hotspot.sh - Set up WiFi hotspot (Install + Configure)

set -e

# Configuration
SSID="ground_station"
PASSWORD="31415926"
HOTSPOT_IP="192.168.4.1"
CONNECTION_NAME="ground_station_hotspot"

echo "==========================================="
echo "  ERIS Ground Station - Hotspot Setup"
echo "==========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./install-hotspot.sh"
    exit 1
fi

echo "[1/3] Installing NetworkManager..."
# Only install if not present to save time on re-runs
if ! command -v nmcli &> /dev/null; then
    apt update
    apt install -y network-manager iw
else
    echo "NetworkManager already installed."
fi

echo ""
echo "[2/3] Configuring WiFi hotspot..."

# Find wireless interface
WIFI_INTERFACE=$(iw dev | awk '$1=="Interface"{print $2}' | head -1)
if [ -z "$WIFI_INTERFACE" ]; then
    echo "ERROR: No wireless interface found"
    exit 1
fi
echo "Found wireless interface: $WIFI_INTERFACE"

# Remove existing hotspot connection if it exists
if nmcli connection show "$CONNECTION_NAME" &> /dev/null; then
    echo "Removing existing hotspot configuration..."
    nmcli connection delete "$CONNECTION_NAME"
fi

# Create the hotspot
echo "Creating hotspot: $SSID"
nmcli connection add \
    type wifi \
    ifname "$WIFI_INTERFACE" \
    con-name "$CONNECTION_NAME" \
    autoconnect yes \
    ssid "$SSID" \
    mode ap \
    ipv4.method shared \
    ipv4.addresses "$HOTSPOT_IP/24" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$PASSWORD"

# Set to auto-connect on boot
nmcli connection modify "$CONNECTION_NAME" connection.autoconnect yes
nmcli connection modify "$CONNECTION_NAME" connection.autoconnect-priority 100

echo ""
echo "[3/3] Finalizing..."
echo "==========================================="
echo "  Hotspot Setup Complete!"
echo "==========================================="
echo ""
echo "Hotspot will start on reboot."
echo ""
echo "  SSID: $SSID"
echo "  Password: $PASSWORD"
echo "  Dashboard: http://$HOTSPOT_IP"
echo ""
read -p "Press Enter to reboot (or Ctrl+C to cancel)..."

reboot
