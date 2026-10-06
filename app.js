'use strict';
const D=window.APP_DATA||{roads:[],landmarks:[],meta:{}};
const APP_VERSION='PWA 1.5.15';
const JR=(window.JR_STATIONS||[]).map(x=>({...x,prefecture:'',municipality:''}));
const RELAY=window.RELAY_STOPS||[];
const MAPS_RESOLVER_URL='https://crimson-dust-53e2.yasutaka5262.workers.dev/';
const $=id=>document.getElementById(id);
const origins={sug:null,dest:null,relay:null,season:null,nearby:null,ride:null,detour:null,interestSave:null};
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

function showView(id){document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id===id));document.querySelectorAll('.side button').forEach(x=>x.classList.toggle('active',x.dataset.view===id));if(id==='favorites')renderFavorites();if(id==='trip')renderTripHistory();window.scrollTo({top:0,behavior:'smooth'});}
document.querySelectorAll('.side button').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
function closeModal(){$('modal').classList.add('hidden');$('modalBody').innerHTML='';}
function modal(html){$('modalBody').innerHTML=html;$('modal').classList.remove('hidden');}
function openUsageGuide(){
  const items=[
    {icon:'🎲',title:'道の駅すごろく',feature:'道の駅をいくつかつないで、走る理由そのものを作るメニュー。',steps:['スタート地点を決める','目的地までの最大直線距離と、目標総走行距離を選ぶ','立ち寄る道の駅の数とミッション有無を決める','「すごろく開始！」でルート候補を見る']},
    {icon:'📍',title:'行先ガチャ',feature:'距離と雰囲気だけ決めて、行き先を1か所ランダムに選ぶ。',steps:['スタート地点を決める','行きたい距離と許容幅を選ぶ','海・山・田舎・市街地など雰囲気を選ぶ','「行先ガチャ！」で目的地を決める']},
    {icon:'🔗',title:'乗り継ぎガチャ',feature:'次の行き先を少しずつ決めながら、行き当たりばったりで走る。',steps:['最初のスタート地点を決める','次に進む距離と方角を選ぶ','「次のマスを決める！」を押す','到着候補が次のスタートになり、続けて乗り継げる']},
    {icon:'🛣️',title:'寄り道しよう',feature:'最終目的地は変えず、途中に小さな道草を1つ足す。',steps:['スタート地点と最終目的地を設定する','道草レベルを選ぶ','景色・甘味・カフェ・温泉など種類を選ぶ','基準地点と半径を決めて「途中でこれ、どう？」を押す']},
    {icon:'🧩',title:'ここからどこ行く？',feature:'「このくらい先」にある登録スポットを距離帯から探す。',steps:['スタート地点を決める','どのくらい先まで行くか選ぶ','道の駅・定番・寄り道など対象を選ぶ','「この条件で探す」で候補を見る']},
    {icon:'🌤️',title:'今日の走り方',feature:'距離・気分・方角から、今日ちょうどよさそうな走り方を提案する。',steps:['スタート地点を決める','今日はどのくらい走るか選ぶ','景色・食べ物・癒しなど気分を選ぶ','方角を選び「この感じで探す！」を押す','結果画面の「探すものジャンルを変える」から、大ジャンルはそのままで景色・道・峠・歴史・建築・カフェ・パン・温泉など細かい探し方を切り替えられる','検索エリアと検索テーマを確認してGoogle Mapsでも探せる']},
    {icon:'🌸',title:'季節を走る',feature:'春夏秋冬の景色や、その時期らしい場所を探す。',steps:['スタート地点を決める','季節を選ぶ。今の季節は自動選択も可能','最大直線距離を決める','「この条件で季節の候補を見る」で探す']},
    {icon:'🗾',title:'気になる場所',feature:'県・スポット区分・カテゴリから、登録地点を眺めて次の候補を探す。',steps:['都道府県を選ぶ','定番・寄り道・道の駅など区分を選ぶ','カテゴリを選び「候補を見る」','マップ確認・保存・☆訪問済み・メモを使える']},
    {icon:'📚',title:'登録スポットを見る',feature:'登録済みスポットを一覧から細かく探すための検索メニュー。',steps:['都道府県・区分・カテゴリを選ぶ','必要なら名称でも絞り込む','「表示」で一覧を見る','マップ確認・☆訪問済み・メモを使える']},
    {icon:'📖',title:'旅の履歴',feature:'実際に行った場所へ、訪問記録と自分のメモを残す。',steps:['「現在地を取得して記録」を押す','300m以内の登録地点があれば、その地点として記録できる','登録地点がなければ座標とメモを保存する','★・訪問回数・日時・メモを残せる','不要になったメモや旅の記録は削除できる']},
    {icon:'🏍️',title:'お気に入りのルート',feature:'各メニューで保存したルートをあとから見返して、もう一度走れる。',steps:['保存済みルートを一覧で見る','「コースを見る」で立ち寄り地点を確認する','Google Mapsや車両別ルートを開く','不要なルートは選択して削除する']}
  ];
  const cards=items.map((x,i)=>'<details class="usage-menu-card"'+(i===0?' open':'')+'><summary><span class="usage-icon">'+x.icon+'</span><span><b>'+esc(x.title)+'</b><small>'+esc(x.feature)+'</small></span></summary><div class="usage-menu-body"><div class="usage-label">使い方</div><ol>'+x.steps.map(v=>'<li>'+esc(v)+'</li>').join('')+'</ol></div></details>').join('');
  modal('<div class="usage-guide"><h2>？ 道の途中。の使い方</h2>'+
    '<p class="usage-lead">「どこへ行こう？」に迷った時に、目的地を決めたり、寄り道を足したり、走った記録を残したりするためのアプリです。</p>'+
    '<div class="usage-common"><h3>📍 まず覚えておく共通操作</h3><p><b>スタート地点</b>は、現在地・駅・Google Mapsで選んだ場所などから設定できます。</p><p><b>🗺 マップで確認</b>で場所を見て、ルートがある画面では125cc以下／250cc以上などのナビ用ボタンも使えます。</p><p><b>☆</b> は訪問済みマーク、<b>📝 メモ</b> はその場所の記録です。★の変更や削除は確認してから反映されます。</p></div>'+
    '<div class="usage-list">'+cards+'</div>'+
    '<div class="usage-footer-note">※ 各距離は候補抽出用の直線距離が中心です。実際の走行距離や通行可否はGoogle Mapsや現地の道路標識・交通規制を確認してください。</div></div>');
}

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

function openSupport(){
  location.href='support.html';
}

function openDetourHome(){showView('detour');}

function openComingSoon(title){
  modal(`<h2>${esc(title)}</h2><p>この機能はただいま準備中です。</p><p class="meta">ホームの入口を先に追加しました。次のアップデートで使えるようにしていきます。</p><div class="actions"><button type="button" class="soft" onclick="closeModal()">閉じる</button></div>`);
}


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
      <label>座標（必須）<input name="coordinates" required inputmode="text" placeholder="例：36.123456,136.123456"></label>
      <button type="button" class="soft contact-current-location" onclick="fillContactCurrentCoordinates(true)">◎ 現在地を再取得</button>
      <div id="contactCoordStatus" class="contact-coord-status"></div>
      <label>おすすめポイント<textarea name="details" rows="5" required placeholder="どんな場所か、何がおすすめかを教えてください"></textarea></label>`;
  }
  $('contactFields').innerHTML=`<div class="contact-selected">選択中：<b>${esc(category)}</b></div>${fields}
    <label>返信用メールアドレス（任意）<input name="replyEmail" type="email" autocomplete="email" placeholder="返信が必要な場合だけ"></label>
    <button type="submit" class="primary contact-submit" id="contactSubmitButton">✉ 送信する</button><div id="contactSendStatus" class="contact-send-status" aria-live="polite"></div>`;
  if(category==='オススメ追加')fillContactCurrentCoordinates(false);
}

async function fillContactCurrentCoordinates(force=false){
  const form=$('contactForm');if(!form||!form.elements.coordinates)return;
  const status=$('contactCoordStatus');
  if(!force&&String(form.elements.coordinates.value||'').trim())return;
  if(status){status.className='contact-coord-status';status.textContent='現在地を取得しています…'}
  try{
    const p=await geo();
    if(!force&&String(form.elements.coordinates.value||'').trim()){
      if(status){status.className='contact-coord-status success';status.textContent='保存済みの地点座標を使用しています。'}
      return;
    }
    const coord=Number(p.lat).toFixed(6)+','+Number(p.lng).toFixed(6);
    form.elements.coordinates.value=coord;
    if(form.elements.mapUrl&&(force||!String(form.elements.mapUrl.value||'').trim()))form.elements.mapUrl.value=googlePoint(p.lat,p.lng,'');
    if(status){status.className='contact-coord-status success';status.textContent='現在地を入力しました：'+coord}
  }catch(e){
    if(status){status.className='contact-coord-status error';status.textContent='現在地を取得できませんでした。位置情報を許可して「現在地を再取得」を押してください。'}
  }
}

function sendContact(event){
  event.preventDefault();
  const form=event.currentTarget;
  const category=form.dataset.category||'';
  if(!CONTACT_CATEGORIES.includes(category)){alert('カテゴリを選んでください。');return;}
  if(category==='オススメ追加'){
    const coord=String(form.elements.coordinates?.value||'').trim();
    if(!/^[-+]?\d+(?:\.\d+)?,[-+]?\d+(?:\.\d+)?$/.test(coord)){
      alert('座標を「36.123456,136.123456」の形式で入力してください。\n「現在地を入れる」ボタンでも入力できます。');
      form.elements.coordinates?.focus();
      return;
    }
  }
  if(!form.reportValidity())return;
  submitContactForm(form,category);
}
async function submitContactForm(form,category){
  const fd=new FormData(form);
  const val=name=>String(fd.get(name)||'').trim();
  const coord=val('coordinates')||((val('latitude')&&val('longitude'))?(val('latitude')+','+val('longitude')):'');
  const detailText=val('details');
  const payload={
    _subject:`【道の途中。】【${category}】`,
    _template:'table',
    _captcha:'false',
    _honey:'',
    カテゴリ:category,
    内容:coord?('座標：'+coord+'\n\n'+detailText):detailText,
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
  if(coord)payload['座標']=coord;
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
  const words={walk:'食べ歩き たい焼き 団子 ソフトクリーム 軽食',rest:'カフェ 喫茶店 ハンバーガー バーガー 甘味処 スイーツ ジェラート パン',hearty:'定食 食堂 ラーメン うどん 丼 お好み焼き'};
  const q=`${base} 周辺 ${words[style]||words.walk}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`
}
function googleRoute(origin,pts,vehicle='250'){
  if(!pts.length)return'#';
  const d=pts[pts.length-1],wps=pts.slice(0,-1).map(navTarget).join('|');
  const avoid=(vehicle==='50'||vehicle==='125')?'&avoid=highways%2Ctolls':'';
  return `https://www.google.com/maps/dir/?api=1&origin=${origin.lat},${origin.lng}&destination=${encodeURIComponent(navTarget(d))}${wps?`&waypoints=${encodeURIComponent(wps)}`:''}&travelmode=driving${avoid}`;
}

