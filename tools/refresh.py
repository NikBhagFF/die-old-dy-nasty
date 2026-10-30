#!/usr/bin/env python3
"""KTC devy snapshot refresher (rebuilt 2026-10-30 after workspace loss).

Pulls the public KeepTradeCut devy-rankings page, extracts the embedded
#ktc-players JSON (no login), maps to the PROSP row shape used by the site,
and rewrites src/prosp.ts in the File source ONLY when the values changed.
ESPN stays paused: GAMES_AT / GAMES_PAUSED lines are preserved verbatim.

Usage: refresh.py [--check]   (check = report change status, write nothing)
"""
import re, json, html, sys, hashlib, urllib.request
from datetime import datetime, timezone, timedelta

SRC = '/downloads/dynasty_pub/src/prosp.ts'
URL = 'https://keeptradecut.com/devy-rankings'

def fetch_rows():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    s = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
    m = re.search(r'id="ktc-players">(\[.*?\])</script>', s, re.S)
    if not m:
        raise RuntimeError('ktc-players JSON not found on page (site shape changed)')
    arr = json.loads(html.unescape(m.group(1)))
    rows = []
    for p in arr:
        sf = p.get('superflexValues') or {}
        rows.append({
            'n': p['playerName'], 'pos': p['position'], 'sch': p.get('team') or '',
            'cls': p.get('draftYear'), 'ht': f"{p.get('heightFeet',0)}'{p.get('heightInches',0)}\"",
            'wt': p.get('weight'), 'v': sf.get('value'), 'rk': sf.get('rank'),
            'pr': sf.get('positionalRank'), 'tr': sf.get('overallTrend'),
        })
    rows.sort(key=lambda r: (r['rk'] is None, r['rk'] or 1e9))
    return rows[:120]  # established export shape: top 120 superflex

def current_rows():
    s = open(SRC).read()
    m = re.search(r'export const PROSP: any = (\{.*?\});\n', s, re.S)
    return json.loads(m.group(1))['rows'], s

def main():
    check_only = '--check' in sys.argv
    new = fetch_rows()
    cur, src = current_rows()
    h_new = hashlib.sha256(json.dumps(new, sort_keys=True).encode()).hexdigest()[:12]
    h_cur = hashlib.sha256(json.dumps(cur, sort_keys=True).encode()).hexdigest()[:12]
    if h_new == h_cur:
        print(f'UNCHANGED {h_cur} ({len(new)} rows)')
        return
    print(f'CHANGED {h_cur} -> {h_new} ({len(new)} rows)')
    if check_only:
        return
    now = datetime.now(timezone.utc)
    et = now.astimezone(timezone(timedelta(hours=-4)))  # EDT (Oct); revisit in Nov for EST
    disp = et.strftime('%b %-d, %-I:%M %p ET')
    iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    games_at = re.search(r'export const GAMES_AT = .*?;\n', src).group(0)
    games_paused = re.search(r'export const GAMES_PAUSED = .*?;\n', src).group(0)
    games_block = re.search(r'export const GAMES: any = .*?;\n', src, re.S)
    out = (
        '// College prospect snapshot: scheduled pull from KeepTradeCut and ESPN (hosted page cannot call them)\n'
        + 'export const PROSP: any = ' + json.dumps({'rows': new}) + ';\n'
        + f'export const PROSP_AT = "{disp}";\n'
        + f'export const PROSP_ISO = "{iso}";\n'
        + (games_block.group(0) if games_block else '')
        + games_at + games_paused
    )
    open(SRC, 'w').write(out)
    print(f'WROTE {SRC} at {disp}')

if __name__ == '__main__':
    main()
