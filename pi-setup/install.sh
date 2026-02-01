#!/bin/bash
# install.sh - Full install (app + hotspot)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Running full install (app + hotspot)..."
echo ""

# Run app install first
"$SCRIPT_DIR/install-app.sh"

echo ""
echo "App installed. Now setting up hotspot..."
echo ""

# Then hotspot
"$SCRIPT_DIR/install-hotspot.sh"