const DETOUR_GENRES=[
  ['random','🎲 おまかせ'],
  ['view','🌄 景色を見る'],
  ['sweets','🍡 甘いもの'],
  ['cafe','☕ カフェ'],
  ['food','🍜 ごはん'],
  ['onsen','♨️ 温泉'],
  ['road','🛣️ 道の駅'],
  ['shrine','⛩️ 神社・寺'],
  ['park','🌳 公園'],
  ['unusual','👀 ちょっと変なもの'],
  ['season','🌸 季節を感じる']
];
const detourContexts=new Map();
let detourContextSeq=0;
let detourRoute={
  origin:null,
  points:[],
  source:'manual',
  title:''
};

function registerDetourContext(origin,destinationOrPoints){
  if(detourContexts.size>300)detourContexts.clear();
  const id='dt'+(++detourContextSeq);
  const points=Array.isArray(destinationOrPoints)?destinationOrPoints:[destinationOrPoints];
  detourContexts.set(id,{
    origin:{...origin},
    points:points.filter(Boolean).map(x=>({...x})),
    vehicle:'250'
  });
  return id;
}
function detourCorridorKm(vehicle){
  return ({'50':3,'125':5,'250':8,'car':10})[vehicle]||8;
}
function detourVehicleLabel(vehicle){
  return ({'50':'50cc','125':'125cc以下','250':'250cc以上','car':'車'})[vehicle]||'250cc以上';
}
function detourLevelSpec(level){
  if(level==='quick')return{label:'🌱 ちょい道草',maxStay:20,major:false};
  if(level==='rest')return{label:'☕ ひと休み',maxStay:40,major:false};
  if(level==='why')return{label:'🧭 せっかくだから',maxStay:75,major:false};
  return{label:'🎲 何が出ても知らんw',maxStay:999,major:true};
}
function detourSegmentMetric(a,b,p){
  const midLat=rad((+a.lat + +b.lat)/2);
  const kx=111.32*Math.cos(midLat),ky=110.574;
  const dx=(+b.lng-(+a.lng))*kx;
  const dy=(+b.lat-(+a.lat))*ky;
  const px=(+p.lng-(+a.lng))*kx;
  const py=(+p.lat-(+a.lat))*ky;
  const len2=dx*dx+dy*dy;
  if(!len2)return{t:0,perp:Math.hypot(px,py)};
  const rawT=(px*dx+py*dy)/len2;
  const t=Math.max(0,Math.min(1,rawT));
  const qx=dx*t,qy=dy*t;
  return{t:rawT,perp:Math.hypot(px-qx,py-qy)};
}
function detourClosestSegment(route,p){
  const nodes=[route.origin,...route.points];
  let best={segment:-1,perp:Infinity,t:0};
  for(let i=0;i<nodes.length-1;i++){
    const m=detourSegmentMetric(nodes[i],nodes[i+1],p);
    if(m.t<0||m.t>1)continue;
    if(m.perp<best.perp)best={segment:i,perp:m.perp,t:m.t};
  }
  return best;
}
function detourText(x){
  return [x.name,x.category,x.summary,x.featureLabel,x.featureCategory,x.kind].filter(Boolean).join(' ');
}
function detourIsMajorDestination(x){
  const t=detourText(x);
  const fc=String(x.featureCategory||'');
  return fc==='museum'||/博物館|美術館|ミュージアム|資料館|記念館|科学館|水族館|動物園|遊園地|テーマパーク|大型施設/.test(t);
}
function detourGenreMatch(x,genre){
  if(genre==='random')return true;
  if(genre==='road')return x.kind==='道の駅';
  if(genre==='season')return seasonMatch(x,currentSeason());
  const t=detourText(x);
  const fc=String(x.featureCategory||'');
  const re={
    view:/展望|眺望|景色|岬|高原|山頂|海岸|湖|滝|渓谷|峡谷|棚田|橋|夕日|夜景/,
    cafe:/カフェ|喫茶|珈琲|コーヒー|茶房|茶屋|ハンバーガー|バーガー/,
    sweets:/甘味|スイーツ|団子|饅頭|まんじゅう|たい焼|ソフト|ジェラート|アイス|菓子|ケーキ|プリン/,
    food:/食堂|レストラン|ラーメン|うどん|そば|丼|定食|焼肉|お好み|バーガー|食事|グルメ/,
    onsen:/温泉|温浴|銭湯|スパ|湯/,
    shrine:/神社|神宮|大社|寺|寺院|観音|不動|霊場/,
    park:/公園|庭園|植物園|花畑|フラワー/,
    unusual:/珍スポット|珍|奇|巨大|レトロ|秘境|不思議|変わった/
  }[genre];
  const fcMap={view:'view',onsen:'onsen',shrine:'shrine',park:'park',unusual:'unusual_ui'};
  return (fcMap[genre]&&fc===fcMap[genre]) || Boolean(re&&re.test(t));
}
function detourStayMinutes(x,genre){
  if(genre==='onsen'||detourGenreMatch(x,'onsen'))return 70;
  if(genre==='food'||detourGenreMatch(x,'food'))return 45;
  if(genre==='cafe'||detourGenreMatch(x,'cafe'))return 35;
  if(genre==='park'||detourGenreMatch(x,'park'))return 35;
  if(genre==='season')return 40;
  if(genre==='shrine'||detourGenreMatch(x,'shrine'))return 25;
  if(genre==='sweets'||detourGenreMatch(x,'sweets'))return 20;
  if(genre==='road'||x.kind==='道の駅')return 20;
  if(genre==='view'||detourGenreMatch(x,'view'))return 15;
  if(genre==='unusual'||detourGenreMatch(x,'unusual'))return 20;
  return 25;
}
function detourAllSpots(){
  return [
    ...D.roads.filter(x=>active(x.gacha)).map(x=>({...x,kind:'道の駅'})),
    ...D.landmarks.filter(x=>active(x.gacha)).map(x=>({...x,kind:pointKind(x)}))
  ].filter(x=>Number.isFinite(+x.lat)&&Number.isFinite(+x.lng));
}
function detourExperienceTitle(x,genre){
  if(genre==='view'||detourGenreMatch(x,'view'))return'🌄 ちょっと景色を見る';
  if(genre==='sweets'||detourGenreMatch(x,'sweets'))return'🍡 甘いものをひとつ';
  if(genre==='cafe'||detourGenreMatch(x,'cafe'))return'☕ ちょっとひと息';
  if(genre==='food'||detourGenreMatch(x,'food'))return'🍜 途中で腹ごしらえ';
  if(genre==='onsen'||detourGenreMatch(x,'onsen'))return'♨️ ひとっ風呂寄ってく？';
  if(genre==='road'||x.kind==='道の駅')return'🛣️ 道の駅でちょっと休憩';
  if(genre==='shrine'||detourGenreMatch(x,'shrine'))return'⛩️ 小さくお参り';
  if(genre==='park'||detourGenreMatch(x,'park'))return'🌳 少しだけ外で休憩';
  if(genre==='unusual'||detourGenreMatch(x,'unusual'))return'👀 ちょっと変なものを見る';
  if(genre==='season')return'🌸 季節をひとつ拾う';
  return'🎲 途中でこれ、どう？';
}
function detourRandomRoutePoint(route){
  const nodes=[route.origin,...route.points];
  if(nodes.length<2)return route.origin;
  const segs=[];
  let total=0;
  for(let i=0;i<nodes.length-1;i++){
    const len=dist(nodes[i].lat,nodes[i].lng,nodes[i+1].lat,nodes[i+1].lng);
    segs.push({a:nodes[i],b:nodes[i+1],len});
    total+=len;
  }
  if(!total)return route.origin;
  const target=total*(0.25+Math.random()*0.5);
  let acc=0;
  for(const seg of segs){
    if(acc+seg.len>=target){
      const t=seg.len?((target-acc)/seg.len):0.5;
      return{lat:+seg.a.lat+(+seg.b.lat-(+seg.a.lat))*t,lng:+seg.a.lng+(+seg.b.lng-(+seg.a.lng))*t};
    }
    acc+=seg.len;
  }
  return nodes[Math.max(0,nodes.length-2)];
}
function detourMapZoomForRadius(radius){
  const r=+radius||10;
  if(r<=3)return 14;
  if(r<=5)return 13;
  if(r<=10)return 12;
  if(r<=20)return 11;
  if(r<=30)return 10;
  if(r<=60)return 9;
  return 8;
}
function detourMapSearchWord(genre){
  return {
    random:'観光スポット',
    view:'展望 景色',
    sweets:'甘味 スイーツ',
    cafe:'カフェ 喫茶店 ハンバーガー バーガー',
    food:'食事 レストラン',
    onsen:'温泉',
    road:'道の駅',
    shrine:'神社 寺',
    park:'公園',
    unusual:'珍スポット',
    season:'季節 観光スポット'
  }[genre]||'観光スポット';
}
function detourFoodSearchUrl(route,genre,point=null,radius=10){
  const p=point||detourRandomRoutePoint(route);
  const word=detourMapSearchWord(genre);
  const zoom=detourMapZoomForRadius(radius);
  return 'https://www.google.com/maps/search/'+encodeURIComponent(word)+'/@'+(+p.lat)+','+(+p.lng)+','+zoom+'z';
}
function detourAnchorPoint(route,anchor){
  if(anchor==='destination')return route.points[route.points.length-1];
  return route.origin;
}
function detourAnchorLabel(anchor){
  return anchor==='destination'?'目的地':'スタート地点';
}
function renderExternalDetourSearch(route,genre,level,anchor,radius){
  const host=$('detourResult');
  if(!host)return;
  const p=detourAnchorPoint(route,anchor);
  const spec=detourLevelSpec(level);
  const cfg={
    cafe:{title:'☕ この辺でひと休み',text:'選んだ基準地点の周辺で、カフェ・喫茶店・ハンバーガー店を探してみる？'},
    sweets:{title:'🍡 この辺で甘いもの',text:'選んだ基準地点の周辺で、甘味・スイーツを探してみる？'},
    food:{title:'🍜 この辺で腹ごしらえ',text:'選んだ基準地点の周辺で、ごはん処を探してみる？'}
  }[genre];
  host.className='result';
  host.innerHTML=`<div class="detour-picked">
    <div class="detour-mission-title">${cfg.title}</div>
    <p>${cfg.text}</p>
    <div class="detour-stats"><span>${esc(spec.label)}</span><span>${esc(detourAnchorLabel(anchor))} 基準</span><span>半径 ${radius}km</span><span>登録DB不要</span></div>
    <p class="meta">Google Mapsの検索範囲は地図側で決まるため、${radius}kmは検索の目安として扱います。</p>
    <div class="detour-actions">
      <a class="mapbtn primary" href="${detourFoodSearchUrl(route,genre,p,radius)}" target="_blank" rel="noopener">Google Mapsでこの辺を探す</a>
      <button type="button" class="soft" onclick="runDetourGacha()">🎲 別の候補</button>
    </div>
  </div>`;
}
function detourRouteLabel(){
  if(!detourRoute.origin||!detourRoute.points.length)return'現在：未設定';
  const d=detourRoute.points[detourRoute.points.length-1];
  const via=Math.max(0,detourRoute.points.length-1);
  const src=detourRoute.source==='favorite'?'⭐ お気に入り':'🗺 自分で指定';
  return `${src} / ${detourRoute.origin.label||'スタート'} → ${d.name||'目的地'}${via?`（途中 ${via}件）`:''}`;
}
function renderDetourRouteStatus(){
  const el=$('detourDestinationStatus');
  if(el)el.textContent=detourRouteLabel();
}
function chooseDetourManual(){
  detourRoute={origin:origins.detour?{...origins.detour}:null,points:[],source:'manual',title:''};
  renderDetourRouteStatus();
  const host=$('detourResult');
  if(host){host.className='result empty';host.textContent='出発地と最終目的地を設定してください。';}
}
function openDetourDestinationMap(){
  window.open('https://www.google.com/maps','_blank','noopener');
}
async function reflectDetourDestination(){
  const raw=await clipboardText();
  if(!raw)return alert('Googleマップで目的地を選び、共有 → Copy Link を押してから反映してください。');
  if(!origins.detour)return alert('先に出発地を設定してください。');
  const q=await resolveMapLink(raw);
  if(!q)return alert('Googleマップの共有リンクから目的地を取得できませんでした。もう一度 Copy Link して再試行してください。');
  detourRoute={
    origin:{...origins.detour},
    points:[{lat:q[0],lng:q[1],name:'Googleマップ共有地点',kind:'目的地'}],
    source:'manual',
    title:'Googleマップで選んだルート'
  };
  renderDetourRouteStatus();
  const host=$('detourResult');
  if(host){host.className='result empty';host.textContent='目的地を反映しました。道草レベルとジャンルを選んでください。';}
}

