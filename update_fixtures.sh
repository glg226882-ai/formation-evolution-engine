#!/bin/bash
cd ~
echo "Fetching live fixtures..."
python3 fetch_live_fixtures.py
if [ $? -ne 0 ]; then
    echo "❌ Fixture fetch failed. Check your internet / API key."
    exit 1
fi
echo "Embedding fixtures into engine_full.html..."
python3 << 'EMBED'
import json
with open('team_profiles.json') as f: teams = json.load(f)
with open('live_fixtures.json') as f: live = json.load(f)
with open('engine_full.html') as f: html = f.read()

# Replace the fixtures array
import re
html = re.sub(r'let fixtures = \[.*?\];', f'let fixtures = {json.dumps(live)};', html, count=1, flags=re.DOTALL)

with open('engine_full.html','w') as f: f.write(html)
print(f'✅ Embedded {len(live)} fixtures.')
EMBED
echo "Done. Reload http://localhost:8081/engine_full.html"
