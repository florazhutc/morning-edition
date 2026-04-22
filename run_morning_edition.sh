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
    
    # Generate archive index
    echo "[$(date)] 📦 Updating archive index..." >> "$LOG_FILE"
    cd "$SCRIPT_DIR"
    /usr/bin/python3 "update_archive.py" >> "$LOG_FILE" 2>> "$ERROR_LOG"
    
    # Auto-commit and push to Trigger Netlify Background Deployment
    echo "[$(date)] ☁️ Pushing to GitHub (for Netlify deployment)..." >> "$LOG_FILE"
    git add magazines/ "$TODAY.html" index.html >> "$LOG_FILE" 2>> "$ERROR_LOG"
    git commit -m "📰 Publish Morning Edition $TODAY" >> "$LOG_FILE" 2>> "$ERROR_LOG"
    git push origin main >> "$LOG_FILE" 2>> "$ERROR_LOG"
else
    echo "[$(date)] ❌ Generation failed (exit code: $EXIT_CODE)" >> "$ERROR_LOG"
fi

exit $EXIT_CODE