function openDetourFavoritePicker(){
  const a=loadFavorites().filter(x=>x.origin&&(x.points||[]).length);
  if(!a.length)return modal(`<h2>⭐ お気に入りのルート</h2><p>寄り道に使える保存ルートがまだありません。</p><div class="actions"><button class="soft" onclick="closeModal()">閉じる</button></div>`);
  modal(`<h2>⭐ どのルートで道草する？</h2>
    <div class="detour-favorite-list">${a.map((x,i)=>`<button type="button" class="detour-favorite-card" onclick="selectDetourFavorite('${esc(x.id)}')">
      <b>${esc(x.title||'保存ルート')}</b>
      <span>${esc(x.startLabel||'スタート')} → ${esc((x.points[x.points.length-1]||{}).name||'目的地')}</span>
      <small>${esc(x.mode||'')} / 立ち寄り ${x.points.length}件</small>
    </button>`).join('')}</div>`);
}
function selectDetourFavorite(id){
  const x=loadFavorites().find(v=>v.id===id);
  if(!x||!x.origin||!(x.points||[]).length)return;
  detourRoute={
    origin:{...x.origin,label:x.startLabel||x.origin.label||'スタート'},
    points:x.points.map(p=>({...p})),
    source:'favorite',
    title:x.title||'お気に入りルート'
  };
  origins.detour={...detourRoute.origin};
  const originHost=$('detourOrigin');
  if(originHost)originHost.textContent='現在：'+(detourRoute.origin.label||'スタート');
  renderDetourRouteStatus();
  closeModal();
  const host=$('detourResult');
  if(host){host.className='result empty';host.textContent='お気に入りルートを読み込みました。道草条件を選んでください。';}
}
function loadDetourFromContext(id){
  const ctx=detourContexts.get(id);
  if(!ctx||!ctx.origin||!ctx.points.length)return alert('ルートを作り直してください。');
  detourRoute={
    origin:{...ctx.origin},
    points:ctx.points.map(p=>({...p})),
    source:'route',
    title:'現在のルート'
  };
  origins.detour={...ctx.origin};
  renderDetourRouteStatus();
  showView('detour');
  const originHost=$('detourOrigin');
  if(originHost)originHost.textContent='現在：'+(ctx.origin.label||'スタート');
}
function openDetour(id){
  loadDetourFromContext(id);
}
function detourInsertedPointsByAnchor(route,pick,anchor){
  const pts=route.points.map(p=>({...p}));
  const insertIndex=anchor==='destination'?Math.max(0,pts.length-1):0;
  pts.splice(insertIndex,0,pick);
  return pts;
}
function runDetourGacha(){
  if(!detourRoute.origin||!detourRoute.points.length)return alert('出発地と最終目的地を設定するか、お気に入りのルートを選んでください。');
  const genre=$('detourGenre')?.value||'random';
  const level=$('detourLevel')?.value||'rest';
  const anchor=$('detourAnchor')?.value||'start';
  const radius=numericValue('detourRadius','detourRadiusFree',1,200);
  const spec=detourLevelSpec(level);
  const route=detourRoute;
  const base=detourAnchorPoint(route,anchor);
  const routeNodes=[route.origin,...route.points];
  const all=detourAllSpots();

  const pool=all.map(x=>{
    const d=dist(base.lat,base.lng,x.lat,x.lng);
    return {...x,_detourDistance:d};
  }).filter(x=>{
    if(x._detourDistance>radius)return false;
    if(!detourGenreMatch(x,genre))return false;
    if(detourStayMinutes(x,genre)>spec.maxStay)return false;
    if(!spec.major&&detourIsMajorDestination(x))return false;
    if(routeNodes.some(n=>dist(n.lat,n.lng,x.lat,x.lng)<0.5))return false;
    return true;
  });

  const host=$('detourResult');
  if(!host)return;

  pool.sort((a,b)=>(a._detourDistance+Math.random()*radius*.35)-(b._detourDistance+Math.random()*radius*.35));
  const pick=pool.length?rand(pool.slice(0,Math.min(25,pool.length))):null;
  const destination=route.points[route.points.length-1];
  const mapUrl=detourFoodSearchUrl(route,genre,base,radius);
  const mapLabel=genre==='random'?'Google Mapsでこの辺を探す':'Google Mapsで'+detourMapSearchWord(genre)+'を探す';

  let registeredHtml='';
  if(pick){
    const meta=spotMeta(pick,pick.kind,null);
    const inserted=detourInsertedPointsByAnchor(route,pick,anchor);
    const mins=detourStayMinutes(pick,genre);
    registeredHtml=`<div class="detour-registered">
      <h4>📚 アプリ登録候補</h4>
      <div class="detour-picked-head">${iconBadge(pick,pick.kind)}<div><h3>${esc(pick.name)}</h3><div class="meta">${esc(meta)}</div></div></div>
      ${pick.summary?`<p>${esc(pick.summary)}</p>`:''}
      <div class="detour-stats">
        <span>${esc(detourAnchorLabel(anchor))}から約 ${pick._detourDistance.toFixed(1)}km</span>
        <span>滞在目安 約${mins}分</span>
      </div>
      <a class="mapbtn" href="${googleRoute(route.origin,inserted,'250')}" target="_blank" rel="noopener">この登録候補に寄って走る</a>
    </div>`;
  }else{
    registeredHtml=`<div class="detour-registered detour-registered-empty">
      <h4>📚 アプリ登録候補</h4>
      <p class="meta">${esc(detourAnchorLabel(anchor))}から${radius}km以内には、このジャンルの登録候補がありません。</p>
    </div>`;
  }

  host.className='result';
  host.innerHTML=`<div class="detour-picked">
    <div class="detour-mission-title">${pick?esc(detourExperienceTitle(pick,genre)):'🎲 この辺で道草'}</div>
    <div class="detour-stats">
      <span>${esc(spec.label)}</span>
      <span>${esc(detourAnchorLabel(anchor))} 基準</span>
      <span>半径 ${radius}km</span>
    </div>
    <div class="detour-map-search">
      <a class="mapbtn primary" href="${mapUrl}" target="_blank" rel="noopener">🗺 ${esc(mapLabel)}</a>
      <p class="meta">Google Mapsでは、選んだ基準地点を中心に検索します。指定kmは地図表示範囲の目安です。</p>
    </div>
    ${registeredHtml}
    <p class="meta">最終目的地「${esc(destination.name||'目的地')}」はそのまま。</p>
    <div class="detour-actions">
      <button type="button" class="soft" onclick="runDetourGacha()">🎲 別の候補</button>
    </div>
  </div>`;
}

