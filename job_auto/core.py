import datetime as dt
import html
import json
import re
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SKILLS = ['python', 'java', 'javascript', 'typescript', 'react', 'node', 'sql', 'mongodb', 'azure', 'docker', 'kubernetes', 'linux', 'playwright', 'ci/cd', 'flask', 'firebase', 'data', 'automation']

def db():
    DATA.mkdir(exist_ok=True)
    c = sqlite3.connect(DATA / 'jobs.sqlite3')
    c.row_factory = sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, title TEXT, company TEXT, location TEXT, url TEXT, description TEXT, published TEXT, first_seen TEXT, last_seen TEXT, score INTEGER, reasons TEXT, term TEXT, status TEXT DEFAULT 'new')''')
    return c

def classify(title, description):
    text = re.sub('<[^>]+>', ' ', html.unescape(title + ' ' + description)).lower()
    if not re.search(r'\b(intern(?:ship)?|co[ -]?op|cooperative)\b', title.lower()):
        return None
    # Require explicit evidence; a year somewhere in a description is insufficient.
    target = bool(re.search(r'(summer[\s,/-]*2027|2027[\s,/-]*summer|(?:may|june|july|august)\s+2027)', text))
    other = bool(re.search(r'(?:summer[\s,/-]*202[0-689]|202[0-689][\s,/-]*summer|(?:fall|winter|spring)[\s,/-]*2027)', title.lower()))
    if other and not target:
        return None
    hits = [s for s in SKILLS if re.search(r'(?<!\w)' + re.escape(s) + r'(?!\w)', text)]
    score = min(100, (45 if target else 10) + len(hits) * 4)
    return score, hits, 'confirmed' if target else 'unconfirmed'

def fetch(source):
    provider, company = source['provider'], source['company']
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', company):
        raise ValueError('Invalid company board identifier')
    if provider == 'greenhouse':
        url = f'https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true'
    elif provider == 'lever':
        url = f'https://api.lever.co/v0/postings/{company}?mode=json'
    else:
        raise ValueError('Unsupported provider')
    req = urllib.request.Request(url, headers={'User-Agent': 'JobAuto/0.1 (personal internship search)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    rows = data['jobs'] if provider == 'greenhouse' else data
    for j in rows:
        if provider == 'greenhouse':
            yield dict(id=f'{provider}:{company}:{j["id"]}', title=j['title'], company=company, location=j.get('location', {}).get('name', ''), url=j['absolute_url'], description=j.get('content', ''), published=j.get('first_published', ''))
        else:
            description = j.get('descriptionPlain', '') + ' ' + ' '.join(x.get('text', '') + ' ' + x.get('content', '') for x in j.get('lists', []))
            published = dt.datetime.fromtimestamp(j['createdAt']/1000, dt.timezone.utc).isoformat() if j.get('createdAt') else ''
            yield dict(id=f'{provider}:{company}:{j["id"]}', title=j['text'], company=company, location=j.get('categories', {}).get('location', ''), url=j['hostedUrl'], description=description, published=published)

def refresh():
    sources = json.loads((ROOT / 'sources.json').read_text())
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    result = {'matched': 0, 'errors': [], 'sources': len(sources)}
    with db() as c:
        for source in sources:
            try:
                for j in fetch(source):
                    match = classify(j['title'], j['description'])
                    if match is None:
                        continue
                    score, hits, term = match
                    c.execute('''INSERT INTO jobs(id,title,company,location,url,description,published,first_seen,last_seen,score,reasons,term) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,location=excluded.location,url=excluded.url,description=excluded.description,published=excluded.published,last_seen=excluded.last_seen,score=excluded.score,reasons=excluded.reasons,term=excluded.term''', (*[j[k] for k in ['id','title','company','location','url','description','published']], now, now, score, json.dumps(hits), term))
                    result['matched'] += 1
            except Exception as exc:
                result['errors'].append({'source': source, 'error': str(exc)})
    return result

def jobs():
    with db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM jobs ORDER BY score DESC,first_seen DESC')]
    for r in rows:
        r['reasons'] = json.loads(r['reasons'])
        r['country'] = country_for(r['location'])
        r['pay'] = pay_check(r['description'], r['country'])
        r['queue_eligible'] = r['term'] == 'confirmed' and r['country'] in ('Canada', 'US') and r['pay']['eligible']
        r.pop('description')
    return rows

def pay_check(text, country):
    text = html.unescape(re.sub('<[^>]+>', ' ', text))
    # Hourly amounts only; annual salary cannot establish an hourly floor.
    pattern = r'(?:(CAD|USD|CA\$|US\$|C\$)\s*)?\$?\s*(\d{2,3}(?:\.\d{1,2})?)\s*(?:[-–—]|to)?\s*\$?\s*(\d{2,3}(?:\.\d{1,2})?)?\s*(?:/\s*(?:hour|hr|h)\b|per\s+hour\b|an?\s+hour\b|hourly\b)'
    matches = list(re.finditer(pattern, text, re.I))
    expected = {'Canada': 'CAD', 'US': 'USD'}.get(country)
    amounts = []
    for m in matches:
        currency = {'CA$':'CAD','C$':'CAD','US$':'USD'}.get((m[1] or '').upper(), (m[1] or '').upper()) or expected
        if expected and currency == expected:
            amounts.append(float(m[2]))
    if not amounts:
        return {'eligible': False, 'floor': None, 'currency': expected, 'reason': 'Hourly pay unavailable or currency/country needs confirmation'}
    floor = min(amounts)
    return {'eligible': floor >= 25, 'floor': floor, 'currency': expected, 'reason': 'Hourly lower bound meets minimum' if floor >= 25 else 'Hourly lower bound below 25'}

def country_for(location):
    if re.search(r'\b(canada|toronto|vancouver|montreal|montréal|ottawa|waterloo|calgary|ontario|quebec)\b', location, re.I):
        return 'Canada'
    if re.search(r'\b(united states|usa|u\.s\.|new york|san francisco|seattle|boston|austin)\b', location, re.I):
        return 'US'
    return None
