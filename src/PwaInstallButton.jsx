import React,{useEffect,useState} from 'react';
import {Download,X} from 'lucide-react';

let deferredPrompt=null;
const promptListeners=new Set();
if(typeof window!=='undefined'){
  window.addEventListener('beforeinstallprompt',event=>{
    event.preventDefault();deferredPrompt=event;
    promptListeners.forEach(listener=>listener(deferredPrompt));
  });
  window.addEventListener('appinstalled',()=>{
    deferredPrompt=null;promptListeners.forEach(listener=>listener(null));
  });
}

export default function PwaInstallButton({label='Yönetim uygulamasını yükle'}){
  const [prompt,setPrompt]=useState(null),[help,setHelp]=useState(false),[installed,setInstalled]=useState(false);
  const isIOS=typeof navigator!=='undefined'&&(/iphone|ipad|ipod/i.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1));
  useEffect(()=>{
    const standalone=window.matchMedia('(display-mode: standalone)');
    const update=()=>setInstalled(standalone.matches||navigator.standalone===true);
    const receivePrompt=value=>setPrompt(value);
    update();standalone.addEventListener?.('change',update);
    promptListeners.add(receivePrompt);receivePrompt(deferredPrompt);
    const onInstalled=()=>setInstalled(true);
    window.addEventListener('appinstalled',onInstalled);
    return()=>{standalone.removeEventListener?.('change',update);promptListeners.delete(receivePrompt);window.removeEventListener('appinstalled',onInstalled)};
  },[]);
  if(installed)return null;
  const install=async()=>{
    if(!prompt){setHelp(true);return}
    await prompt.prompt();
    await prompt.userChoice;
    setPrompt(null);
  };
  return <>
    <button type="button" className="pwa-install-btn" onClick={install}><Download size={17}/><span>{label}</span></button>
    {help&&<div className="pwa-help-overlay" onClick={()=>setHelp(false)}>
      <section className="pwa-help" role="dialog" aria-modal="true" aria-labelledby="pwa-help-title" onClick={e=>e.stopPropagation()}>
        <button type="button" className="icon pwa-help-close" aria-label="Kapat" onClick={()=>setHelp(false)}><X size={20}/></button>
        <Download size={28}/><h2 id="pwa-help-title">Yönetimi telefona ekleyin</h2>
        {isIOS?<p>Safari’de <strong>Paylaş</strong> düğmesine dokunun, <strong>Ana Ekrana Ekle</strong> seçeneğini seçin ve <strong>Ekle</strong> ile tamamlayın.</p>:<p>Tarayıcı menüsünü açıp <strong>Uygulamayı yükle</strong> veya <strong>Ana ekrana ekle</strong> seçeneğine dokunun.</p>}
        <button type="button" className="secondary" onClick={()=>setHelp(false)}>Anladım</button>
      </section>
    </div>}
  </>;
}
