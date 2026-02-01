#!/bin/bash
# disable-hotspot.sh - Disable hotspot and connect to regular WiFi
# Usage: sudo ./disable-hotspot.sh "WiFiName" "password"

set -e

if [ "$#" -lt 2 ]; then
    echo "Usage: sudo ./disable-hotspot.sh \"WiFiName\" \"password\""
    echo "Example: sudo ./disable-hotspot.sh \"David\" \"dddddddd\""
    exit 1
fi

WIFI_NAME="$1"
WIFI_PASS="$2"

echo "Disabling hotspot..."
nmcli connection down ground_station_hotspot 2>/dev/null || true

echo "Connecting to $WIFI_NAME..."
nmcli device wifi connect "$WIFI_NAME" password "$WIFI_PASS"

echo ""
echo "Connected! New IP:"
hostname -I
