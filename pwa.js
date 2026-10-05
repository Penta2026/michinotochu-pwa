const PWA_APP_VERSION='1.0.3';
const PWA_DEFAULT_DB_VERSION='2.8.20';
let pwaUpdateRunning=false;

function pwaStoredDbVersion(){
  return localStorage.getItem('michino_db_version')||PWA_DEFAULT_DB_VERSION;
}
function setPwaStatus(text,hasUpdate=false){
  const s=document.getElementById('pwaDbStatus');
  const p=document.getElementById('pwaUpdatePanel');
  if(s)s.textContent=text;
  if(p)p.classList.toggle('has-update',!!hasUpdate);
  const f=document.getElementById('footerVersion');
  if(f)f.textContent=`PWA Ver${PWA_APP_VERSION} / DB Ver${pwaStoredDbVersion()}`;
}
function setPwaUpdateButton(busy){
  const b=document.getElementById('pwaUpdateButton');
  if(!b)return;
  b.disabled=!!busy;
  b.textContent=busy?'更新中…':'🔄 最新版に更新';
}
async function fetchLatestVersion(){
  const r=await fetch(`data/version.json?t=${Date.now()}`,{cache:'no-store'});
  if(!r.ok)throw new Error('version');
  return await r.json();
}
async function updateDbIfNeeded(v){
  const cur=pwaStoredDbVersion();
  if(!v.dbVersion||v.dbVersion===cur)return false;
  setPwaStatus(`DB Ver${v.dbVersion}を更新中…`,true);
  const url=(v.dataFile||'data/app_data.js')+`?db=${encodeURIComponent(v.dbVersion)}&t=${Date.now()}`;
  const r=await fetch(url,{cache:'no-store'});
  if(!r.ok)throw new Error('data');
  const text=await r.text();
  if(!text.includes('window.APP_DATA=')||text.length<1000)throw new Error('invalid data');
  const cache=await caches.open('michino-db');
  await cache.put('data/app_data.js',new Response(text,{headers:{'Content-Type':'application/javascript; charset=utf-8'}}));
  localStorage.setItem('michino_db_version',v.dbVersion);
  return true;
}
function versionDifferent(latest,current){
  return String(latest||'').trim()!==String(current||'').trim();
}
async function updateAppShellIfNeeded(v){
  if(!v.appVersion||!versionDifferent(v.appVersion,PWA_APP_VERSION))return false;
  setPwaStatus(`PWA Ver${v.appVersion}を更新中…`,true);
  if(!('serviceWorker' in navigator))return true;
  const reg=await navigator.serviceWorker.getRegistration('./')||await navigator.serviceWorker.register('./service-worker.js');
  await reg.update();
  const worker=reg.installing||reg.waiting;
  if(worker&&worker.state!=='activated'){
    await new Promise(resolve=>{
      const done=()=>resolve();
      worker.addEventListener('statechange',()=>{if(worker.state==='activated')done();});
      setTimeout(done,5000);
    });
  }
  return true;
}
async function updateEverything(manual=false){
  if(pwaUpdateRunning)return;
  pwaUpdateRunning=true;
  setPwaUpdateButton(true);
  setPwaStatus('最新版を確認しています…',false);
  try{
    const v=await fetchLatestVersion();
    const dbUpdated=await updateDbIfNeeded(v);
    const appUpdated=await updateAppShellIfNeeded(v);
    if(appUpdated||dbUpdated){
      setPwaStatus('更新しました。再読み込みします…',false);
      setTimeout(()=>location.reload(),350);
      return;
    }
    setPwaStatus(`PWA Ver${PWA_APP_VERSION} / DB Ver${pwaStoredDbVersion()}（最新）`,false);
    if(manual)alert('PWA本体・データベースともに最新版です。');
  }catch(e){
    console.warn('PWA update failed',e);
    setPwaStatus(`PWA Ver${PWA_APP_VERSION} / DB Ver${pwaStoredDbVersion()}（オフライン）`,false);
    if(manual)alert('最新版を確認できませんでした。通信状態を確認してください。');
  }finally{
    pwaUpdateRunning=false;
    setPwaUpdateButton(false);
  }
}
window.updateEverything=updateEverything;

window.addEventListener('load',async()=>{
  if('serviceWorker' in navigator){
    try{
      const reg=await navigator.serviceWorker.register('./service-worker.js');
      await reg.update();
    }catch(e){console.warn(e);}
  }
  setPwaStatus('最新版を確認しています…');
  await updateEverything(false);
});
