#!/bin/bash
# Morning Edition cron launcher
# Runs daily at 1:00 PM

cd "/Users/flora/Desktop/news magazines test"

# Load environment variables
set -a
source .env
set +a

# Run the generator
python3 generate_magazine.py >> /Users/flora/Desktop/news-magazine-cron.log 2>&1

# Update index.html with today's magazine link
LATEST=$(ls -t magazines/*.html | head -1)
FILENAME=$(basename "$LATEST")

# Get the date from filename (e.g., 2026-05-06)
DATE_STR=$(echo "$FILENAME" | sed 's/magazines\///; s/.html//')

# Format date for display
DISPLAY_DATE=$(date -j -f "%Y-%m-%d" "$DATE_STR" "+%B %d, %Y" 2>/dev/null || echo "$DATE_STR")

# Add to index.html if not already there
if ! grep -q "$FILENAME" index.html; then
    sed -i '' "s|<div class=\"archive-grid\">|<div class=\"archive-grid\">\\
\\
        <a href=\"magazines/$FILENAME\" class=\"issue-card\">\\
            <div class=\"issue-date\">$DISPLAY_DATE</div>\\
            <div class=\"issue-title\">Morning Edition - $DATE_STR</div>\\
            <div class=\"issue-arrow\">→</div>\\
        </a>|" index.html
fi

# Commit and push changes
cd "/Users/flora/Desktop/news magazines test"
git add -A
git commit -m "📰 Auto-publish $(date +%Y-%m-%d)" >/dev/null 2>&1
git push >/dev/null 2>&1