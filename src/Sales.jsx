import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {AlertTriangle,Archive,CalendarClock,Check,ChevronLeft,ChevronRight,Mic,Navigation,Pencil,Phone,Plus,Save,Search,Square,Trash2,Users,X} from 'lucide-react';
import {api,money} from './api';
import {useStore} from './main';

/* ---------- tarih ve durum yardımcıları ---------- */
const DAY=86400000;
const MONTHS=['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'];
const WEEKDAYS=['Pzt','Sal','Çar','Per','Cum','Cmt','Paz'];
const RELATION_TAGS=['Abisi','Kardeşi','Arkadaşı','Akrabası','Komşusu','İş yeri','Her yıl alır'];
export const isoDate=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
export const parseDate=value=>{const m=/^(\d{4})-(\d{2})-(\d{2})/.exec(String(value||''));return m?new Date(+m[1],+m[2]-1,+m[3]):null};
const today=()=>{const n=new Date();return new Date(n.getFullYear(),n.getMonth(),n.getDate())};
const daysUntil=value=>{const d=parseDate(value);return d?Math.round((d-today())/DAY):null};
const shortDate=value=>{const d=parseDate(value);return d?`${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`:''};
const relDays=n=>n===0?'Bugün':n<0?`${-n} gün gecikti`:`${n} gün kaldı`;
export function reminderState(customer,defaultLead){
  if(customer.active===false) return {tone:'none',days:null};
  const days=daysUntil(customer.next_reminder_at);
  if(days===null) return {tone:'none',days:null};
  const lead=Number(customer.reminder_lead_days ?? defaultLead)||0;
  return {tone:days<0?'late':days<=lead?'soon':'upcoming',days};
}
const TONE_TEXT={late:'Gecikti',soon:'Yaklaşıyor',upcoming:'Planlı',none:'Tarih girilmedi'};
const byReminder=(a,b)=>{const x=parseDate(a.next_reminder_at),y=parseDate(b.next_reminder_at);if(!x&&!y)return (a.name||'').localeCompare(b.name||'','tr');if(!x)return 1;if(!y)return -1;return x-y};
const mapsLink=l=>`https://www.google.com/maps?q=${l.lat},${l.lng}`;
const inLastYear=at=>{const d=parseDate(at);return d&&(today()-d)/DAY<=365&&(today()-d)>=0};

