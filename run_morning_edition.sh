#!/bin/bash
# Morning Edition — Runner Script
# Ensures proper environment for launchd execution

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$HOME/Library/Logs/morning-edition.log"
ERROR_LOG="$HOME/Library/Logs/morning-edition-error.log"
OUTPUT_DIR="$SCRIPT_DIR/magazines"
TODAY=$(date +%Y-%m-%d)

# Create output dir if needed
mkdir -p "$OUTPUT_DIR"

# Skip if today's issue already exists
if [ -f "$OUTPUT_DIR/$TODAY.html" ]; then
    echo "[$(date)] Today's issue ($TODAY) already exists. Skipping." >> "$LOG_FILE"
    exit 0
fi

echo "[$(date)] Starting Morning Edition generation for $TODAY..." >> "$LOG_FILE"

# Run the generator
/usr/bin/python3 "$SCRIPT_DIR/generate_magazine.py" >> "$LOG_FILE" 2>> "$ERROR_LOG"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ] && [ -f "$OUTPUT_DIR/$TODAY.html" ]; then
    echo "[$(date)] ✅ Successfully generated $TODAY.html" >> "$LOG_FILE"
else
    echo "[$(date)] ❌ Generation failed (exit code: $EXIT_CODE)" >> "$ERROR_LOG"
fi

exit $EXIT_CODE
