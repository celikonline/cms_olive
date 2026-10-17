"""Enrich seed descriptions from public product detail pages; no database writes."""
import concurrent.futures as cf
import json,re,urllib.request
from html import unescape
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
seed=json.loads((ROOT/'backend/seed.json').read_text(encoding='utf-8'))
def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x:yield from walk(v)
def clean(s):
    s=re.sub(r'<(style|script)\b[^>]*>.*?</\1>','',s,flags=re.S|re.I)
    s=re.sub(r'</(?:p|h[1-6]|li|div)>|<br\s*/?>','\n\n',s,flags=re.I)
    return re.sub(r'\n\s*\n(?:\s*\n)+','\n\n',unescape(re.sub('<[^>]+>','',s))).strip()
def enrich(p):
    try:
        req=urllib.request.Request('https://altingida45.com/'+p['slug'],headers={'User-Agent':'Mozilla/5.0'})
        s=urllib.request.urlopen(req,timeout=25).read().decode()
        d=json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',s)[1])['props']['pageProps']
        for ob in walk(d.get('pageSpecificData') or d.get('propValues')):
            if ob.get('id')==p['id'] and isinstance(ob.get('description'),str):
                description=clean(ob['description'])
                if len(description)>len(p['description']): p['description']=description
    except Exception as e: print('Description unavailable',p['slug'],type(e).__name__)
    return p
with cf.ThreadPoolExecutor(max_workers=6) as pool: seed['products']=list(pool.map(enrich,seed['products']))
(ROOT/'backend/seed.json').write_text(json.dumps(seed,ensure_ascii=False,indent=2),encoding='utf-8')
print('Descriptions enriched:',sum(len(p['description'])>350 for p in seed['products']))
