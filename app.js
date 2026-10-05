'use strict';
const D=window.APP_DATA||{roads:[],landmarks:[],meta:{}};
const APP_VERSION='PWA 1.0.29';
const JR=(window.JR_STATIONS||[]).map(x=>({...x,prefecture:'',municipality:''}));
const RELAY=window.RELAY_STOPS||[];
const $=id=>document.getElementById(id);
const origins={sug:null,dest:null,relay:null,season:null,nearby:null,interestSave:null};
let pendingInterestSave=null;
let relayTrail=[];
const FEATURES=[
 ['','すべて'],['history','歴史・街並み'],['shrine','神社・お寺'],['nature','山・自然'],['sea','海・島'],['construction','橋・建設物'],['museum','博物館・資料館'],['onsen','温泉'],['park','公園・花'],['view','展望・景色'],['road_drive','道・ドライブ'],['experience','体験・文化'],['unusual_ui','珍スポット']
];
const PREFECTURE_ORDER=[
'北海道',
'青森県','岩手県','宮城県','秋田県','山形県','福島県',
'茨城県','栃木県','群馬県','埼玉県','千葉県','東京都','神奈川県',
'新潟県','富山県','石川県','福井県','山梨県','長野県','岐阜県','静岡県','愛知県',
'三重県','滋賀県','京都府','大阪府','兵庫県','奈良県','和歌山県',
'鳥取県','島根県','岡山県','広島県','山口県',
'徳島県','香川県','愛媛県','高知県',
'福岡県','佐賀県','長崎県','熊本県','大分県','宮崎県','鹿児島県','沖縄県'
];
const PREFECTURE_INDEX=new Map(PREFECTURE_ORDER.map((p,i)=>[p,i]));
function sortPrefectures(list){
  return [...list].sort((a,b)=>(PREFECTURE_INDEX.get(a)??999)-(PREFECTURE_INDEX.get(b)??999)||a.localeCompare(b,'ja'));
}

const MISSIONS=[
'その土地っぽいお菓子を1つ探す','1000円以内で一番気になったものを選ぶ','コーヒーかお茶を1杯飲む','道の駅の看板とバイクを撮る','「誰が買うんだこれ」と思う商品を探す','地元野菜を1つ見つける','変わった飲み物を1つ探す','この駅で一番いい景色を撮る','500円以内で旅の記念になりそうなものを探す','何も買わずに、この駅の良いところを1つ見つける','ご当地キャラを探す','パン・饅頭・団子のどれかを探す','地元産と書かれた商品を3つ見つける','初めて見る食べ物を1つ探す','ご当地ソフト・アイスを探す','その地域らしい調味料を1つ探す','一番高そうなお土産を探す','一番小さいお土産を探す','面白い商品名を1つ見つける','方言や地名が入った商品を探す','道の駅から見える山・海・川のどれかを撮る','「この場所っぽいな」と思う風景を1枚撮る','建物や看板で気になるデザインを1つ見つける','バイク以外の旅人っぽい乗り物を1台見つける','駐車場で一番遠くから来てそうなナンバーを探す','次回来たら食べてみたいものを1つ決める','その駅でおすすめされている観光地を1つ見つける','駅の掲示板やパンフレットから知らなかった場所を1つ見つける','「今日ここに来てよかった」と思えるものを1つ見つける','何もしないで5分だけ休憩する'
];

function showView(id){document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id===id));document.querySelectorAll('.side button').forEach(x=>x.classList.toggle('active',x.dataset.view===id));if(id==='favorites')renderFavorites();window.scrollTo({top:0,behavior:'smooth'});}
document.querySelectorAll('.side button').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
function closeModal(){$('modal').classList.add('hidden');$('modalBody').innerHTML='';}
function modal(html){$('modalBody').innerHTML=html;$('modal').classList.remove('hidden');}
function openAbout(){modal(`<h2>道の途中。</h2>
  <p><b>Ver${esc(APP_VERSION)}</b></p>
  <p>乗る理由を作ったり、行ってみたい場所を眺めたりするためのツールです。</p>
  <details class="about-disclaimer">
    <summary>⚠ 免責事項</summary>
    <div class="about-disclaimer-body">
      <p>「道の途中。」は、ツーリングやドライブの行き先選びを楽しむための補助ツールです。掲載している施設情報・位置情報・道路情報・ルート候補などは、正確性や最新性を保証するものではありません。</p>
      <p>実際の走行時は、現地の道路標識・交通規制・通行止め・施設案内などを優先してください。</p>
      <p><b>125cc以下のルート表示について：</b>高速道路・有料道路を避ける設定を利用した参考ルートであり、すべての道路が車両区分上通行可能であることを保証するものではありません。必ず現地の標識・規制に従ってください。</p>
      <p>天候、道路状況、災害、施設の休業・閉鎖などにより、表示内容と実際の状況が異なる場合があります。</p>
      <p>本アプリの利用によって生じた事故・損害・トラブルについて、製作者は責任を負いかねます。安全を最優先にご利用ください。</p>
      <p>Google Mapsなど外部サービスを開いた場合は、それぞれのサービスの利用条件・案内に従ってください。</p>
    </div>
  </details>
  <p><b>製作者：ぺんた</b><br>Created by ぺんた<br>© 2026 Penta</p>`)}

const CONTACT_EMAIL='penta.michi.2026@gmail.com';
const CONTACT_CATEGORIES=['バグ報告','ポイントズレ報告','要望','オススメ追加'];

function openContact(){
  modal(`<h2>✉ 製作者に連絡</h2>
    <p class="contact-lead">内容に近いカテゴリを選んでください。</p>
    <div class="contact-category-grid">
      ${CONTACT_CATEGORIES.map(c=>`<button type="button" class="contact-category-btn" data-contact-category="${esc(c)}" onclick="contactSelectCategory('${esc(c)}')">${esc(c)}</button>`).join('')}
    </div>
    <form id="contactForm" class="contact-form" onsubmit="sendContact(event)">
      <div id="contactFields" class="contact-fields"><p class="contact-hint">上のカテゴリを選ぶと入力欄が表示されます。</p></div>
    </form>
    <p class="contact-note">メールアプリは不要です。この画面から直接送信できます。</p>`);
}

