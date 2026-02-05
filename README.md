# Radio DJ Bay

A Liquidsoap-based radio routing service that accepts multiple audio inputs and outputs to an audio device (e.g., FM transmitter). Supports live DJ connections, AirPlay streaming, and automated playlists.

## Architecture

```
                                    ┌─────────────────┐
[DJ Software] ──Shoutcast/Icecast──▶│                 │
         (port 8005)                │                 │
                                    │                 │
[iPhone/Mac] ──────AirPlay─────────▶│   Liquidsoap    │───▶ [Audio Device] ───▶ [Amp]
         ("Radio DJ Bay")           │                 │
                                    │                 │
[Local Music] ─────Playlist────────▶│                 │
         (/media/radio/*)           │                 │
                                    │                 │
[SomaFM] ──────HTTP Stream─────────▶│                 │
         (emergency fallback)       └─────────────────┘
```

## Fallback Priority

When no higher-priority source is active, the system automatically falls through to the next available source:

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | **Live DJ** | Shoutcast/Icecast connection on port 8005 |
| 2 | **AirPlay** | Any Apple device streaming to "Radio DJ Bay" |
| 3 | **Local Playlist** | Music from `/media/radio/kstk` or `/media/radio/pandora` |
| 4 | **SomaFM Synphaera** | Internet radio stream (emergency backup) |
| 5 | **Silence** | Last resort if all else fails |

## Components

### Files

| File | Purpose |
|------|---------|
| `radio.liq` | Main Liquidsoap configuration script |
| `radio.service` | Systemd service for Liquidsoap |
| `shairport-sync.conf` | AirPlay receiver configuration |
| `shairport-sync.service` | Systemd service for AirPlay receiver |
| `airplay-notify.sh` | Script triggered on AirPlay start/stop events |
| `setup.sh` | Installation script |

### Services

| Service | Port | Purpose |
|---------|------|---------|
| `radio.service` | 8005 (DJ), 1234 (telnet) | Main Liquidsoap routing |
| `shairport-sync.service` | 5000 (AirPlay) | AirPlay audio receiver |

## Input Sources

### 1. Live DJ (Shoutcast/Icecast)

DJs connect using any Shoutcast/Icecast-compatible source client:

| Setting | Value |
|---------|-------|
| Host | Your server's IP address |
| Port | `8005` |
| Mount | `/live` |
| Username | (see `.env` file) |
| Password | (see `.env` file) |

**Compatible software:**
- BUTT (Broadcast Using This Tool)
- Mixxx
- IDJC (Internet DJ Console)
- VirtualDJ
- Traktor (with streaming plugin)

### 2. AirPlay

The server appears as **"Radio DJ Bay"** on your local network. Any Apple device (iPhone, iPad, Mac) can stream audio directly to it.

- Audio is captured via a FIFO pipe from shairport-sync
- Silence detection: Falls through after 3 seconds of no audio
- Volume control is handled by Liquidsoap (device volume ignored)

### 3. Local Playlists

Two "stations" with music directories:

| Station | Directory | Description |
|---------|-----------|-------------|
| `kstk` | `/media/radio/kstk/` | Default station |
| `pandora` | `/media/radio/pandora/` | Alternative station |

**Features:**
- Recursive scanning (subdirectories included)
- Auto-reload when files are added/removed
- Random shuffle playback
- Supports MP3, FLAC, OGG, WAV, and other common formats

### 4. SomaFM Synphaera

Emergency internet radio fallback. Ambient/electronic music stream that plays if:
- No DJ is connected
- No AirPlay audio
- Local playlists are empty or unavailable

## Directory Structure

```
/etc/liquidsoap/
└── radio.liq              # Main configuration

/etc/shairport-sync.conf    # AirPlay configuration

/var/log/liquidsoap/
└── radio.log              # Liquidsoap logs

/media/radio/
├── kstk/                  # KSTK station music
│   ├── album1/
│   ├── album2/
│   └── ...
└── pandora/               # Pandora station music
    └── ...
```

## Telnet Control Interface

Connect to the control interface:

```bash
telnet localhost 1234
```

### Available Commands

| Command | Description |
|---------|-------------|
| `station.set kstk` | Switch to KSTK playlist |
| `station.set pandora` | Switch to Pandora playlist |
| `station.get` | Show current active station |
| `help` | List all available commands |
| `list` | List all sources and outputs |
| `exit` / `quit` | Disconnect from telnet |

## Configuration

### Changing the Audio Output Device

Edit `/etc/liquidsoap/radio.liq` and modify the `output.alsa` line:

```liquidsoap
# List available devices with: aplay -l
output.alsa(device="hw:1,0", radio)  # Use specific hardware
output.alsa(device="plughw:1,0", radio)  # With software conversion
```

### Changing the AirPlay Device Name

Edit `/etc/shairport-sync.conf`:

```
general = {
  name = "My Radio Station";  // Change this
  ...
};
```

### Adding Icecast Output

To also stream to an Icecast server, uncomment this section in `/etc/liquidsoap/radio.liq`:

```liquidsoap
output.icecast(
  %mp3(bitrate=128),
  host="localhost",
  port=8000,
  password="changeme",
  mount="/stream",
  radio
)
```

### Adjusting Silence Detection

The AirPlay input uses silence detection to fall through when not in use. Adjust in `radio.liq`:

```liquidsoap
airplay_input = strip_blank(
  max_blank=3.0,    # Seconds of silence before fallback
  threshold=-40.0,  # dB threshold for "silence"
  airplay_raw
)
```