function active(v){return !String(v||'').includes('除外')}
function groupClass(kind){return kind==='道の駅'?'group-road':kind==='定番スポット'?'group-A':'group-B'}
function iconPath(feature){const f=feature||'generic';return `assets/icons/ic_feature_${f}.png`}
function featureOf(x,kind){return kind==='道の駅'?'road_station':(x.featureCategory||'generic')}
function iconBadge(x,kind){return `<div class="icon-badge ${groupClass(kind)}"><img src="${iconPath(featureOf(x,kind))}" onerror="this.src='assets/icons/ic_feature_generic.png'" alt=""></div>`}
function pointKind(x){if(x.groupName)return x.groupName; if(x.level==='A')return'定番スポット';if(x.level==='B')return'寄り道スポット';return'道の駅'}
function mapBtn(x,label='マップで確認'){return `<a class="mapbtn map-check" href="${googlePoint(x.lat,x.lng,x.name,x)}" target="_blank" rel="noopener">🗺 ${label}</a>`}
function routeButtons(origin,pts){
  if(!origin||!pts||!pts.length)return'';
  const d=pts[pts.length-1];
  const detourId=registerDetourContext(origin,pts);
  return `<div class="route-buttons">
    <a class="mapbtn map-check" href="${googlePoint(d.lat,d.lng,d.name,d)}" target="_blank" rel="noopener">🗺 マップで確認</a>
    <div class="food-search-group">
      <a class="mapbtn food-walk" href="${googleFoodSearch(d,'walk')}" target="_blank" rel="noopener">🍡 食べ歩き</a>
      <a class="mapbtn food-rest" href="${googleFoodSearch(d,'rest')}" target="_blank" rel="noopener">☕ ひと息</a>
      <a class="mapbtn food-hearty" href="${googleFoodSearch(d,'hearty')}" target="_blank" rel="noopener">🍜 がっつり</a>
    </div>
    <a class="mapbtn bike125" href="${googleRoute(origin,pts,'125')}" target="_blank" rel="noopener">🛵 125cc以下</a>
    <a class="mapbtn bike250" href="${googleRoute(origin,pts,'250')}" target="_blank" rel="noopener">🏍 250cc以上</a>
    <button type="button" class="soft detour-open" onclick="openDetour('${detourId}')">🛣️ 寄り道しよう</button>
  </div>`;
}
function numericValue(selectId,freeId,min,max){const e=$(freeId);if(e&&String(e.value).trim()!==''){const n=+e.value;if(Number.isFinite(n)&&n>=min&&n<=max)return n;}return +$(selectId).value}
function dirText16(v){return ['北','北北東','北東','東北東','東','東南東','南東','南南東','南','南南西','南西','西南西','西','西北西','北西','北北西'][Math.round(v/22.5)%16]}

function renderStartPanels(){['sug','dest','relay','season','nearby','ride','detour'].forEach(k=>{const host=$(k+'Start');host.innerHTML=`<div class="panel start-panel"><h3>📍 スタート地点</h3><div class="origin-status" id="${k}Origin">現在：未設定</div><div class="start-simple"><button class="soft start-current" onclick="useCurrent('${k}')">◎ 現在地を使う</button><button class="soft start-station" onclick="stationPicker('${k}')">🚉 駅を選ぶ</button><div class="map-pick-row"><button class="soft start-map" onclick="openStartMap('${k}')">🗺 Googleマップでスタート地点を選ぶ</button><button class="info-btn" onclick="showMapStartHelp()" title="使い方">ⓘ</button></div><button class="soft reflect-btn start-reflect" onclick="reflectMapLink('${k}')">🔗 コピーしたリンクを反映</button></div></div>`;});}
function setOrigin(k,lat,lng,label){origins[k]={lat:+lat,lng:+lng,label:label||'選択地点'};const host=$(`${k}Origin`);if(host)host.textContent=`現在：${origins[k].label}`;if(k==='detour'&&detourRoute.source!=='favorite'){detourRoute.origin={...origins[k]};renderDetourRouteStatus();}if(k==='interestSave'&&pendingInterestSave)showInterestSaveDialog();}
function parseCoords(s){const t=decodeURIComponent(String(s||'').replace(/\+/g,'%20'));const pats=[/@(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)/,/!3d(-?\d{1,2}(?:\.\d+)?)!4d(-?\d{1,3}(?:\.\d+)?)/,/[?&](?:q|query|ll|center)=(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)/,/(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)/];for(const p of pats){const m=t.match(p);if(m){const a=+m[1],b=+m[2];if(Math.abs(a)<=90&&Math.abs(b)<=180)return[a,b]}}return null}
function firstUrl(s){const m=String(s||'').match(/https?:\/\/[^\s]+/i);return m?m[0].replace(/[\])。,]+$/,''):null}
function openStartMap(k){window.open('https://www.google.com/maps','_blank','noopener')}
function showMapStartHelp(){modal(`<h2>Googleマップから選ぶ</h2><p>ブラウザでGoogleマップが開きます。スタート地点にしたい場所を選択し、<b>共有 → リンクをコピー</b>してください。</p><p>この画面に戻り、<b>「コピーしたリンクを反映」</b>を押すとスタート地点に設定されます。</p>`)}
function showDetourDestinationHelp(){modal(`<h2>Googleマップから選ぶ</h2><p>ブラウザでGoogleマップが開きます。目的地にしたい場所を選択し、<b>共有 → リンクをコピー</b>してください。</p><p>この画面に戻り、<b>「コピーしたリンクを反映」</b>を押すと目的地に設定されます。</p>`)}
async function clipboardText(){try{return(await navigator.clipboard.readText()).trim()}catch(e){const v=window.prompt('Googleマップでコピーした共有リンクを貼り付けてください。','');return(v||'').trim()}}
async function resolveMapLink(raw){
  const direct=parseCoords(raw);
  if(direct)return direct;
  const u=firstUrl(raw);
  if(!u)return null;
  try{
    const api=MAPS_RESOLVER_URL+'?url='+encodeURIComponent(u);
    const r=await fetch(api,{cache:'no-store'});
    if(!r.ok)return null;
    const j=await r.json();
    if(j&&j.ok&&Number.isFinite(+j.lat)&&Number.isFinite(+j.lng))return[+j.lat,+j.lng];
  }catch(e){}
  return null
}
async function reflectMapLink(k){const raw=await clipboardText();if(!raw)return alert('Googleマップで共有リンクをコピーしてから「コピーしたリンクを反映」を押してください。');const q=await resolveMapLink(raw);if(!q)return alert('共有リンクから場所を取得できませんでした。Googleマップで地点を選び、共有からリンクをコピーして再試行してください。');setOrigin(k,q[0],q[1],'Googleマップ共有地点');alert('スタート地点を反映しました。')}
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
const RIDE_STYLE_KEY='michinotochu_ride_style_v1';
const RIDE_DISTANCE_LABELS={'10':'🛵 ちょい乗り','20':'🌿 ひとっ走り','40':'🏍️ ぶらっと行こう','70':'🌤️ いい感じに走る','100':'🔥 今日は走るぞ','300':'🚀 遠くまで行こう'};
const RIDE_MOOD_LABELS={random:'🎲 おまかせ',road:'🏠 道の駅へ',classic:'⭐ いいとこ行きたい',detour:'🌿 ちょっと寄りたい',scenery:'🌊 景色が見たい',food:'☕ なんか食べたい',heal:'♨️ 癒されたい'};

