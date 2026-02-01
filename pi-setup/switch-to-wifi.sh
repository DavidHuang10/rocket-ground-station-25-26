#!/bin/bash
# switch-to-wifi.sh - Switch Pi to connect to a WiFi network on next reboot
# Run this while connected via hotspot
#
# Usage: sudo ./switch-to-wifi.sh "WiFiName" "password"

set -e

if [ "$#" -lt 2 ]; then
    echo "Usage: sudo ./switch-to-wifi.sh \"WiFiName\" \"password\""
    echo "Example: sudo ./switch-to-wifi.sh \"David\" \"dddddddd\""
    exit 1
fi

WIFI_NAME="$1"
WIFI_PASS="$2"

echo "Adding/updating WiFi connection: $WIFI_NAME..."

# Add or update the WiFi connection
nmcli connection delete "$WIFI_NAME" 2>/dev/null || true
nmcli connection add \
    type wifi \
    con-name "$WIFI_NAME" \
    ssid "$WIFI_NAME" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$WIFI_PASS" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100

# Lower hotspot priority so WiFi wins
nmcli connection modify ground_station_hotspot connection.autoconnect-priority 0

echo ""
echo "Done! On next reboot, Pi will connect to $WIFI_NAME."
echo "SSH back in at: raspy@raspy-ground-station.local"
echo ""
read -p "Reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
fi
