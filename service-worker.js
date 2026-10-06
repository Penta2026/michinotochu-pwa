const SHELL_CACHE='michino-shell-v1.5.15';
const DB_CACHE='michino-db';
const SHELL=[
  './','./index.html','./support.html','./legal.html','./privacy.html','./terms.html','./history.html','./style.css?v=1.5.15','./app.js?v=1.5.15','./pwa.js?v=1.5.15','./data/road_summaries_chugoku.js?v=1.5.15','./data/road_summaries_shikoku.js?v=1.5.15','./data/road_summaries_kyushu_okinawa.js?v=1.5.15','./data/road_summaries_kinki.js?v=1.5.15','./data/road_summaries_chubu.js?v=1.5.15','./data/road_summaries_kanto.js?v=1.5.15','./data/road_summaries_tohoku.js?v=1.5.15','./data/road_summaries_hokkaido.js?v=1.5.15','./data/road_summaries_final.js?v=1.5.15','./data/spot_overrides.js?v=1.5.15','./manifest.webmanifest?v=1.5.15',
  './assets/home/home_background.png','./assets/home/home_sprite_3.js?v=1.5.15','./assets/home/home_sprite_2.js?v=1.5.15','./assets/home/home_sprite_1.js?v=1.5.15','./assets/home/home_sprite_0.js?v=1.5.15',
  './assets/home/home_btn_sugoroku.webp?v=1.5.15','./assets/home/home_btn_destination.webp?v=1.5.15','./assets/home/home_btn_relay.webp?v=1.5.15','./assets/home/home_btn_detour.webp?v=1.5.15',
  './assets/home/home_btn_nearby.webp?v=1.5.15','./assets/home/home_btn_ride_style.webp?v=1.5.15','./assets/home/home_btn_season.webp?v=1.5.15','./assets/home/home_btn_interest.webp?v=1.5.15',
  './assets/home/home_btn_saved.webp?v=1.5.15','./assets/home/home_btn_history.webp?v=1.5.15','./icons/icon-192.png?v=1.5.15','./icons/icon-512.png?v=1.5.15'
];
self.addEventListener('install',event=>{event.waitUntil((async()=>{
  const shell=await caches.open(SHELL_CACHE); for(const url of SHELL){try{await shell.add(url);}catch(e){console.warn('shell cache skip',url,e);}}
  const db=await caches.open(DB_CACHE); if(!(await db.match('./data/app_data.js'))){try{await db.add('./data/app_data.js');}catch(e){}}
  self.skipWaiting();
})());});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{
  const keys=await caches.keys();
  await Promise.all(keys.filter(k=>k.startsWith('michino-shell-')&&k!==SHELL_CACHE).map(k=>caches.delete(k)));
  await self.clients.claim();
})());});
self.addEventListener('message',event=>{if(event.data&&event.data.type==='SKIP_WAITING')self.skipWaiting();});
self.addEventListener('fetch',event=>{
  const u=new URL(event.request.url);
  if(event.request.method!=='GET') return;
  if(u.pathname.endsWith('/data/version.json')){
    event.respondWith(fetch(event.request,{cache:'no-store'}).catch(()=>caches.match(event.request))); return;
  }
  if(u.pathname.endsWith('/data/app_data.js')){
    event.respondWith((async()=>{const db=await caches.open(DB_CACHE); return (await db.match('./data/app_data.js')) || fetch(event.request);})()); return;
  }
  event.respondWith((async()=>{
    if(event.request.mode==='navigate'){
      try{
        const res=await fetch(event.request,{cache:'no-store'});
        if(res&&res.ok){const c=await caches.open(SHELL_CACHE); c.put('./index.html',res.clone());}
        return res;
      }catch(e){return caches.match('./index.html');}
    }
    const cached=await caches.match(event.request);
    if(cached) return cached;
    try{const res=await fetch(event.request); if(res&&res.ok){const c=await caches.open(SHELL_CACHE); c.put(event.request,res.clone());} return res;}
    catch(e){throw e;}
  })());
});
