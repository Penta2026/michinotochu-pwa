const PWA_APP_VERSION='1.5.15';
const PWA_DEFAULT_DB_VERSION='2.8.20';
const PWA_NETWORK_TIMEOUT_MS=5000;
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
async function fetchWithTimeout(url,options={},timeout=PWA_NETWORK_TIMEOUT_MS){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),timeout);
  try{
    return await fetch(url,{...options,signal:controller.signal});
  }finally{
    clearTimeout(timer);
  }
}
async function fetchLatestVersion(){
  const r=await fetchWithTimeout(`data/version.json?t=${Date.now()}`,{cache:'no-store'});
  if(!r.ok)throw new Error('version');
  return await r.json();
}
async function updateDbIfNeeded(v,isStartup=false){
  const cur=pwaStoredDbVersion();
  if(!v.dbVersion||v.dbVersion===cur)return false;
  setPwaStatus(`DB Ver${v.dbVersion}を更新中…`,true);
  if(isStartup)setStartupText(`DB Ver${cur} → ${v.dbVersion} を更新中`);
  const url=(v.dataFile||'data/app_data.js')+`?db=${encodeURIComponent(v.dbVersion)}&t=${Date.now()}`;
  const r=await fetchWithTimeout(url,{cache:'no-store'},12000);
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
async function serviceWorkerRegistration(){
  if(!('serviceWorker' in navigator))return null;
  const existing=await navigator.serviceWorker.getRegistration('./');
  if(existing)return existing;
  return await Promise.race([
    navigator.serviceWorker.register('./service-worker.js'),
    new Promise((_,reject)=>setTimeout(()=>reject(new Error('sw timeout')),3000))
  ]);
}
function waitWorkerActivated(worker,timeout=8000){
  if(!worker||worker.state==='activated')return Promise.resolve();
  return Promise.race([
    new Promise(resolve=>{
      const onState=()=>{if(worker.state==='activated'){worker.removeEventListener('statechange',onState);resolve()}};
      worker.addEventListener('statechange',onState);
    }),
    new Promise(resolve=>setTimeout(resolve,timeout))
  ]);
}
function waitControllerChange(timeout=8000){
  if(!('serviceWorker' in navigator))return Promise.resolve();
  return Promise.race([
    new Promise(resolve=>navigator.serviceWorker.addEventListener('controllerchange',()=>resolve(),{once:true})),
    new Promise(resolve=>setTimeout(resolve,timeout))
  ]);
}
async function updateAppShellIfNeeded(v,isStartup=false){
  if(!v.appVersion||!versionDifferent(v.appVersion,PWA_APP_VERSION))return false;
  setPwaStatus(`PWA Ver${v.appVersion}を更新中…`,true);
  if(isStartup)setStartupText(`PWA Ver${PWA_APP_VERSION} → ${v.appVersion} を更新中`);
  const reg=await serviceWorkerRegistration();
  if(!reg)return true;
  const before=navigator.serviceWorker.controller;
  await Promise.race([
    reg.update(),
    new Promise((_,reject)=>setTimeout(()=>reject(new Error('sw update timeout')),6000))
  ]);
  const worker=reg.installing||reg.waiting;
  if(worker){
    if(reg.waiting)try{reg.waiting.postMessage({type:'SKIP_WAITING'})}catch(e){}
    await waitWorkerActivated(worker,9000);
  }
  if(before===navigator.serviceWorker.controller)await waitControllerChange(1800);
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
      setTimeout(()=>{
        const u=new URL(location.href);
        u.searchParams.set('_pwa',v.appVersion);
        location.replace(u.toString());
      },250);
      return;
    }
    setPwaStatus(`PWA Ver${PWA_APP_VERSION} / DB Ver${pwaStoredDbVersion()}（最新）`,false);
    if(manual)alert('PWA本体・データベースともに最新版です。');
  }catch(e){
    console.warn('PWA update failed',e);
    setPwaStatus(`PWA Ver${PWA_APP_VERSION} / DB Ver${pwaStoredDbVersion()}（確認省略）`,false);
    if(isStartup)setStartupText('更新確認を終了して起動します');
    if(manual)alert('更新確認に時間がかかったため終了しました。現在の版はそのまま使えます。');
  }finally{
    pwaUpdateRunning=false;
    setPwaUpdateButton(false);
    if(isStartup&&!shouldReload)setTimeout(finishStartup,150);
  }
}
window.updateEverything=updateEverything;

window.addEventListener('load',()=>{
  const startupSafety=setTimeout(()=>{
    if(!pwaStartupComplete){
      setPwaStatus(`PWA Ver${PWA_APP_VERSION} / DB Ver${pwaStoredDbVersion()}（起動優先）`,false);
      finishStartup();
    }
  },6500);
  setPwaStatus('最新版を確認しています…');
  updateEverything(false,true).finally(()=>clearTimeout(startupSafety));
});
