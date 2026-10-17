from html.parser import HTMLParser
from pathlib import Path
import concurrent.futures as cf
import hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parents[1]
class Images(HTMLParser):
    def __init__(self): super().__init__(); self.href=None; self.images={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a': self.href=a.get('href')
        if tag=='img' and self.href and self.href.startswith('/blog/') and a.get('src','').startswith('https://cdn'):
            self.images[self.href.split('/')[-1]]=a['src'].replace('image_3840','image_1080')
    def handle_endtag(self,tag):
        if tag=='a': self.href=None
p=Images();p.feed((ROOT/'reference.html').read_text(encoding='utf-8'))
seed=json.loads((ROOT/'backend/seed.json').read_text(encoding='utf-8'))
def download(post):
    url=p.images.get(post['slug'])
    if url:
        name=hashlib.sha256(url.encode()).hexdigest()[:18]+'.webp'
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        try:
            (ROOT/'public/assets'/name).write_bytes(urllib.request.urlopen(req,timeout=25).read())
            post['image']='/assets/'+name
        except Exception as e:print(type(e).__name__,post['slug'])
    return post
with cf.ThreadPoolExecutor(max_workers=6) as pool: seed['posts']=list(pool.map(download,seed['posts']))
(ROOT/'backend/seed.json').write_text(json.dumps(seed,ensure_ascii=False,indent=2),encoding='utf-8')
print('Blog images:',sum(bool(p['image']) for p in seed['posts']))
