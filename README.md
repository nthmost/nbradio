# KNOB: Noisebridge Radio

Internet radio station for the [Noisebridge](https://noisebridge.net) hackerspace, built with Liquidsoap and Icecast. Streams 24/7 with scheduled programming, live DJ override, and a web dashboard.

**Listen now:** [nthmost.com/nbradio](https://nthmost.com/nbradio/)

## Architecture

```
[DJ Software] ──Shoutcast──▶ [Liquidsoap:8005] ──▶ [Icecast:8000] ──▶ [Listeners]
                                    │
[Local Music] ──────────────────────┘
     /media/radio/*
                                    │
[SomaFM Synphaera] ─────────────────┘ (emergency fallback)
```

## Schedule

| Time | Show | Format |
|------|------|--------|
| 2am–10am | AUTODJ | Songs + callsigns + commercials |
| 10am–11am | Pandora's Box | Songs + callsigns + commercials |
| 11am–5pm | AUTODJ | Songs + callsigns + commercials |
| 5pm–6pm | Pandora's Box | Songs + callsigns + commercials |
| 6pm–10pm | AUTODJ | Songs + callsigns + commercials |
| 10pm–2am | Noisefloor | True random (dubstep/bass) |

A live DJ overrides the schedule at any time.

## Fallback Priority

1. **Live DJ** — Shoutcast/Icecast source client on port 8005
2. **Scheduled Programming** — AUTODJ / Pandora's Box / Noisefloor
3. **SomaFM Synphaera** — Internet radio fallback (ambient/electronic)
4. **Silence** — Last resort

## Live DJ Connection

Any Shoutcast/Icecast-compatible source client works (BUTT, Mixxx, OBS, Audio Hijack, etc.):

| Setting | Value |
|---------|-------|
| Host | `beyla:8005` |
| Mount | `/live` |
| Username | `nbradio` |
| Password | `nbradio` |

You must be on the Noisebridge network.

## Web Dashboard

A live "now playing" dashboard with an in-browser audio player:

- **Public:** https://nthmost.com/nbradio/
- **LAN:** http://beyla.local/nbradio/
- **API:** `GET /api/now-playing` (JSON)

Served by `nowplaying_web.py` — a zero-dependency Python stdlib HTTP server that polls Icecast and Liquidsoap telnet for metadata.

## Files

| File | Purpose |
|------|---------|
| `radio.liq` | Main Liquidsoap configuration (schedule, sources, output) |
| `radio.service` | Systemd service for Liquidsoap |
| `radio-listener.service` | Local ALSA audio output via MPV |
| `nowplaying.py` | Terminal now-playing HUD (Rich) |
| `nowplaying_web.py` | Web dashboard and JSON API server |
| `nowplaying.service` | Systemd service for the web dashboard |
| `apache-nowplaying.conf` | Apache reverse proxy config snippet |
| `setup.sh` | Installation script |
| `generate_autodj_playlist.sh` | Scans audio files, generates AUTODJ playlist |

## Stream URLs

| URL | Access |
|-----|--------|
| `http://localhost:8000/stream.ogg` | On the server |
| `http://beyla.local:8000/stream.ogg` | LAN (direct) |
| `https://nthmost.com/nbradio/stream.ogg` | Public (proxied) |

## Contributing Music

Ask nthmost on the Noisebridge Discord for an account on beyla. Music goes in `/media/radio/` under the appropriate directory.

## Setup

```bash
./setup.sh
sudo systemctl enable --now radio.service radio-listener nowplaying.service
```

See `CLAUDE.md` for detailed service configuration, deployment steps, and implementation notes.
