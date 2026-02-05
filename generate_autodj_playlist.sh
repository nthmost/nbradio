#!/bin/bash
# Generate AUTODJ playlist: all short songs (30s-10min) from /media/radio
# Excludes callsigns, commercials, promos, sounds, and non-audio files.
# Output: /media/radio/autodj_all_songs.m3u

MEDIA_DIR="/media/radio"
OUTPUT="$MEDIA_DIR/autodj_all_songs.m3u"
MIN_DURATION=30
MAX_DURATION=600
EXCLUDE_DIRS="callsigns|commercials|promos|sounds|test|configs|html|log|scripts|random_assets"

tmpfile=$(mktemp)
count=0

find "$MEDIA_DIR" -type f \( -name '*.mp3' -o -name '*.ogg' -o -name '*.flac' -o -name '*.wav' \) -print0 2>/dev/null | \
while IFS= read -r -d $'\0' f; do
    # Skip excluded directories
    if echo "$f" | grep -qE "/($EXCLUDE_DIRS)/"; then
        continue
    fi
    dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null)
    if [ -n "$dur" ]; then
        # Compare as integers (truncate decimal)
        dur_int=${dur%.*}
        if [ "$dur_int" -ge "$MIN_DURATION" ] && [ "$dur_int" -le "$MAX_DURATION" ]; then
            echo "$f"
        fi
    fi
done > "$tmpfile"

count=$(wc -l < "$tmpfile")
mv "$tmpfile" "$OUTPUT"
chmod 644 "$OUTPUT"
echo "Generated $OUTPUT with $count tracks"
