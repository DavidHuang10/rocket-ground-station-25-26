#!/bin/bash
# sync-to-pi.sh - One-command deployment to the Ground Station

set -e

# Configuration
PI_USER="raspy"
PI_HOST="raspy-ground-station.local" 
# Use IP if mDNS is flaky, e.g.: PI_HOST="192.168.4.1"

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/"
DEST_DIR="/home/raspy/ground-station/"

echo "==========================================="
echo "  Deploying to $PI_HOST"
echo "==========================================="
echo "Source: $SOURCE_DIR"
echo "Dest:   $PI_USER@$PI_HOST:$DEST_DIR"
echo ""

rsync -avzp --delete \
  --exclude '.git' \
  --exclude '.gitignore' \
  --exclude '.DS_Store' \
  --exclude '__pycache__' \
  --exclude 'venv' \
  --exclude '.vscode' \
  "$SOURCE_DIR" "$PI_USER@$PI_HOST:$DEST_DIR"

echo ""
echo "==========================================="
echo "  Sync Complete!"
echo "==========================================="
echo ""
echo "To restart the service on the Pi run:"
echo "ssh $PI_USER@$PI_HOST 'sudo systemctl restart ground-station'"
