const PWA_APP_VERSION='1.0.1';
const PWA_DEFAULT_DB_VERSION='2.8.20';
function pwaStoredDbVersion(){return localStorage.getItem('michino_db_version')||PWA_DEFAULT_DB_VERSION;}
function setPwaStatus(text,hasUpdate=false){
  const s=document.getElementById('pwaDbStatus'); const p=document.getElementById('pwaUpdatePanel');
  if(s)s.textContent=text; if(p)p.classList.toggle('has-update',!!hasUpdate);
  const f=document.getElementById('footerVersion'); if(f)f.textContent=`PWA Ver${PWA_APP_VERSION} / DB Ver${pwaStoredDbVersion()}`;
}
async function checkPwaDataUpdate(manual=false){
  const b=document.getElementById('pwaUpdateButton'); if(b)b.disabled=true;
  try{
    const r=await fetch(`data/version.json?t=${Date.now()}`,{cache:'no-store'}); if(!r.ok)throw new Error('version');
    const v=await r.json(); const cur=pwaStoredDbVersion();
    if(v.dbVersion && v.dbVersion!==cur){
      setPwaStatus(`新しいDB Ver${v.dbVersion}があります`,true);
      const ok=confirm(`新しいスポットデータがあります。\
DB Ver${cur} → Ver${v.dbVersion}\
\
今すぐ更新しますか？`);
      if(ok)await applyPwaDataUpdate(v);
    }else{setPwaStatus(`DB Ver${cur}（最新）`,false); if(manual)alert('データベースは最新です。');}
  }catch(e){setPwaStatus(`DB Ver${pwaStoredDbVersion()}（オフライン）`,false); if(manual)alert('更新情報を確認できませんでした。通信状態を確認してください。');}
  finally{if(b)b.disabled=false;}
}
async function applyPwaDataUpdate(v){
  const b=document.getElementById('pwaUpdateButton'); if(b){b.disabled=true;b.textContent='更新中…';}
  try{
    const url=(v.dataFile||'data/app_data.js')+`?db=${encodeURIComponent(v.dbVersion)}&t=${Date.now()}`;
    const r=await fetch(url,{cache:'no-store'}); if(!r.ok)throw new Error('data');
    const text=await r.text();
    if(!text.includes('window.APP_DATA=')||text.length<1000)throw new Error('invalid');
    const cache=await caches.open('michino-db');
    await cache.put('data/app_data.js',new Response(text,{headers:{'Content-Type':'application/javascript; charset=utf-8'}}));
    localStorage.setItem('michino_db_version',v.dbVersion);
    alert(`DB Ver${v.dbVersion}へ更新しました。再読み込みします。`); location.reload();
  }catch(e){alert('データ更新に失敗しました。旧データはそのまま残しています。');}
  finally{if(b){b.disabled=false;b.textContent='🔄 データ更新を確認';}}
}
window.addEventListener('load',async()=>{
  if('serviceWorker' in navigator){try{await navigator.serviceWorker.register('./service-worker.js');}catch(e){console.warn(e);}}
  setPwaStatus(`DB Ver${pwaStoredDbVersion()}`);
  setTimeout(()=>checkPwaDataUpdate(false),1200);
});