/* ---------- saha sayfası ---------- */
export default function Customers({data,reload}){
  const {settings,notify}=useStore();
  const [params,setParams]=useSearchParams();
  const tab=params.get('tab')==='takvim'?'takvim':'liste';
  const [query,setQuery]=useState(''),[filter,setFilter]=useState('tumu'),[archived,setArchived]=useState(false);
  const [editor,setEditor]=useState(null),[orderFor,setOrderFor]=useState(null),[error,setError]=useState('');
  const lead=Number(settings?.reminder_lead_days??30);
  const all=data.customers||[];
  const active=useMemo(()=>all.filter(c=>c.active!==false),[all]);
  const rows=useMemo(()=>active.map(c=>({...c,state:reminderState(c,lead)})).sort(byReminder),[active,lead]);
  const visible=useMemo(()=>{
    const text=query.toLocaleLowerCase('tr');
    return rows.filter(c=>{
      const d=c.state.days;
      const byFilter=filter==='tumu'||(filter==='yenilenecek'&&d!==null&&d<=lead)||(filter==='late'&&c.state.tone==='late')||(filter==='soon'&&c.state.tone==='soon')||(filter==='bu-ay'&&d!==null&&d<=31)||(filter==='yeni'&&!c.last_order_at);
      return byFilter&&((c.name||'').toLocaleLowerCase('tr').includes(text)||(c.phone||'').includes(query)||(c.note||'').toLocaleLowerCase('tr').includes(text)||(c.city||'').toLocaleLowerCase('tr').includes(text));
    });
  },[rows,query,filter,lead]);
  const archivedRows=useMemo(()=>all.filter(c=>archived&&c.active===false),[all,archived]);
  const stats={
    soon:rows.filter(c=>c.state.tone==='soon').length, late:rows.filter(c=>c.state.tone==='late').length,
    revenue:rows.flatMap(c=>c.orders||[]).filter(o=>inLastYear(o.at)).reduce((n,o)=>n+Number(o.total||0),0),
    orders:rows.flatMap(c=>c.orders||[]).filter(o=>inLastYear(o.at)).length};
  const open=id=>setEditor(id?structuredClone(all.find(c=>c.id===id)):{name:'',phone:'',address:'',city:'',note:'',salesperson:settings.field_salespeople?.[0]||'Müfit',source:'Saha',location:null,cycle_months:settings.renewal_months??12,reminder_lead_days:settings.reminder_lead_days??30,last_order_at:'',next_reminder_at:'',active:true});
  return <>
    <div className="saha-bar"><div className="tabs"><button className={tab==='liste'?'selected':''} onClick={()=>setParams({})}>Müşteriler</button><button className={tab==='takvim'?'selected':''} onClick={()=>setParams({tab:'takvim'})}>Hatırlatma takvimi</button></div></div>
    <div className="saha-stats">{[['Aktif müşteri',active.length,'Kayıtlı saha müşterisi','','tumu'],['Yenilenecek',stats.soon,'Hatırlatma aralığında','warn','yenilenecek'],['Geciken',stats.late,'Aranması gereken','late','late'],['Son 12 ay',money(stats.revenue),stats.orders+' sipariş','','tumu']].map(([label,value,note,cls,key])=><article className={'saha-stat '+cls} key={label} role="button" tabIndex={0} title="Bu listeyi göster" onClick={()=>setFilter(key)} onKeyDown={e=>{if(e.key==='Enter')setFilter(key)}}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>)}</div>
    {error&&<div className="error" role="alert">{error}<button onClick={reload}>Tekrar dene</button></div>}
    {tab==='takvim'?<RenewalCalendar customers={rows} onOpen={open} onOrder={setOrderFor}/>
    :<div className="admin-panel"><div className="table-toolbar"><div className="search-input"><Search size={18}/><input aria-label="Müşteri ara" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ad, telefon, not veya il ara…"/></div><label className="check"><input type="checkbox" checked={archived} onChange={e=>setArchived(e.target.checked)}/>Arşivi göster</label><button onClick={()=>open(null)}><Plus size={17}/>Yeni müşteri</button></div><div className="saha-filters chip-set">{[['tumu','Tümü'],['yenilenecek','Yenilenecek'],['late','Geciken'],['soon','Yaklaşan'],['bu-ay','Bu ay'],['yeni','Siparişi olmayan']].map(([key,label])=><button key={key} className={'chip '+(filter===key?'active':'')} onClick={()=>setFilter(key)}>{label}</button>)}</div>
      {visible.length?<div className="customer-grid">{visible.map(c=><CustomerCard key={c.id} customer={c} onOpen={()=>open(c.id)} onOrder={()=>setOrderFor(c)}/>)}</div>:<div className="admin-empty"><Users size={34}/><h3>{all.length?'Bu filtrede müşteri yok':'Henüz müşteri kaydı yok'}</h3><p>{all.length?'Farklı bir filtre seçin ya da aramayı temizleyin.':'Kapıda satış yaptığınızda müşteriyi kaydedin; yenileme hatırlatması otomatik kurulur.'}</p><button onClick={()=>open(null)}>Yeni müşteri ekle</button></div>}
      {archivedRows.length>0&&<div className="table-scroll"><table><thead><tr><th>Arşivdeki müşteri</th><th>Telefon</th><th>Son sipariş</th><th className="align-right">İşlemler</th></tr></thead><tbody>{archivedRows.map(c=><tr key={c.id}><td><strong>{c.name}</strong></td><td>{c.phone||'—'}</td><td>{c.last_order_at?shortDate(c.last_order_at):'—'}</td><td><div className="row-actions"><button className="icon" title="Düzenle" onClick={()=>open(c.id)}><Pencil size={16}/></button></div></td></tr>)}</tbody></table></div>}
    </div>}
    {editor&&<CustomerEditor customer={editor} settings={settings} reload={reload} close={()=>setEditor(null)}/>}
    {orderFor&&<OrderDialog customer={orderFor} close={()=>setOrderFor(null)} reload={reload} notify={notify}/>}
  </>;
}

