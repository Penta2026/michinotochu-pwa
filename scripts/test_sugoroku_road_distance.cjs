"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {buildRequestUrl,decodeRoute,calculate}=require("../sugoroku-road-distance.js");
const origin={lat:34.3975,lng:132.4596};
const point={lat:34.501,lng:132.577};
const goal={lat:34.608,lng:132.715};

test("external call uses opt-in GET with valid ordered lon-lat waypoints",()=>{
 const url=buildRequestUrl(origin,[point,goal]);
 assert.match(url,/^https:\/\/routing\.openstreetmap\.de\/routed-car\/route\/v1\/driving\//);
 assert.ok(url.indexOf("132.459600,34.397500")<url.indexOf("132.577000,34.501000"));
 assert.ok(url.indexOf("132.577000,34.501000")<url.indexOf("132.715000,34.608000"));
 assert.match(url,/overview=false&steps=false&alternatives=false$/);
 assert.throws(()=>buildRequestUrl(origin,[]),/invalid_waypoints/);
 assert.throws(()=>buildRequestUrl(origin,[{lat:NaN,lng:132}]),/invalid_waypoints/);
});

test("reject invalid, absent, or incomplete road measurements",()=>{
 const good={code:"Ok",routes:[{distance:42000,legs:[{distance:18000},{distance:24000}]}]};
 assert.equal(decodeRoute(good,2,32).totalKm,42);
 for(const broken of [
  {code:"NoRoute",routes:[]},
  {code:"Ok",routes:[{distance:42000,legs:[{distance:18000}]}]},
  {code:"Ok",routes:[{distance:40000,legs:[{distance:18000},{distance:24000}]}]},
 ]){
  assert.throws(()=>decodeRoute(broken,2,32));
 }
 assert.throws(()=>decodeRoute(good,2,43),/invalid_road_distance/);
});

test("one explicit user action yields one route request and reuses session cache",async()=>{
 let calls=0;
 const fetchImpl=async(url,options)=>{
  calls++;
  assert.equal(options.method,"GET");
  assert.equal(options.cache,"no-store");
  assert.equal(options.referrerPolicy,"strict-origin-when-cross-origin");
  return {ok:true,async json(){return {code:"Ok",routes:[{
   distance:42000,legs:[{distance:18000},{distance:24000}]
  }]}}};
 };
 const input={origin,points:[point,goal],minimumKm:32,fetchImpl};
 const result=await calculate(input);
 assert.equal(result.totalKm,42);
 assert.deepEqual(result.segmentsKm,[18,24]);
 assert.equal(result.profile,"car");
 assert.equal(result.indicative,true);
 assert.equal(result.fromCache,false);
 assert.equal((await calculate(input)).fromCache,true);
 assert.equal(calls,1);
});

test("UI requests road estimates ONLY on button click and states privacy limit",()=>{
 const app=fs.readFileSync(path.join(__dirname,"..","app.js"),"utf8");
 const html=fs.readFileSync(path.join(__dirname,"..","index.html"),"utf8");
 const privacy=fs.readFileSync(path.join(__dirname,"..","privacy.html"),"utf8");
 assert.match(app,/function showSugorokuRoadDistance\(/);
 assert.match(app,/onclick="showSugorokuRoadDistance\(\)"/);
 assert.match(app,/出発地と経由地の座標をOSRMの公開サービスへ送信/);
 assert.match(app,/四輪向けの参考値/);
 assert.match(html,/sugoroku-road-distance\.js\?v=1\.6\.31/);
 assert.match(privacy,/「道路距離を試算（外部サービス）」を利用者が押した場合に限り/);
 assert.doesNotMatch(html,/id="sugTravel"/);
});
