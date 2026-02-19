#!/bin/bash
# Setup script for Radio DJ Bay

set -e

echo "=== Radio DJ Bay Setup ==="

# Install dependencies
echo "Checking dependencies..."
PACKAGES_TO_INSTALL=""

if ! command -v liquidsoap &> /dev/null; then
    PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL liquidsoap liquidsoap-plugin-alsa"
fi


if [ -n "$PACKAGES_TO_INSTALL" ]; then
    echo "Installing: $PACKAGES_TO_INSTALL"
    sudo apt-get update
    sudo apt-get install -y $PACKAGES_TO_INSTALL
else
    echo "All dependencies already installed."
fi

# Verify radio user exists and configure groups
if ! id "radio" &>/dev/null; then
    echo "ERROR: 'radio' user does not exist. Please create it first:"
    echo "  sudo useradd -r -m -s /bin/bash radio"
    exit 1
fi

echo "Configuring radio user..."
sudo usermod -a -G audio radio

# Create log directory
echo "Creating log directory..."
sudo mkdir -p /var/log/liquidsoap
sudo chown radio:radio /var/log/liquidsoap

# Create music directories (if they don't exist)
echo "Setting up music directories..."
sudo mkdir -p /media/radio/kstk
sudo mkdir -p /media/radio/pandora
sudo chown -R radio:radio /media/radio

# Create config directory and copy Liquidsoap script
echo "Installing Liquidsoap configuration..."
sudo mkdir -p /etc/liquidsoap
sudo cp radio.liq /etc/liquidsoap/
sudo chown root:radio /etc/liquidsoap/radio.liq
sudo chmod 640 /etc/liquidsoap/radio.liq

# Install systemd service
echo "Installing systemd service..."
sudo cp radio.service /etc/systemd/system/
sudo systemctl daemon-reload

# Set up Now Playing HUD for nbradio user
echo "Setting up Now Playing HUD..."
if ! id "nbradio" &>/dev/null; then
    echo "Creating 'nbradio' user..."
    sudo useradd -r -m -s /bin/bash nbradio
fi
sudo -u nbradio pip install --user rich 2>/dev/null || sudo pip install rich
sudo install -m 755 -o nbradio -g nbradio nowplaying.py /usr/local/bin/nowplaying

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the service:"
echo "  sudo systemctl start radio"
echo ""
echo "To enable on boot:"
echo "  sudo systemctl enable radio"
echo ""
echo "DJ Connection Info:"
echo "  Host: $(hostname -I | awk '{print $1}')"
echo "  Port: 8005"
echo "  Mount: /live"
echo "  Username/Password: see .env file"
echo ""
echo "Music Directories:"
echo "  /media/radio/kstk     - KSTK station music"
echo "  /media/radio/pandora  - Pandora station music"
echo ""
echo "Station Control (via telnet localhost 1234):"
echo "  station.set kstk      - Switch to KSTK"
echo "  station.set pandora   - Switch to Pandora"
echo "  station.get           - Show current station"
echo ""
echo "Fallback Chain:"
echo "  1. Live DJ input (Shoutcast/Icecast)"
echo "  2. Active station playlist (default: kstk)"
echo "  3. SomaFM Synphaera (emergency)"
echo ""
