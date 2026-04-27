import json, os, pandas as pd, numpy as np
from difflib import get_close_matches

# ========== CONFIG ==========
PLAYERS_CSV = None   # leave None to auto‑detect

# ========== HELPERS ==========
def find_fifa_csv():
    """Search for the FIFA 23 players CSV (from kagglehub or manual download)."""
    # common locations
    search_paths = [
        os.path.expanduser("~/.cache/kagglehub/datasets/stefanoleone992/fifa-23-complete-player-dataset"),
        os.path.expanduser("~/.cache/kagglehub/datasets/sjots/fifa-23-complete-player-dataset"),
        os.path.expanduser("~/storage/downloads"),
        "."
    ]
    for base in search_paths:
        if not os.path.exists(base):
            continue
        for root, dirs, files in os.walk(base):
            for f in files:
                if f.endswith('.csv') and ('player' in f.lower() or 'fifa' in f.lower()):
                    return os.path.join(root, f)
    return None

def normalize_name(s):
    if not isinstance(s, str):
        return str(s)
    s = s.strip()
    map_dict = {
        'Manchester Utd': 'Manchester United', 'Man Utd': 'Manchester United', 'Man United': 'Manchester United',
        'Man City': 'Manchester City', 'Spurs': 'Tottenham Hotspur', 'Tottenham': 'Tottenham Hotspur',
        'Newcastle Utd': 'Newcastle United', 'Wolves': 'Wolverhampton Wanderers',
        'Brighton & Hove': 'Brighton & Hove Albion', 'West Ham': 'West Ham United',
        'FC Bayern': 'Bayern Munich', 'Bayern': 'Bayern Munich', 'FC Bayern München': 'Bayern Munich',
        'FC Barcelona': 'Barcelona', 'Real Madrid CF': 'Real Madrid', 'Atlético Madrid': 'Atletico Madrid',
        'AC Milan': 'Milan', 'Inter Milan': 'Inter', 'Juventus FC': 'Juventus',
        'AS Roma': 'Roma', 'SSC Napoli': 'Napoli', 'PSG': 'Paris Saint-Germain',
        'Paris SG': 'Paris Saint-Germain', 'Olympique Marseille': 'Marseille',
        'Olympique Lyonnais': 'Lyon', 'Bor. Dortmund': 'Borussia Dortmund',
        'Bayer Leverkusen': 'Bayer Leverkusen', 'Leverkusen': 'Bayer Leverkusen',
        'Schalke': 'Schalke 04', 'Eintracht Frankfurt': 'Eintracht Frankfurt',
        'VfB': 'VfB Stuttgart', 'Wolfsburg': 'VfL Wolfsburg', 'Werder': 'Werder Bremen',
        'Hoffenheim': 'TSG Hoffenheim', 'Hertha BSC': 'Hertha Berlin', 'Hamburger SV': 'Hamburg',
        'Köln': 'FC Köln', 'Mainz': 'FC Mainz 05', 'Augsburg': 'FC Augsburg',
        'Freiburg': 'SC Freiburg', 'Union Berlin': '1. FC Union Berlin',
        'Bochum': 'VfL Bochum',
    }
    if s in map_dict:
        return map_dict[s]
    return s

# ========== MAIN ==========
def main():
    if not os.path.exists('team_profiles.json'):
        print('❌ team_profiles.json not found. Run the builder first.')
        return

    # Load current profiles
    with open('team_profiles.json') as f:
        profiles = json.load(f)

    team_names = list(profiles.keys())
    print(f'✅ Loaded {len(team_names)} teams.')

    # Locate FIFA CSV
    csv_path = PLAYERS_CSV or find_fifa_csv()
    if not csv_path:
        print('❌ Could not find a FIFA 23 players CSV.')
        print('   Download it from Kaggle:')
        print('   python3 -c "import kagglehub; print(kagglehub.dataset_download(\'stefanoleone992/fifa-23-complete-player-dataset\'))"')
        print('   Then re-run this script.')
        return
    print(f'📂 Using FIFA data: {csv_path}')

    # Load players
    players = pd.read_csv(csv_path, low_memory=False)
    players.columns = [c.lower().strip().replace(' ', '_') for c in players.columns]

    # Detect team column
    team_col = None
    for col in ['club_name', 'team', 'club', 'team_name']:
        if col in players.columns:
            team_col = col
            break
    if team_col is None:
        print('❌ Could not find a team column in the CSV.')
        return

    players[team_col] = players[team_col].apply(normalize_name)

    # Attributes to aggregate (numeric FIFA attributes)
    attr_list = [
        'overall', 'potential', 'value_eur', 'wage_eur', 'age',
        'pace', 'shooting', 'passing', 'dribbling', 'defending', 'physic',
        'attacking_crossing', 'attacking_finishing', 'attacking_heading_accuracy',
        'attacking_short_passing', 'attacking_volleys',
        'skill_dribbling', 'skill_curve', 'skill_fk_accuracy', 'skill_long_passing',
        'skill_ball_control',
        'movement_acceleration', 'movement_sprint_speed', 'movement_agility',
        'movement_reactions', 'movement_balance',
        'power_shot_power', 'power_jumping', 'power_stamina', 'power_strength',
        'power_long_shots',
        'mentality_aggression', 'mentality_interceptions', 'mentality_positioning',
        'mentality_vision', 'mentality_penalties', 'mentality_composure',
        'defending_marking_awareness', 'defending_standing_tackle', 'defending_sliding_tackle',
    ]
    available = [c for c in attr_list if c in players.columns]
    print(f'📊 Aggregating {len(available)} attributes...')

    # Keep only top 23 players per club for squad average
    if 'overall' in players.columns:
        top_players = players.sort_values('overall', ascending=False).groupby(team_col).head(23)
    else:
        top_players = players.groupby(team_col).head(23)

    team_stats = top_players.groupby(team_col)[available].mean().round(1)
    # Extra team metrics
    team_stats['squad_size'] = players.groupby(team_col).size()
    if 'age' in players.columns:
        team_stats['avg_age'] = players.groupby(team_col)['age'].mean().round(1)
    if 'value_eur' in players.columns:
        team_stats['total_value_millions'] = (players.groupby(team_col)['value_eur'].sum() / 1e6).round(0)

    # Match FIFA teams to StatsBomb teams
    fifa_teams = list(team_stats.index)
    matched = 0
    for sb_team in team_names:
        match = None
        if sb_team in fifa_teams:
            match = sb_team
        else:
            candidates = get_close_matches(sb_team, fifa_teams, n=1, cutoff=0.7)
            if candidates:
                match = candidates[0]
        if match:
            row = team_stats.loc[match]
            fifa_data = {}
            for col in team_stats.columns:
                val = row[col]
                if isinstance(val, (np.floating, float)):
                    val = round(float(val), 2)
                elif isinstance(val, np.integer):
                    val = int(val)
                fifa_data[col] = val
            profiles[sb_team]['_fifa'] = fifa_data
            matched += 1

    print(f'✅ Matched {matched}/{len(team_names)} teams with FIFA data.')

    # Save enriched profiles
    with open('team_profiles.json', 'w') as f:
        json.dump(profiles, f, indent=2)

    print('💾 team_profiles.json updated with FIFA ratings.')

if __name__ == "__main__":
    main()
