import json, os
import numpy as np
import pandas as pd
from collections import Counter, defaultdict
from statsbombpy import sb

# ================== CONFIG ==================
MIN_MATCHES = 3
# ============================================

def safe_div(a, b):
    return a / b if b else 0.0

def manual_entropy(counts):
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts]
    return -sum(p * np.log2(p) for p in probs if p > 0)

def compute_fluidity(formations):
    if not formations:
        return 0.5
    cnt = Counter(formations)
    vals = list(cnt.values())
    ent = manual_entropy(vals)
    max_ent = np.log2(len(cnt)) if len(cnt) > 1 else 1.0
    return ent / max_ent

def map_percentile_scores(values, reverse=False):
    arr = np.array(values, dtype=float)
    mask = ~np.isnan(arr)
    scores = np.full(len(values), 5.0)
    if not np.any(mask):
        return scores
    valid = arr[mask]
    sorted_idx = np.argsort(valid)
    ranks = np.empty_like(sorted_idx, dtype=float)
    ranks[sorted_idx] = np.arange(1, len(valid)+1)
    for v in np.unique(valid):
        tie_idx = np.where(valid == v)[0]
        avg_rank = ranks[tie_idx].mean()
        ranks[tie_idx] = avg_rank
    pct = (ranks - 1) / (len(valid) - 1) * 10
    scores[mask] = pct
    if reverse:
        scores[mask] = 10 - scores[mask]
    return np.round(scores, 1)

def compute_team_stats(comp_id, season_id):
    matches = sb.matches(competition_id=comp_id, season_id=season_id)
    team_data = defaultdict(lambda: {
        'matches': 0,
        'goals_for': [], 'goals_against': [], 'xG_for': [], 'xG_against': [],
        'shots_for': [], 'shots_against': [],
        'passes_total': [], 'passes_success': [], 'pass_lengths': [],
        'pressures': [], 'tackles': [], 'interceptions': [], 'clearances': [],
        'duels': [], 'duels_won': [],
        'formations': [],
        'possession': []
    })

    for _, match in matches.iterrows():
        match_id = match['match_id']
        home_team = match['home_team']
        away_team = match['away_team']

        try:
            events = sb.events(match_id=match_id)
        except Exception:
            continue

        try:
            lineups = sb.lineups(match_id=match_id)
        except:
            lineups = {}

        for team, opp in [(home_team, away_team), (away_team, home_team)]:
            td = team_data[team]
            td['matches'] += 1

            team_events = events[events['team'] == team]

            goals = team_events[team_events['shot_outcome'] == 'Goal']
            td['goals_for'].append(len(goals))
            xg_col = 'shot_statsbomb_xg'
            xg = team_events[xg_col].sum() if xg_col in team_events.columns else 0.0
            td['xG_for'].append(xg)

            shots = team_events[team_events['type'] == 'Shot']
            td['shots_for'].append(len(shots))

            passes = team_events[team_events['type'] == 'Pass']
            td['passes_total'].append(len(passes))
            succ = passes[passes['pass_outcome'].isna()]
            td['passes_success'].append(len(succ))
            if 'pass_length' in passes.columns:
                td['pass_lengths'].extend(passes['pass_length'].dropna().tolist())

            pressures = team_events[team_events['type'] == 'Pressure']
            td['pressures'].append(len(pressures))
            tackles = team_events[team_events['type'] == 'Tackle']
            td['tackles'].append(len(tackles))
            interceptions = team_events[team_events['type'] == 'Interception']
            td['interceptions'].append(len(interceptions))
            clearances = team_events[team_events['type'] == 'Clearance']
            td['clearances'].append(len(clearances))

            duels = team_events[team_events['type'].isin(['Duel', 'Tackle'])]
            won_duels = duels[duels.get('duel_outcome') == 'Won'] if 'duel_outcome' in duels.columns else \
                        duels[duels.get('tackle_outcome') == 'Won']
            td['duels'].append(len(duels))
            td['duels_won'].append(len(won_duels))

            opp_events = events[events['team'] == opp]
            t_pass = len(passes)
            opp_pass = len(opp_events[opp_events['type'] == 'Pass'])
            total = t_pass + opp_pass
            td['possession'].append(t_pass / total * 100 if total > 0 else 50.0)

            if team in lineups:
                lineup = lineups[team]
                if not lineup.empty:
                    pos = Counter()
                    for _, row in lineup.iterrows():
                        p = row.get('position', '')
                        if 'Goalkeeper' in p or 'GK' in p:
                            continue
                        if 'Back' in p or 'Defender' in p:
                            pos['Defender'] += 1
                        elif 'Midfield' in p:
                            pos['Midfielder'] += 1
                        elif 'Forward' in p or 'Winger' in p or 'Striker' in p or 'Attacker' in p:
                            pos['Forward'] += 1
                    if pos:
                        td['formations'].append(f"{pos.get('Defender',0)}-{pos.get('Midfielder',0)}-{pos.get('Forward',0)}")

            td['goals_against'].append(len(opp_events[opp_events['shot_outcome'] == 'Goal']))
            xg_opp = opp_events[xg_col].sum() if xg_col in opp_events.columns else 0.0
            td['xG_against'].append(xg_opp)
            td['shots_against'].append(len(opp_events[opp_events['type'] == 'Shot']))

    return team_data

