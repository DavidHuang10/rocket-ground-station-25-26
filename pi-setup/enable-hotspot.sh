#!/bin/bash
# enable-hotspot.sh - Enable the ground station hotspot

set -e

echo "Starting hotspot..."
nmcli connection up ground_station_hotspot

echo ""
echo "Hotspot active!"
echo "  SSID: ground_station"
echo "  Password: 31415926"
echo "  Dashboard: http://192.168.4.1"