const RIDE_FOOD_GENRES={
  random:{label:'🎲 おまかせ'},
  cafe:{label:'☕ カフェ・喫茶',query:'カフェ 喫茶店',re:/カフェ|喫茶|珈琲|コーヒー|茶房|茶屋/},
  burger:{label:'🍔 ハンバーガー',query:'ハンバーガー バーガー',re:/ハンバーガー|バーガー/},
  bakery:{label:'🥐 パン・ベーカリー',query:'パン ベーカリー',re:/パン屋|パン工房|ベーカリー|ブーランジェリー|クロワッサン|食パン|サンドイッチ/},
  sweets:{label:'🍰 スイーツ・甘味',query:'スイーツ 甘味',re:/甘味|スイーツ|団子|饅頭|まんじゅう|ソフト|ジェラート|アイス|菓子|ケーキ|プリン|たい焼き/},
  meal:{label:'🍚 ごはん',query:'ごはん 食堂 レストラン',re:/食堂|レストラン|ラーメン|うどん|そば|丼|定食|グルメ|食事|お好み焼き/}
};
const RIDE_SCENERY_GENRES={
  random:{label:'🎲 おまかせ'},
  sea:{label:'🌊 海・海岸',query:'海岸 景色',tags:['sea'],re:/海|海岸|浜|岬|島|灯台|港|湾|磯|海峡/},
  mountain:{label:'⛰️ 山・高原',query:'山 高原 絶景',re:/山|岳|高原|峠|峰|丘|草原|牧場/},
  lake:{label:'🏞️ 湖・池',query:'湖 池 景色',re:/湖|池|沼|湿原/},
  waterfall:{label:'💧 滝・渓谷',query:'滝 渓谷',re:/滝|渓谷|峡谷|峡|渓流|清流/},
  view:{label:'🌄 展望・絶景',query:'展望台 絶景',tags:['view'],re:/展望|眺望|パノラマ|ビューポイント|景勝/},
  night:{label:'🌃 夜景',query:'夜景スポット',re:/夜景|夕景|夕日|星空|ライトアップ/},
  road:{label:'🛣️ 道・峠・スカイライン',query:'峠 スカイライン ドライブウェイ',tags:['road_drive'],re:/峠|街道|旧道|スカイライン|ドライブウェイ|ドライブロード|山岳道路|海岸道路|林道|道路/}
};
const RIDE_CLASSIC_GENRES={
  random:{label:'🎲 おまかせ'},
  scenery:{label:'🌄 絶景・景勝地',query:'絶景 観光名所',tags:['view','sea','nature','park'],re:/絶景|景勝|展望|眺望/},
  history:{label:'🏯 歴史・史跡',query:'史跡 歴史 観光',tags:['history','shrine'],re:/史跡|歴史|城|古墳|宿場|街並|町並/},
  architecture:{label:'🌉 建築・橋・ダム',query:'建築 橋 ダム 観光',tags:['construction'],re:/建築|洋館|橋|ダム|塔|水門|発電所/},
  unusual:{label:'👀 珍スポット',query:'珍スポット',tags:['unusual_ui'],re:/珍|奇妙|不思議|変わった|巨大/},
  culture:{label:'🏛️ 文化・資料館',query:'博物館 資料館 文化',tags:['museum','experience'],re:/博物館|資料館|記念館|美術館|工房|文化|伝統|工芸/}
};
const RIDE_DETOUR_GENRES={
  random:{label:'🎲 おまかせ'},
  view:{label:'🌄 景色',query:'展望スポット 景色',tags:['view','sea','nature'],re:/展望|眺望|景色|海|山|高原|湖|滝/},
  shrine:{label:'⛩️ 神社・寺',query:'神社 寺',tags:['shrine'],re:/神社|大社|神宮|寺|寺院|霊場/},
  park:{label:'🌳 公園・花',query:'公園 花',tags:['park'],re:/公園|庭園|花園|植物園|花畑|桜並木/},
  unusual:{label:'👀 珍スポット',query:'珍スポット',tags:['unusual_ui'],re:/珍|奇妙|不思議|変わった|巨大/},
  construction:{label:'🌉 橋・建設物',query:'橋 ダム 建造物',tags:['construction'],re:/橋|ダム|堰|水門|隧道|トンネル|塔|高架/},
  experience:{label:'🎨 体験・文化',query:'体験 文化 スポット',tags:['experience','museum'],re:/工房|市場|牧場|農園|ワイナリー|醸造|酒蔵|陶芸|体験|工芸|文化/}
};
const RIDE_HEAL_GENRES={
  random:{label:'🎲 おまかせ'},
  healing:{label:'🌿 ヒーリングスポット',queries:['癒しスポット','ヒーリングスポット','パワースポット'],re:/癒し|ヒーリング|パワースポット|霊場|名水|巨木|森林浴/},
  shrine:{label:'⛩️ 神社・寺',queries:['神社','寺','神社 寺'],tags:['shrine']},
  onsen:{label:'♨️ 温泉',queries:['日帰り温泉','温泉','露天風呂'],tags:['onsen'],re:/温泉|湯治|共同浴場|足湯/},
  nature:{label:'🌲 静かな自然',queries:['森林浴','庭園','滝','湖','高原'],tags:['nature','park'],re:/庭園|森林|森|湖|池|滝|高原|渓谷|名水|巨木/}
};
const RIDE_SUBGENRE_CONFIGS={
  food:RIDE_FOOD_GENRES,
  scenery:RIDE_SCENERY_GENRES,
  classic:RIDE_CLASSIC_GENRES,
  detour:RIDE_DETOUR_GENRES,
  heal:RIDE_HEAL_GENRES
};
const rideSubgenreSelections={food:'random',scenery:'random',classic:'random',detour:'random',heal:'random'};
let rideLastSearchBearing=null;

function rideSubgenreConfig(mood){return RIDE_SUBGENRE_CONFIGS[mood]||null}
function rideSubgenreKeys(mood){const cfg=rideSubgenreConfig(mood);return cfg?Object.keys(cfg).filter(k=>k!=='random'):[]}
function effectiveRideSubgenre(mood){
  const cfg=rideSubgenreConfig(mood);if(!cfg)return null;
  const selected=rideSubgenreSelections[mood]||'random';
  if(selected!=='random'&&cfg[selected])return selected;
  return rand(rideSubgenreKeys(mood));
}
function rideSubgenreLabel(mood,key){return rideSubgenreConfig(mood)?.[key]?.label||key||''}
function rideSubgenreMatch(x,mood,key){
  const g=rideSubgenreConfig(mood)?.[key];if(!g)return true;
  const t=rideStyleText(x),tags=uiCategoryTags(x);
  if(g.tags&&g.tags.some(tag=>tags.has(tag)))return true;
  return !!(g.re&&g.re.test(t));
}
function rideSubgenreQuery(mood,key){
  const g=rideSubgenreConfig(mood)?.[key];if(!g)return null;
  if(g.queries)return rand(g.queries);
  return g.query||null;
}

const RIDE_DIRECTION_LABELS={random:'🎲 おまかせ',north:'⬆️ 北',east:'➡️ 東',south:'⬇️ 南',west:'⬅️ 西'};
const RIDE_DIRECTION_BEARINGS={north:0,east:90,south:180,west:270};
function rideDistanceBand(km){const t={10:5,20:5,40:8,70:10,100:15,300:15}[+km]||Math.max(5,Math.round(+km*.15));return{min:Math.max(1,+km-t),max:+km+t,tol:t}}
function rideStyleText(x){return [x.name,x.category,x.summary,x.featureLabel,x.featureCategory,x.scenery,x.groupName].filter(Boolean).join(' ')}
function rideMoodMatch(x,mood){
  if(mood==='random')return true;
  if(mood==='road')return x.kind==='道の駅';
  if(mood==='classic')return x.level==='A';
  if(mood==='detour')return x.level==='B';
  const t=rideStyleText(x),tags=uiCategoryTags(x);
  if(mood==='scenery')return ['view','sea','nature','park','construction','road_drive'].some(v=>tags.has(v))||/海|海岸|岬|湖|池|沼|展望|眺望|景色|高原|山|峠|滝|渓谷|峡谷|棚田|夕日|夜景|橋/.test(t);
  if(mood==='food')return /カフェ|喫茶|珈琲|コーヒー|ハンバーガー|バーガー|甘味|スイーツ|団子|饅頭|まんじゅう|ソフト|ジェラート|アイス|菓子|ケーキ|プリン|食堂|レストラン|ラーメン|うどん|そば|丼|定食|グルメ|食事/.test(t);
  if(mood==='heal')return ['onsen','shrine','park','nature'].some(v=>tags.has(v))||/癒し|ヒーリング|パワースポット|森林浴|温泉|湯|神社|神宮|大社|寺|寺院|霊場|庭園|森林|森|湖|池|滝|高原|渓谷|名水|巨木/.test(t);
  return true;
}
function rideMapQuery(mood,subgenre=null){
  const q=rideSubgenreQuery(mood,subgenre);
  if(q)return q;
  const pool={
    random:['観光スポット','展望台','カフェ','道の駅'],
    road:['道の駅'],
    classic:['観光名所'],
    detour:['穴場スポット','小さな観光スポット','展望スポット'],
    scenery:['展望台','海岸','岬','湖','滝'],
    food:['カフェ','ハンバーガー','スイーツ','ごはん'],
    heal:['癒しスポット','神社','温泉','森林浴']
  }[mood]||['観光スポット'];
  return rand(pool)
}
function rideMapZoom(km){if(km<=20)return 12;if(km<=70)return 11;return 10}
function pointAtDistance(origin,km,bearingDeg){const R=6371,br=rad(bearingDeg),lat1=rad(+origin.lat),lon1=rad(+origin.lng),d=km/R;const lat2=Math.asin(Math.sin(lat1)*Math.cos(d)+Math.cos(lat1)*Math.sin(d)*Math.cos(br));const lon2=lon1+Math.atan2(Math.sin(br)*Math.sin(d)*Math.cos(lat1),Math.cos(d)-Math.sin(lat1)*Math.sin(lat2));return{lat:lat2*180/Math.PI,lng:lon2*180/Math.PI}}
const RIDE_DIRECTION_HALF_WIDTH=30;
function rideDirectionDelta(actual,target){return Math.abs(((actual-target+540)%360)-180)}
function rideMapSearchUrl(origin,query,targetKm,targetBearing){const center=pointAtDistance(origin,targetKm,targetBearing);return 'https://www.google.com/maps/search/'+encodeURIComponent(query)+'/@'+center.lat+','+center.lng+','+rideMapZoom(targetKm)+'z'}
function rideSaveSelection(){
  const distance=$('rideDistance')?.value||'40',mood=$('rideMood')?.value||'random',direction=$('rideDirection')?.value||'random';
  try{localStorage.setItem(RIDE_STYLE_KEY,JSON.stringify({distance,mood,direction,subgenres:{...rideSubgenreSelections}}))}catch(e){}
  const band=rideDistanceBand(+distance),note=$('rideDistanceNote');if(note)note.textContent='目安：スタート地点から'+band.min+'〜'+band.max+'km'
}
function rideRestoreSelection(){
  try{
    const v=JSON.parse(localStorage.getItem(RIDE_STYLE_KEY)||'null');
    if(v&&$('rideDistance')&&RIDE_DISTANCE_LABELS[String(v.distance)])$('rideDistance').value=String(v.distance);
    if(v&&$('rideMood')&&RIDE_MOOD_LABELS[v.mood])$('rideMood').value=v.mood;
    if(v&&$('rideDirection')&&RIDE_DIRECTION_LABELS[v.direction])$('rideDirection').value=v.direction;
    if(v&&v.subgenres)Object.keys(rideSubgenreSelections).forEach(k=>{if(rideSubgenreConfig(k)?.[v.subgenres[k]])rideSubgenreSelections[k]=v.subgenres[k]});
  }catch(e){}
  rideSaveSelection()
}
function initRideStyleUI(){document.querySelectorAll('.ride-distance-grid button,.ride-mood-grid button,.ride-direction-grid button').forEach(b=>b.addEventListener('click',()=>setTimeout(rideSaveSelection,0)))}
function openRideSubgenreChanger(mood){
  const cfg=rideSubgenreConfig(mood);if(!cfg)return;
  const selected=rideSubgenreSelections[mood]||'random';
  const buttons=Object.keys(cfg).map(key=>'<button type="button" class="ride-mood-change-option'+(key===selected?' active':'')+'" onclick="setRideSubgenre(\''+escJs(mood)+'\',\''+escJs(key)+'\')">'+esc(cfg[key].label)+(key===selected?'<small>現在の設定</small>':'')+'</button>').join('');
  modal('<div class="ride-mood-change-modal"><h2>🔄 探すものジャンルを変える</h2><p class="meta">「'+esc(RIDE_MOOD_LABELS[mood]||mood)+'」はそのまま。探す内容だけ変えます。</p><div class="ride-mood-change-grid">'+buttons+'</div></div>');
}
function setRideSubgenre(mood,key){
  const cfg=rideSubgenreConfig(mood);if(!cfg||!cfg[key])return;
  rideSubgenreSelections[mood]=key;
  rideSaveSelection();
  closeModal();
  runRideStyle(true);
}