function contactSelectCategory(category){
  if(!CONTACT_CATEGORIES.includes(category))return;
  const form=$('contactForm'); if(!form)return;
  form.dataset.category=category;
  document.querySelectorAll('.contact-category-btn').forEach(b=>b.classList.toggle('active',b.dataset.contactCategory===category));
  let fields='';
  if(category==='バグ報告'){
    fields=`<label>どの画面で？<input name="screen" placeholder="例：行先ガチャ"></label>
      <label>ひとことで<input name="title" required placeholder="例：ボタンを押しても反応しない"></label>
      <label>詳しい内容<textarea name="details" rows="6" required placeholder="何をした時に、どうなったかを書いてください"></textarea></label>`;
  }else if(category==='ポイントズレ報告'){
    fields=`<label>スポット名<input name="title" required placeholder="例：○○展望台"></label>
      <label>正しい場所のGoogleマップURL<input name="mapUrl" inputmode="url" placeholder="共有リンクを貼り付け"></label>
      <label>詳しい内容<textarea name="details" rows="5" required placeholder="どのくらいずれているか、正しい場所の目印など"></textarea></label>`;
  }else if(category==='要望'){
    fields=`<label>要望のタイトル<input name="title" required placeholder="例：検索条件を追加してほしい"></label>
      <label>詳しい内容<textarea name="details" rows="6" required placeholder="こんな機能がほしい、こうなると使いやすい、など"></textarea></label>`;
  }else{
    fields=`<label>区分<select name="recommendType" required><option value="定番">定番</option><option value="寄り道">寄り道</option></select></label>
      <label>都道府県<input name="prefecture" placeholder="例：広島県"></label>
      <label>おすすめ名称<input name="title" required placeholder="例：○○展望台"></label>
      <label>GoogleマップURL<input name="mapUrl" inputmode="url" placeholder="分かれば共有リンクを貼り付け"></label>
      <label>おすすめポイント<textarea name="details" rows="5" required placeholder="どんな場所か、何がおすすめかを教えてください"></textarea></label>`;
  }
  $('contactFields').innerHTML=`<div class="contact-selected">選択中：<b>${esc(category)}</b></div>${fields}
    <label>返信用メールアドレス（任意）<input name="replyEmail" type="email" autocomplete="email" placeholder="返信が必要な場合だけ"></label>
    <button type="submit" class="primary contact-submit" id="contactSubmitButton">✉ 送信する</button><div id="contactSendStatus" class="contact-send-status" aria-live="polite"></div>`;
}

function sendContact(event){
  event.preventDefault();
  const form=event.currentTarget;
  const category=form.dataset.category||'';
  if(!CONTACT_CATEGORIES.includes(category)){alert('カテゴリを選んでください。');return;}
  if(!form.reportValidity())return;
  submitContactForm(form,category);
}
async function submitContactForm(form,category){
  const fd=new FormData(form);
  const val=name=>String(fd.get(name)||'').trim();
  const payload={
    _subject:`【道の途中。】【${category}】`,
    _template:'table',
    _captcha:'false',
    _honey:'',
    カテゴリ:category,
    内容:val('details'),
    PWA:APP_VERSION,
    DB:localStorage.getItem('michino_db_version')||'2.8.20',
    送信日時:new Date().toLocaleString('ja-JP'),
    端末ブラウザ:navigator.userAgent
  };
  if(val('recommendType'))payload['区分']=val('recommendType');
  if(val('prefecture'))payload['都道府県']=val('prefecture');
  if(val('screen'))payload['画面']=val('screen');
  if(val('title'))payload['タイトル・対象名']=val('title');
  if(val('mapUrl'))payload['Googleマップ']=val('mapUrl');
  if(val('replyEmail'))payload['email']=val('replyEmail');
  const button=$('contactSubmitButton');
  const status=$('contactSendStatus');
  if(button){button.disabled=true;button.textContent='送信中…';}
  if(status){status.className='contact-send-status';status.textContent='送信しています…';}
  try{
    const response=await fetch('https://formsubmit.co/ajax/'+encodeURIComponent(CONTACT_EMAIL),{
      method:'POST',
      headers:{'Content-Type':'application/json','Accept':'application/json'},
      body:JSON.stringify(payload)
    });
    let data=null;
    try{data=await response.json();}catch(e){}
    if(!response.ok || (data&&data.success===false))throw new Error((data&&data.message)||'send failed');
    if(status){status.className='contact-send-status success';status.textContent='送信しました。ご協力ありがとうございます！';}
    form.reset();
    setTimeout(()=>closeModal(),1600);
  }catch(e){
    console.warn('Contact send failed',e);
    if(status){status.className='contact-send-status error';status.textContent='送信できませんでした。通信状態を確認して、もう一度お試しください。';}
  }finally{
    if(button){button.disabled=false;button.textContent='✉ 送信する';}
  }
}