function CustomerCard({customer:c,onOpen,onOrder}){
  const state=c.state||{tone:'none',days:null};
  return <article className="customer-card">
    <div className="customer-card-head"><div><h3>{c.name}</h3><small>{c.salesperson||'Saha'} · {c.source||'Saha'}</small></div><span className={'badge '+(state.tone==='late'?'red':state.tone==='none'?'amber':'green')}>{TONE_TEXT[state.tone]}</span></div>
    <p className="customer-reminder">{c.next_reminder_at?<><CalendarClock size={15}/>{shortDate(c.next_reminder_at)} <b>{state.days!==null&&relDays(state.days)}</b></>:<><CalendarClock size={15}/>Yenileme tarihi girilmedi</>}</p>
    {c.note&&<p className="customer-note">{c.note}</p>}
    <div className="customer-meta"><span><Phone size={14}/>{c.phone||'Telefon yok'}</span><span><AlertTriangle size={14}/>{c.last_order_at?'Son sipariş '+shortDate(c.last_order_at):'Sipariş geçmişi yok'}</span></div>
    {c.location&&<a className="customer-map" href={mapsLink(c.location)} target="_blank" rel="noreferrer"><Navigation size={14}/>Teslim konumunu haritada aç</a>}
    <div className="customer-actions">{c.phone&&<a className="secondary button" href={'tel:'+c.phone.replaceAll(' ','')}><Phone size={15}/>Ara</a>}<button className="secondary" onClick={onOpen}><Pencil size={15}/>Detay</button><button onClick={onOrder}><Check size={15}/>Sipariş verildi</button></div>
  </article>;
}

