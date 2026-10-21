"use strict";
(function(){
const el=id=>document.getElementById(id);const state={target:null,stops:[]};
const esc=v=>String(v==null?"":v).replace(/[&<>"\x27]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","\x27":"&#39;"}[c]));
const valid=p=>p&&p.lat!=null&&p.lng!=null&&Number.isFinite(+p.lat)&&Number.isFinite(+p.lng);
const label=p=>valid(p)?p.lat+","+p.lng:(p.navQuery||p.name||"");
const dKm=(a,b)=>{const r=x=>x*Math.PI/180,dl=r(b.lat-a.lat),do_=r(b.lng-a.lng),v=Math.sin(dl/2)**2+Math.cos(r(a.lat))*Math.cos(r(b.lat))*Math.sin(do_/2)**2;return 12742*Math.atan2(Math.sqrt(v),Math.sqrt(1-v))};
const azimuth=(a,b)=>{const r=x=>x*Math.PI/180,y=Math.sin(r(b.lng-a.lng))*Math.cos(r(b.lat)),x=Math.cos(r(a.lat))*Math.sin(r(b.lat))-Math.sin(r(a.lat))*Math.cos(r(b.lat))*Math.cos(r(b.lng-a.lng));return(Math.atan2(y,x)*180/Math.PI+360)%360};
const groupOptions=[["","すべて"],["cafe","カフェ・飲食"],["shop","バイクショップ"],["rest","ライダー休憩所"],["lodging","ライダー向け宿泊"],["service","整備・サービス"],["community","交流スポット"]];
const origin=()=>typeof origins!=="undefined"?origins.ride:null;
function spots(goalOnly=false){const data=window.APP_DATA||{};return [...(data.roads||[]).map(x=>({...x,tourGroup:"road"})),...(data.landmarks||[]).map(x=>({...x,tourGroup:x.level==="A"?"A":"B"})),...(window.RIDERS_CAFES||[]).filter(x=>(x.publish!==false||x.testOnly)&&(!goalOnly||(x.gachaDestinationEligible===true||(x.gachaDestinationEligible!==false&&["cafe","food","rest","community"].includes(x.spotCategory||"cafe"))))).map(x=>({...x,tourGroup:"riders"}))].filter(valid)}
function categoryOptions(group){return group==="riders"?groupOptions:(group==="A"||group==="B")&&typeof FEATURES!=="undefined"?FEATURES:[["","すべて"]]}
function fillCategory(groupId,categoryId){const group=el(groupId).value;el(categoryId).innerHTML=categoryOptions(group).map(x=>"<option value="+JSON.stringify(x[0])+">"+esc(x[1])+"</option>").join("")}
function changeGroup(){
 fillCategory("tourGroup","tourCategory");
 el("tourCategory").value="";
 const eventMode=el("tourGroup").value==="roadEvent";
 // Both event and ordinary spots use the SAME destination picker.
 const picker=el("tourCandidatePicker");
 if(picker)picker.hidden=false;
 // Detailed events and manual cache refresh belong to the destination stage,
 // not the filter stage; they are shown only for event mode.
 const eventBox=el("tourEventsBox"),list=el("tourEventList"),btn=el("tourEventListBtn");
 if(eventBox)eventBox.hidden=!eventMode;
 if(!eventMode&&list&&btn&& !list.hidden){
  list.hidden=true;btn.setAttribute("aria-expanded","false");
  btn.textContent="📅 条件内の開催イベントを詳しく見る";
 }
 searchSilently();
}
function changeNearGroup(){fillCategory("tourNearGroup","tourNearCategory");if(state.target)nearby()}
function byCategory(x,group,cat){return group==="riders"?(!cat||(x.spotCategory||"cafe")===cat):((group==="A"||group==="B")&&cat?featureMatch(x,cat):true)}
function dropOptions(list,selectId,placeholder,formatter){el(selectId).innerHTML='<option value="">'+esc(placeholder)+'</option>'+list.map((x,i)=>'<option value="'+i+'">'+esc(formatter(x))+'</option>').join("")}
const compass={north:0,east:90,south:180,west:270};
function tourSearchSettings(){
 const from=origin(),km=Number(el("tourDistance")?.value),tol=Number(el("tourTolerance")?.value);
 const dir=el("tourDirection")?.value||"all";
 if(!valid(from))return {error:"先に出発地点を設定してください"};
 if(!(km>0&&km<=1000&&tol>=0&&tol<=300))return {error:"距離の入力値を確認してください"};
 return {from,km,tol,dir};
}
// The target selector and the event list MUST share this filter.
// In particular, no event list may ever fall back to unfiltered nationwide data.
function goalCandidates(settings,group,cat=""){
 const {from,km,tol,dir}=settings;
 // For event search, avoid assembling unrelated landmarks and cafés.
 const source=group==="roadEvent"
  ? (window.APP_DATA?.roads||[]).filter(valid).map(x=>({...x,tourGroup:"road"}))
  : spots(true);
 // Cheap distance and direction checks MUST precede event matching.
 return source.filter(x=>group==="all"||x.tourGroup===group||group==="roadEvent")
  .filter(x=>byCategory(x,group,cat))
  .map(x=>({...x,tourKm:dKm(from,x),tourAz:azimuth(from,x)}))
  .filter(x=>x.tourKm>=Math.max(0,km-tol)&&x.tourKm<=km+tol)
  .filter(x=>dir==="all"||Math.abs((x.tourAz-compass[dir]+540)%360-180)<=33.75)
  .filter(x=>group!=="roadEvent"||activeRoadEvents(x).length>0)
  .sort((a,b)=>Math.abs(a.tourKm-km)-Math.abs(b.tourKm-km));
}
function search(){
 const settings=tourSearchSettings();
 if(settings.error){alert(settings.error);return}
 const group=el("tourGroup").value,cat=el("tourCategory").value;
 const list=goalCandidates(settings,group,cat);
 window.tourCandidates=list;
 dropOptions(list,"tourTargetSelect","目標地点を選択してください",x=>x.name+" / "+(x.prefecture||"")+" / 直線"+x.tourKm.toFixed(1)+"km"+(group==="roadEvent"?" / 📅"+activeRoadEvents(x).length+"件":""));
 const distanceText="直線"+Math.max(0,settings.km-settings.tol)+"〜"+(settings.km+settings.tol)+"km";
 const extra=group==="roadEvent"?"・イベント開催駅のみ":"";
 el("tourCandidateCount").textContent=(group==="roadEvent"&&!eventsReady?"⚠️ イベント情報が未取得です。下の「イベント情報の更新・取得状況」から更新してください。":"候補 "+list.length+"件 / "+distanceText+extra+(list.length===0?"（条件を広げると候補が見つかることがあります）":""));
 renderRoadEventList();
}
function chooseTarget(x){if(!x)return;state.target={name:x.name,lat:x.lat,lng:x.lng,navQuery:x.navQuery||""};state.stops=[];const notice=el("tourTargetNotice");if(notice)notice.textContent="✅ 目標地点を「"+x.name+"」に設定しました。以下に目標地点から直線"+el("tourRadius").value+"km以内の追加候補を表示しています。";render();nearby();const eventInfo=el("tourTargetEventNotice");if(eventInfo){const es=activeRoadEvents(x);eventInfo.hidden=es.length===0;eventInfo.innerHTML=es.length?"<b>📅 この道の駅の開催予定イベント</b>"+es.map(e=>"<div>"+esc(e.startDate)+(e.endDate!==e.startDate?"〜"+esc(e.endDate):"")+"："+esc(e.title)+(e.url?' <a href="'+esc(e.url)+'" target="_blank" rel="noopener noreferrer">公式案内 ↗</a>':"")+"</div>").join(""):""}}
function choose(i){chooseTarget(window.tourCandidates?.[i])}
function chooseEvent(i){
 const candidate=window.tourEventCandidates?.[i];
 if(!candidate)return;
 chooseTarget(candidate);
 renderRoadEventList();
}
function nearby(){if(!state.target)return alert("目標地点を選択してください");const km=+el("tourRadius").value;if(!(km>=0&&km<=300))return alert("寄り道半径を確認してください");const group=el("tourNearGroup").value,cat=el("tourNearCategory").value;const list=spots().filter(x=>group==="all"||x.tourGroup===group).filter(x=>byCategory(x,group,cat)).filter(x=>dKm(x,state.target)<=km&&!(x.name===state.target.name&&x.lat===state.target.lat&&x.lng===state.target.lng)).sort((a,b)=>dKm(a,state.target)-dKm(b,state.target));window.tourNearList=list;dropOptions(list,"tourNearSelect","追加する寄り道地点を選択してください",x=>x.name+" / "+(x.prefecture||"")+" / 直線"+dKm(x,state.target).toFixed(1)+"km");el("tourNearCount").textContent="周辺候補 "+list.length+"件（目標地点から直線"+km+"km以内）"}
function add(x){if(!state.target)return alert("目標地点を選択してください");if(state.stops.length>=2)return alert("寄り道は最大2地点です");state.stops.push(x);render()}
function addNearby(i){const x=window.tourNearList?.[i];if(x)add({name:x.name,lat:x.lat,lng:x.lng,navQuery:x.navQuery||""})}
function chooseSelected(){const v=el("tourTargetSelect").value;if(v==="")return alert("目標地点を選択してください");choose(Number(v))}
function addNearbySelected(){const v=el("tourNearSelect").value;if(v==="")return alert("寄り道地点を選択してください");addNearby(Number(v))}
function remove(i){state.stops.splice(i,1);render()}
function render(){const mapButton=el("tourTargetMapBtn");if(mapButton)mapButton.hidden=!state.target;el("tourPlanState").innerHTML="<div>🎯 目標："+esc(state.target?.name||"未選択")+"</div>"+state.stops.map((x,i)=>"<div>☕ 寄り道"+(i+1)+"："+esc(x.name)+" <button class=\"soft tour-action tour-action-danger\" onclick=\"tourRemove("+i+")\">削除</button></div>").join("")+"<div class=\"meta\">中間経由地 "+(state.target?1+state.stops.length:0)+"/3</div>"+(state.target?'<button type="button" class="soft tour-action tour-action-map" onclick="tourPreviewRoute(true)">🗺️ 登録地点までのルート・走行距離を確認</button>':"")}
function previewRoute(includeStops=false){const from=origin(),target=state.target;if(!from||!target)return alert("出発地点と目標地点を設定してください");const path=includeStops?[target,...state.stops]:[target];const params=new URLSearchParams({api:"1",origin:label(from),destination:label(path[path.length-1]),travelmode:"driving"});if(path.length>1)params.set("waypoints",path.slice(0,-1).map(label).join("|"));if(el("tourVehicle").value==="125")params.set("avoid","highways,tolls");const url="https://www.google.com/maps/dir/?"+params.toString();if(url.length>2048)return alert("GoogleマップのURL上限を超えています");window.open(url,"_blank","noopener")}
function changeReturn(){el("tourReturnExtra").hidden=el("tourReturnSame").checked}
function openMaps(){if(!origin()||!state.target)return alert("出発地点と目標地点を設定してください");const ret=el("tourReturnSame").checked?origin():(()=>{const v=el("tourReturnName").value.trim();return v?{name:v,navQuery:v}:(typeof origins!=="undefined"&&origins.tourReturn)||null})();if(!ret)return alert("帰着地点を指定してください");const params=new URLSearchParams({api:"1",origin:label(origin()),destination:label(ret),waypoints:[state.target,...state.stops].map(label).join("|"),travelmode:"driving"});if(el("tourVehicle").value==="125")params.set("avoid","highways,tolls");const url="https://www.google.com/maps/dir/?"+params;if(url.length>2048)return alert("地名が長すぎるためGoogleマップへ渡せません");window.open(url,"_blank","noopener")}
const EVENT_URL="./data/road_events.json";let roadEvents=[];let eventsReady=false;
// Creating Intl.DateTimeFormat inside every event/station comparison blocked
// mobile browsers for seconds. Reuse one formatter and index live events once.
const jstDateFormatter=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit"});
const jpToday=()=>jstDateFormatter.format(new Date());
const roadKey=v=>String(v||"").normalize("NFKC").replace(/^道の駅[\s　「『]*(?:「|『)?/,"").replace(/[\s　・･「」『』（）()\-ー]/g,"").toLowerCase();
const prefectureKey=v=>String(v||"").replace(/[都道府県\s　]/g,"");
let indexedEventsSource=null,indexedEventsDate="",indexedEvents=new Map();
function liveEventIndex(){
 const today=jpToday();
 if(indexedEventsSource!==roadEvents||indexedEventsDate!==today){
  const next=new Map();
  for(const e of roadEvents){
   if(!e||!e.roadName||!/^\d{4}-\d{2}-\d{2}$/.test(e.endDate||"")||
      e.endDate<today||(e.publishedAt&&e.publishedAt>today)||e.status==="cancelled")continue;
   const key=roadKey(e.roadName);
   if(!next.has(key))next.set(key,[]);
   next.get(key).push(e);
  }
  indexedEvents=next;indexedEventsSource=roadEvents;indexedEventsDate=today;
 }
 return indexedEvents;
}
const activeRoadEvents=x=>(liveEventIndex().get(roadKey(x.name))||[]).filter(
 e=>!e.prefecture||!x.prefecture||prefectureKey(x.prefecture)===prefectureKey(e.prefecture));
function roadEventCacheStatus(){
 return {ready:eventsReady,checkedAt:localStorage.getItem(EVENT_CHECK_KEY)||"",
  total:roadEvents.length,sourceUpdatedAt:localStorage.getItem(EVENT_SOURCE_DATE_KEY)||""};
}

const EVENT_CACHE_KEY="michino_road_events_cache_v1";
const EVENT_CHECK_KEY="michino_road_events_checked_v1";
const EVENT_SOURCE_DATE_KEY="michino_road_events_source_date_v1";
function eventDate(v){return /^\d{4}-\d{2}-\d{2}$/.test(v||"")}
function sanitizeEvent(e){if(!e||typeof e!=="object")return null;const allowedUrl=typeof e.url==="string"&&/^https:\/\//i.test(e.url)?e.url:"";if(!e.roadName||!e.title||!eventDate(e.startDate)||!eventDate(e.endDate)||e.endDate<e.startDate)return null;return {roadName:String(e.roadName).slice(0,120),prefecture:String(e.prefecture||"").slice(0,30),title:String(e.title).slice(0,160),startDate:e.startDate,endDate:e.endDate,publishedAt:eventDate(e.publishedAt)?e.publishedAt:"",url:allowedUrl,status:e.status==="cancelled"?"cancelled":"scheduled"}}
function renderRoadEventList(){
 const list=el("tourEventList");if(!list||list.hidden)return;
 const settings=tourSearchSettings();
 window.tourEventCandidates=[];
 if(settings.error){list.innerHTML='<p class="note">'+esc(settings.error)+'。出発地点と目標距離を設定すると、条件内のイベント開催駅だけを表示します。</p>';return}
 if(!eventsReady){list.innerHTML='<p class="note">イベント情報が未取得です。「イベント情報を更新」を押してください。</p>';return}
 const stations=goalCandidates(settings,"roadEvent");
 window.tourEventCandidates=stations;
 const area="出発地点から直線"+Math.max(0,settings.km-settings.tol)+"〜"+(settings.km+settings.tol)+"km"+(settings.dir!=="all"?"・指定方角内":"");
 if(!stations.length){list.innerHTML='<p class="note">📅 '+esc(area)+'に開催予定イベントのある道の駅はありません。全国の駅は表示していません。</p>';return}
 const count=stations.reduce((n,x)=>n+activeRoadEvents(x).length,0);
 list.innerHTML='<p class="note">📅 '+esc(area)+'：該当'+stations.length+'駅・開催終了前のイベント'+count+'件</p>'+
  stations.map((x,i)=>'<div class="panel" style="margin:8px 0;padding:12px"><strong>📍 '+esc(x.name)+'</strong> <span class="note">'+esc(x.prefecture||"")+'</span><div class="note">出発地点から直線'+x.tourKm.toFixed(1)+'km</div>'+
   activeRoadEvents(x).map(e=>'<div style="margin-top:8px"><div>📅 '+esc(e.startDate)+(e.endDate!==e.startDate?' 〜 '+esc(e.endDate):'')+'</div><div>'+esc(e.title)+'</div>'+(e.url?'<div style="margin-top:6px"><a href="'+esc(e.url)+'" target="_blank" rel="noopener noreferrer">公式イベント案内 ↗</a></div>':'')+'</div>').join("")+
   '<button type="button" class="soft tour-action tour-action-select" style="width:100%;margin-top:10px" onclick="tourChooseEvent('+i+')">'+(state.target&&state.target.name===x.name&&+state.target.lat===+x.lat&&+state.target.lng===+x.lng?'✅ 目標に登録済み':'🎯 この道の駅を目標に登録')+'</button></div>').join("");
}
function toggleRoadEventList(){const list=el("tourEventList"),btn=el("tourEventListBtn");if(!list||!btn)return;list.hidden=!list.hidden;btn.setAttribute("aria-expanded",String(!list.hidden));btn.textContent=list.hidden?"📅 条件内の開催イベントを詳しく見る":"📅 イベント詳細を閉じる";renderRoadEventList()}
function renderEventStatus(message){const e=el("tourEventStatus");if(!e)return;const checked=localStorage.getItem(EVENT_CHECK_KEY),active=Array.from(liveEventIndex().values()).reduce((n,v)=>n+v.length,0);e.textContent=(message?message+" / ":"")+(checked?"最終取得："+new Date(checked).toLocaleString("ja-JP"):"未取得")+" / 元データ更新："+(localStorage.getItem(EVENT_SOURCE_DATE_KEY)||"不明")+" / 登録 "+roadEvents.length+"件（終了前 "+active+"件）"}
function loadLocalRoadEvents(){try{const payload=JSON.parse(localStorage.getItem(EVENT_CACHE_KEY)||"null");roadEvents=Array.isArray(payload?.events)?payload.events.map(sanitizeEvent).filter(Boolean):[];eventsReady=!!payload}catch(e){roadEvents=[];eventsReady=false}renderEventStatus();searchSilently()}
async function updateRoadEvents(){const btn=el("tourEventUpdateBtn");if(btn){btn.disabled=true;btn.textContent="⏳ イベント情報を取得中…"}try{const res=await fetch(EVENT_URL+"?t="+Date.now(),{cache:"no-store"});if(!res.ok)throw Error("HTTP "+res.status);const payload=await res.json();if(payload?.schemaVersion!==1||!Array.isArray(payload.events))throw Error("イベントJSONの形式が不正です");const cleaned=payload.events.map(sanitizeEvent);if(cleaned.some(x=>!x))throw Error("不正なイベント情報が含まれています");localStorage.setItem(EVENT_CACHE_KEY,JSON.stringify({events:cleaned}));localStorage.setItem(EVENT_CHECK_KEY,new Date().toISOString());localStorage.setItem(EVENT_SOURCE_DATE_KEY,/^\d{4}-\d{2}-\d{2}$/.test(payload.updatedAt||"")?payload.updatedAt:"");roadEvents=cleaned;eventsReady=true;renderEventStatus("✅ 更新しました");renderRoadEventList();alert("イベント情報を更新しました！ 登録 "+roadEvents.length+"件。");if(el("tourGroup")?.value==="roadEvent")searchSilently();if(el("interestType")?.value==="roadEvent")window.runInterest?.()}catch(e){console.warn("イベント情報の取得失敗",e);renderEventStatus("⚠️ 取得失敗："+String(e.message||e).slice(0,100)+"。以前のデータを使用中");alert("イベント情報の取得に失敗しました。\n"+String(e.message||e)+"\n通信状態を確認して再度お試しください。")}finally{if(btn){btn.disabled=false;btn.textContent="🔄 イベント情報を更新"}}}
function searchSilently(){
 const settings=tourSearchSettings();
 if(settings.error){
  window.tourCandidates=[];
  dropOptions([],"tourTargetSelect",settings.error==="先に出発地点を設定してください"?"出発地点を設定してください":"距離条件を確認してください",x=>x.name);
  el("tourCandidateCount").textContent=settings.error;
  renderRoadEventList();
  return;
 }
 search();
}
const PLAN_KEY="michino_touring_plans_v1";let activePlanId=null;
function allPlans(){try{const a=JSON.parse(localStorage.getItem(PLAN_KEY)||"[]");return Array.isArray(a)?a:[]}catch(e){return[]}}
function selectedReturn(){if(el("tourReturnSame").checked)return origin();const v=el("tourReturnName").value.trim();return v?{name:v,navQuery:v}:(typeof origins!=="undefined"&&origins.tourReturn)||null}
function planSnapshot(){if(!origin()||!state.target)return null;return{id:activePlanId||null,name:el("tourPlanName").value.trim()||"今日のツーリング",origin:{...origin()},target:{...state.target},stops:state.stops.map(x=>({...x})),returnSame:el("tourReturnSame").checked,returnPoint:el("tourReturnSame").checked?null:selectedReturn(),vehicle:el("tourVehicle").value,updatedAt:new Date().toISOString()}}
function savePlan(asNew=false){const plan=planSnapshot();if(!plan)return alert("出発地点と目標地点を設定してください");if(!plan.returnSame&&!plan.returnPoint)return alert("帰着地点を設定してください");const plans=allPlans();if(!asNew&&activePlanId){const i=plans.findIndex(x=>x.id===activePlanId);if(i>=0){plans[i]={...plan,id:activePlanId};localStorage.setItem(PLAN_KEY,JSON.stringify(plans));renderPlans();alert("計画を上書き保存しました");return}}if(plans.length>=30)return alert("保存できるツーリング計画は30件までです");plan.id=Date.now()+"-"+Math.random().toString(36).slice(2,7);activePlanId=plan.id;plans.unshift(plan);localStorage.setItem(PLAN_KEY,JSON.stringify(plans));renderPlans();alert("ツーリング計画を保存しました")}
function loadPlan(id){const p=allPlans().find(x=>x.id===id);if(!p)return;activePlanId=id;setOrigin("ride",p.origin.lat,p.origin.lng,p.origin.label||"保存した出発地");state.target={...p.target};state.stops=Array.isArray(p.stops)?p.stops.slice(0,2):[];el("tourPlanName").value=p.name||"";el("tourVehicle").value=p.vehicle||"250";el("tourReturnSame").checked=p.returnSame!==false;el("tourReturnName").value="";if(!p.returnSame&&p.returnPoint){if(valid(p.returnPoint))setOrigin("tourReturn",p.returnPoint.lat,p.returnPoint.lng,p.returnPoint.label||p.returnPoint.name||"保存した帰着地");else el("tourReturnName").value=p.returnPoint.navQuery||p.returnPoint.name||""}changeReturn();render();renderPlans();const notice=el("tourTargetNotice");if(notice)notice.textContent="✅ 保存した計画の目標地点「"+(state.target?.name||"未設定")+"」を読み込みました。";if(state.target)nearby();showView("ride")}
function deletePlan(id){if(!confirm("このツーリング計画を削除しますか？"))return;localStorage.setItem(PLAN_KEY,JSON.stringify(allPlans().filter(x=>x.id!==id)));if(activePlanId===id)activePlanId=null;renderPlans()}
function renderPlans(){const area=el("tourSavedPlans");if(!area)return;const plans=allPlans();area.innerHTML='<option value="">保存した計画を選択</option>'+plans.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+" / "+esc((p.updatedAt||"").slice(0,10))+'</option>').join("");if(activePlanId&&plans.some(p=>p.id===activePlanId))area.value=activePlanId}
function renderFavoritePlans(){const node=el("tourFavoriteList");if(!node)return;const plans=allPlans();node.innerHTML=plans.length?plans.map((p,i)=>'<div class="fav-card"><div class="fav-top"><div><span class="pill">ツーリング計画</span><h3>'+esc(p.name||"今日のツーリング")+'</h3></div></div><div class="meta">スタート：'+esc(p.origin?.label||"出発地点")+' → 目標：'+esc(p.target?.name||"未設定")+' / 追加 '+(p.stops?.length||0)+'件<br>帰着：'+esc(p.returnSame!==false?"出発地点と同じ":p.returnPoint?.label||p.returnPoint?.name||"別指定")+' / 保存日 '+esc((p.updatedAt||"").slice(0,10))+'</div><div class="actions"><button type="button" class="soft" onclick="tourOpenFavoritePlan('+i+')">✏️ 今日の走り方で編集</button><button type="button" class="soft" onclick="tourMapFavoritePlan('+i+')">🗺 Googleマップで確認</button></div></div>').join(""):'<div class="note">保存したツーリング計画はまだありません。</div>'}
function openFavoritePlan(i){const p=allPlans()[i];if(p)loadPlan(p.id)}
function mapFavoritePlan(i){const p=allPlans()[i];if(!p?.origin||!p.target)return alert("ルート情報が不足しています");const path=[p.target,...(p.stops||[])].slice(0,3);const destination=p.returnSame!==false?p.origin:p.returnPoint;if(!destination)return alert("帰着地点が未設定です");const params=new URLSearchParams({api:"1",origin:label(p.origin),destination:label(destination),waypoints:path.map(label).join("|"),travelmode:"driving"});if(p.vehicle==="125")params.set("avoid","highways,tolls");const url="https://www.google.com/maps/dir/?"+params.toString();if(url.length>2048)return alert("Googleマップ連携URLが長すぎます");window.open(url,"_blank","noopener")}
function loadSelected(){const id=el("tourSavedPlans").value;if(id)loadPlan(id)}
function deleteSelected(){const id=el("tourSavedPlans").value;if(id)deletePlan(id)}
function sendToDetour(){if(!origin()||!state.target)return alert("先に出発地点と目標地点を指定してください");const snapshot=planSnapshot();if(!snapshot)return;window.tourImportToDetour?.(snapshot);showView("detour")}
function importFromDetour(){const chosen=window.tourExportFromDetour?.();if(!chosen)return alert("寄り道から取り込む地点がありません");if(chosen.length>2)return alert("寄り道は最大2地点です。寄り道しようで選択数を減らしてください");state.stops=chosen.map(p=>({name:p.name||"寄り道地点",lat:p.lat,lng:p.lng,navQuery:p.navQuery||""}));render();showView("ride");alert("寄り道"+chosen.length+"地点を反映しました。保存すると計画を更新できます。")}


function exportPoints(){
 const from=origin();
 if(!valid(from)||!valid(state.target))throw new Error("出発地点と目標地点を設定してね。");
 let ret;
 if(el("tourReturnSame").checked)ret=from;
 else {
  const typed=el("tourReturnName").value.trim();
  ret=typed?null:(typeof origins!=="undefined"?origins.tourReturn:null);
  if(!valid(ret))throw new Error("帰着地点は座標で指定してね。地図か現在地から選べるよ。");
 }
 const stops=[state.target,...state.stops];
 if(stops.length>6)throw new Error("経由地は最大6地点までだよ。");
 const all=[{role:"START",point:from},...stops.map(point=>({role:"VIA",point})),{role:"GOAL",point:ret}];
 if(all.some(x=>!valid(x.point)))throw new Error("座標を持たない地点があるよ。");
 const cell=value=>'"'+String(value??"").replace(/"/g,'""').replace(/[\\r\\n]+/g," ")+'"';
 return "BIKENAV-ROUTE/1\\n"+all.map(({role,point})=>
  [role,cell(point.name||point.label||({"START":"出発地","VIA":"経由地","GOAL":"目的地"}[role])),Number(point.lat).toFixed(7),Number(point.lng).toFixed(7)].join(",")
 ).join("\\n");
}
async function copyExportText(text){
 if(navigator.clipboard&&window.isSecureContext){try{await navigator.clipboard.writeText(text);return true}catch(e){}}
 const elText=document.createElement("textarea");elText.value=text;elText.style.position="fixed";elText.style.left="-9999px";document.body.appendChild(elText);elText.select();
 const ok=document.execCommand("copy");elText.remove();return ok;
}
async function copyRoutePoints(){
 try{const value=exportPoints();if(!await copyExportText(value))throw new Error("コピーできなかったよ。ブラウザの権限を確認してね。");alert("地点データをコピーしたよ。BikeNavigatorの貼り付け画面で使ってね。")}
 catch(e){alert(e.message||"コピーに失敗しました。")}
}
async function shareRoutePoints(){
 try{
  const value=exportPoints();
  if(navigator.share){try{await navigator.share({title:"道の途中。 地点データ",text:value});return}catch(e){if(e.name==="AbortError")return}}
  if(await copyExportText(value))alert("共有に対応していないので、地点データをコピーしたよ。");
  else throw new Error("共有・コピーに失敗したよ。");
 }catch(e){alert(e.message||"共有に失敗しました。")}
}

window.tourCopyRoutePoints=copyRoutePoints;window.tourShareRoutePoints=shareRoutePoints;
window.tourEventsForStation=activeRoadEvents;window.tourEventCacheStatus=roadEventCacheStatus;window.tourChooseEvent=chooseEvent;window.tourRefreshCandidates=searchSilently;window.tourRefreshEventList=renderRoadEventList;window.tourPreviewRoute=previewRoute;window.tourToggleEventList=toggleRoadEventList;window.tourUpdateRoadEvents=updateRoadEvents;window.tourRenderFavoritePlans=renderFavoritePlans;window.tourOpenFavoritePlan=openFavoritePlan;window.tourMapFavoritePlan=mapFavoritePlan;window.tourGroupChanged=changeGroup;window.tourSavePlan=()=>savePlan(false);window.tourSavePlanAs=()=>savePlan(true);window.tourLoadSelected=loadSelected;window.tourDeleteSelected=deleteSelected;window.tourSendToDetour=sendToDetour;window.tourImportFromDetour=importFromDetour;window.tourNearGroupChanged=changeNearGroup;window.tourChooseSelected=chooseSelected;window.tourAddNearbySelected=addNearbySelected;window.tourSearch=search;window.tourChoose=choose;window.tourSearchNearby=nearby;window.tourAddNearby=addNearby;window.tourRemove=remove;window.tourReturnChanged=changeReturn;window.tourOpenMaps=openMaps;
document.addEventListener("DOMContentLoaded",()=>{if(el("tourGroup")){
 changeGroup();changeNearGroup();render();changeReturn();renderPlans();loadLocalRoadEvents();
 // Recalculate options when a filter changes, without a separate search button.
 ["tourDistance","tourTolerance","tourDirection","tourCategory"].forEach(id=>{
  const field=el(id);
  if(field)field.addEventListener("change",searchSilently);
 });
 // Nearby options are recalculated after changing their own conditions;
 // no extra "update nearby spots" button is needed.
 ["tourRadius","tourNearCategory"].forEach(id=>{
  const field=el(id);
  if(field)field.addEventListener("change",()=>{if(state.target)nearby()});
 });
}});
})();
