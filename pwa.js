const PWA_APP_VERSION='1.0.5';
const PWA_DEFAULT_DB_VERSION='2.8.20';
let pwaUpdateRunning=false;
let pwaStartupComplete=false;

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
function setStartupText(text){
  const s=document.getElementById('pwaStartupText');
  if(s)s.textContent=text;
}
function finishStartup(){
  if(pwaStartupComplete)return;
  pwaStartupComplete=true;
  document.body.classList.remove('pwa-starting');
  const gate=document.getElementById('pwaStartupGate');
  if(gate){
    gate.classList.add('done');
    setTimeout(()=>gate.remove(),220);
  }
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
async function updateDbIfNeeded(v,isStartup=false){
  const cur=pwaStoredDbVersion();
  if(!v.dbVersion||v.dbVersion===cur)return false;
  setPwaStatus(`DB Ver${v.dbVersion}を更新中…`,true);
  if(isStartup)setStartupText(`DB Ver${cur} → ${v.dbVersion} を更新中`);
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
async function updateAppShellIfNeeded(v,isStartup=false){
  if(!v.appVersion||!versionDifferent(v.appVersion,PWA_APP_VERSION))return false;
  setPwaStatus(`PWA Ver${v.appVersion}を更新中…`,true);
  if(isStartup)setStartupText(`PWA Ver${PWA_APP_VERSION} → ${v.appVersion} を更新中`);
  if(!('serviceWorker' in navigator))return true;
  const reg=await navigator.serviceWorker.getRegistration('./')||await navigator.serviceWorker.register('./service-worker.js');
  await reg.update();
  const worker=reg.installing||reg.waiting;
  if(worker&&worker.state!=='activated'){
    await new Promise(resolve=>{
      let settled=false;
      const done=()=>{if(!settled){settled=true;resolve();}};
      worker.addEventListener('statechange',()=>{if(worker.state==='activated')done();});
      setTimeout(done,5000);
    });
  }
  return true;
}
async function updateEverything(manual=false,isStartup=false){
  if(pwaUpdateRunning)return;
  pwaUpdateRunning=true;
  setPwaUpdateButton(true);
  setPwaStatus('最新版を確認しています…',false);
  if(isStartup)setStartupText('PWA本体とデータベースを確認中');
  let shouldReload=false;
  try{
    const v=await fetchLatestVersion();
    const dbUpdated=await updateDbIfNeeded(v,isStartup);
    const appUpdated=await updateAppShellIfNeeded(v,isStartup);
    shouldReload=appUpdated||dbUpdated;
    if(shouldReload){
      setPwaStatus('更新しました。再読み込みします…',false);
      if(isStartup)setStartupText('更新完了。最新版で起動します…');
      setTimeout(()=>location.reload(),350);
      return;
    }
    setPwaStatus(`PWA Ver${PWA_APP_VERSION} / DB Ver${pwaStoredDbVersion()}（最新）`,false);
    if(manual)alert('PWA本体・データベースともに最新版です。');
  }catch(e){
    console.warn('PWA update failed',e);
    setPwaStatus(`PWA Ver${PWA_APP_VERSION} / DB Ver${pwaStoredDbVersion()}（オフライン）`,false);
    if(isStartup)setStartupText('更新確認できませんでした。保存済みの版で起動します');
    if(manual)alert('最新版を確認できませんでした。通信状態を確認してください。');
  }finally{
    pwaUpdateRunning=false;
    setPwaUpdateButton(false);
    if(isStartup&&!shouldReload)setTimeout(finishStartup,250);
  }
}
window.updateEverything=updateEverything;

window.addEventListener('load',async()=>{
  if('serviceWorker' in navigator){
    try{await navigator.serviceWorker.register('./service-worker.js');}
    catch(e){console.warn(e);}
  }
  setPwaStatus('最新版を確認しています…');
  await updateEverything(false,true);
});