/* ---------- hatırlatma takvimi ---------- */
function RenewalCalendar({customers,onOpen,onOrder}){
  const now=today();
  const [cursor,setCursor]=useState({y:now.getFullYear(),m:now.getMonth()});
  const [selected,setSelected]=useState(isoDate(now));
  const month=useMemo(()=>customers.filter(c=>{const d=parseDate(c.next_reminder_at);return d&&d.getFullYear()===cursor.y&&d.getMonth()===cursor.m}),[customers,cursor]);
  const byDay=useMemo(()=>{const map={};month.forEach(c=>{const day=parseDate(c.next_reminder_at).getDate();(map[day]=map[day]||[]).push(c)});return map},[month]);
  const cells=useMemo(()=>{const first=new Date(cursor.y,cursor.m,1);const start=new Date(cursor.y,cursor.m,1-((first.getDay()+6)%7));return Array.from({length:42},(_,i)=>new Date(start.getFullYear(),start.getMonth(),start.getDate()+i))},[cursor]);
  const shift=n=>{const d=new Date(cursor.y,cursor.m+n,1);setCursor({y:d.getFullYear(),m:d.getMonth()})};
  const selectedDate=parseDate(selected);
  const dayList=selectedDate&&selectedDate.getMonth()===cursor.m?byDay[selectedDate.getDate()]||[]:null;
  const listed=dayList||month;
  const overdue=customers.filter(c=>c.state.tone==='late');
  return <><section className="admin-panel"><div className="panel-head"><h2>{MONTHS[cursor.m]} {cursor.y}</h2><div className="calendar-nav"><button className="icon" aria-label="Önceki ay" onClick={()=>shift(-1)}><ChevronLeft/></button><button className="secondary" onClick={()=>setCursor({y:now.getFullYear(),m:now.getMonth()})}>Bu ay</button><button className="icon" aria-label="Sonraki ay" onClick={()=>shift(1)}><ChevronRight/></button></div></div>
    <div className="calendar-wrap"><div className="cal-grid">{WEEKDAYS.map(w=><span className="cal-head" key={w}>{w}</span>)}{cells.map(d=>{const key=isoDate(d);const list=byDay[d.getDate()]||[];const tone=list.reduce((t,c)=>t==='late'||c.state.tone==='late'?'late':t==='soon'||c.state.tone==='soon'?'soon':t,'');return <button key={key} className={'cal-day '+(d.getMonth()!==cursor.m?'muted ':'')+(key===selected?'selected ':'')+(list.length?'has ':'')+(tone||'')} onClick={()=>setSelected(key)}><b>{d.getDate()}</b>{list.length>0&&<span className="cal-count">{list.length}</span>}{list.length>0&&<small>{list[0].name.split(' ')[0]}{list.length>1?' +'+(list.length-1):''}</small>}</button>})}</div>
    <div className="calendar-side">{dayList!==null&&<div className="panel-head"><h3>{shortDate(selected)} · {dayList.length} müşteri</h3>{dayList.length>0&&<button className="secondary" onClick={()=>setSelected('')}>Tüm ayı göster</button>}</div>}{listed.length?<div className="reminder-list">{listed.map(c=><div className="reminder-row" key={c.id}><span className={'badge '+(c.state.tone==='late'?'red':c.state.tone==='soon'?'amber':'green')}>{c.state.days!==null?relDays(c.state.days):TONE_TEXT[c.state.tone]}</span><div><strong>{c.name}</strong><small>{shortDate(c.next_reminder_at)} · {c.phone||'telefon yok'}{c.note?' · '+c.note:''}</small></div><div className="reminder-actions">{c.phone&&<a className="icon" title="Ara" href={'tel:'+c.phone.replaceAll(' ','')}><Phone size={16}/></a>}<button className="icon" title="Detay" onClick={()=>onOpen(c.id)}><Pencil size={16}/></button><button className="secondary" onClick={()=>onOrder(c)}>Sipariş verildi</button></div></div>)}</div>:<div className="admin-empty"><CalendarClock size={32}/><p>Bu ay için yenileme hatırlatması yok.</p></div>}</div></div></section>
    <section className="admin-panel" style={{marginTop:20}}><div className="panel-head"><h2>Geciken hatırlatmalar</h2><Link className="text-link" to="/admin/customers">Listeye dön</Link></div>{overdue.length?<div className="reminder-list">{overdue.map(c=><div className="reminder-row" key={c.id}><span className="badge red">{relDays(c.state.days)}</span><div><strong>{c.name}</strong><small>{shortDate(c.next_reminder_at)} · {c.phone||'telefon yok'}</small></div><div className="reminder-actions"><button className="icon" title="Detay" onClick={()=>onOpen(c.id)}><Pencil size={16}/></button><button className="secondary" onClick={()=>onOrder(c)}>Sipariş verildi</button></div></div>)}</div>:<p className="muted" style={{padding:'22px 23px'}}>Geciken hatırlatma yok, tüm müşteriler planında.</p>}</section></>;
}

