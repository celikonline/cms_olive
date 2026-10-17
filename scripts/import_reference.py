"""Import public reference content; run explicitly to refresh seed, never live data."""
import concurrent.futures as cf
import hashlib
import json
import re
import urllib.request
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'public' / 'assets'
ASSETS.mkdir(parents=True, exist_ok=True)
CATEGORIES = [('zeytin','Zeytin'),('zeytinyagi','Zeytinyağı'),('tursu','Turşu'),('dogal-urun','Doğal Ürün'),('bitki-cayi','Bitki Çayı'),('sabun','Sabun'),('tohum','Tohum'),('sebze','Sebze'),('baklagil','Baklagil'),('sirke','Sirke'),('baharat','Baharat'),('kuru-meyve','Kuru Meyve')]

def fetch(path):
    try:
        req=urllib.request.Request('https://altingida45.com'+path,headers={'User-Agent':'Mozilla/5.0'})
        s=urllib.request.urlopen(req,timeout=30).read().decode()
        match=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',s)
        return json.loads(match[1])['props']['pageProps'] if match else {}
    except Exception as e:
        print('Fetch failed',path,type(e).__name__); return {}

def objects(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from objects(v)
    elif isinstance(x,list):
        for v in x: yield from objects(v)

def text(s):
    s=re.sub(r'<(style|script)\b[^>]*>.*?</\1>','',s or '',flags=re.S|re.I)
    s=re.sub(r'</(?:p|h[1-6]|li|div)>|<br\s*/?>','\n\n',s,flags=re.I)
    return re.sub(r'\n\s*\n(?:\s*\n)+','\n\n',unescape(re.sub('<[^>]+>','',s))).strip()
home=json.loads((ROOT/'reference-data.json').read_text(encoding='utf-8'))['props']['pageProps']
paths=['/'+slug for slug,_ in CATEGORIES]+['/pages/'+s for s in ['hakkimizda','sss','mesafeli-satis-sozlesmesi','iptal-ve-iade-politikasi','gizlilik-sozlesmesi','iletisim']]
with cf.ThreadPoolExecutor(max_workers=5) as pool: fetched=list(pool.map(fetch,paths))
products={}; blogs={}; pages={}; urls={}
def asset(url):
    if not url: return ''
    url=url.replace('image_3840','image_1080').replace('/3840/','/1080/')
    name=hashlib.sha256(url.encode()).hexdigest()[:18]+'.webp'
    urls[url]=name
    return '/assets/'+name

for data_index,data in enumerate([home]+fetched):
    for obj in objects(data.get('propValues',[])+[data.get('pageSpecificData')]):
        if 'variants' in obj and 'metaData' in obj and obj.get('name') and obj.get('variants'):
            slug=obj['metaData'].get('slug'); variants=[]
            for v in obj['variants']:
                price=(v.get('prices') or [{}])[0]
                imgs=v.get('images') or []
                im=next((i for i in imgs if i.get('isMain')),imgs[0] if imgs else {})
                url='https://cdn.myikas.com/images/202b9198-4bb7-47f7-a073-05131fa660dc/'+im.get('imageId','')+'/'
                url+=('1080/'+im['fileName']+'.webp') if im.get('fileName') else 'image_1080.webp'
                variants.append({'id':v['id'],'name':' / '.join(a.get('name','') for a in v.get('variantValues',[])) or 'Standart','price':price.get('discountPrice') or price.get('sellPrice') or 0,'original_price':price.get('sellPrice') or 0,'stock':int(v.get('stock',sum(s.get('stockCount',0) for s in v.get('stocks',[]))) or 0),'image':asset(url)})
            cats=[c['slug'] for c in obj.get('categories',[])]
            if 1<=data_index<=len(CATEGORIES): cats.append(CATEGORIES[data_index-1][0])
            cats=list(dict.fromkeys(products.get(slug,{}).get('categories',[])+cats))
            products[slug]={'id':obj['id'],'slug':slug,'name':obj['name'],'description':text(obj.get('description') or obj['metaData'].get('description')),'categories':cats,'image':variants[0]['image'],'price':variants[0]['price'],'stock':sum(v['stock'] for v in variants),'variants':variants,'active':True}
        if 'title' in obj and isinstance(obj.get('title'),str) and ('content' in obj or 'body' in obj) and ('slug' in obj or 'metaData' in obj):
            meta=obj.get('metaData') or {}; slug=obj.get('slug') or meta.get('slug')
            if slug:
                record={'id':str(obj.get('id') or slug),'slug':slug,'title':obj['title'],'body':text(obj.get('content') or obj.get('body')),'image':'','active':True}
                (blogs if 'blog' in str(obj.keys()).lower() or 'blogCategory' in obj else pages)[slug]=record

slides=[]
for entry in home['propValues']:
    pv=entry['propValues']
    if pv.get('sliders'):
        for s in pv['sliders']['value']:
            v=s['value']; slides.append({'title':v['title']['value'],'subtitle':v['subtitle']['value'],'image':asset('https://cdn.myikas.com/images/'+v['image']['value']['id']+'/image_1080.webp')})

# Static page data is held under pageSpecificData in the source storefront.
for path,data in zip(paths,fetched):
    if not path.startswith('/pages/'): continue
    spec=data.get('propValues') or []
    for ob in objects(spec):
        body=ob.get('content') or ob.get('body') or ob.get('description')
        if isinstance(body,str) and len(body)>100:
            slug=path.split('/')[-1]
            if 'customDataId' in ob: continue
            titles={'hakkimizda':'Hakkımızda','sss':'Sıkça Sorulan Sorular','mesafeli-satis-sozlesmesi':'Mesafeli Satış Sözleşmesi','iptal-ve-iade-politikasi':'İptal ve İade Politikası','gizlilik-sozlesmesi':'Gizlilik Politikası','iletisim':'İletişim'}
            pages[slug]={'id':slug,'slug':slug,'title':titles[slug],'body':text(body),'image':'','active':True}; break

summary=json.loads((ROOT/'reference-summary.json').read_text(encoding='utf-8'))
blog_links=list(dict.fromkeys(l for l in summary['links'] if l and l.startswith('/blog/')))
with cf.ThreadPoolExecutor(max_workers=5) as pool: blog_data=list(pool.map(fetch,blog_links))
for path,data in zip(blog_links,blog_data):
    for ob in objects(data.get('pageSpecificData') or {}):
        body=ob.get('content') or ob.get('description')
        if isinstance(body,str) and len(body)>150:
            slug=path.split('/')[-1]; title=ob.get('title') or ob.get('name') or data.get('pageTitle') or slug
            image=next((i['src'] for i in summary['images'] if i.get('alt')==title and i.get('src','').startswith('https://cdn')),'')
            blogs[slug]={'id':slug,'slug':slug,'title':title,'body':text(body),'image':asset(image),'active':True}; break

theme_imgs=list(dict.fromkeys(i['src'] for i in summary['images'] if i.get('src','').startswith('https://cdn') and i.get('alt')=='Image'))
category_images=[asset(u) for u in theme_imgs[4:7]]
logo=asset('https://cdn.myikas.com/images/theme-images/e9631d37-bcbd-4a70-8dde-5bf006c67dfe/image_180.webp')
def download(item):
    url,name=item; dest=ASSETS/name
    if dest.exists(): return
    try: dest.write_bytes(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read())
    except Exception as e: print('Asset failed',url,type(e).__name__)
with cf.ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(download,urls.items()))
tile_images={'bitki-cayi':category_images[0],'zeytin':category_images[1],'zeytinyagi':category_images[2]}
seed={'products':list(products.values()),'categories':[{'id':s,'slug':s,'name':n,'image':tile_images.get(s,'')} for s,n in CATEGORIES],'posts':list(blogs.values()),'pages':list(pages.values()),'settings':{'brand':'Altın Gıda','announcement':'🚚 350 TL ÜZERİ KARGO BEDAVA! | ALTI 59,99 TL','phone':'0545 503 73 78','email':'','address':'Tevfikiye mahallesi 53 Yeni Sokak 268 No, Kırkağaç / Manisa','shipping_threshold':350,'shipping_fee':59.99,'logo':logo,'slides':slides,'about':'Dedem çiftçiydi, babam üreticiydi… ben bilgisayar mühendisi oldum ama toprağı hiç bırakmadım. Onlardan aldığım emeği, dürüst üretim anlayışını ve toprağa olan saygıyı bugünün bakış açısıyla devam ettiriyorum.','founder':'İbrahim Gündüz'}}
(ROOT/'backend'/'seed.json').write_text(json.dumps(seed,ensure_ascii=False,indent=2),encoding='utf-8')
print('Imported',len(products),'products,',len(blogs),'posts,',len(pages),'pages,',len(urls),'assets')