function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function rad(x){return x*Math.PI/180}
function dist(a,b,c,d){const R=6371,p1=rad(a),p2=rad(c),dp=rad(c-a),dl=rad(d-b),q=Math.sin(dp/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;return 2*R*Math.atan2(Math.sqrt(q),Math.sqrt(1-q));}
function bearing(a,b,c,d){const y=Math.sin(rad(d-b))*Math.cos(rad(c)),x=Math.cos(rad(a))*Math.sin(rad(c))-Math.sin(rad(a))*Math.cos(rad(c))*Math.cos(rad(d-b));return (Math.atan2(y,x)*180/Math.PI+360)%360}
function dirText(v){return ['北','北東','東','南東','南','南西','西','北西'][Math.round(v/45)%8]}
function rand(a){return a[Math.floor(Math.random()*a.length)]}
function shuffle(a){for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a}
function useNameNavigation(x){
  if(!x)return false;
  if(x.navMode==='coord')return false;
  if(x.navMode==='name')return true;
  if(x.kind==='道の駅'||x.featureCategory==='road_station')return true;
  if(x.featureCategory==='road')return false;
  return Boolean(x.prefecture||x.municipality||x.category||x.level);
}
function navSearchQuery(x){
  if(!x)return'';
  if((x.navQuery||'').trim())return x.navQuery.trim();
  let name=(x.name||'').trim();
  if((x.kind==='道の駅'||x.featureCategory==='road_station')&&!name.startsWith('道の駅'))name='道の駅 '+name;
  return [x.prefecture||'',name].filter(Boolean).join(' ').trim();
}
function coordTarget(x){return `${x.latRaw||String(x.lat)},${x.lngRaw||String(x.lng)}`}
function navTarget(x){return useNameNavigation(x)?navSearchQuery(x):coordTarget(x)}
function googlePoint(lat,lng,name='',x=null){
  const q=(x&&useNameNavigation(x))?navSearchQuery(x):`${Number(lat)},${Number(lng)}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`
}
function googleFoodSearch(x,style='walk'){
  if(!x)return'#';
  const base=useNameNavigation(x)?navSearchQuery(x):(Number.isFinite(+x.lat)&&Number.isFinite(+x.lng)?`${x.lat},${x.lng}`:navSearchQuery(x));
  const words={walk:'食べ歩き たい焼き 団子 ソフトクリーム 軽食',rest:'カフェ 喫茶店 甘味処 スイーツ ジェラート パン',hearty:'定食 食堂 ラーメン うどん 丼 お好み焼き'};
  const q=`${base} 周辺 ${words[style]||words.walk}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`
}
function googleRoute(origin,pts,vehicle='250'){
  if(!pts.length)return'#';
  const d=pts[pts.length-1],wps=pts.slice(0,-1).map(navTarget).join('|');
  const avoid=vehicle==='125'?'&avoid=highways%2Ctolls':'';
  return `https://www.google.com/maps/dir/?api=1&origin=${origin.lat},${origin.lng}&destination=${encodeURIComponent(navTarget(d))}${wps?`&waypoints=${encodeURIComponent(wps)}`:''}&travelmode=driving${avoid}`;
}
function active(v){return !String(v||'').includes('除外')}
function groupClass(kind){return kind==='道の駅'?'group-road':kind==='定番スポット'?'group-A':'group-B'}
function iconPath(feature){const f=feature||'generic';return `assets/icons/ic_feature_${f}.png`}
function featureOf(x,kind){return kind==='道の駅'?'road_station':(x.featureCategory||'generic')}
function iconBadge(x,kind){return `<div class="icon-badge ${groupClass(kind)}"><img src="${iconPath(featureOf(x,kind))}" onerror="this.src='assets/icons/ic_feature_generic.png'" alt=""></div>`}
function pointKind(x){if(x.groupName)return x.groupName; if(x.level==='A')return'定番スポット';if(x.level==='B')return'寄り道スポット';return'道の駅'}
function mapBtn(x,label='マップで確認'){return `<a class="mapbtn map-check" href="${googlePoint(x.lat,x.lng,x.name,x)}" target="_blank" rel="noopener">🗺 ${label}</a>`}
function routeButtons(origin,pts){if(!origin||!pts||!pts.length)return'';const d=pts[pts.length-1];return `<div class="route-buttons"><a class="mapbtn map-check" href="${googlePoint(d.lat,d.lng,d.name,d)}" target="_blank" rel="noopener">🗺 マップで確認</a><div class="food-search-group"><a class="mapbtn food-walk" href="${googleFoodSearch(d,'walk')}" target="_blank" rel="noopener">🍡 食べ歩き</a><a class="mapbtn food-rest" href="${googleFoodSearch(d,'rest')}" target="_blank" rel="noopener">☕ ひと息</a><a class="mapbtn food-hearty" href="${googleFoodSearch(d,'hearty')}" target="_blank" rel="noopener">🍜 がっつり</a></div><a class="mapbtn bike125" href="${googleRoute(origin,pts,'125')}" target="_blank" rel="noopener">🛵 125cc以下</a><a class="mapbtn bike250" href="${googleRoute(origin,pts,'250')}" target="_blank" rel="noopener">🏍 250cc以上</a></div>`}
function numericValue(selectId,freeId,min,max){const e=$(freeId);if(e&&String(e.value).trim()!==''){const n=+e.value;if(Number.isFinite(n)&&n>=min&&n<=max)return n;}return +$(selectId).value}
function dirText16(v){return ['北','北北東','北東','東北東','東','東南東','南東','南南東','南','南南西','南西','西南西','西','西北西','北西','北北西'][Math.round(v/22.5)%16]}

function renderStartPanels(){['sug','dest','relay','season','nearby'].forEach(k=>{const host=$(k+'Start');host.innerHTML=`<div class="panel start-panel"><h3>📍 スタート地点</h3><div class="origin-status" id="${k}Origin">現在：未設定</div><div class="start-simple"><button class="soft start-current" onclick="useCurrent('${k}')">◎ 現在地を使う</button><button class="soft start-station" onclick="stationPicker('${k}')">🚉 駅を選ぶ</button><div class="map-pick-row"><button class="soft start-map" onclick="openStartMap('${k}')">🗺 Googleマップから選ぶ</button><button class="info-btn" onclick="showMapStartHelp()" title="使い方">ⓘ</button></div><button class="soft reflect-btn start-reflect" onclick="reflectMapLink('${k}')">🔗 コピーしたリンクを反映</button></div></div>`;});}
function setOrigin(k,lat,lng,label){origins[k]={lat:+lat,lng:+lng,label:label||'選択地点'};const host=$(`${k}Origin`);if(host)host.textContent=`現在：${origins[k].label}`;if(k==='interestSave'&&pendingInterestSave)showInterestSaveDialog();}
function parseCoords(s){const t=decodeURIComponent(String(s||'').replace(/\+/g,'%20'));const pats=[/@(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)/,/!3d(-?\d{1,2}(?:\.\d+)?)!4d(-?\d{1,3}(?:\.\d+)?)/,/[?&](?:q|query|ll|center)=(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)/,/(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)/];for(const p of pats){const m=t.match(p);if(m){const a=+m[1],b=+m[2];if(Math.abs(a)<=90&&Math.abs(b)<=180)return[a,b]}}return null}
function firstUrl(s){const m=String(s||'').match(/https?:\/\/[^\s]+/i);return m?m[0].replace(/[\])。,]+$/,''):null}
function openStartMap(k){window.open('https://www.google.com/maps','_blank','noopener')}
function showMapStartHelp(){modal(`<h2>Googleマップから選ぶ</h2><p>ブラウザでGoogleマップが開きます。スタート地点にしたい場所を選択し、<b>共有 → リンクをコピー</b>してください。</p><p>この画面に戻り、<b>「リンクを反映」</b>を押すとスタート地点に設定されます。</p>`)}
async function clipboardText(){try{return(await navigator.clipboard.readText()).trim()}catch(e){const v=window.prompt('Googleマップでコピーした共有リンクを貼り付けてください。','');return(v||'').trim()}}
async function resolveMapLink(raw){const direct=parseCoords(raw);if(direct)return direct;const u=firstUrl(raw);if(!u)return null;try{const r=await fetch(`/resolve-map?url=${encodeURIComponent(u)}`,{cache:'no-store'});if(r.ok){const j=await r.json();if(j&&j.ok&&Number.isFinite(+j.lat)&&Number.isFinite(+j.lng))return[+j.lat,+j.lng]}}catch(e){}return null}
async function reflectMapLink(k){const raw=await clipboardText();if(!raw)return alert('Googleマップで共有リンクをコピーしてから「リンクを反映」を押してください。');const q=await resolveMapLink(raw);if(!q)return alert('共有リンクから場所を取得できませんでした。Googleマップで地点を選び、共有からリンクをコピーして再試行してください。');setOrigin(k,q[0],q[1],'Googleマップ共有地点');alert('スタート地点を反映しました。')}
function geo(){return new Promise((resolve,reject)=>navigator.geolocation?navigator.geolocation.getCurrentPosition(p=>resolve({lat:p.coords.latitude,lng:p.coords.longitude}),reject,{enableHighAccuracy:true,timeout:10000,maximumAge:30000}):reject(new Error('geolocation')))}
async function useCurrent(k){try{const p=await geo();setOrigin(k,p.lat,p.lng,'現在地')}catch(e){alert('現在地を取得できません。Windowsまたはブラウザの位置情報を許可して、もう一度お試しください。')}}
let stationAdminReady=false;
function estimateStationAdmin(){if(stationAdminReady)return;const anchors=[...D.roads,...D.landmarks].filter(x=>x.prefecture&&x.municipality&&Number.isFinite(+x.lat)&&Number.isFinite(+x.lng));for(const st of JR){let best=null,bd=1e9;for(const a of anchors){const dx=st.lat-(+a.lat),dy=(st.lng-(+a.lng))*Math.cos(rad(st.lat)),q=dx*dx+dy*dy;if(q<bd){bd=q;best=a}}if(best){st.prefecture=best.prefecture;st.municipality=best.municipality}}stationAdminReady=true;}
function stationPicker(k){estimateStationAdmin();const prefs=sortPrefectures(new Set(JR.map(x=>x.prefecture).filter(Boolean)));modal(`<h2>🚉 駅を選ぶ</h2><div class="meta">県 → 市区町村 → 駅名 の順に選択してください。</div><label>県<select id="stPref" onchange="fillStationCities('${k}')"><option>すべて</option>${prefs.map(p=>`<option>${esc(p)}</option>`).join('')}</select></label><label>市区町村<select id="stCity" onchange="fillStationModal('${k}')"><option>すべて</option></select></label><label>駅名<select id="stStation"></select></label><button class="primary" style="width:100%;margin-top:12px" onclick="applyStationModal('${k}')">この駅をスタートにする</button>`);fillStationCities(k)}
function fillStationCities(k){const p=$('stPref').value,cs=[...new Set(JR.filter(x=>p==='すべて'||x.prefecture===p).map(x=>x.municipality).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'ja'));$('stCity').innerHTML='<option>すべて</option>'+cs.map(c=>`<option>${esc(c)}</option>`).join('');fillStationModal(k)}
function fillStationModal(k){const p=$('stPref').value,c=$('stCity').value;const list=JR.filter(x=>(p==='すべて'||x.prefecture===p)&&(c==='すべて'||x.municipality===c)).sort((a,b)=>a.name.localeCompare(b.name,'ja')).slice(0,1000);$('stStation').innerHTML=list.map(x=>`<option value="${JR.indexOf(x)}">${esc(x.name)}駅</option>`).join('')}
function applyStationModal(k){const idx=+$('stStation').value,st=JR[idx];if(!st)return alert('駅を選択してください。');if(k==='interestSave'){closeModal();setOrigin(k,st.lat,st.lng,st.name+'駅');return;}setOrigin(k,st.lat,st.lng,st.name+'駅');closeModal()}