/* ---------- müşteri düzenleyici ---------- */
function CustomerEditor({customer,settings,reload,close}){
  const {notify}=useStore();
  const [item,setItem]=useState(customer),[error,setError]=useState(''),[busy,setBusy]=useState(false),[showOrder,setShowOrder]=useState(false);
  const update=(k,v)=>setItem(old=>({...old,[k]:v}));
  useEffect(()=>{const esc=e=>{if(e.key==='Escape')close()};document.addEventListener('keydown',esc);return()=>document.removeEventListener('keydown',esc)},[close]);
  async function save(e){
    e.preventDefault();setBusy(true);setError('');
    const body={name:item.name,phone:item.phone,address:item.address,city:item.city,note:item.note,salesperson:item.salesperson,
      source:item.source,location:item.location||null,cycle_months:item.cycle_months,reminder_lead_days:item.reminder_lead_days,
      last_order_at:item.last_order_at||'',next_reminder_at:item.next_reminder_at||'',active:item.active!==false};
    try{const saved=await api('/admin/customers'+(item.id?'/'+item.id:''),{method:item.id?'PUT':'POST',body});setItem(saved);await reload();notify('Müşteri kaydedildi.')}
    catch(e){setError(e.message)}finally{setBusy(false)}
  }
  return <div className="modal-overlay"><section className="editor-modal" role="dialog" aria-modal="true" aria-label="Müşteri kaydı"><div className="drawer-head"><h2>{item.id?item.name||'Müşteri':'Yeni müşteri'}</h2><button className="icon" aria-label="Kapat" onClick={close}><X/></button></div>
    <form onSubmit={save}><div className="editor-body">
      <label>Ad Soyad<input autoFocus required value={item.name||''} onChange={e=>update('name',e.target.value)}/></label>
      <div className="form-grid"><label>Telefon<input value={item.phone||''} onChange={e=>update('phone',e.target.value)} placeholder="05xx xxx xx xx"/></label><label>Saha satış temsilcisi<input value={item.salesperson||''} onChange={e=>update('salesperson',e.target.value)} list="saha-people"/><datalist id="saha-people">{(settings.field_salespeople||[]).map(p=><option key={p} value={p}/>)}</datalist></label></div>
      <div className="form-grid"><label>İl / İlçe<input value={item.city||''} onChange={e=>update('city',e.target.value)}/></label><label>Kayıt kaynağı<select value={item.source||'Saha'} onChange={e=>update('source',e.target.value)}>{['Saha','Web','Telefon','Diğer'].map(s=><option key={s}>{s}</option>)}</select></label></div>
      <label>Açık adres<textarea rows={2} value={item.address||''} onChange={e=>update('address',e.target.value)}/></label>
      <label>Yakınlık / hatırlatma notu<textarea rows={2} value={item.note||''} onChange={e=>update('note',e.target.value)} placeholder="Örn: Özgür'ün arkadaşı, her yıl 5 litrelik alır."/></label>
      <LocationBox value={item.location} onChange={v=>update('location',v)}/>
      <div className="form-grid"><label>Yenileme periyodu (ay)<input type="number" min="1" max="60" value={item.cycle_months??12} onChange={e=>update('cycle_months',e.target.value)}/></label><label>Kaç gün önce hatırlat<input type="number" min="0" max="365" value={item.reminder_lead_days??30} onChange={e=>update('reminder_lead_days',e.target.value)}/></label></div>
      <div className="form-grid"><label>Son sipariş tarihi<input type="date" value={item.last_order_at||''} onChange={e=>update('last_order_at',e.target.value)}/></label><label>Sonraki hatırlatma<input type="date" value={item.next_reminder_at||''} onChange={e=>update('next_reminder_at',e.target.value)}/><small>Boş bırakırsanız son sipariş tarihinden otomatik hesaplanır.</small></label></div>
      <label className="check"><input type="checkbox" checked={item.active!==false} onChange={e=>update('active',e.target.checked)}/>Kayıt aktif</label>
      {item.id&&<><div className="panel-head"><h3>Sipariş geçmişi</h3><button type="button" className="secondary" onClick={()=>setShowOrder(!showOrder)}><Plus size={15}/>Sipariş verildi</button></div>{showOrder&&<OrderForm customer={item} onDone={saved=>{setItem(saved);setShowOrder(false);reload()}}/>}
        {item.orders?.length?<div className="history-list">{[...item.orders].reverse().map(o=><div className="history-row" key={o.id}><strong>{shortDate(o.at)}</strong><span>{o.items||o.note||'Sipariş'}{o.total?<> · {money(o.total)}</>:null}</span><small>{o.source}</small></div>)}</div>:<p className="muted">Henüz sipariş kaydı yok.</p>}
        {!showOrder&&<p className="muted">Kapıda satış tamamlandığında “Sipariş verildi” ile işaretleyin; bir sonraki yıl için hatırlatma otomatik kurulur.</p>}
        <div className="panel-head"><h3>Hatırlatma notları</h3><small>{item.notes?.length||0} not</small></div>
        {item.notes?.length?<div className="note-list">{[...item.notes].reverse().map(n=><div className="note-row" key={n.id}><div className="note-head"><span className={'badge '+(n.source==='voice'?'green':'amber')}>{n.source==='voice'?'Sesli':'Elle yazıldı'}</span><small>{n.author?n.author+' · ':''}{new Date(n.at).toLocaleString('tr-TR')}</small><button type="button" className="icon" title="Notu sil" onClick={async()=>{try{const saved=await api('/admin/customers/'+item.id+'/notes/'+n.id,{method:'DELETE'});setItem(saved);notify('Not silindi.')}catch(e){notify(e.message)}}}><Trash2 size={15}/></button></div>{n.text&&<p className="note-text">{n.text}</p>}{n.audio&&<audio controls preload="none" src={n.audio}/>}</div>)}</div>:<p className="muted">Mikrofonla konuşun; sesiniz yazıya çevrilip buraya kaydedilir.</p>}
        <VoiceCapture chips={RELATION_TAGS} onSave={async note=>{try{const saved=await api('/admin/customers/'+item.id+'/notes',{method:'POST',body:note});setItem(saved);notify('Not kaydedildi.')}catch(e){notify(e.message);throw e}}}/></>}
      {error&&<p className="error" role="alert">{error}</p>}
    </div><div className="editor-actions">{item.id&&<button type="button" className="secondary danger" onClick={async()=>{try{await api('/admin/customers/'+item.id,{method:'DELETE'});await reload();notify('Müşteri arşivlendi.');close()}catch(e){setError(e.message)}}}><Archive size={16}/>Arşivle</button>}<button type="button" className="secondary" onClick={close}>Kapat</button><button disabled={busy}>{busy?'Kaydediliyor…':'Kaydet'}<Save size={16}/></button></div></form></section></div>;
}

