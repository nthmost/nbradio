# Quick Start Guide

Step-by-step instructions to get KNOB: Noisebridge Radio running.

## Prerequisites

- Ubuntu/Debian-based Linux system
- Audio files in `/media/radio/` (see README for directory structure)
- Icecast2 installed and running on port 8000

## Step 1: Verify the radio user

```bash
id radio

# If it doesn't exist:
sudo useradd -r -m -s /bin/bash -G audio radio
```

## Step 2: Install dependencies

```bash
sudo apt-get update
sudo apt-get install -y liquidsoap icecast2 mpv
pip install rich  # for the terminal HUD
```

## Step 3: Run the setup script

```bash
cd /path/to/nbradio
./setup.sh
```

This will:
- Add the `radio` user to the `audio` group
- Create `/var/log/liquidsoap/` for logs
- Install `radio.liq` to `/etc/liquidsoap/`
- Install systemd service files
- Generate the AUTODJ playlist

## Step 4: Set up credentials

```bash
cp .env.example .env
# Edit .env with your DJ and Icecast passwords
```

## Step 5: Start the services

```bash
sudo systemctl enable --now icecast2
sudo systemctl enable --now radio.service
sudo systemctl enable --now radio-listener
sudo systemctl enable --now nowplaying.service
```

## Step 6: Verify it's working

### Check service status

```bash
systemctl status icecast2 radio.service radio-listener nowplaying.service
```

### Check the stream

```bash
# Stream should be live
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/stream.ogg
# Should return 200

# Dashboard should be serving
curl -s http://localhost:8080/api/now-playing | python3 -m json.tool
```

### Open the dashboard

- LAN: http://beyla.local/nbradio/
- Or directly: http://localhost:8080/

### Test a DJ connection

Using BUTT, Mixxx, OBS, or similar:
- Host: `beyla:8005`
- Mount: `/live`
- Username: `nbradio`
- Password: `nbradio`

## Troubleshooting

### Service won't start

```bash
journalctl -u radio -e
sudo tail -f /var/log/liquidsoap/radio.log

# Test config directly
sudo -u liquidsoap liquidsoap --check /etc/liquidsoap/radio.liq
```

### No local audio output

```bash
# Check ALSA device
aplay -l

# Test directly
sudo -u radio speaker-test -D plughw:CARD=PCH,DEV=0 -c 2

# Check radio user is in audio group
groups radio
```

### Dashboard not loading

```bash
systemctl status nowplaying.service
journalctl -u nowplaying -f

# Test manually
cd /home/radio/nbradio && python3 nowplaying_web.py --port 8080
```

## Quick Reference

| Task | Command |
|------|---------|
| Restart everything | `sudo systemctl restart icecast2 radio.service radio-listener nowplaying.service` |
| Check status | `systemctl status icecast2 radio.service radio-listener nowplaying.service` |
| View Liquidsoap logs | `sudo tail -f /var/log/liquidsoap/radio.log` |
| View dashboard logs | `journalctl -u nowplaying -f` |
| Telnet control | `telnet localhost 1234` |

## Service Dependency Order

```
icecast2 → radio.service → radio-listener
                         → nowplaying.service
```

The systemd unit files handle dependencies automatically.
