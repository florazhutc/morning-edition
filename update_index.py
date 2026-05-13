#!/usr/bin/env python3
"""Update index.html with latest magazine link."""

import re
from pathlib import Path
from datetime import datetime

magazines = sorted(Path('magazines').glob('*.html'), reverse=True)
if not magazines:
    print('No magazines found')
    exit(0)

latest = magazines[0]
date_str = latest.stem
print(f'Latest: {date_str}')

try:
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    display = dt.strftime('%B %d, %Y')
except:
    display = date_str

with open('index.html', 'r') as f:
    content = f.read()

if latest.name not in content:
    new_link = f'''<a href="magazines/{latest.name}" class="issue-card">
            <div class="issue-date">{display}</div>
            <div class="issue-title">Morning Edition - {date_str}</div>
            <div class="issue-arrow">→</div>
        </a>'''
    content = content.replace('<div class="archive-grid">', '<div class="archive-grid">' + new_link)

    # Update count
    count = len(list(Path('magazines').glob('*.html')))
    content = re.sub(r'Powering \d+ issues', f'Powering {count} issues', content)

    with open('index.html', 'w') as f:
        f.write(content)
    print(f'Updated index.html with {date_str}')
else:
    print('Link already exists')