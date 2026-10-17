"""Integration tests use an isolated temporary SQLite database, never live records."""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

tmp=tempfile.TemporaryDirectory()
os.environ['DATA_DIR']=tmp.name
os.environ['ADMIN_PASSWORD']='integration-test-password'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import app as server
server.initialize()

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.client=server.app.test_client()
        self.token=self.client.get('/api/session').json['csrf']

    def post(self,url,data): return self.client.post(url,json=data,headers={'X-CSRF-Token':self.token})
    def put(self,url,data): return self.client.put(url,json=data,headers={'X-CSRF-Token':self.token})
    def login(self):
        r=self.post('/api/login',{'username':'admin','password':'integration-test-password'})
        self.assertEqual(r.status_code,200);self.token=r.json['csrf']

    def test_access_and_csrf(self):
        self.assertEqual(self.client.get('/api/admin/data').status_code,401)
        self.assertEqual(self.client.post('/api/login',json={}).status_code,403)
        self.assertEqual(self.post('/api/login',{'username':'admin','password':'wrong'}).status_code,401)
        self.login();self.assertEqual(self.client.get('/api/admin/data').status_code,200)

    def test_import_assets_categories_and_content(self):
        data=self.client.get('/api/store').json
        self.assertGreaterEqual(len(data['products']),100)
        self.assertEqual(len(data['categories']),12)
        self.assertGreaterEqual(len(data['pages']),5)
        self.assertGreaterEqual(len(data['posts']),20)
        for p in data['products']:
            self.assertTrue(p['categories'],p['name'])
            self.assertTrue((server.ROOT/'public'/p['image'].lstrip('/')).is_file(),p['image'])
            self.assertTrue(all(v['name'] for v in p['variants']))
        self.assertTrue(all('.ikas-editor' not in p['body'] for p in data['posts']))

    def test_order_atomic_stock_and_cancel(self):
        self.login()
        item={'name':'Test Order Product','slug':'test-order-product','price':100,'stock':3,'categories':['zeytin'],'variants':[{'id':'test-stock','name':'1 KG','price':100,'stock':3,'image':''}],'active':True}
        p=self.post('/api/admin/products',item).json
        payload={'customer':{'name':'Integration Test','phone':'05550000000','address':'Test address','city':'Manisa'},'items':[{'id':p['id'],'variant_id':'test-stock','quantity':2,'price':1}]}
        r=self.post('/api/orders',payload);self.assertEqual(r.status_code,201)
        self.assertEqual(r.json['total'],259.99) # Server ignores client price.
        oid=r.json['id']
        self.assertEqual(self.post('/api/orders',payload).status_code,400) # Oversell is rejected.
        product=next(x for x in self.client.get('/api/store').json['products'] if x['id']==p['id'])
        self.assertEqual(product['stock'],1)
        self.assertEqual(self.put('/api/admin/orders/'+oid,{'status':'Tamamlandı'}).status_code,400)
        self.assertEqual(self.put('/api/admin/orders/'+oid,{'status':'İptal'}).status_code,200)
        self.assertEqual(self.put('/api/admin/orders/'+oid,{'status':'İptal'}).status_code,400)
        product=next(x for x in self.client.get('/api/store').json['products'] if x['id']==p['id'])
        self.assertEqual(product['stock'],3)
        web=next(x for x in self.client.get('/api/admin/data').json['customers'] if x['phone']=='05550000000')
        self.assertEqual(web['source'],'Web')
        self.assertEqual(web['last_order_at'],server.today())
        self.assertTrue(any(o['id']==oid for o in web['orders']))
        self.assertEqual(web['next_reminder_at'],server.add_months(web['last_order_at'],12))

    def test_customer_renewal_notes_and_voice(self):
        self.login()
        c=self.post('/api/admin/customers',{'name':'Kapı Müşterisi','phone':'0544 111 22 33','address':'Test sokak 1',
            'city':'Kırkağaç / Manisa','note':'Özgür’ün arkadaşı','salesperson':'Müfit','location':{'lat':39.1,'lng':27.2,'accuracy':12}}).json
        self.assertEqual(c['cycle_months'],12)
        self.assertEqual(c['reminder_lead_days'],30)
        self.assertIsNone(c['next_reminder_at'])
        self.assertEqual(c['location']['lat'],39.1)
        self.assertEqual(self.post('/api/admin/customers',{'name':'Kopya','phone':'05441112233'}).status_code,400)
        self.assertEqual(self.post('/api/admin/customers',{'name':'X'}).status_code,400)
        self.assertEqual(self.post('/api/admin/customers',{'name':'Konum','location':{'lat':200,'lng':10}}).status_code,400)
        r=self.post('/api/admin/customers/%s/order'%c['id'],{'at':'2026-10-17','total':750,'items':'2 × Zeytinyağı 5 L'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['last_order_at'],'2026-10-17')
        self.assertEqual(r.json['next_reminder_at'],'2027-10-17')
        self.assertEqual(r.json['orders'][0]['total'],750)
        self.assertEqual(self.post('/api/admin/customers/%s/order'%c['id'],{'at':'17.10.2026'}).status_code,400)
        note=self.post('/api/admin/customers/%s/notes'%c['id'],{'text':'Abisi; her yıl 5 litrelik ister.','source':'voice'})
        self.assertEqual(note.status_code,200)
        self.assertEqual(note.json['notes'][0]['source'],'voice')
        self.assertEqual(note.json['notes'][0]['author'],'Müfit')
        self.assertEqual(self.post('/api/admin/customers/%s/notes'%c['id'],{'text':'','audio':''}).status_code,400)
        self.assertEqual(self.post('/api/admin/customers/%s/notes'%c['id'],{'audio':'/media/x.webm'}).status_code,400)
        nid=note.json['notes'][0]['id']
        self.assertEqual(self.put('/api/admin/customers/%s/notes/%s'%(c['id'],nid),{'text':'Düzeltilmiş not'}).json['notes'][0]['text'],'Düzeltilmiş not')
        uploaded=self.client.post('/api/admin/upload',data={'file':(io.BytesIO(b'\x1aE\xdf\xa3'+b'0'*400),'not.webm')},headers={'X-CSRF-Token':self.token})
        self.assertEqual(uploaded.status_code,200)
        self.assertTrue(uploaded.json['url'].startswith('/api/admin/voice/'))
        self.assertEqual(self.client.get(uploaded.json['url']).status_code,200)
        self.assertEqual(self.client.get(uploaded.json['url']).headers['Cache-Control'],'no-store')
        self.assertTrue(any(x['id']==c['id'] and len(x['notes'])==1 for x in self.client.get('/api/admin/data').json['customers']))
        self.assertEqual(self.post('/api/admin/customers',{'name':'Varsayılanlar','cycle_months':24}).json['cycle_months'],24)
        self.assertEqual(self.client.delete('/api/admin/customers/'+c['id'],headers={'X-CSRF-Token':self.token}).status_code,200)
        archived=next(x for x in self.client.get('/api/admin/data').json['customers'] if x['id']==c['id'])
        self.assertFalse(archived['active'])
        self.assertTrue(archived['archived'])
        self.assertEqual(self.client.get('/api/admin/data').status_code,200)

    def test_crud_validation_and_soft_archive(self):
        self.login()
        p=self.post('/api/admin/pages',{'title':'Test Page','slug':'test-page','body':'Test content','active':True}).json
        self.assertIn('id',p)
        self.assertEqual(self.post('/api/admin/pages',{'title':'Duplicate','slug':'test-page'}).status_code,400)
        self.assertEqual(self.client.delete('/api/admin/pages/'+p['id'],headers={'X-CSRF-Token':self.token}).status_code,200)
        self.assertFalse(any(x['id']==p['id'] for x in self.client.get('/api/store').json['pages']))
        p['active']=True
        self.assertEqual(self.put('/api/admin/pages/'+p['id'],p).status_code,200)
        self.assertTrue(any(x['id']==p['id'] for x in self.client.get('/api/store').json['pages']))
        self.assertEqual(self.post('/api/admin/products',{'name':'Invalid','slug':'invalid','price':-1}).status_code,400)

    def test_contact_newsletter_and_upload_validation(self):
        self.assertEqual(self.post('/api/subscribe',{'email':'invalid'}).status_code,400)
        self.assertEqual(self.post('/api/subscribe',{'email':'test@example.com'}).status_code,200)
        self.assertEqual(self.post('/api/subscribe',{'email':'test@example.com'}).status_code,200)
        self.assertEqual(self.post('/api/contact',{'name':'Test','email':'test@example.com','message':'Hello'}).status_code,201)
        self.login()
        r=self.client.post('/api/admin/upload',data={'file':(io.BytesIO(b'<script>alert(1)</script>'),'x.png')},headers={'X-CSRF-Token':self.token})
        self.assertEqual(r.status_code,400)
        self.assertEqual(len(self.client.get('/api/admin/data').json['subscribers']),1)

if __name__=='__main__': unittest.main(verbosity=2)
