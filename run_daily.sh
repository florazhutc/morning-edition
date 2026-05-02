#!/bin/bash
# Morning Edition cron launcher
# Runs daily at 12:00 PM

cd "/Users/flora/Desktop/news magazines test"

# Load environment variables
set -a
source .env
set +a

# Run the generator
python3 generate_magazine.py >> /Users/flora/Desktop/news-magazine-cron.log 2>&1