function LocationBox({value,onChange}){
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  function capture(){
    if(!navigator.geolocation){setError('Bu cihaz konum servisini desteklemiyor. Adresi elle girin.');return}
    setBusy(true);setError('');
    navigator.geolocation.getCurrentPosition(
      p=>{onChange({lat:Number(p.coords.latitude.toFixed(6)),lng:Number(p.coords.longitude.toFixed(6)),accuracy:Math.round(p.coords.accuracy||0),at:new Date().toISOString().slice(0,19)+'Z'});setBusy(false)},
      e=>{setError(e.code===1?'Konum izni verilmedi. Tarayıcı ayarlarından izin verin.':'Konum alınamadı: '+e.message);setBusy(false)},
      {enableHighAccuracy:true,timeout:20000,maximumAge:0});
  }
  return <div className="geo-box"><div className="panel-head"><h3>Teslim konumu</h3>{value?<button type="button" className="secondary" onClick={()=>onChange(null)}>Konumu temizle</button>:<button type="button" className="secondary" onClick={capture} disabled={busy}><Navigation size={15}/>{busy?'Alınıyor…':'Konumu al'}</button>}</div>{value?<p className="geo-value"><Navigation size={14}/>{value.lat}, {value.lng}{value.accuracy?` · ±${value.accuracy} m`:''}<a href={mapsLink(value)} target="_blank" rel="noreferrer">Haritada aç</a></p>:<p className="muted">Kapıda teslim sırasında “Konumu al” ile telefonun GPS konumunu kaydedin; sonraki ziyarette tek dokunuşla haritada açılır.</p>}{error&&<p className="error" role="alert">{error}</p>}</div>;
}