def build_profiles(comp_id, season_id):
    raw = compute_team_stats(comp_id, season_id)
    qualified = {t: d for t, d in raw.items() if d['matches'] >= MIN_MATCHES}
    if not qualified:
        return {}, {}

    teams = list(qualified.keys())
    n = len(teams)
    summaries = []

    for t in teams:
        d = qualified[t]
        m = d['matches']
        avg_goals_for = np.mean(d['goals_for'])
        avg_goals_against = np.mean(d['goals_against'])
        avg_xg_for = np.mean(d['xG_for'])
        avg_xg_against = np.mean(d['xG_against'])
        avg_shots_for = np.mean(d['shots_for'])
        avg_shots_against = np.mean(d['shots_against'])
        avg_passes = np.mean(d['passes_total'])
        pass_success = safe_div(np.sum(d['passes_success']), np.sum(d['passes_total'])) if np.sum(d['passes_total']) > 0 else np.nan
        avg_pass_len = np.mean(d['pass_lengths']) if d['pass_lengths'] else np.nan

        avg_pressures = np.mean(d['pressures'])
        avg_tackles = np.mean(d['tackles'])
        avg_interceptions = np.mean(d['interceptions'])
        avg_clearances = np.mean(d['clearances'])
        avg_duels = np.mean(d['duels'])
        duel_win_rate = safe_div(np.sum(d['duels_won']), np.sum(d['duels'])) if np.sum(d['duels']) > 0 else np.nan

        avg_possession = np.mean(d['possession'])
        fluidity = compute_fluidity(d['formations'])

        summaries.append({
            'team': t,
            'm': m,
            'goals_for': avg_goals_for,
            'goals_against': avg_goals_against,
            'xg_for': avg_xg_for,
            'xg_against': avg_xg_against,
            'shots_for': avg_shots_for,
            'shots_against': avg_shots_against,
            'passes': avg_passes,
            'pass_success': pass_success,
            'pass_len': avg_pass_len,
            'pressures': avg_pressures,
            'tackles': avg_tackles,
            'interceptions': avg_interceptions,
            'clearances': avg_clearances,
            'duel_win_rate': duel_win_rate,
            'possession': avg_possession,
            'fluidity': fluidity,
        })

    off_raw = [s['goals_for'] for s in summaries], [s['xg_for'] for s in summaries], [s['shots_for'] for s in summaries], [s['possession'] for s in summaries], [s['pressures'] for s in summaries]
    off_scores = np.column_stack([
        map_percentile_scores(off_raw[0]),
        map_percentile_scores(off_raw[1]),
        map_percentile_scores(off_raw[2]),
        map_percentile_scores(off_raw[3]),
        map_percentile_scores(off_raw[4])
    ])
    off_weights = np.array([0.4, 0.3, 0.15, 0.1, 0.05])
    offensive_strength = np.clip(off_scores @ off_weights, 0, 10)

    def_raw = [s['goals_against'] for s in summaries], [s['xg_against'] for s in summaries], [s['shots_against'] for s in summaries], [s['tackles'] for s in summaries], [s['interceptions'] for s in summaries], [s['clearances'] for s in summaries], [s['duel_win_rate'] for s in summaries]
    def_scores = np.column_stack([
        map_percentile_scores(def_raw[0], reverse=True),
        map_percentile_scores(def_raw[1], reverse=True),
        map_percentile_scores(def_raw[2], reverse=True),
        map_percentile_scores(def_raw[3]),
        map_percentile_scores(def_raw[4]),
        map_percentile_scores(def_raw[5]),
        map_percentile_scores(def_raw[6])
    ])
    def_weights = np.array([0.4, 0.3, 0.1, 0.05, 0.05, 0.05, 0.05])
    defensive_solidity = np.clip(def_scores @ def_weights, 0, 10)

    profiles = {}
    match_counts = {}
    for i, s in enumerate(summaries):
        team = s['team']
        if s['possession'] > 55:
            style = 'possession'
        elif s['pressures'] > np.percentile([x['pressures'] for x in summaries], 70):
            style = 'attack'
        elif s['goals_against'] < np.percentile([x['goals_against'] for x in summaries], 30):
            style = 'defense'
        else:
            style = 'balanced'

        tendency = (
            f"Avg goals: {s['goals_for']:.2f} for, {s['goals_against']:.2f} against. "
            f"Shots: {s['shots_for']:.1f} for, {s['shots_against']:.1f} against. "
            f"Poss: {s['possession']:.1f}%. Fluid: {s['fluidity']:.2f}. "
            f"Style: {style}."
        )
        profiles[team] = {
            "league": "StatsBomb Open Data",
            "baseFormation": "unknown",
            "style": style,
            "offensiveStrength": round(float(offensive_strength[i]), 1),
            "defensiveSolidity": round(float(defensive_solidity[i]), 1),
            "fluidity": round(float(s['fluidity']), 2),
            "homeAggression": 1.0,
            "awayCautious": 1.0,
            "tendency": tendency,
            "_raw": {
                "xg_for": round(float(s['xg_for']), 3),
                "xg_against": round(float(s['xg_against']), 3),
                "pressures": round(float(s['pressures']), 1),
                "duel_win_rate": round(float(s['duel_win_rate']), 2) if not np.isnan(s['duel_win_rate']) else None,
            }
        }
        match_counts[team] = s['m']

    return profiles, match_counts


