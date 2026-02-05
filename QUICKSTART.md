# Quick Start Guide

Step-by-step instructions to get Radio DJ Bay running.

## Prerequisites

- Ubuntu/Debian-based Linux system
- A `radio` user already created (you mentioned you have this)
- Audio output device configured (e.g., USB sound card for FM transmitter)

## Step 1: Verify the radio user

```bash
# Check that the radio user exists
id radio

# If not, create it:
sudo useradd -r -m -s /bin/bash -G audio radio
```

## Step 2: Install dependencies

```bash
sudo apt-get update
sudo apt-get install -y liquidsoap liquidsoap-plugin-alsa shairport-sync avahi-daemon
```

## Step 3: Run the setup script

```bash
cd /path/to/nbradio
./setup.sh
```

This will:
- Add the `radio` user to the `audio` group
- Create `/var/log/liquidsoap/` for logs
- Create `/media/radio/kstk/` and `/media/radio/pandora/` directories
- Install configuration files to `/etc/`
- Install systemd service files

## Step 4: Add music to the playlists

```bash
# Copy music to the station directories
# (as the radio user or with appropriate permissions)
cp -r /path/to/your/music/* /media/radio/kstk/

# Or for the pandora station
cp -r /path/to/other/music/* /media/radio/pandora/
```

## Step 5: Configure the audio output device

List available audio devices:

```bash
aplay -l
```

Example output:
```
**** List of PLAYBACK Hardware Devices ****
card 0: PCH [HDA Intel PCH], device 0: ALC892 Analog [ALC892 Analog]
card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
```

If your FM transmitter is on card 1, edit the config:

```bash
sudo nano /etc/liquidsoap/radio.liq
```

Find this line near the bottom:
```liquidsoap
output.alsa(device="default", radio)
```

Change it to:
```liquidsoap
output.alsa(device="hw:1,0", radio)
```

## Step 6: Start the services

```bash
# Start both services
sudo systemctl start shairport-sync
sudo systemctl start radio

# Check status
sudo systemctl status shairport-sync
sudo systemctl status radio
```

## Step 7: Enable on boot (optional)

```bash
sudo systemctl enable shairport-sync radio
```

## Step 8: Verify it's working

### Check the logs

```bash
# Liquidsoap logs
sudo tail -f /var/log/liquidsoap/radio.log

# Or via journald
journalctl -u radio -f
```

### Test AirPlay

On an iPhone or Mac:
1. Open Control Center
2. Tap the AirPlay icon
3. Look for "Radio DJ Bay"
4. Select it and play audio

### Test DJ connection

Using BUTT or similar software:
- Server: `your-server-ip`
- Port: `8005`
- Mount: `/live`
- Username: (see `.env` file)
- Password: (see `.env` file)

### Test telnet control

```bash
telnet localhost 1234
```

Then type:
```
station.get
station.set pandora
station.get
```

## Troubleshooting

### Service won't start

```bash
# Check for errors
journalctl -u radio -e
journalctl -u shairport-sync -e

# Test liquidsoap config directly
sudo -u radio liquidsoap --check /etc/liquidsoap/radio.liq
```

### No audio output

```bash
# Test ALSA directly
sudo -u radio speaker-test -D hw:1,0 -c 2

# Check if radio user is in audio group
groups radio
```

### AirPlay not visible

```bash
# Check avahi is running
sudo systemctl status avahi-daemon

# Check shairport-sync is running
sudo systemctl status shairport-sync
```

### Playlists not playing

```bash
# Check if music files exist and are readable
sudo -u radio ls -la /media/radio/kstk/

# Check file permissions
sudo chown -R radio:radio /media/radio/
```

## Quick Reference

| Task | Command |
|------|---------|
| Start services | `sudo systemctl start shairport-sync radio` |
| Stop services | `sudo systemctl stop radio shairport-sync` |
| Restart services | `sudo systemctl restart shairport-sync radio` |
| View logs | `journalctl -u radio -f` |
| Switch to KSTK | `echo "station.set kstk" | nc localhost 1234` |
| Switch to Pandora | `echo "station.set pandora" | nc localhost 1234` |
| Check current station | `echo "station.get" | nc localhost 1234` |

## Service Dependency Order

```
avahi-daemon → shairport-sync → radio
```

Always start shairport-sync before radio (the systemd dependencies handle this automatically).
