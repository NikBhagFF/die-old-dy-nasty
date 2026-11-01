const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.argv[2]||process.cwd(),html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const assets=[...html.matchAll(/(?:src|href)=["']([^"']+\.(?:js|css))["']/g)].map(m=>m[1]);
assert(assets.some(p=>p.endsWith('.js'))&&assets.some(p=>p.endsWith('.css')),'index must name JS and CSS');
for(const p of assets){assert(!p.includes('..')&&!/^https?:/.test(p),'only local entry assets supported');assert(fs.statSync(path.join(root,p)).size>0,'missing/empty '+p)}
const d=JSON.parse(fs.readFileSync(path.join(root,'ai-status.json'),'utf8'));assert.equal(d.schema,1);assert.equal(d.sides.length,2);assert(Number.isFinite(Date.parse(d.updated_at)));
let rows=0;for(const s of d.sides){assert(s.name);assert(Number.isFinite(Date.parse(s.reported_at)));assert(Array.isArray(s.rows)&&s.rows.length);const seen=new Set();for(const r of s.rows){assert(r.service&&r.status&&Number.isFinite(Date.parse(r.reported_at)));assert(!seen.has(r.service),'duplicate AI row');seen.add(r.service);if(r.event_at)assert(Number.isFinite(Date.parse(r.event_at)));rows++}}
const js=assets.filter(p=>p.endsWith('.js')).map(p=>fs.readFileSync(path.join(root,p),'utf8')).join('\n');
// Extract the actual compiled whole/2dp display formatter from the served bundle, not a copied implementation.
// Shape-tolerant: matches any name/whitespace, anchored on the semantic contract
// (guard returning String(input); Number(); Number.isInteger ? String : toFixed(2)).
const match=js.match(/([\w$]+)\s*=\s*\(\s*([\w$]+)\s*\)\s*=>\s*\{\s*if\s*\([\s\S]{0,160}?Number\(\2\)[\s\S]{0,160}?\)\s*return\s+String\(\2\);\s*(?:const|let)\s+([\w$]+)\s*=\s*Number\(\2\);\s*return\s+Number\.isInteger\(\3\)\s*\?\s*String\(\3\)\s*:\s*\3\.toFixed\(2\)\s*;?\s*\}/);
assert(match,'actual compiled whole/2dp formatter not found: review compiler/source change');
const f=vm.runInNewContext('('+match[0].slice(match[0].indexOf('('))+')');
for(const [v,want] of [[0,'0'],[21,'21'],[21.3636,'21.36'],[-1.239,'-1.24'],['0','0'],[null,'null'],['','']])assert.equal(f(v),want);
// nflNumber contract (src/nflDisplay.ts): non-number/non-finite -> "Unknown"; integer -> plain; else toFixed(2).
const nflM=js.match(/function\s+nflNumber\s*\(\s*([\w$]+)\s*\)\s*\{[\s\S]{0,300}?toFixed\(2\)[\s\S]{0,80}?\}/);
assert(nflM,'actual compiled nflNumber formatter not found: review compiler/source change');
const nfl=vm.runInNewContext('('+nflM[0]+')');
for(const [v,want] of [[0,'0'],[21,'21'],[21.3636,'21.36'],[-1.239,'-1.24'],[NaN,'Unknown'],[undefined,'Unknown'],['21','Unknown'],[null,'Unknown']])assert.equal(nfl(v),want);
assert(js.includes('Dynasty Calendar')&&js.includes('Pick Odds'),'core renderer missing: Dynasty Calendar / Pick Odds (playoff-odds section removed per owner direction 2026-10-31; markers are current surviving League-tab + Draft-tab renderers)');
console.log(JSON.stringify({result:'PASS',entryAssets:assets,aiRows:rows,checks:['local JS/CSS exists','AI schema/unique rows/valid report times','actual compiled whole/2dp formatter','actual compiled nflNumber formatter','core renderer markers present'],limits:['no vendor calls','old report is not an outage','not full-site calculation/source coverage','not File host parity or visual test']}));
