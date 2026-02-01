#!/bin/bash
# switch-to-hotspot.sh - Switch Pi to broadcast its own hotspot on next reboot
# Run this while connected via phone hotspot

set -e

echo "Setting ground_station hotspot as highest priority..."

# Make hotspot highest priority (will win over phone WiFi)
nmcli connection modify ground_station_hotspot connection.autoconnect-priority 100

# Lower priority of any other connections
for conn in $(nmcli -t -f NAME connection show | grep -v ground_station_hotspot); do
    nmcli connection modify "$conn" connection.autoconnect-priority 0 2>/dev/null || true
done

echo ""
echo "Done! On next reboot, Pi will broadcast the ground_station hotspot."
echo ""
echo "  SSID: ground_station"
echo "  Password: 31415926"
echo "  Dashboard: http://192.168.4.1"
echo ""
read -p "Reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
fi