function runRideStyle(preserveArea=false){
  const o=requireOrigin('ride');if(!o)return;
  const targetKm=+($('rideDistance')?.value||40),mood=$('rideMood')?.value||'random',direction=$('rideDirection')?.value||'random';
  rideSaveSelection();
  const band=rideDistanceBand(targetKm);
  const targetBearing=(preserveArea&&Number.isFinite(rideLastSearchBearing))
    ?rideLastSearchBearing
    :(direction==='random'?Math.random()*360:RIDE_DIRECTION_BEARINGS[direction]);
  rideLastSearchBearing=targetBearing;
  let pool=[];
  pool.push(...D.roads.filter(x=>active(x.gacha)).map(x=>({...x,kind:'道の駅'})));
  pool.push(...D.landmarks.filter(x=>active(x.gacha)).map(x=>({...x,kind:pointKind(x)})));
  pool=pool.map(x=>({...x,d:dist(o.lat,o.lng,+x.lat,+x.lng),br:bearing(o.lat,o.lng,+x.lat,+x.lng)}))
    .filter(x=>x.d>=band.min&&x.d<=band.max&&rideDirectionDelta(x.br,targetBearing)<=RIDE_DIRECTION_HALF_WIDTH&&rideMoodMatch(x,mood));

  const subgenre=effectiveRideSubgenre(mood);
  if(subgenre)pool=pool.filter(x=>rideSubgenreMatch(x,mood,subgenre));

  pool.sort((a,b)=>(Math.abs(a.d-targetKm)+rideDirectionDelta(a.br,targetBearing)/10+Math.random()*4)-(Math.abs(b.d-targetKm)+rideDirectionDelta(b.br,targetBearing)/10+Math.random()*4));
  const pick=pool.length?rand(pool.slice(0,Math.min(24,pool.length))):null;
  const mapQuery=rideMapQuery(mood,subgenre);
  const mapUrl=rideMapSearchUrl(o,mapQuery,targetKm,targetBearing),host=$('rideResult');if(!host)return;host.className='result';
  const searchDirection=dirText16(targetBearing);
  const directionLabel=direction==='random'?'🎲 おまかせ → '+searchDirection:RIDE_DIRECTION_LABELS[direction];
  const subgenreLabel=subgenre?rideSubgenreLabel(mood,subgenre):'';
  const searchTheme=subgenre?(RIDE_MOOD_LABELS[mood]+' ＞ '+subgenreLabel):(RIDE_MOOD_LABELS[mood]||mood);
  const selectedSubgenre=rideSubgenreSelections[mood]||null;
  const searchGuide='<div class="ride-search-guide">'+
    '<div class="ride-search-guide-title">📍 今回探す場所</div>'+
    '<div class="ride-search-area"><span class="ride-search-label">エリア</span><b>スタート地点から '+esc(searchDirection)+'へ 約'+targetKm+'km 周辺</b></div>'+
    '<div class="ride-search-sub">目安 '+band.min+'〜'+band.max+'km / 検索方向 ±'+RIDE_DIRECTION_HALF_WIDTH+'°</div>'+
    '<div class="ride-search-area"><span class="ride-search-label">探すもの</span><b>'+esc(searchTheme)+'</b></div>'+
    '<div class="ride-search-query">Google Maps 検索ワード：<b>'+esc(mapQuery)+'</b></div>'+
    '</div>';
  let registered='';
  if(pick){
    const saveAction="saveSingle('今日の走り方','"+escJs(pick.name)+"',"+pick.lat+","+pick.lng+",'"+escJs(pick.kind)+"','"+escJs(o.label)+"',"+o.lat+","+o.lng+")";
    registered='<div class="ride-registered"><div class="ride-result-kicker">📚 アプリ登録候補</div>'+spotCard(pick,pick.kind,pick.d,false,saveAction,0,o)+'</div>';
  }else registered='<div class="ride-registered ride-empty"><div class="ride-result-kicker">📚 アプリ登録候補</div><p class="meta">'+band.min+'〜'+band.max+'km・'+esc(directionLabel)+'方向では登録候補が見つからなかったよ。Google Maps側で探してみよう。</p></div>';

  const changer=rideSubgenreConfig(mood)
    ?'<div class="ride-mood-change-wrap"><button type="button" class="ride-mood-change-button" onclick="openRideSubgenreChanger(\''+escJs(mood)+'\')">🔄 探すものジャンルを変える <span>現在：'+esc(subgenreLabel)+(selectedSubgenre==='random'?'（おまかせ）':'')+'</span></button></div>'
    :'';

  host.innerHTML='<div class="ride-result-head"><div class="ride-result-title">'+esc(RIDE_DISTANCE_LABELS[String(targetKm)]||targetKm+'km')+' × '+esc(RIDE_MOOD_LABELS[mood]||mood)+'</div>'+
    '<div class="meta">直線距離 '+band.min+'〜'+band.max+'km / 方向 '+esc(directionLabel)+'（±'+RIDE_DIRECTION_HALF_WIDTH+'°）</div></div>'+
    searchGuide+
    changer+
    '<div class="ride-map-search"><a class="mapbtn primary" href="'+mapUrl+'" target="_blank" rel="noopener">🗺 このエリアをGoogle Mapsで探す</a></div>'+registered;
}
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
        <div class="map-pick-row"><button class="soft start-map" onclick="openStartMap('interestSave')">🗺 Googleマップでスタート地点を選ぶ</button><button class="info-btn" onclick="showMapStartHelp()" title="使い方">ⓘ</button></div>
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
function spotCard(x,kind,d,selectable=false,saveAction=null,index=0,routeOrigin=null,detailAction=null){const navActions=routeOrigin?routeButtons(routeOrigin,[x]):mapBtn(x);const tripActions=routeOrigin?'':tripSpotActions(x,kind);return `<div class="spot-card"><div class="spot-main${detailAction?' detail-clickable':''}"${detailAction?` onclick="${detailAction}" role="button" tabindex="0"`:''}>${selectable?`<input class="spot-select near-check" type="checkbox" data-i="${index}">`:''}${iconBadge(x,kind)}<div class="spot-info"><h3>${esc(x.name)}</h3><div class="meta">${esc(spotMeta(x,kind,d))}</div>${x.summary?`<div class="meta">${esc(x.summary)}</div>`:''}</div></div><div class="actions">${navActions}${saveAction?`<button class="soft" onclick="${saveAction}">保存</button>`:''}${tripActions}</div></div>`}
function interestItemById(id,kind){const src=kind==='道の駅'?D.roads:D.landmarks;const x=src.find(v=>String(v.id)===String(id));return x?{...x,kind}:null}
function showInterestDetailById(id,kind){const x=interestItemById(id,kind);if(!x)return;const details=[];if(x.summary)details.push(`<p>${esc(x.summary)}</p>`);if(x.access)details.push(`<div class="detail-block"><b>🚗 アクセス</b><div>${esc(x.access)}</div></div>`);if(x.arrivalPointType)details.push(`<div class="detail-block"><b>📍 到着目安</b><div>${esc(x.arrivalPointType)}</div></div>`);modal(`<h2 class="detail-title">${esc(x.name)}</h2><div class="meta detail-meta">${esc(spotMeta(x,kind,null))}</div>${details.join('')||'<p class="meta">この地点の追加説明は登録されていません。</p>'}<div class="route-buttons detail-route">${mapBtn(x,'Googleマップで確認')}</div><div class="actions trip-detail-actions">${tripSpotActions(x,kind)}</div>`)}


