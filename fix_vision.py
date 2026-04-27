import json, re, os

# ------------------------------------------------------------
# 1. ADD TACTICAL VISIONS TO team_profiles.json
# ------------------------------------------------------------
with open('team_profiles.json', 'r') as f:
    teams = json.load(f)

def get_stat(prof, key, default):
    tendency = prof.get('tendency', '')
    m = re.search(rf'{key}:\s*([\d\.]+)', tendency)
    if m:
        val = m.group(1).rstrip('.')   # remove any trailing dot
        try:
            return float(val)
        except ValueError:
            pass
    # fallback to _raw if present
    raw = prof.get('_raw', {})
    if key.lower() in raw and raw[key.lower()] is not None:
        return float(raw[key.lower()])
    return default
for team, prof in teams.items():
    poss = get_stat(prof, 'Poss', 50)
    fluid = get_stat(prof, 'Fluid', 0.5)
    press = prof.get('_raw', {}).get('pressures', 25)
    off_str = prof.get('offensiveStrength', 5) / 10.0
    def_sol = prof.get('defensiveSolidity', 5) / 10.0
    style = prof.get('style', 'balanced')

    # Estimate pressure from style if not in raw
    if not prof.get('_raw') or 'pressures' not in prof['_raw']:
        press = {'attack': 28, 'defense': 22, 'possession': 25, 'balanced': 25}[style]

    # Approximate width based on style and fluidity
    width_base = {'possession': 6.5, 'attack': 7.2, 'defense': 5.0, 'balanced': 6.0}[style]
    width = width_base + (fluid - 0.5) * 2

    # Pass length estimate
    pass_len = {'possession': 17, 'attack': 21, 'defense': 19, 'balanced': 20}[style]
    pass_len += (off_str - 0.5) * 2

    # ---------- classification ----------
    if poss > 55 and pass_len < 20:
        vision = 'Tiki-Taka'
    elif press > 30 and 45 <= poss <= 60:
        vision = 'Gegenpressing'
    elif poss < 42 and def_sol > 0.75 and width < 5.5:
        vision = 'Park the Bus'
    elif width > 7.0 and off_str > 0.6:
        vision = 'Wing Play'
    elif poss < 45 and pass_len > 22 and off_str > 0.55:
        vision = 'Counter-Attack'
    else:
        vision = 'Balanced'

    prof['tactical_vision'] = vision

with open('team_profiles.json', 'w') as f:
    json.dump(teams, f, indent=2)
print(f'✅ Added tactical visions to {len(teams)} teams.')

# ------------------------------------------------------------
# 2. UPDATE engine.html WITH VISION CARD (CSS, HTML, JS)
# ------------------------------------------------------------
with open('engine.html', 'r') as f:
    html = f.read()

# Only add if not already present
if 'vision-card' not in html:
    # ---- CSS ----
    vision_css = '''
    .vision-card {
      background: linear-gradient(135deg, #1a2a1a, #0d1a0d);
      border-radius: var(--radius-md);
      padding: 18px;
      margin-top: 16px;
      border: 2px solid var(--accent-gold);
      text-align: center;
    }
    .vision-title {
      font-size: 1.3rem; font-weight: 800; color: var(--accent-gold); margin-bottom: 6px;
    }
    .vision-desc {
      font-size: 0.9rem; color: var(--accent-mint); margin-bottom: 10px;
    }
    .vision-stats {
      font-size: 0.78rem; color: var(--accent-muted);
    }'''
    # insert before </style>
    html = html.replace('</style>', vision_css + '\n</style>', 1)

    # ---- HTML div ----
    vision_div = '\n        <div class="vision-card" id="visionCard"></div>'
    # insert after the fifa card div
    html = html.replace('<div class="fifa-card" id="fifaCard"></div>',
                        '<div class="fifa-card" id="fifaCard"></div>' + vision_div, 1)

    # ---- JavaScript ----
    vision_js = '''
    function renderVision(team) {
      const vision = team.tactical_vision;
      const card = document.getElementById('visionCard');
      if (!vision) { card.style.display='none'; return; }
      card.style.display='block';
      const desc = {
        'Tiki-Taka': 'Short passing, high possession, patient build‑up',
        'Gegenpressing': 'Intense press, vertical compactness, rapid transitions',
        'Park the Bus': 'Deep defensive block, disciplined shape, low risk',
        'Wing Play': 'Wide attacks, overlapping full‑backs, crosses',
        'Counter-Attack': 'Low possession, fast breaks, direct play',
        'Balanced': 'Flexible depth, situational pressing, mixed approach'
      };
      const icon = {
        'Tiki-Taka': '🧠', 'Gegenpressing': '⚡', 'Park the Bus': '🚌',
        'Wing Play': '↔️', 'Counter-Attack': '💨', 'Balanced': '⚖️'
      };
      let stats = '';
      const raw = team._raw || {};
      const press = raw.pressures || '?';
      const possMatch = (team.tendency||'').match(/Poss: ([\d.]+)%/);
      const poss = possMatch ? possMatch[1] : '?';
      stats = `Press: ${press} | Poss: ${poss}%`;
      card.innerHTML = `
        <div class="vision-title">${icon[vision]||''} ${vision}</div>
        <div class="vision-desc">${desc[vision]||''}</div>
        <div class="vision-stats">${stats}</div>
      `;
    }
    // Call renderVision after FIFA card
    const origUpdate = updatePrediction;
    updatePrediction = function() {
      origUpdate();
      const teamKey = document.getElementById('teamSelect').value;
      renderVision(teamsDB[teamKey]);
    };
    '''
    # insert before the closing </script> of the main script block
    html = html.replace('</script>\n</body>', '</script>\n' + vision_js + '\n</body>', 1)

    with open('engine.html', 'w') as f:
        f.write(html)
    print('✅ engine.html updated with Tactical Vision card.')
else:
    print('ℹ️  Vision card already present in engine.html.')
