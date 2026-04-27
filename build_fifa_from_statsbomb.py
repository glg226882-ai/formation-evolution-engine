import json, re, numpy as np

with open('team_profiles.json') as f:
    teams = json.load(f)

def get_val(prof, key, default=0):
    t = prof.get('tendency', '')
    m = re.search(rf'{key}:\s*([\d\.]+)', t)
    if m:
        return float(m.group(1).rstrip('.'))
    raw = prof.get('_raw', {})
    if key.lower() in raw:
        v = raw[key.lower()]
        if v is not None:
            return float(v)
    return default

team_names = list(teams.keys())
all_stats = {
    'goals_for': [],
    'goals_against': [],
    'shots_for': [],
    'shots_against': [],
    'possession': [],
    'pressures': [],
    'tackles': [],
    'interceptions': [],
    'duel_win_rate': [],
    'fluidity': [],
}

for name in team_names:
    p = teams[name]
    all_stats['goals_for'].append(get_val(p, 'Avg goals', 1.0))
    all_stats['goals_against'].append(get_val(p, 'against', 1.0))
    all_stats['shots_for'].append(get_val(p, 'Shots', 1.0))
    all_stats['shots_against'].append(get_val(p, 'against', 1.0))
    all_stats['possession'].append(get_val(p, 'Poss', 50.0))
    all_stats['pressures'].append(p.get('_raw', {}).get('pressures', 25))
    all_stats['tackles'].append(p.get('_raw', {}).get('tackles_per_match', 15))
    all_stats['interceptions'].append(p.get('_raw', {}).get('interceptions_per_match', 10))
    all_stats['duel_win_rate'].append(p.get('_raw', {}).get('duel_win_rate', 0.5) * 100)
    all_stats['fluidity'].append(get_val(p, 'Fluid', 0.5) * 100)

for k in all_stats:
    all_stats[k] = np.array(all_stats[k])

def percentile_score(values, reverse=False):
    arr = np.array(values, dtype=float)
    mask = ~np.isnan(arr)
    scores = np.full(len(values), 50.0)
    if not np.any(mask):
        return scores.astype(int)
    valid = arr[mask]
    order = np.argsort(valid)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(valid)+1)
    for v in np.unique(valid):
        idxs = np.where(valid == v)[0]
        avg_rank = ranks[idxs].mean()
        ranks[idxs] = avg_rank
    pct = (ranks - 1) / (len(valid) - 1) * 99
    pct = np.round(pct).astype(int)
    scores[mask] = pct
    if reverse:
        scores[mask] = 99 - scores[mask]
    return scores

fifa_ratings = {
    'Pace': {
        'Acceleration': percentile_score(all_stats['pressures']),
        'Sprint Speed': percentile_score(all_stats['fluidity']),
    },
    'Shooting': {
        'Finishing': percentile_score(all_stats['goals_for']),
        'Shot Power': percentile_score(all_stats['shots_for']),
        'Long Shots': percentile_score(all_stats['shots_for']),
    },
    'Passing': {
        'Vision': percentile_score(all_stats['possession']),
        'Short Passing': percentile_score(all_stats['possession']),
        'Long Passing': percentile_score(all_stats['possession']),
    },
    'Dribbling': {
        'Agility': percentile_score(all_stats['fluidity']),
        'Balance': percentile_score(all_stats['duel_win_rate']),
    },
    'Defending': {
        'Defensive Awareness': percentile_score(all_stats['interceptions']),
        'Standing Tackle': percentile_score(all_stats['tackles']),
        'Sliding Tackle': percentile_score(all_stats['tackles']),
    },
    'Physical': {
        'Strength': percentile_score(all_stats['duel_win_rate']),
        'Stamina': percentile_score(all_stats['pressures']),
    },
    'Mentality': {
        'Aggression': percentile_score(all_stats['tackles']),
        'Vision': percentile_score(all_stats['possession']),
    },
}

for i, name in enumerate(team_names):
    prof = teams[name]
    fifa_block = {}
    for cat, stats in fifa_ratings.items():
        fifa_block[cat] = {}
        for stat_name, score_array in stats.items():
            fifa_block[cat][stat_name] = int(score_array[i])
    prof['_fifa'] = fifa_block

with open('team_profiles.json', 'w') as f:
    json.dump(teams, f, indent=2)
print(f'✅ StatsBomb FIFA cards built for {len(teams)} teams.')