function OrderForm({customer,saved,onDone}){
  const {notify}=useStore();
  const [form,setForm]=useState({at:isoDate(today()),total:'',items:'',note:''}),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const update=(k,v)=>setForm(old=>({...old,[k]:v}));
  async function submit(){
    setBusy(true);setError('');
    try{const body=await api('/admin/customers/'+customer.id+'/order',{method:'POST',body:{...form,total:form.total===''?0:form.total,source:'Kapı teslimi'}});notify('Sipariş kaydedildi; hatırlatma bir sonraki yıla kuruldu.');saved?.();onDone(body)}
    catch(e){setError(e.message)}finally{setBusy(false)}
  }
  return <div className="order-form">
    <div className="form-grid"><label>Tarih<input type="date" value={form.at} onChange={e=>update('at',e.target.value)}/></label><label>Tutar (TL)<input type="number" min="0" step="0.01" value={form.total} onChange={e=>update('total',e.target.value)}/></label></div>
    <label>Alınan ürünler<input value={form.items} onChange={e=>update('items',e.target.value)} placeholder="2 × Zeytinyağı 5 L"/></label>
    <label>Not<textarea rows={2} value={form.note} onChange={e=>update('note',e.target.value)}/></label>
    {error&&<p className="error">{error}</p>}
    <div className="order-actions"><button type="button" disabled={busy} onClick={submit}>{busy?'Kaydediliyor…':'Siparişi kaydet'}<Check size={16}/></button></div>
  </div>;
}

function OrderDialog({customer,close,reload,notify}){
  return <div className="modal-overlay"><section className="editor-modal small" role="dialog" aria-modal="true" aria-label="Sipariş kaydı"><div className="drawer-head"><h2>{customer.name}</h2><button className="icon" aria-label="Kapat" onClick={close}><X/></button></div><div className="editor-body"><p className="info-banner">Sipariş kaydedildiğinde bu müşteri için bir sonraki hatırlatma {customer.cycle_months||12} ay sonrasına kurulur.</p><OrderForm customer={customer} saved={()=>reload()} onDone={()=>{close()}}/></div></section></div>;
}