if __name__ == '__main__':
    import os, json

    PROGRESS_FILE = 'progress.json'
    PROFILES_FILE = 'team_profiles.json'

    completed = set()
    all_profiles = {}
    team_weight = {}

    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            completed = set(tuple(x) for x in json.load(f))
    if os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE, 'r') as f:
            existing = json.load(f)
            for team, prof in existing.items():
                if team not in all_profiles:
                    all_profiles[team] = prof
                    team_weight[team] = 5

    print("Fetching all available competitions from StatsBomb...")
    all_comps = sb.competitions()
    comp_pairs = list(all_comps[['competition_id', 'season_id']].drop_duplicates().itertuples(index=False))
    print(f"Found {len(comp_pairs)} competition/season pairs.")

    for comp_id, season_id in comp_pairs:
        pair = (int(comp_id), int(season_id))
        if pair in completed:
            print(f"Skipping already processed: {comp_id}/{season_id}")
            continue

        try:
            print(f"Processing competition {comp_id}, season {season_id}...")
            profs, counts = build_profiles(comp_id, season_id)
            for team, prof in profs.items():
                m = counts.get(team, 0)
                if team not in all_profiles:
                    all_profiles[team] = prof
                    team_weight[team] = m
                else:
                    old_w = team_weight[team]
                    new_w = old_w + m
                    old = all_profiles[team]
                    old['offensiveStrength'] = round((old['offensiveStrength'] * old_w + prof['offensiveStrength'] * m) / new_w, 1)
                    old['defensiveSolidity'] = round((old['defensiveSolidity'] * old_w + prof['defensiveSolidity'] * m) / new_w, 1)
                    old['fluidity'] = round((old['fluidity'] * old_w + prof['fluidity'] * m) / new_w, 2)
                    if m > old_w:
                        old['style'] = prof['style']
                    old['tendency'] = prof['tendency']
                    team_weight[team] = new_w
        except Exception as e:
            print(f"Error on {comp_id}/{season_id}: {e}")
            continue

        completed.add(pair)
        with open(PROGRESS_FILE, 'w') as f:
            json.dump([list(x) for x in completed], f)
        with open(PROFILES_FILE, 'w') as f:
            json.dump(all_profiles, f, indent=2)

        print(f"Progress saved. Processed {pair}. Total teams so far: {len(all_profiles)}")

    print(f"\nAll competitions processed. Final team count: {len(all_profiles)}")
    print(f"Full profiles saved to {PROFILES_FILE}")
