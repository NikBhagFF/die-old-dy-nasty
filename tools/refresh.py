#!/usr/bin/env python3
"""Refresh the established top-120 KTC devy snapshot without touching other data.
Usage: python refresh.py --source path/to/prosp.ts [--check] [--html saved.html]
Only the public KTC devy page is fetched. No other source is requested.
"""
import argparse, hashlib, html, json, math, os, re, tempfile, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
URL = 'https://keeptradecut.com/devy-rankings'
PATTERN = r'(export const PROSP: any = )(\{.*?\})(;\n)'

def parse_rows(page):
    match = re.search(r'id=[\"\x27]ktc-players[\"\x27]>(\[.*?\])</script>', page, re.S)
    if not match:
        raise ValueError('KTC player JSON missing; keep the existing snapshot')
    players = json.loads(html.unescape(match.group(1)))
    rows = []
    for p in players:
        sf = p.get('superflexValues') or {}
        rows.append(dict(n=p['playerName'], pos=p['position'], sch=p.get('team'),
            cls=p.get('draftYear'), ht=(str(p['heightFeet']) + "'" + str(p['heightInches']) + '\"') if p.get('heightFeet') is not None and p.get('heightInches') is not None else None,
            wt=p.get('weight'), v=sf.get('value'), rk=sf.get('rank'),
            pr=sf.get('positionalRank'), tr=sf.get('overallTrend')))
    if len(rows) < 120:
        raise ValueError('Fewer than 120 source rows; keep the existing snapshot')
    for r in rows:
        if not r['n'] or r['pos'] not in ('QB','RB','WR','TE'):
            raise ValueError('Invalid player identity/position')
        for key in ('v','rk','pr'):
            if isinstance(r[key], bool) or not isinstance(r[key], (int,float)) or not math.isfinite(r[key]) or r[key] < (0 if key == 'v' else 1):
                raise ValueError('Missing or invalid value/rank; keep the existing snapshot')
    rows.sort(key=lambda r:r['rk'])
    rows=rows[:120]
    if len({(r['n'],r['pos'],r['sch']) for r in rows}) != 120 or len({r['rk'] for r in rows}) != 120:
        raise ValueError('Duplicate identities or ranks')
    return rows

def extract(source):
    match = re.search(PATTERN, source, re.S)
    if not match:
        raise ValueError('Existing PROSP export not recognized')
    return match, json.loads(match.group(2))

def digest(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def updated(source, rows, now):
    match, data = extract(source)
    data['rows'] = rows
    result=source[:match.start(2)] + json.dumps(data,ensure_ascii=False) + source[match.end(2):]
    et=now.astimezone(ZoneInfo('America/New_York'))
    for name,value in [('PROSP_AT',et.strftime('%b %-d, %-I:%M %p ET')),('PROSP_ISO',now.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))]:
        result,count=re.subn(r'(export const '+name+r' = )"[^"]*";', lambda m:m.group(1)+json.dumps(value)+';', result)
        if count != 1:
            raise ValueError('Timestamp export missing or duplicated')
    _, new_data=extract(result)
    if {k:v for k,v in data.items() if k!='rows'} != {k:v for k,v in new_data.items() if k!='rows'}:
        raise ValueError('Non-ranking data changed')
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--check',action='store_true')
    ap.add_argument('--html',type=Path,help='Use an already saved source response, without a network request')
    args=ap.parse_args()
    source=args.source.read_text()
    _,current=extract(source)
    if args.html:
        page=args.html.read_text()
    else:
        request=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request,timeout=30) as response:
            page=response.read().decode('utf-8')
    rows=parse_rows(page)
    old,new=digest(current['rows']),digest(rows)
    print(json.dumps(dict(status='UNCHANGED' if old==new else 'CHANGED',checked_at=datetime.now(timezone.utc).isoformat(),source=URL,rows=len(rows),old_sha256=old,new_sha256=new)))
    if old==new or args.check:
        return
    result=updated(source,rows,datetime.now(timezone.utc))
    with tempfile.NamedTemporaryFile('w',dir=args.source.parent,delete=False) as temp:
        temp.write(result)
        temp.flush()
        os.fsync(temp.fileno())
        temporary=temp.name
    os.replace(temporary,args.source)
if __name__=='__main__':
    main()