/* ---------- konuşmayı yazıya çeviren not kaydı ---------- */
function VoiceCapture({chips,onSave}){
  const [text,setText]=useState(''),[live,setLive]=useState(''),[status,setStatus]=useState('idle'),[seconds,setSeconds]=useState(0);
  const [blob,setBlob]=useState(null),[preview,setPreview]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const recognition=useRef(null),recorder=useRef(null),chunks=useRef([]),stream=useRef(null),timer=useRef(null),finalText=useRef(''),previewRef=useRef(''),usedSpeech=useRef(false);
  const Speech=typeof window!=='undefined'&&(window.SpeechRecognition||window.webkitSpeechRecognition);
  const supported=typeof navigator!=='undefined'&&!!navigator.mediaDevices?.getUserMedia&&typeof window.MediaRecorder!=='undefined';
  const recording=status==='recording';
  useEffect(()=>()=>{
    clearInterval(timer.current);
    try{recognition.current?.abort()}catch{}
    try{recorder.current&&recorder.current.state!=='inactive'&&recorder.current.stop()}catch{}
    stream.current?.getTracks().forEach(t=>t.stop());
    if(previewRef.current)URL.revokeObjectURL(previewRef.current);
  },[]);
  async function start(){
    setError('');setBlob(null);finalText.current=text?text+' ':'';
    if(supported){
      try{
        const media=await navigator.mediaDevices.getUserMedia({audio:true});stream.current=media;chunks.current=[];
        const types=['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus','audio/ogg'];
        const mime=types.find(t=>window.MediaRecorder.isTypeSupported?.(t));
        const rec=new MediaRecorder(media,mime?{mimeType:mime}:undefined);
        rec.ondataavailable=e=>{if(e.data&&e.data.size)chunks.current.push(e.data)};
        rec.onstop=()=>{stream.current?.getTracks().forEach(t=>t.stop());const made=new Blob(chunks.current,{type:rec.mimeType||'audio/webm'});setBlob(made);
          if(previewRef.current)URL.revokeObjectURL(previewRef.current);previewRef.current=URL.createObjectURL(made);setPreview(previewRef.current)};
        rec.start();recorder.current=rec;
      }catch{setError('Mikrofon izni verilmedi. Notu yazarak da kaydedebilirsiniz.')}
    }
    if(Speech){
      try{
        const r=new Speech();r.lang='tr-TR';r.continuous=true;r.interimResults=true;
        r.onresult=e=>{usedSpeech.current=true;let interim='';for(let i=e.resultIndex;i<e.results.length;i++){const res=e.results[i];if(res.isFinal)finalText.current+=res[0].transcript+' ';else interim+=res[0].transcript}setLive(interim);setText(finalText.current)};
        r.onerror=e=>{if(e.error==='not-allowed'||e.error==='service-not-allowed')setError('Ses tanıma izni yok. Notu yazarak kaydedebilirsiniz.');else if(!['no-speech','aborted'].includes(e.error))setError('Konuşma yazıya çevrilemedi: '+e.error)};
        r.start();recognition.current=r;
      }catch{}
    }else if(!supported)setError('Bu tarayıcı sesi kaydetmiyor. Notu yazarak kaydedin.');
    setStatus('recording');setSeconds(0);timer.current=setInterval(()=>setSeconds(s=>s+1),1000);
  }
  function stop(){
    try{recognition.current?.stop()}catch{}
    try{if(recorder.current&&recorder.current.state!=='inactive')recorder.current.stop()}catch{}
    clearInterval(timer.current);setStatus('stopped');setLive('');
  }
  function reset(){
    setText('');setLive('');setBlob(null);setSeconds(0);setStatus('idle');
    if(previewRef.current){URL.revokeObjectURL(previewRef.current);previewRef.current='';setPreview('')}
    finalText.current='';
  }
  async function save(){
    if(!text.trim()&&!blob)return setError('Önce konuşun ya da notu yazın.');
    setBusy(true);setError('');
    try{
      let audio='';
      if(blob){const form=new FormData();form.append('file',new File([blob],'sesli-not.webm',{type:blob.type||'audio/webm'}));audio=(await api('/admin/upload',{method:'POST',body:form})).url}
      await onSave({text:text.trim(),audio,source:audio||usedSpeech.current?'voice':'manual'});
      reset();usedSpeech.current=false;
      reset();
    }catch(e){setError(e.message)}finally{setBusy(false)}
  }
  return <div className="voice-box">
    <div className="voice-head"><span className="eyebrow">KONUŞARAK NOT</span>{recording&&<b className="rec-indicator"><i/>{Math.floor(seconds/60)}:{String(seconds%60).padStart(2,'0')} kayıt</b>}</div>
    <div className="chip-set">{chips.map(chip=><button type="button" key={chip} className="chip" onClick={()=>{setText(t=>(t?t.replace(/\s*$/,' '):'')+chip+': ');finalText.current=(finalText.current?finalText.current.replace(/\s*$/,' '):'')+chip+': '}}>+ {chip}</button>)}</div>
    <textarea rows={3} value={text+(live?' '+live:'')} onChange={e=>{setText(e.target.value);finalText.current=e.target.value}} placeholder="Konuşun; yazıya çevrilen metin burada görünür ve düzenlenebilir."/>
    {preview&&<audio controls src={preview}/>}
    {error&&<p className="error" role="alert">{error}</p>}
    <div className="voice-actions">{recording?<button type="button" className="danger" onClick={stop}><Square size={15}/>Kaydı bitir</button>:<button type="button" onClick={start}><Mic size={16}/>Konuşmaya başla</button>}<button type="button" className="secondary" disabled={busy||recording||(!text.trim()&&!blob)} onClick={save}>{busy?'Kaydediliyor…':'Notu kaydet'}<Save size={15}/></button>{(text||blob)&&!recording&&<button type="button" className="secondary" onClick={reset}>Temizle</button>}</div>
    {!Speech&&<small>Ses yazıya çevirme bu tarayıcıda yok; ses kaydı saklanır, notu elle yazabilirsiniz.</small>}
  </div>;
}
