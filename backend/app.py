import calendar
import json
import math
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import timedelta
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
INSTANCE = Path(os.environ.get('DATA_DIR', Path(__file__).parent / 'instance'))
INSTANCE.mkdir(parents=True, exist_ok=True)
secret_file = INSTANCE / 'session-secret'
if not secret_file.exists(): secret_file.write_text(secrets.token_hex(32))
app = Flask(__name__, static_folder=None)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secret_file.read_text(), MAX_CONTENT_LENGTH=6*1024*1024,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                  SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE')=='1', PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
DB = INSTANCE / 'store.sqlite3'
KINDS = {'products','categories','posts','pages','messages','subscribers','customers'}
SETTING_DEFAULTS = {'field_salespeople':['Müfit'],'renewal_months':12,'reminder_lead_days':30}
VOICE_DIR = INSTANCE / 'voice'
attempts = {}

@contextmanager
def db():
    conn=sqlite3.connect(DB,timeout=15); conn.row_factory=sqlite3.Row
    try:
        with conn: yield conn
    finally: conn.close()

def initialize():
    with db() as con:
        con.executescript('''CREATE TABLE IF NOT EXISTS records(kind TEXT,id TEXT,payload TEXT NOT NULL,PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY,password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
        if not con.execute("SELECT 1 FROM meta WHERE key='initialized'").fetchone():
            seed=json.loads((Path(__file__).parent/'seed.json').read_text(encoding='utf-8'))
            for kind in ['products','categories','posts','pages']:
                for item in seed[kind]: con.execute('INSERT OR IGNORE INTO records VALUES(?,?,?)',(kind,item['id'],json.dumps(item,ensure_ascii=False)))
            con.execute('INSERT INTO meta VALUES(?,?)',('settings',json.dumps(seed['settings'],ensure_ascii=False)))
            con.execute('INSERT INTO meta VALUES(?,?)',('initialized','1'))
        if not con.execute('SELECT 1 FROM users').fetchone():
            password=os.environ.get('ADMIN_PASSWORD') or secrets.token_urlsafe(15)
            con.execute('INSERT INTO users VALUES(?,?)',('admin',generate_password_hash(password)))
            if not os.environ.get('ADMIN_PASSWORD'):
                target=Path(os.environ.get('ADMIN_FILE',ROOT/'.local'/'admin.txt'))
                try:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_text('Kullanıcı: admin\nŞifre: '+password+'\n',encoding='utf-8')
                    print('Yönetici şifresi: %s'%target,flush=True)
                except OSError:
                    print('UYARI: şifre dosyası yazılamadı (%s). ADMIN_PASSWORD ortam değişkenini kullanın.'%target,flush=True)

def records(kind,con=None):
    if con is not None: return [json.loads(r['payload']) for r in con.execute('SELECT payload FROM records WHERE kind=? ORDER BY rowid',(kind,))]
    with db() as c: return records(kind,c)

def settings(con=None):
    if con is not None: return {**SETTING_DEFAULTS,**json.loads(con.execute("SELECT value FROM meta WHERE key='settings'").fetchone()[0])}
    with db() as c: return settings(c)

def now_iso(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def today(): return time.strftime('%Y-%m-%d',time.localtime())
def add_months(value,months):
    """Ay ekleyerek yenileme tarihi üretir; ayın son günü taşması düzeltilir."""
    try: year,month,day=(int(part) for part in str(value).split('-')[:3])
    except (TypeError,ValueError): return None
    index=year*12+month-1+int(months); year,month=divmod(index,12); month+=1
    return f'{year:04d}-{month:02d}-{min(day,calendar.monthrange(year,month)[1]):02d}'
def norm_phone(value):
    """Telefonu karşılaştırmak için sadeleştirir: 0/90 öneki ve işaretler kaldırılır."""
    digits=re.sub(r'\D','',str(value or ''))
    if len(digits)==12 and digits.startswith('90'): digits=digits[2:]
    if len(digits)==11 and digits.startswith('0'): digits=digits[1:]
    return digits
def clean_date(value):
    text=str(value or '').strip()
    if not text: return None
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',text): raise ValueError('Tarih YYYY-AA-GG biçiminde olmalı.')
    return text
def renewal_date(last_order_at,months): return add_months(last_order_at,months) if last_order_at else None

def save(con,kind,item):
    con.execute('INSERT INTO records VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload',(kind,item['id'],json.dumps(item,ensure_ascii=False)))

def admin(fn):
    @wraps(fn)
    def wrapped(*a,**kw):
        if not session.get('admin'): return jsonify(error='Yönetici girişi gerekli.'),401
        return fn(*a,**kw)
    return wrapped

@app.before_request
def protect():
    if request.path.startswith('/api/') and request.method not in ['GET','HEAD','OPTIONS']:
        if not session.get('csrf') or not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session['csrf']):
            return jsonify(error='Oturum doğrulanamadı. Sayfayı yenileyin.'),403

@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='SAMEORIGIN'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    if request.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
    return response

@app.errorhandler(413)
def too_large(e): return jsonify(error='Dosya en fazla 5 MB olabilir.'),413

@app.errorhandler(400)
def bad_request(e): return jsonify(error='Geçersiz istek.'),400

@app.get('/api/session')
def get_session():
    if 'csrf' not in session: session['csrf']=secrets.token_hex(24)
    return jsonify(authenticated=bool(session.get('admin')),csrf=session['csrf'])

@app.post('/api/login')
def login():
    ip=request.remote_addr; now=time.time(); recent=[t for t in attempts.get(ip,[]) if now-t<300]
    if len(recent)>=8: return jsonify(error='Çok fazla deneme. 5 dakika sonra tekrar deneyin.'),429
    data=request.get_json() or {}
    with db() as c: user=c.execute('SELECT * FROM users WHERE username=?',(data.get('username',''),)).fetchone()
    if not user or not check_password_hash(user['password'],data.get('password','')):
        attempts[ip]=recent+[now]; return jsonify(error='Kullanıcı adı veya şifre yanlış.'),401
    attempts.pop(ip,None); session.clear(); session['admin']=user['username']; session['csrf']=secrets.token_hex(24); session.permanent=True
    return jsonify(authenticated=True,csrf=session['csrf'])

@app.post('/api/logout')
def logout():
    session.clear(); return jsonify(ok=True)

@app.get('/api/store')
def store():
    return jsonify(settings=settings(),**{k:[r for r in records(k) if r.get('active',True)] for k in ['products','categories','posts','pages']})

@app.get('/api/admin/data')
@admin
def admin_data():
    with db() as c: orders=[json.loads(r[0]) for r in c.execute('SELECT payload FROM orders ORDER BY rowid DESC')]
    return jsonify(settings=settings(),orders=orders,**{k:records(k) for k in KINDS})

def number(v):
    n=float(v)
    if not math.isfinite(n) or n<0: raise ValueError('Negatif veya geçersiz sayı.')
    return n

def clean_item(kind,data):
    if kind in {'messages','subscribers'}: raise ValueError('Bu kayıt türü düzenlenemez.')
    data={k:v for k,v in data.items() if k in {'id','name','title','slug','description','body','price','stock','image','categories','variants','active'}}
    if not str(data.get('name') or data.get('title') or '').strip(): raise ValueError('Ad / başlık zorunlu.')
    if not re.fullmatch(r'[a-z0-9-]+',data.get('slug','')): raise ValueError('Bağlantı yalnızca küçük harf, rakam ve tire içerebilir.')
    data['active']=bool(data.get('active',True))
    image=data.get('image','')
    if image and not (image.startswith('/assets/') or image.startswith('/media/') or image.startswith('https://')): raise ValueError('Geçersiz görsel adresi.')
    if kind=='products':
        data['price']=number(data.get('price',0)); data['stock']=int(number(data.get('stock',0)))
        vs=data.get('variants') or [{'id':str(uuid.uuid4()),'name':'Standart','price':data['price'],'stock':data['stock'],'image':image}]
        for v in vs:
            v['price']=number(v.get('price',0)); v['stock']=int(number(v.get('stock',0))); v['id']=str(v.get('id') or uuid.uuid4())
        if len({v['id'] for v in vs})!=len(vs): raise ValueError('Varyant kimlikleri benzersiz olmalı.')
        data['variants']=vs; data['price']=vs[0]['price']; data['stock']=sum(v['stock'] for v in vs)
        data['categories']=data.get('categories') or []
    return data

@app.route('/api/admin/<kind>',methods=['POST'])
@app.route('/api/admin/<kind>/<item_id>',methods=['PUT','DELETE'])
@admin
def mutate(kind,item_id=None):
    if kind not in KINDS: return jsonify(error='Kayıt türü bulunamadı.'),404
    if kind=='customers': return mutate_customer(item_id)
    with db() as c:
        old=c.execute('SELECT payload FROM records WHERE kind=? AND id=?',(kind,item_id)).fetchone() if item_id else None
        if item_id and not old: return jsonify(error='Kayıt bulunamadı.'),404
        if request.method=='DELETE':
            item=json.loads(old[0]); item['active']=False; item['archived']=True; save(c,kind,item)
            return jsonify(ok=True)
        try:
            item=clean_item(kind,request.get_json() or {}); item['id']=item_id or str(uuid.uuid4())
            if any(r.get('slug')==item['slug'] and r['id']!=item['id'] for r in records(kind,c)): raise ValueError('Bu bağlantı zaten kullanılıyor.')
            if kind in {'products','categories'}:
                if item['slug'] in {'admin','urunler','sepet','siparis','pages','blog','api','media','assets'}: raise ValueError('Bu bağlantı sistem tarafından kullanılıyor.')
                other='categories' if kind=='products' else 'products'
                if any(r.get('slug')==item['slug'] for r in records(other,c)): raise ValueError('Bu bağlantı başka bir ürün veya kategori tarafından kullanılıyor.')
        except (ValueError,TypeError,KeyError) as e: return jsonify(error=str(e)),400
        if kind=='categories' and old:
            old_slug=json.loads(old[0])['slug']
            if old_slug!=item['slug']:
                for product in records('products',c):
                    product['categories']=[item['slug'] if s==old_slug else s for s in product['categories']]
                    save(c,'products',product)
        save(c,kind,item)
    return jsonify(item)

def location_value(raw):
    """Kapı teslimi konumunu doğrular: enlem/boylam aralıkları ve doğruluk."""
    if not raw: return None
    if not isinstance(raw,dict): raise ValueError('Konum bilgisi geçersiz.')
    try: lat,lon=float(raw.get('lat')),float(raw.get('lng'))
    except (TypeError,ValueError): raise ValueError('Konum koordinatları geçersiz.')
    if not (-90<=lat<=90 and -180<=lon<=180): raise ValueError('Konum koordinatları aralık dışında.')
    try: accuracy=int(float(raw.get('accuracy') or 0))
    except (TypeError,ValueError): accuracy=0
    return {'lat':round(lat,6),'lng':round(lon,6),'accuracy':max(0,min(accuracy,10000)),'at':str(raw.get('at') or now_iso())[:40]}

def order_entry(raw):
    if not isinstance(raw,dict): raise ValueError('Sipariş kaydı geçersiz.')
    at=clean_date(raw.get('at')) or today()
    try: total=float(raw.get('total') or 0)
    except (TypeError,ValueError): raise ValueError('Sipariş tutarı geçersiz.')
    if not math.isfinite(total) or total<0: raise ValueError('Sipariş tutarı geçersiz.')
    return {'id':str(raw.get('id') or uuid.uuid4()),'at':at,'total':round(total,2),
            'items':str(raw.get('items') or '')[:500],'note':str(raw.get('note') or '')[:500],
            'source':str(raw.get('source') or 'Saha')[:40]}

def note_entry(raw):
    if not isinstance(raw,dict): raise ValueError('Not kaydı geçersiz.')
    text=str(raw.get('text') or '').strip()[:2000]
    audio=str(raw.get('audio') or '').strip()[:300]
    if audio and not audio.startswith('/api/admin/voice/'): raise ValueError('Ses kaydı adresi geçersiz.')
    if not text and not audio: raise ValueError('Not metni boş olamaz.')
    source='voice' if raw.get('source')=='voice' else 'manual'
    return {'id':str(raw.get('id') or uuid.uuid4()),'text':text,'audio':audio,'source':source,
            'author':str(raw.get('author') or '')[:80],'at':str(raw.get('at') or now_iso())[:40]}

def clean_customer(data,existing=None):
    """Saha müşterisini doğrular; yenileme tarihi son siparişten otomatik hesaplanır."""
    if not isinstance(data,dict): raise ValueError('Müşteri bilgisi geçersiz.')
    old=existing or {}
    def text(key,limit):
        value=str(data.get(key,old.get(key,'')) or '').strip()
        if len(value)>limit: raise ValueError('Bu alan en fazla %d karakter olabilir.'%limit)
        return value
    item={k:old.get(k) for k in ['id','created_at','archived'] if old.get(k) is not None}
    item['name']=text('name',120)
    if len(item['name'])<2: raise ValueError('Müşteri adı zorunlu.')
    item['phone']=text('phone',25)
    if item['phone'] and not re.fullmatch(r'[+\d\s()\-]{10,25}',item['phone']): raise ValueError('Geçerli bir telefon numarası girin.')
    item['address']=text('address',400); item['city']=text('city',120); item['note']=text('note',2000)
    item['salesperson']=text('salesperson',80) or next(iter(settings()['field_salespeople'] or ['Saha']),'Saha')
    item['source']=text('source',40) or 'Saha'
    item['location']=location_value(data.get('location',old.get('location')))
    if 'cycle_months' in data or not old:
        try: item['cycle_months']=int(float(data.get('cycle_months',old.get('cycle_months') or settings()['renewal_months'])))
        except (TypeError,ValueError): raise ValueError('Yenileme periyodu geçersiz.')
        if not 1<=item['cycle_months']<=60: raise ValueError('Yenileme periyodu 1-60 ay arasında olmalı.')
    if 'reminder_lead_days' in data or not old:
        try: item['reminder_lead_days']=int(float(data.get('reminder_lead_days',old.get('reminder_lead_days') or settings()['reminder_lead_days'])))
        except (TypeError,ValueError): raise ValueError('Hatırlatma aralığı geçersiz.')
        if not 0<=item['reminder_lead_days']<=365: raise ValueError('Hatırlatma aralığı 0-365 gün arasında olmalı.')
    item['last_order_at']=clean_date(data.get('last_order_at',old.get('last_order_at')))
    item['next_reminder_at']=clean_date(data.get('next_reminder_at',old.get('next_reminder_at'))) or renewal_date(item['last_order_at'],item['cycle_months'])
    if 'orders' in data or not old:
        orders=data.get('orders',old.get('orders') or [])
        if not isinstance(orders,list) or len(orders)>500: raise ValueError('Sipariş geçmişi geçersiz.')
        item['orders']=[order_entry(o) for o in orders]
    if 'notes' in data or not old:
        notes=data.get('notes',old.get('notes') or [])
        if not isinstance(notes,list) or len(notes)>500: raise ValueError('Not listesi geçersiz.')
        item['notes']=[note_entry(n) for n in notes]
    item['active']=bool(data.get('active',old.get('active',True)))
    item['updated_at']=now_iso(); item.setdefault('created_at',now_iso())
    return item

def load_customer(con,item_id):
    row=con.execute('SELECT payload FROM records WHERE kind=? AND id=?',('customers',item_id)).fetchone()
    return json.loads(row[0]) if row else None

def mutate_customer(item_id=None):
    with db() as c:
        old=load_customer(c,item_id) if item_id else None
        if item_id and not old: return jsonify(error='Müşteri bulunamadı.'),404
        if request.method=='DELETE':
            old['active']=False; old['archived']=True; old['updated_at']=now_iso(); save(c,'customers',old)
            return jsonify(ok=True)
        try:
            item=clean_customer(request.get_json() or {},old); item['id']=item_id or str(uuid.uuid4())
            if item['phone'] and any(r.get('phone') and r['id']!=item['id'] and norm_phone(r['phone'])==norm_phone(item['phone']) for r in records('customers',c)):
                raise ValueError('Bu telefon numarası başka bir müşteride kayıtlı.')
        except (ValueError,TypeError,KeyError,AttributeError) as e: return jsonify(error=str(e)),400
        save(c,'customers',item)
    return jsonify(item)

@app.post('/api/admin/customers/<cid>/order')
@admin
def customer_order(cid):
    """Kapıda satış tamamlandı: sipariş kaydı eklenir ve bir sonraki hatırlatma kurulur."""
    data=request.get_json() or {}
    with db() as c:
        item=load_customer(c,cid)
        if not item: return jsonify(error='Müşteri bulunamadı.'),404
        try:
            entry=order_entry({'at':data.get('at') or today(),'total':data.get('total'),'items':data.get('items'),
                               'note':data.get('note'),'source':data.get('source') or 'Kapı teslimi'})
        except ValueError as e: return jsonify(error=str(e)),400
        item['orders']=item.get('orders',[])+[entry]
        item['last_order_at']=entry['at']
        item['next_reminder_at']=renewal_date(entry['at'],item.get('cycle_months') or settings()['renewal_months'])
        if data.get('location') is not None:
            try: item['location']=location_value(data.get('location'))
            except ValueError as e: return jsonify(error=str(e)),400
        item['updated_at']=now_iso(); save(c,'customers',item)
    return jsonify(item)

@app.route('/api/admin/customers/<cid>/notes',methods=['POST'])
@app.route('/api/admin/customers/<cid>/notes/<nid>',methods=['PUT','DELETE'])
@admin
def customer_notes(cid,nid=None):
    """Konuşmadan çevrilen notlar dâhil müşteri hatırlatma notlarını yönetir."""
    with db() as c:
        item=load_customer(c,cid)
        if not item: return jsonify(error='Müşteri bulunamadı.'),404
        notes=item.get('notes',[])
        if request.method=='DELETE':
            if not any(n['id']==nid for n in notes): return jsonify(error='Not bulunamadı.'),404
            item['notes']=[n for n in notes if n['id']!=nid]
        elif request.method=='PUT':
            index=next((i for i,n in enumerate(notes) if n['id']==nid),None)
            if index is None: return jsonify(error='Not bulunamadı.'),404
            try: notes[index]={**note_entry({**notes[index],**(request.get_json() or {})}),'id':nid}
            except ValueError as e: return jsonify(error=str(e)),400
            item['notes']=notes
        else:
            try: item['notes']=notes+[note_entry({**(request.get_json() or {}),'author':(request.get_json() or {}).get('author') or item.get('salesperson') or 'Saha'})]
            except ValueError as e: return jsonify(error=str(e)),400
        item['updated_at']=now_iso(); save(c,'customers',item)
    return jsonify(item)

@app.get('/api/admin/voice/<path:name>')
@admin
def voice(name): return send_from_directory(VOICE_DIR,name)

def link_customer(con,customer,order):
    """Web siparişini telefondan eşleşen saha müşterisine bağlar; sipariş akışını asla bozmaz."""
    try:
        phone=norm_phone(customer.get('phone'))
        if not phone: return
        item=next((r for r in records('customers',con) if r.get('phone') and norm_phone(r['phone'])==phone),None)
        if item is None:
            item=clean_customer({'name':str(customer.get('name') or '')[:120] or 'Web müşterisi','phone':customer.get('phone'),
                                 'address':str(customer.get('address') or '')[:400],'city':str(customer.get('city') or '')[:120],
                                 'note':str(customer.get('note') or '')[:2000],'source':'Web'})
            item['id']=str(uuid.uuid4())
        at=order['created_at'][:10]
        item['orders']=item.get('orders',[])+[{'id':order['id'],'at':at,'total':order['total'],
            'items':' · '.join('%s × %s'%(l['quantity'],l['name']) for l in order['items'])[:500],
            'note':'Web sitesinden sipariş talebi','source':'Web'}]
        if not item.get('last_order_at'):
            item['last_order_at']=at; item['next_reminder_at']=renewal_date(at,item.get('cycle_months') or settings()['renewal_months'])
        if customer.get('location'):
            try: item['location']=location_value(customer['location'])
            except ValueError: pass
        item['updated_at']=now_iso(); save(con,'customers',item)
    except (ValueError,TypeError,KeyError): pass

@app.put('/api/admin/settings')
@admin
def update_settings():
    data=request.get_json() or {}; old=settings()
    for key in old:
        if key in data: old[key]=data[key]
    try:
        old['shipping_fee']=number(old['shipping_fee']); old['shipping_threshold']=number(old['shipping_threshold'])
        if not old['brand'].strip() or not isinstance(old['slides'],list) or not old['slides']: raise ValueError('Marka ve en az bir slayt gerekli.')
        for s in old['slides']:
            if not all(isinstance(s.get(k),str) for k in ['title','subtitle','image']): raise ValueError('Slayt alanları geçersiz.')
        people=old.get('field_salespeople')
        if not isinstance(people,list) or not 1<=len(people)<=20 or not all(isinstance(p,str) and p.strip() for p in people): raise ValueError('En az bir saha satış temsilcisi adı girin.')
        old['field_salespeople']=[p.strip()[:80] for p in people]
        old['renewal_months']=int(float(old.get('renewal_months') or 12)); old['reminder_lead_days']=int(float(old.get('reminder_lead_days') or 30))
        if not 1<=old['renewal_months']<=60 or not 0<=old['reminder_lead_days']<=365: raise ValueError('Yenileme periyodu 1-60 ay, hatırlatma aralığı 0-365 gün olmalı.')
    except (ValueError,TypeError,AttributeError) as e: return jsonify(error=str(e)),400
    with db() as c: c.execute("UPDATE meta SET value=? WHERE key='settings'",(json.dumps(old,ensure_ascii=False),))
    return jsonify(old)

def media_signature(content):
    """Yüklenen dosyanın gerçek türünü içeriğinden belirler."""
    if content.startswith(b'\x89PNG\r\n\x1a\n'): return 'image','png'
    if content.startswith(b'\xff\xd8\xff'): return 'image','jpg'
    if content[:4]==b'RIFF' and content[8:12]==b'WEBP': return 'image','webp'
    if content[:4]==b'\x1aE\xdf\xa3': return 'audio','webm'
    if content[:4]==b'OggS': return 'audio','ogg'
    if content[:4]==b'RIFF' and content[8:12]==b'WAVE': return 'audio','wav'
    if content[4:8]==b'ftyp': return 'audio','m4a' if content[8:12] in {b'M4A ',b'mp42',b'isom',b'mp41'} else 'mp4'
    if content[:3]==b'ID3' or content[:2]==b'\xff\xfb': return 'audio','mp3'
    return None,None

@app.post('/api/admin/upload')
@admin
def upload():
    f=request.files.get('file')
    if not f: return jsonify(error='Dosya seçin.'),400
    content=f.read()
    kind,ext=media_signature(content)
    if not kind or len(content)>5*1024*1024:
        return jsonify(error='En fazla 5 MB PNG, JPG, WebP görseli veya ses kaydı yükleyin.'),400
    folder=(VOICE_DIR if kind=='audio' else INSTANCE/'uploads'); folder.mkdir(parents=True,exist_ok=True)
    name=secrets.token_hex(16)+'.'+ext; (folder/name).write_bytes(content)
    return jsonify(url=('/api/admin/voice/' if kind=='audio' else '/media/')+name)

@app.get('/media/<path:name>')
def media(name): return send_from_directory(INSTANCE/'uploads',name)

@app.post('/api/orders')
def order():
    data=request.get_json() or {}; customer=data.get('customer') or {}; items=data.get('items') or []
    if not all(str(customer.get(k,'')).strip() for k in ['name','phone','address','city']): return jsonify(error='Ad, telefon, adres ve il zorunludur.'),400
    if not re.fullmatch(r'[+\d\s()-]{10,25}',customer['phone']): return jsonify(error='Geçerli bir telefon numarası girin.'),400
    if not isinstance(items,list) or not 1<=len(items)<=100: return jsonify(error='Sepet boş veya geçersiz.'),400
    with db() as c:
        c.execute('BEGIN IMMEDIATE'); catalog={p['id']:p for p in records('products',c)}; lines=[]; subtotal=0; quantities={}
        try:
            for i in items:
                q=i['quantity']
                if type(q) is not int or not 1<=q<=100: raise ValueError('Geçersiz adet.')
                key=(i['id'],i['variant_id']); quantities[key]=quantities.get(key,0)+q
            for (pid,vid),q in quantities.items():
                p=catalog.get(pid)
                if not p or not p.get('active',True): raise ValueError('Bir ürün artık satışta değil.')
                v=next((v for v in p['variants'] if v['id']==vid),None)
                if not v or v['stock']<q: raise ValueError(p['name']+': yeterli stok yok.')
                cents=round(v['price']*100); subtotal+=cents*q; v['stock']-=q; p['stock']=sum(v['stock'] for v in p['variants']); save(c,'products',p)
                lines.append({'id':pid,'variant_id':vid,'name':p['name'],'variant':v['name'],'quantity':q,'price':cents/100})
        except (ValueError,KeyError,TypeError) as e:
            c.rollback(); return jsonify(error=str(e)),400
        s=settings(c); shipping=0 if subtotal>=round(s['shipping_threshold']*100) else round(s['shipping_fee']*100)
        oid='AG-'+uuid.uuid4().hex[:10].upper()
        payload={'id':oid,'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'customer':{k:str(customer.get(k,''))[:1000] for k in ['name','phone','email','address','city','note']},'items':lines,'subtotal':subtotal/100,'shipping':shipping/100,'total':(subtotal+shipping)/100,'status':'Yeni','payment':'Ödeme alınmadı — sipariş talebi'}
        c.execute('INSERT INTO orders VALUES(?,?)',(oid,json.dumps(payload,ensure_ascii=False)))
        link_customer(c,customer,payload)
    return jsonify(id=oid,total=payload['total']),201

@app.put('/api/admin/orders/<oid>')
@admin
def update_order(oid):
    status=(request.get_json() or {}).get('status')
    with db() as c:
        c.execute('BEGIN IMMEDIATE'); r=c.execute('SELECT payload FROM orders WHERE id=?',(oid,)).fetchone()
        if not r: return jsonify(error='Sipariş bulunamadı.'),404
        order=json.loads(r[0]); allowed={'Yeni':['Hazırlanıyor','İptal'],'Hazırlanıyor':['Kargoda','İptal'],'Kargoda':['Tamamlandı'],'Tamamlandı':[],'İptal':[]}
        if status not in allowed[order['status']]: return jsonify(error='Bu durum değişikliği yapılamaz.'),400
        if status=='İptal':
            catalog={p['id']:p for p in records('products',c)}
            for line in order['items']:
                p=catalog.get(line['id'])
                if p:
                    v=next((v for v in p['variants'] if v['id']==line['variant_id']),None)
                    if v: v['stock']+=line['quantity']; p['stock']=sum(v['stock'] for v in p['variants']); save(c,'products',p)
        order['status']=status; c.execute('UPDATE orders SET payload=? WHERE id=?',(json.dumps(order,ensure_ascii=False),oid))
    return jsonify(order)

@app.post('/api/subscribe')
def subscribe():
    email=str((request.get_json() or {}).get('email','')).strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254: return jsonify(error='Geçerli bir e-posta adresi girin.'),400
    with db() as c: save(c,'subscribers',{'id':email,'email':email,'active':True})
    return jsonify(ok=True)

@app.post('/api/contact')
def contact():
    d=request.get_json() or {}
    if not all(str(d.get(k,'')).strip() for k in ['name','email','message']): return jsonify(error='Tüm alanları doldurun.'),400
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',str(d['email'])): return jsonify(error='Geçerli bir e-posta adresi girin.'),400
    item={'id':str(uuid.uuid4()),**{k:str(d[k])[:5000] for k in ['name','email','message']},'active':True}
    with db() as c: save(c,'messages',item)
    return jsonify(ok=True),201

@app.get('/api/health')
def health(): return jsonify(ok=True)

@app.route('/',defaults={'path':''})
@app.route('/<path:path>')
def frontend(path):
    if path.startswith('api/'): return jsonify(error='Adres bulunamadı.'),404
    dist=ROOT/'dist'
    if not dist.exists(): return 'Önce npm run build komutunu çalıştırın.',503
    if path and (dist/path).is_file(): return send_from_directory(dist,path)
    if path.startswith('assets/'): return '',404
    page='admin.html' if path=='admin' or path.startswith('admin/') else 'index.html'
    return send_from_directory(dist,page)

if __name__=='__main__':
    initialize()
    from waitress import serve
    host=os.environ.get('HOST','127.0.0.1'); port=int(os.environ.get('PORT',8000))
    shown='127.0.0.1' if host in ['0.0.0.0','::'] else host
    print('Mağaza: http://%s:%d | Yönetim: /admin'%(shown,port),flush=True)
    print('Veri klasörü: %s'%INSTANCE,flush=True)
    serve(app,host=host,port=port)