const TRIP_HISTORY_KEY='michinotochu_trip_history_v1';
const TRIP_NEARBY_KM=0.3;

function loadTripStore(){
  try{
    const v=JSON.parse(localStorage.getItem(TRIP_HISTORY_KEY)||'null');
    if(v&&v.records&&typeof v.records==='object')return v;
  }catch(e){}
  return{records:{}};
}
function saveTripStore(store){localStorage.setItem(TRIP_HISTORY_KEY,JSON.stringify(store))}
function tripRegisteredKey(x,kind){
  const prefix=kind==='道の駅'?'road':'spot';
  const id=(x&&x.id!==undefined&&x.id!==null&&String(x.id)!=='')?String(x.id):'';
  if(id)return prefix+':id:'+id;
  return prefix+':geo:'+Number(x.lat).toFixed(6)+','+Number(x.lng).toFixed(6);
}
function findRegisteredSpotByTripKey(key){
  const isRoad=String(key).startsWith('road:');
  const src=isRoad?D.roads:D.landmarks;
  const body=String(key).replace(/^(road|spot):/,'');
  let x=null;
  if(body.startsWith('id:')){
    const id=body.slice(3);
    x=src.find(v=>String(v.id)===id)||null;
  }else if(body.startsWith('geo:')){
    const [la,ln]=body.slice(4).split(',').map(Number);
    x=src.find(v=>Math.abs((+v.lat)-la)<1e-5&&Math.abs((+v.lng)-ln)<1e-5)||null;
  }
  if(!x)return null;
  return{...x,kind:isRoad?'道の駅':pointKind(x)};
}
function makeRegisteredTripRecord(key){
  const x=findRegisteredSpotByTripKey(key); if(!x)return null;
  const now=new Date().toISOString();
  return{
    key,registered:true,spotId:x.id??null,kind:x.kind,name:x.name||'登録地点',
    lat:+x.lat,lng:+x.lng,prefecture:x.prefecture||'',municipality:x.municipality||'',
    starred:false,starredAt:null,notes:[],visits:[],createdAt:now,updatedAt:now
  };
}
function tripRecordByKey(key){return loadTripStore().records[key]||null}
function tripRecordForEdit(key){return tripRecordByKey(key)||makeRegisteredTripRecord(key)}
function tripDateTime(v){try{return new Date(v).toLocaleString('ja-JP',{year:'numeric',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}catch(e){return''}}
function tripLastActivity(r){
  const a=[r.updatedAt,r.starredAt,...(r.visits||[]).map(v=>v.at),...(r.notes||[]).map(n=>n.at)].filter(Boolean).map(v=>new Date(v).getTime()).filter(Number.isFinite);
  return a.length?Math.max(...a):0;
}
function tripMemoCount(r){return Array.isArray(r?.notes)?r.notes.length:0}
function tripLatestMemo(r){const n=Array.isArray(r?.notes)&&r.notes.length?r.notes[r.notes.length-1]:null;return n?n.text:''}
function tripSpotActions(x,kind){
  if(!x||!Number.isFinite(+x.lat)||!Number.isFinite(+x.lng))return'';
  const key=tripRegisteredKey(x,kind),r=tripRecordByKey(key),on=!!r?.starred,count=tripMemoCount(r);
  return '<button type="button" class="soft trip-star-btn'+(on?' is-on':'')+'" data-trip-star-key="'+esc(key)+'" onclick="toggleTripStar(\''+escJs(key)+'\')">'+(on?'★':'☆')+'</button>'+
    '<button type="button" class="soft trip-memo-btn" data-trip-memo-key="'+esc(key)+'" onclick="openTripMemo(\''+escJs(key)+'\')">📝 メモ'+(count?' '+count:'')+'</button>';
}
function refreshTripSpotButtons(key){
  const r=tripRecordByKey(key),on=!!r?.starred,count=tripMemoCount(r);
  document.querySelectorAll('[data-trip-star-key]').forEach(b=>{if(b.dataset.tripStarKey===key){b.textContent=on?'★':'☆';b.classList.toggle('is-on',on)}});
  document.querySelectorAll('[data-trip-memo-key]').forEach(b=>{if(b.dataset.tripMemoKey===key)b.textContent='📝 メモ'+(count?' '+count:'')});
}
function toggleTripStar(key){
  const store=loadTripStore();
  let r=store.records[key]||makeRegisteredTripRecord(key); if(!r)return;
  const next=!r.starred;
  const msg=next?'「'+r.name+'」を ★ 訪問済みにしますか？':'「'+r.name+'」の ★ 訪問済みを解除しますか？\nメモや訪問記録は残ります。';
  if(!confirm(msg))return;
  r.starred=next;r.starredAt=next?new Date().toISOString():null;r.updatedAt=new Date().toISOString();
  store.records[key]=r;saveTripStore(store);refreshTripSpotButtons(key);
  if(document.querySelector('#trip.view.active'))renderTripHistory();
}
function tripMemoListHtml(r){
  const notes=r?.notes||[];
  if(!notes.length)return'<div class="trip-no-memo">まだメモはありません。</div>';
  return '<div class="trip-memo-list">'+notes.map(n=>'<div class="trip-memo-entry"><div class="trip-memo-date">'+esc(tripDateTime(n.at))+'</div><div>'+esc(n.text).replace(/\n/g,'<br>')+'</div></div>').join('')+'</div>';
}
function openTripMemo(key,notice=''){
  const stored=tripRecordByKey(key),r=stored||tripRecordForEdit(key);if(!r)return;
  const map=googlePoint(r.lat,r.lng,r.name);
  const hasRecord=!!stored&&(((stored.visits||[]).length)||tripMemoCount(stored)||stored.starred);
  modal('<h2>📝 '+esc(r.name)+'</h2>'+
    (notice?'<div class="trip-memo-notice">'+esc(notice)+'</div>':'')+
    '<div class="meta">'+(r.registered?'登録地点':'未登録地点')+' / '+Number(r.lat).toFixed(6)+', '+Number(r.lng).toFixed(6)+'</div>'+
    tripMemoListHtml(r)+
    '<label class="trip-memo-label">メモを追記<textarea id="tripMemoText" rows="5" placeholder="ここで見たもの、食べたもの、また来たい理由など"></textarea></label>'+
    '<button type="button" class="primary trip-memo-add" onclick="appendTripMemo(\''+escJs(key)+'\')">📝 追記する</button>'+
    '<div class="actions"><a class="mapbtn map-check" href="'+map+'" target="_blank" rel="noopener">🗺 マップで確認</a>'+
    (!r.registered?'<button type="button" class="soft" onclick="openTripRecommendation(\''+escJs(key)+'\')">✉ 登録地点として送る</button>':'')+'</div>'+
    (tripMemoCount(r)?'<div class="trip-delete-zone"><button type="button" class="danger" onclick="deleteTripMemo(\''+escJs(key)+'\')">この地点のメモをすべて消す</button></div>':'')+
    (hasRecord?'<div class="trip-record-delete-zone"><div class="meta">'+(r.registered?'★・訪問履歴・メモをまとめて削除します。登録スポット自体は消えません。':'この未登録地点の履歴を丸ごと削除します。')+'</div><button type="button" class="danger" onclick="deleteTripRecord(\''+escJs(key)+'\')">🗑 この旅の記録を削除</button></div>':''));
}
function appendTripMemo(key){
  const text=String($('tripMemoText')?.value||'').trim();if(!text)return alert('追記するメモを入力してください。');
  const store=loadTripStore();let r=store.records[key]||tripRecordForEdit(key);if(!r)return;
  r.notes=Array.isArray(r.notes)?r.notes:[];r.notes.push({id:Date.now()+'_'+Math.random().toString(36).slice(2,6),text,at:new Date().toISOString()});
  r.updatedAt=new Date().toISOString();store.records[key]=r;saveTripStore(store);refreshTripSpotButtons(key);renderTripHistory();openTripMemo(key,'メモを追記しました。');
}
function deleteTripMemo(key){
  const store=loadTripStore(),r=store.records[key];if(!r||!tripMemoCount(r))return;
  if(!confirm('「'+r.name+'」のメモをすべて消しますか？\n訪問記録と★は残ります。'))return;
  r.notes=[];r.updatedAt=new Date().toISOString();store.records[key]=r;saveTripStore(store);refreshTripSpotButtons(key);renderTripHistory();openTripMemo(key,'メモを削除しました。');
}
function deleteTripRecord(key){
  const store=loadTripStore(),r=store.records[key];if(!r)return;
  const msg=r.registered
    ?'「'+r.name+'」の旅の記録を削除しますか？\n\n★・訪問回数・訪問日時・メモがすべて消えます。\n登録スポット自体は残ります。'
    :'「'+r.name+'」の旅の記録を丸ごと削除しますか？\n\nこの未登録地点の座標・訪問履歴・メモがすべて消えます。';
  if(!confirm(msg))return;
  delete store.records[key];
  saveTripStore(store);
  refreshTripSpotButtons(key);
  closeModal();
  renderTripHistory();
}
function allRegisteredTripSpots(){
  return[
    ...D.roads.filter(x=>Number.isFinite(+x.lat)&&Number.isFinite(+x.lng)).map(x=>({...x,kind:'道の駅'})),
    ...D.landmarks.filter(x=>Number.isFinite(+x.lat)&&Number.isFinite(+x.lng)).map(x=>({...x,kind:pointKind(x)}))
  ];
}
function nearestRegisteredTripSpot(p){
  let best=null,bd=Infinity;
  for(const x of allRegisteredTripSpots()){
    const d=dist(p.lat,p.lng,+x.lat,+x.lng);
    if(d<bd){bd=d;best=x}
  }
  return best?{spot:best,d:bd,key:tripRegisteredKey(best,best.kind)}:null;
}
async function checkTripCurrentLocation(){
  const status=$('tripCurrentStatus'),host=$('tripCurrentResult');
  if(status)status.textContent='現在地を取得しています…';
  if(host)host.innerHTML='';
  try{
    const p=await geo(),near=nearestRegisteredTripSpot(p);
    if(status)status.textContent='現在地：'+p.lat.toFixed(6)+', '+p.lng.toFixed(6);
    if(near&&near.d<=TRIP_NEARBY_KM){
      const m=Math.max(1,Math.round(near.d*1000)),x=near.spot,r=tripRecordByKey(near.key);
      host.innerHTML='<div class="trip-current-card matched"><div class="trip-current-kicker">📍 近くの登録地点が見つかりました</div><h3>'+(r?.starred?'★ ':'☆ ')+esc(x.name)+'</h3><div class="meta">'+esc(spotMeta(x,x.kind,null))+' / 現在地から約'+m+'m</div><p>この地点として旅の記録を残しますか？</p><div class="actions"><button type="button" class="primary" onclick="recordRegisteredTripVisit(\''+escJs(near.key)+'\','+p.lat+','+p.lng+')">記録を残す</button>'+mapBtn(x,'マップで確認')+'</div></div>';
    }else{
      host.innerHTML='<div class="trip-current-card unmatched"><div class="trip-current-kicker">📌 近くに登録地点はありません</div><h3>この座標を旅の履歴に残せます</h3><div class="meta">'+p.lat.toFixed(6)+', '+p.lng.toFixed(6)+'</div><p>どんな場所だったかをメモして保存します。</p><button type="button" class="primary" onclick="openCustomTripRecord('+p.lat+','+p.lng+')">この場所の記録を残す</button></div>';
    }
  }catch(e){
    if(status)status.textContent='現在地を取得できませんでした。';
    if(host)host.innerHTML='<div class="trip-current-card error">ブラウザまたは端末の位置情報を許可して、もう一度お試しください。</div>';
  }
}
function recordRegisteredTripVisit(key,lat,lng){
  const store=loadTripStore();let r=store.records[key]||makeRegisteredTripRecord(key);if(!r)return;
  const meters=Math.round(dist(+lat,+lng,r.lat,r.lng)*1000);
  if(!confirm('現在地から約'+meters+'mの「'+r.name+'」として記録しますか？'))return;
  const now=new Date().toISOString();r.starred=true;r.starredAt=r.starredAt||now;r.visits=Array.isArray(r.visits)?r.visits:[];r.visits.push({at:now,lat:+lat,lng:+lng});r.updatedAt=now;
  store.records[key]=r;saveTripStore(store);refreshTripSpotButtons(key);renderTripHistory();openTripMemo(key,'訪問記録を追加して ★ をONにしました。');
}
function openCustomTripRecord(lat,lng){
  modal('<h2>📌 未登録地点を記録</h2><div class="meta">座標：'+Number(lat).toFixed(6)+', '+Number(lng).toFixed(6)+'</div>'+
    '<label class="trip-memo-label">場所の呼び名（任意）<input id="tripCustomName" placeholder="例：海沿いの小さな展望所"></label>'+
    '<label class="trip-memo-label">どんな場所？（必須）<textarea id="tripCustomMemo" rows="6" placeholder="景色、雰囲気、立ち寄った理由などを残してください。"></textarea></label>'+
    '<button type="button" class="primary trip-memo-add" onclick="saveCustomTripRecord('+Number(lat)+','+Number(lng)+')">この場所を保存</button>');
}
function saveCustomTripRecord(lat,lng){
  const memo=String($('tripCustomMemo')?.value||'').trim();if(!memo)return alert('どんな場所だったか、メモを残してください。');
  const name=String($('tripCustomName')?.value||'').trim();
  const now=new Date().toISOString(),key='custom:'+Date.now()+'_'+Math.random().toString(36).slice(2,7);
  const r={key,registered:false,spotId:null,kind:'未登録地点',name:name||'未登録地点',lat:+lat,lng:+lng,prefecture:'',municipality:'',starred:true,starredAt:now,notes:[{id:Date.now()+'_n',text:memo,at:now}],visits:[{at:now,lat:+lat,lng:+lng}],createdAt:now,updatedAt:now};
  const store=loadTripStore();store.records[key]=r;saveTripStore(store);closeModal();renderTripHistory();
  const host=$('tripCurrentResult');if(host)host.innerHTML='<div class="trip-current-card saved">✓ 未登録地点として旅の履歴に保存しました。</div>';
}
function openTripRecommendation(key){
  const r=tripRecordByKey(key);if(!r||r.registered)return;
  const memo=(r.notes||[]).map(n=>n.text).join('\n---\n');
  openContact();contactSelectCategory('オススメ追加');
  const form=$('contactForm');if(!form)return;
  if(form.elements.recommendType)form.elements.recommendType.value='寄り道';
  if(form.elements.title)form.elements.title.value=(r.name&&r.name!=='未登録地点')?r.name:'';
  if(form.elements.mapUrl)form.elements.mapUrl.value=googlePoint(r.lat,r.lng,r.name);
  const coord=Number(r.lat).toFixed(6)+','+Number(r.lng).toFixed(6);
  if(form.elements.coordinates)form.elements.coordinates.value=coord;
  if(form.elements.details)form.elements.details.value=(memo?memo+'\n\n':'')+'旅の履歴から送信';
}
function renderTripHistory(){
  const host=$('tripHistoryList'),count=$('tripHistoryCount');if(!host)return;
  const store=loadTripStore();
  const list=Object.values(store.records).filter(r=>r&&((r.visits||[]).length||tripMemoCount(r)||r.starred)).sort((a,b)=>tripLastActivity(b)-tripLastActivity(a));
  if(count)count.textContent=list.length+'地点';
  if(!list.length){host.innerHTML='<div class="panel trip-empty-history">まだ旅の記録はありません。<br>「現在地を取得して記録」から最初の1件を残してみよう。</div>';return}
  host.innerHTML=list.map(r=>{
    const visits=r.visits||[],last=visits.length?visits[visits.length-1]:null,memo=tripLatestMemo(r);
    const key=escJs(r.key),map=googlePoint(r.lat,r.lng,r.name);
    return '<div class="trip-history-card"><div class="trip-history-top"><div><div class="trip-history-name">'+(r.starred?'★ ':'☆ ')+esc(r.name)+'</div><div class="meta">'+esc(r.registered?(r.kind||'登録地点'):'未登録地点')+(r.prefecture?' / '+esc(r.prefecture)+' '+esc(r.municipality||''):'')+'</div></div><span class="trip-visit-count">'+(visits.length?'訪問 '+visits.length+'回':'訪問時刻なし')+'</span></div>'+
      (last?'<div class="trip-last-visit">最後の記録：'+esc(tripDateTime(last.at))+'</div>':'')+
      (memo?'<div class="trip-history-memo">'+esc(memo).replace(/\n/g,'<br>')+'</div>':'<div class="trip-history-memo empty-memo">メモなし</div>')+
      '<div class="actions"><a class="mapbtn map-check" href="'+map+'" target="_blank" rel="noopener">🗺 マップで確認</a>'+
      (r.registered?'<button type="button" class="soft trip-star-btn'+(r.starred?' is-on':'')+'" data-trip-star-key="'+esc(r.key)+'" onclick="toggleTripStar(\''+key+'\')">'+(r.starred?'★':'☆')+'</button>':'')+
      '<button type="button" class="soft trip-memo-btn" data-trip-memo-key="'+esc(r.key)+'" onclick="openTripMemo(\''+key+'\')">📝 メモ'+(tripMemoCount(r)?' '+tripMemoCount(r):'')+'</button>'+
      (!r.registered?'<button type="button" class="soft" onclick="openTripRecommendation(\''+key+'\')">✉ 登録地点として送る</button>':'')+
      '</div></div>';
  }).join('');
}

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
    const ids=['sugResult','destResult','relayResult','relayHistory','seasonResult','nearbyResult','rideResult','interestResult'];
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
function init(){if(window.HOME_SPRITE_B64)document.documentElement.style.setProperty('--home-sprite-image',`url("data:image/webp;base64,${window.HOME_SPRITE_B64}")`);renderStartPanels();fillSelectors();rideRestoreSelection();initChoiceUI();initRideStyleUI();const fv=$('footerVersion');if(fv)fv.textContent=APP_VERSION+' / DB Ver'+(localStorage.getItem('michino_db_version')||'2.8.20');restoreReturnState();}
init();