function requireOrigin(k){const o=origins[k];if(!o){alert('スタート地点を設定してください。');return null}return o}
function runSugoroku(){const o=requireOrigin('sug');if(!o)return;const radius=numericValue('sugRadius','sugRadiusFree',1,2000),goal=numericValue('sugTravel','sugTravelFree',1,3000);let n=+$('sugCount').value;if(!n)n=1+Math.floor(Math.random()*5);const pool=D.roads.filter(x=>active(x.gacha)).map(x=>({...x,d:dist(o.lat,o.lng,x.lat,x.lng)})).filter(x=>x.d<=radius).sort((a,b)=>a.d-b.d);if(pool.length<n)return $('sugResult').innerHTML='<p>条件内の道の駅が不足しています。最大直線距離を広げてください。</p>';const targetStep=Math.max(15,goal/n),route=[];let prev=o,remaining=[...pool];for(let i=0;i<n;i++){let choices=remaining.map(x=>({...x,sd:dist(prev.lat,prev.lng,x.lat,x.lng)})).sort((a,b)=>Math.abs(a.sd-targetStep)-Math.abs(b.sd-targetStep)).slice(0,Math.min(30,remaining.length));const p=rand(choices);route.push(p);remaining=remaining.filter(x=>x.id!==p.id);prev=p}const final=route[route.length-1];const mission=$('sugMission').checked?rand(MISSIONS):'ミッションなし';$('sugResult').classList.remove('empty');$('sugResult').innerHTML=`<div class="goal"><small>GOAL</small><br><b>${esc(final.name)}</b></div><div class="mission">${esc(mission)}</div><div>${route.map((x,i)=>`<div class="route-line"><b>${i+1}. ${esc(x.name)}</b><div class="meta">${esc(x.prefecture)} ${esc(x.municipality||'')} / 直線距離 約${dist(o.lat,o.lng,x.lat,x.lng).toFixed(1)}km</div></div>`).join('')}</div><div class="actions">${routeButtons(o,route)}<button class="soft" onclick='saveFavorite(${JSON.stringify({mode:'道の駅すごろく',title:final.name,startLabel:o.label,origin:o,points:route.map(x=>({name:x.name,lat:x.lat,lng:x.lng,latRaw:x.latRaw||String(x.lat),lngRaw:x.lngRaw||String(x.lng),kind:'道の駅',prefecture:x.prefecture,featureCategory:'road_station',navMode:'name',navQuery:x.navQuery||navSearchQuery(x)})),routeSummary:route.map((x,i)=>`${i+1}. ${x.name}`).join(' → ')}).replaceAll("'","&#39;")})'>お気に入りに保存</button><button class="soft" onclick="resetResult('sug')">結果をリセット</button></div>`}
function resetResult(k){$(k+'Result').classList.add('empty');$(k+'Result').innerHTML='条件を設定してください。'}
function runDestination(){const o=requireOrigin('dest');if(!o)return;const target=numericValue('destDist','destDistFree',1,2000),tol=numericValue('destTol','destTolFree',1,500),mood=$('destMood').value;let pool=[];pool.push(...D.roads.filter(x=>active(x.gacha)).map(x=>({...x,kind:'道の駅'})));pool.push(...D.landmarks.filter(x=>active(x.gacha)).map(x=>({...x,kind:pointKind(x)})));pool=pool.map(x=>({...x,d:dist(o.lat,o.lng,x.lat,x.lng)})).filter(x=>Math.abs(x.d-target)<=tol);if(mood!=='なんでも'&&mood!=='ランドマーク'){const re={海:/海|岬|島|港|海岸/,山:/山|高原|峠|渓谷|滝/,田舎:/田園|棚田|農|里|高原/,市街地:/街|駅|市場|公園|城/}[mood];const q=pool.filter(x=>re&&re.test(`${x.name} ${x.category||''} ${x.summary||''}`));if(q.length)pool=q}if(mood==='ランドマーク')pool=pool.filter(x=>x.kind!=='道の駅');if(!pool.length)return $('destResult').innerHTML='<p>この距離帯に候補がありません。距離か許容幅を変更してください。</p>';const x=rand(pool);$('destResult').classList.remove('empty');$('destResult').innerHTML=`${spotCard(x,x.kind,x.d,false,null,0,o)}<div class="actions"><button class="soft" onclick='saveFavorite(${JSON.stringify({mode:'行先ガチャ',title:x.name,startLabel:o.label,origin:o,points:[{name:x.name,lat:x.lat,lng:x.lng,latRaw:x.latRaw||String(x.lat),lngRaw:x.lngRaw||String(x.lng),kind:x.kind,prefecture:x.prefecture,featureCategory:x.featureCategory,navMode:useNameNavigation(x)?'name':'coord',navQuery:useNameNavigation(x)?navSearchQuery(x):''}],routeSummary:''}).replaceAll("'","&#39;")})'>お気に入りに保存</button></div>`}
function runRelay(){const o=requireOrigin('relay');if(!o)return;const t=numericValue('relayDist','relayDistFree',1,500),dir=$('relayDir').value;const options={北:[337.5,0,22.5],東:[67.5,90,112.5],南:[157.5,180,202.5],西:[247.5,270,292.5]};const targetBearing=rand(options[dir]||options.北);let pool=RELAY.map(x=>({...x,d:dist(o.lat,o.lng,x.lat,x.lng),br:bearing(o.lat,o.lng,x.lat,x.lng)})).filter(x=>Math.abs(x.d-t)<=Math.max(3,t*.75)&&Math.abs(((x.br-targetBearing+540)%360)-180)<=32);if(!pool.length)pool=RELAY.map(x=>({...x,d:dist(o.lat,o.lng,x.lat,x.lng),br:bearing(o.lat,o.lng,x.lat,x.lng)})).sort((a,b)=>(Math.abs(a.d-t)+Math.abs(((a.br-targetBearing+540)%360)-180)/8)-(Math.abs(b.d-t)+Math.abs(((b.br-targetBearing+540)%360)-180)/8)).slice(0,10);if(!pool.length)return alert('候補がありません。');const x=rand(pool);relayTrail.push(x);$('relayResult').classList.remove('empty');$('relayResult').innerHTML=`<h3>${esc(x.name)}</h3><div class="meta">距離：約${x.d.toFixed(1)}km / 選択：${esc(dir)} → ガチャ：${dirText16(targetBearing)} / 実際：${dirText16(x.br)}</div><div class="actions">${routeButtons(o,[x])}<button class="soft" onclick='saveFavorite(${JSON.stringify({mode:'乗り継ぎガチャ',title:x.name,startLabel:o.label,origin:o,points:[{name:x.name,lat:x.lat,lng:x.lng,latRaw:x.latRaw||String(x.lat),lngRaw:x.lngRaw||String(x.lng),kind:'目的地'}],routeSummary:''}).replaceAll("'","&#39;")})'>お気に入りに保存</button></div>`;setOrigin('relay',x.lat,x.lng,x.name);$('relayHistory').innerHTML=relayTrail.length?`<div class="panel"><b>今回の乗り継ぎ</b><div class="meta">${relayTrail.map((x,i)=>`${i+1}. ${esc(x.name)}`).join(' → ')}</div></div>`:''}
function currentSeason(){const m=new Date().getMonth()+1;return m>=3&&m<=5?'春':m>=6&&m<=8?'夏':m>=9&&m<=11?'秋':'冬'}
function seasonMatch(x,s){const t=`${x.name} ${x.category||''} ${x.summary||''} ${x.featureLabel||''}`;const map={春:/桜|梅|菜の花|芝桜|花畑|チューリップ|藤|新緑|公園/,夏:/海|海岸|岬|湖|滝|高原|ひまわり|渓谷|湿原|島|展望/,秋:/紅葉|銀杏|すすき|棚田|田園|山|峠|高原|渓谷|峡谷/,冬:/雪|氷|樹氷|冬|温泉|流氷|霧氷|雪景色|合掌/};return map[s].test(t)}
function runSeason(){const o=requireOrigin('season');if(!o)return;let s=$('seasonSelect').value;if(s==='auto')s=currentSeason();const r=numericValue('seasonRadius','seasonRadiusFree',1,2000);let all=D.landmarks.filter(x=>active(x.gacha)&&seasonMatch(x,s)).map(x=>({...x,d:dist(o.lat,o.lng,x.lat,x.lng),kind:pointKind(x)})).sort((a,b)=>a.d-b.d),list=all.filter(x=>x.d<=r),fallback=false;if(!list.length){list=all.slice(0,12);fallback=true}else list=list.slice(0,12);$('seasonResult').innerHTML=(fallback?`<div class="panel full">圏内に候補がないため、近い${s}の候補を表示します。</div>`:'')+list.map(x=>spotCard(x,x.kind,x.d,false,`saveSingle('${escJs('季節を走る')}','${escJs(x.name)}',${x.lat},${x.lng},'${escJs(x.kind)}','${escJs(o.label)}',${o.lat},${o.lng})`,0,o)).join('')}
function runNearby(){const o=requireOrigin('nearby');if(!o)return;const t=numericValue('nearbyDist','nearbyDistFree',1,2000),type=$('nearbyType').value,min=Math.max(0,t-10),max=t+10;let pool=[];if(type==='all'||type==='road')pool.push(...D.roads.filter(x=>active(x.gacha)).map(x=>({...x,kind:'道の駅'})));if(type==='all'||type==='A')pool.push(...D.landmarks.filter(x=>active(x.gacha)&&x.level==='A').map(x=>({...x,kind:'定番スポット'})));if(type==='all'||type==='B')pool.push(...D.landmarks.filter(x=>active(x.gacha)&&x.level==='B').map(x=>({...x,kind:'寄り道スポット'})));pool=pool.map(x=>({...x,d:dist(o.lat,o.lng,x.lat,x.lng)})).filter(x=>x.d>=min&&x.d<=max).sort((a,b)=>a.d-b.d);window._nearby={origin:o,list:pool.slice(0,80)};$('nearbyResult').innerHTML=`<div class="panel full">${t}±10km / ${pool.length}件${pool.length>80?'（近い80件を表示）':''}</div>`+window._nearby.list.map((x,i)=>spotCard(x,x.kind,x.d,false,`saveSingle('ここからどこ行く？','${escJs(x.name)}',${x.lat},${x.lng},'${escJs(x.kind)}','${escJs(o.label)}',${o.lat},${o.lng})`,i,o)).join('')}
function selectedNearby(){return [...document.querySelectorAll('.near-check:checked')].map(x=>window._nearby.list[+x.dataset.i]).slice(0,8)}
function openNearbyRoute(){const pts=selectedNearby();if(!pts.length)return alert('場所を選択してください。');window.open(googleRoute(window._nearby.origin,pts),'_blank','noopener')}
function saveNearbySelected(){const pts=selectedNearby();if(!pts.length)return alert('保存する場所を選択してください。');const o=window._nearby.origin;saveFavorite({mode:'ここからどこ行く？',title:pts[pts.length-1].name,startLabel:o.label,origin:o,points:pts.map(x=>({name:x.name,lat:x.lat,lng:x.lng,latRaw:x.latRaw||String(x.lat),lngRaw:x.lngRaw||String(x.lng),kind:x.kind,prefecture:x.prefecture,featureCategory:x.featureCategory,navMode:useNameNavigation(x)?'name':'coord',navQuery:useNameNavigation(x)?navSearchQuery(x):''})),routeSummary:''})}
function escJs(s){return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'")}
function saveSingle(mode,name,lat,lng,kind,label,ola,oln){
  const x=[...D.roads,...D.landmarks].find(v=>v.name===name&&Math.abs((+v.lat)-(+lat))<1e-7&&Math.abs((+v.lng)-(+lng))<1e-7);
  const navMode=x?(useNameNavigation(x)?'name':'coord'):'coord';
  const navQuery=x&&navMode==='name'?navSearchQuery(x):'';
  saveFavorite({mode,title:name,startLabel:label,origin:{lat:ola,lng:oln,label},points:[{name,lat,lng,latRaw:x?.latRaw||String(lat),lngRaw:x?.lngRaw||String(lng),kind,prefecture:x?.prefecture||'',featureCategory:x?.featureCategory||'',navMode,navQuery}],routeSummary:''})
}
function beginInterestSave(name,lat,lng,kind){
  pendingInterestSave={name,lat:+lat,lng:+lng,kind};
  origins.interestSave=null;
  showInterestSaveDialog();
}
function showInterestSaveDialog(){
  if(!pendingInterestSave)return;
  const o=origins.interestSave;
  modal(`<h2>📍 スタート地点も一緒に保存</h2>
    <p class="meta">${esc(pendingInterestSave.name)} を「気になる場所」として保存します。あとで125cc以下／250cc以上ルートを開けるよう、スタート地点も登録します。</p>
    <div class="panel start-panel"><h3>📍 スタート地点</h3><div class="origin-status" id="interestSaveOrigin">現在：${esc(o?.label||'未設定')}</div>
      <div class="start-simple">
        <button class="soft start-current" onclick="useCurrent('interestSave')">◎ 現在地を使う</button>
        <button class="soft start-station" onclick="stationPicker('interestSave')">🚉 駅を選ぶ</button>
        <div class="map-pick-row"><button class="soft start-map" onclick="openStartMap('interestSave')">🗺 Googleマップから選ぶ</button><button class="info-btn" onclick="showMapStartHelp()">ⓘ</button></div>
        <button class="soft reflect-btn start-reflect" onclick="reflectMapLink('interestSave')">🔗 コピーしたリンクを反映</button>
      </div>
    </div>
    <button class="primary" style="width:100%;margin-top:12px" onclick="commitInterestSave()" ${o?'':'disabled'}>この条件で保存</button>`);
}
function commitInterestSave(){
  if(!pendingInterestSave)return;
  const o=origins.interestSave;if(!o)return alert('スタート地点を設定してください。');
  const x=pendingInterestSave;
  saveSingle('気になる場所',x.name,x.lat,x.lng,x.kind,o.label,o.lat,o.lng);
  pendingInterestSave=null;origins.interestSave=null;closeModal();
}
function fillSelectors(){const prefs=sortPrefectures(new Set([...D.roads,...D.landmarks].map(x=>x.prefecture).filter(Boolean)));for(const id of ['interestPref','browsePref'])$(id).innerHTML=prefs.map(p=>`<option>${esc(p)}</option>`).join('');for(const id of ['interestFeature','browseFeature'])$(id).innerHTML=FEATURES.map(([v,l])=>`<option value="${v}">${l}</option>`).join('')}
function runInterest(){const p=$('interestPref').value,t=$('interestType').value,f=$('interestFeature').value;let pool=[];if((t==='all'||t==='road')&&!f)pool.push(...D.roads.filter(x=>x.prefecture===p).map(x=>({...x,kind:'道の駅'})));if(t==='all'||t==='A')pool.push(...D.landmarks.filter(x=>x.prefecture===p&&x.level==='A'&&featureMatch(x,f)).map(x=>({...x,kind:'定番スポット'})));if(t==='all'||t==='B')pool.push(...D.landmarks.filter(x=>x.prefecture===p&&x.level==='B'&&featureMatch(x,f)).map(x=>({...x,kind:'寄り道スポット'})));pool.sort((a,b)=>a.name.localeCompare(b.name,'ja'));$('interestResult').innerHTML=`<div class="panel full">${esc(p)} / ${pool.length}件</div>`+pool.map(x=>spotCard(x,x.kind,null,false,`beginInterestSave('${escJs(x.name)}',${x.lat},${x.lng},'${escJs(x.kind)}')`,0,null,`showInterestDetailById('${escJs(x.id)}','${escJs(x.kind)}')`)).join('')}
function uiCategoryTags(x){
  const tags=new Set(),fc=x.featureCategory||'',text=`${x.name||''} ${x.featureLabel||''}`;
  const add=(tag,re)=>{if(re.test(text))tags.add(tag)};
  if(fc==='castle_history')tags.add('history');
  if(fc==='shrine_temple')tags.add('shrine');
  if(['mountain','waterfall','lake'].includes(fc))tags.add('nature');
  if(['coast','cape','island','lighthouse','port'].includes(fc))tags.add('sea');
  if(['bridge','dam'].includes(fc))tags.add('construction');
  if(fc==='museum')tags.add('museum');
  if(fc==='onsen')tags.add('onsen');
  if(fc==='park')tags.add('park');
  if(fc==='observatory')tags.add('view');
  if(fc==='road')tags.add('road_drive');
  add('history',/城跡|城郭|史跡|遺跡|古墳|宿場|街並|町並|歴史|武家|陣屋|関所|古民家|旧[^ ]*(邸|屋敷)/);
  add('shrine',/神社|大社|神宮|寺|寺院|霊場|札所|観音|不動尊/);
  add('nature',/山|岳|高原|森林|原生林|渓谷|峡谷|峡|滝|湖|池|湿原|鍾乳洞|洞窟|巨木|奇岩|岩場/);
  add('sea',/海|海岸|浜|岬|島|灯台|港|湾|磯|海峡/);
  add('construction',/橋|ダム|堰|水門|隧道|トンネル|塔|高架|水路|発電所|堤防|閘門|用水/);
  add('museum',/博物館|資料館|記念館|美術館|科学館|展示館|郷土館|歴史館|ミュージアム|資料室|世界遺産センター/);
  add('onsen',/温泉|湯治|共同浴場|足湯/);
  add('park',/公園|庭園|花園|植物園|フラワー|桜並木|花畑/);
  add('view',/展望|夜景|眺望|パノラマ|棚田|ビューポイント/);
  add('road_drive',/街道|旧道|峠|道路|スカイライン|ドライブ|鉄道跡|廃線|旧線|旧駅|駅跡/);
  add('experience',/工房|市場|牧場|農園|ワイナリー|醸造|酒蔵|陶芸|体験|工芸|伝統|劇場|水族館|動物園|文化館|交流館/);
  if((fc==='unusual'||fc==='generic'||!fc)&&tags.size===0)tags.add('unusual_ui');
  return tags;
}
function featureMatch(x,f){if(!f)return true;return uiCategoryTags(x).has(f)}
function runBrowse(){const p=$('browsePref').value,t=$('browseType').value,f=$('browseFeature').value,q=$('browseQuery').value.trim();let pool=[];if((t==='all'||t==='road')&&!f)pool.push(...D.roads.filter(x=>x.prefecture===p).map(x=>({...x,kind:'道の駅'})));if(t==='all'||t==='A')pool.push(...D.landmarks.filter(x=>x.prefecture===p&&x.level==='A'&&featureMatch(x,f)).map(x=>({...x,kind:'定番スポット'})));if(t==='all'||t==='B')pool.push(...D.landmarks.filter(x=>x.prefecture===p&&x.level==='B'&&featureMatch(x,f)).map(x=>({...x,kind:'寄り道スポット'})));if(q)pool=pool.filter(x=>x.name.includes(q));pool.sort((a,b)=>a.name.localeCompare(b.name,'ja'));$('browseResult').innerHTML=`<div class="panel full">${esc(p)} / ${pool.length}件</div>`+pool.map(x=>spotCard(x,x.kind)).join('')}
function spotMeta(x,kind,d){
  const parts=[x.prefecture||'',x.municipality||''].filter(Boolean);
  const feature=(x.featureLabel||x.category||'').trim();
  if(kind!=='道の駅')parts.push(kind);
  if(feature && feature!==kind && feature!=='道の駅')parts.push(feature);
  if(Number.isFinite(d))parts.push('約'+d.toFixed(1)+'km');
  return parts.join(' / ');
}
function spotCard(x,kind,d,selectable=false,saveAction=null,index=0,routeOrigin=null,detailAction=null){const navActions=routeOrigin?routeButtons(routeOrigin,[x]):mapBtn(x);return `<div class="spot-card"><div class="spot-main${detailAction?' detail-clickable':''}"${detailAction?` onclick="${detailAction}" role="button" tabindex="0"`:''}>${selectable?`<input class="spot-select near-check" type="checkbox" data-i="${index}">`:''}${iconBadge(x,kind)}<div class="spot-info"><h3>${esc(x.name)}</h3><div class="meta">${esc(spotMeta(x,kind,d))}</div>${x.summary?`<div class="meta">${esc(x.summary)}</div>`:''}</div></div><div class="actions">${navActions}${saveAction?`<button class="soft" onclick="${saveAction}">保存</button>`:''}</div></div>`}
function interestItemById(id,kind){const src=kind==='道の駅'?D.roads:D.landmarks;const x=src.find(v=>String(v.id)===String(id));return x?{...x,kind}:null}
function showInterestDetailById(id,kind){const x=interestItemById(id,kind);if(!x)return;const details=[];if(x.summary)details.push(`<p>${esc(x.summary)}</p>`);if(x.access)details.push(`<div class="detail-block"><b>🚗 アクセス</b><div>${esc(x.access)}</div></div>`);if(x.arrivalPointType)details.push(`<div class="detail-block"><b>📍 到着目安</b><div>${esc(x.arrivalPointType)}</div></div>`);modal(`<h2 class="detail-title">${esc(x.name)}</h2><div class="meta detail-meta">${esc(spotMeta(x,kind,null))}</div>${details.join('')||'<p class="meta">この地点の追加説明は登録されていません。</p>'}<div class="route-buttons detail-route">${mapBtn(x,'Googleマップで確認')}</div>`)}

function favoriteKey(){return'michinotochu_favorites_v2'}
function loadFavorites(){try{return JSON.parse(localStorage.getItem(favoriteKey())||'[]')}catch(e){return[]}}
function saveFavorite(obj){let a=loadFavorites();if(a.length>=20)return alert('保存上限です。不要なコースを削除してください。');obj.savedAt=new Date().toISOString();obj.id=Date.now()+'_'+Math.random().toString(36).slice(2,7);a.unshift(obj);localStorage.setItem(favoriteKey(),JSON.stringify(a));alert('お気に入りコースに保存しました。');}
function renderFavorites(){const a=loadFavorites();$('favoriteList').innerHTML=a.length?a.map((x,i)=>{const pts=x.points||[],distance=x.origin&&pts.length?dist(x.origin.lat,x.origin.lng,pts[pts.length-1].lat,pts[pts.length-1].lng):null;return `<div class="fav-card"><div class="fav-top"><div><span class="pill">${esc(x.mode)}</span><h3>${esc(x.title)}</h3></div><input type="checkbox" class="fav-check" data-id="${esc(x.id)}"></div>${x.routeSummary?`<div class="route-summary">${esc(x.routeSummary)}</div>`:''}<div class="meta">スタート：${esc(x.startLabel||'未設定')} / 立ち寄り ${pts.length}件${Number.isFinite(distance)?` / 直線 約${distance.toFixed(1)}km`:''}<br>保存日 ${new Date(x.savedAt).toLocaleDateString('ja-JP')}</div><div class="actions"><button class="soft" onclick="favoriteDetail(${i})">コースを見る</button></div>${x.origin&&pts.length?routeButtons(x.origin,pts):''}</div>`}).join(''):'<div class="panel">保存されたコースはありません。</div>'}
function favoriteDetail(i){const x=loadFavorites()[i];if(!x)return;modal(`<h2>${esc(x.title)}</h2><span class="pill">${esc(x.mode)}</span><p class="meta">スタート：${esc(x.startLabel||'未設定')}</p>${x.routeSummary?`<p>${esc(x.routeSummary)}</p>`:''}<div class="station-list">${(x.points||[]).map((p,j)=>`<div class="station-btn"><span><b>${j+1}. ${esc(p.name)}</b><small>${esc(p.kind||'')}</small></span></div>`).join('')}</div>${x.origin&&(x.points||[]).length?routeButtons(x.origin,x.points):''}`)}
function deleteSelectedFavorites(){const ids=new Set([...document.querySelectorAll('.fav-check:checked')].map(x=>x.dataset.id));if(!ids.size)return alert('削除するコースを選択してください。');localStorage.setItem(favoriteKey(),JSON.stringify(loadFavorites().filter(x=>!ids.has(x.id))));renderFavorites()}

function initChoiceUI(){
  document.querySelectorAll('.choice-grid[data-target]').forEach(grid=>{const id=grid.dataset.target,sel=$(id);if(!sel)return;const vals=(grid.dataset.values||'').split(','),labels=(grid.dataset.labels||'').split(',');grid.innerHTML=vals.map((v,i)=>`<button type="button" data-value="${esc(v)}">${esc(labels[i]||((/^\d+$/.test(v))?v+' km':v))}</button>`).join('');const paint=()=>grid.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.value===sel.value));grid.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{sel.value=b.dataset.value;const free=$(id+'Free');if(free)free.value='';paint()}));paint();});
  document.querySelectorAll('.direction-grid[data-target]').forEach(grid=>{const sel=$(grid.dataset.target);const paint=()=>grid.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.value===sel.value));grid.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{sel.value=b.dataset.value;paint()}));paint();});
  document.querySelectorAll('.free-number input').forEach(inp=>inp.addEventListener('input',()=>{if(inp.value!==''){const base=inp.id.replace(/Free$/,'');document.querySelectorAll(`.choice-grid[data-target="${base}"] button`).forEach(b=>b.classList.remove('active'));}}));
  document.querySelectorAll('.toggle-choice button').forEach(b=>b.addEventListener('click',()=>{const on=b.dataset.mission==='on';$('sugMission').checked=on;document.querySelectorAll('.toggle-choice button').forEach(x=>x.classList.toggle('active',x===b));}));
}
const RETURN_STATE_KEY='michinotochu_return_state_v1';
function saveReturnState(){
  try{
    const active=document.querySelector('.view.active')?.id||'home';
    const ids=['sugResult','destResult','relayResult','relayHistory','seasonResult','nearbyResult','interestResult'];
    const results={};
    ids.forEach(id=>{const el=$(id);if(el)results[id]=el.innerHTML;});
    localStorage.setItem(RETURN_STATE_KEY,JSON.stringify({
      ts:Date.now(),active,scrollY:window.scrollY,results,
      origins:JSON.parse(JSON.stringify(origins)),
      relayTrail:JSON.parse(JSON.stringify(relayTrail))
    }));
  }catch(e){console.warn('return state save failed',e)}
}
function restoreReturnState(){
  try{
    const raw=localStorage.getItem(RETURN_STATE_KEY);
    if(!raw)return;
    localStorage.removeItem(RETURN_STATE_KEY);
    const st=JSON.parse(raw);
    if(!st||!st.ts||Date.now()-st.ts>30*60*1000)return;
    if(st.origins&&typeof st.origins==='object')Object.keys(origins).forEach(k=>origins[k]=st.origins[k]||null);
    if(Array.isArray(st.relayTrail))relayTrail=st.relayTrail;
    if(st.results)Object.entries(st.results).forEach(([id,html])=>{const el=$(id);if(el&&typeof html==='string')el.innerHTML=html;});
    if(st.active&&$(st.active))showView(st.active);
    setTimeout(()=>window.scrollTo({top:Number(st.scrollY)||0,behavior:'auto'}),0);
  }catch(e){
    localStorage.removeItem(RETURN_STATE_KEY);
    console.warn('return state restore failed',e);
  }
}
document.addEventListener('click',e=>{
  const a=e.target.closest&&e.target.closest('a.mapbtn');
  if(a&&String(a.href||'').includes('google.com/maps/'))saveReturnState();
});
function init(){renderStartPanels();fillSelectors();initChoiceUI();const fv=$('footerVersion');if(fv)fv.textContent=APP_VERSION+' / DB Ver'+(localStorage.getItem('michino_db_version')||'2.8.20');restoreReturnState();}
init();
