#!/bin/bash
# Local listener - plays the icecast stream through system audio
# Run this as your regular user (not radio) to hear the stream locally

STREAM_URL="${1:-http://localhost:8000/stream.ogg}"

# Try mpv first, fall back to ffplay, then vlc
if command -v mpv &> /dev/null; then
    exec mpv --no-video "$STREAM_URL"
elif command -v ffplay &> /dev/null; then
    exec ffplay -nodisp -autoexit "$STREAM_URL"
elif command -v vlc &> /dev/null; then
    exec vlc --intf dummy "$STREAM_URL"
else
    echo "No suitable player found. Install mpv, ffplay, or vlc."
    exit 1
fi
