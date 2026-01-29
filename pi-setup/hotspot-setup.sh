#!/bin/bash
# hotspot-setup.sh - Configure WiFi hotspot using NetworkManager

set -e

SSID="ground_station"
PASSWORD="31415926"
HOTSPOT_IP="192.168.4.1"
CONNECTION_NAME="ground_station_hotspot"

echo "=== Setting up WiFi Hotspot ==="

# Check for NetworkManager
if ! command -v nmcli &> /dev/null; then
    echo "ERROR: NetworkManager (nmcli) not found."
    echo "Install with: sudo apt install network-manager"
    exit 1
fi

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
echo "=== Hotspot configured successfully ==="
echo "SSID: $SSID"
echo "Password: $PASSWORD"
echo "Pi IP: $HOTSPOT_IP"
echo ""
echo "To start hotspot now: sudo nmcli connection up $CONNECTION_NAME"
