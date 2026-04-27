import json, urllib.request

API_KEY = "YOUR_FOOTBALL_DATA_API_KEY"
HEADERS = {"X-Auth-Token": API_KEY}

LEAGUES = {
    "PL": "Premier League",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "PD": "La Liga",
    "FL1": "Ligue 1",
}

all_fixtures = []

for code, name in LEAGUES.items():
    url = f"https://api.football-data.org/v4/competitions/{code}/matches?status=SCHEDULED"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
            for m in data.get("matches", []):
                all_fixtures.append({
                    "home": m["homeTeam"]["name"],
                    "away": m["awayTeam"]["name"],
                    "date": m["utcDate"][:10],
                    "league": name,
                    "status": m.get("status", "SCHEDULED"),
                })
        print(f"✅ {name}: fetched")
    except Exception as e:
        print(f"❌ {name}: {e}")

with open("live_fixtures.json", "w") as f:
    json.dump(all_fixtures, f, indent=2)

print(f"\nSaved {len(all_fixtures)} upcoming fixtures to live_fixtures.json")
