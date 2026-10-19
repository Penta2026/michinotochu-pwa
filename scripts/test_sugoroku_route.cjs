"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {plan, km, heading} = require("../sugoroku-route.js");

const origin = {lat:35, lng:132, label:"出発"};
const entry = (id, lat, lng) => ({id, name:id, prefecture:"広島県", lat, lng, gacha:true});
const eastGoal=entry("東ゴール",35,132.55);
const westGoal=entry("西ゴール",35,131.45);
const eastStations=[
  entry("東1",35,132.13),entry("東2",35,132.27),entry("東3",35,132.42),
];
const wrong=[
  entry("北方向",35.40,132.20),
  entry("出発地の西",35,131.88),
  entry("ゴールの先",35,132.64),
  entry("大回りの南",34.7,132.31),
];

test("chooses the goal FIRST; only forward stations in goal-bearing ±45 degrees",()=>{
  const result=plan({origin,stations:[...eastStations,...wrong,eastGoal],
                     distanceKm:50,count:6,random:()=>0.9});
  assert.equal(result.ok,true);
  assert.equal(result.goal.id,"東ゴール");
  assert.deepEqual(result.points.map(x=>x.id),["東1","東2","東3","東ゴール"]);
  assert.equal(result.count,4);
  assert.equal(result.requestedCount,6);
  assert.ok(result.straightLegKm <= result.goalDistanceKm*1.30);
  let last=0;
  for(const stop of result.points){
    const advance=stop.lng-origin.lng;
    assert.ok(advance>last);
    last=advance;
    const a=heading(origin,stop),g=result.bearingDegrees;
    assert.ok(Math.abs(((a-g+540)%360)-180) <= 45);
  }
});

test("draws a RANDOM goal direction; no direction setting required",()=>{
  const s=[eastGoal,westGoal];
  const east=plan({origin,stations:s,distanceKm:50,count:5,random:()=>0});
  const west=plan({origin,stations:s,distanceKm:50,count:5,random:()=>0.99});
  assert.equal(east.ok,true);
  assert.equal(west.ok,true);
  assert.equal(east.goal.id,"東ゴール");
  assert.equal(west.goal.id,"西ゴール");
  assert.deepEqual(east.points.map(x=>x.id),["東ゴール"]);
  assert.deepEqual(west.points.map(x=>x.id),["西ゴール"]);
  assert.equal(east.directionName,"東");
  assert.equal(west.directionName,"西");
});

test("never forces extra stations when none lie in the forward sector",()=>{
  const result=plan({origin,stations:[eastGoal,...wrong],distanceKm:50,
                     count:6,random:()=>0});
  assert.equal(result.ok,true);
  assert.deepEqual(result.points.map(x=>x.id),["東ゴール"]);
});

test("fails safely when there is no goal near the specified straight distance",()=>{
  const result=plan({origin,stations:[eastGoal],distanceKm:150,count:5});
  assert.equal(result.ok,false);
  assert.equal(result.reason,"no_goal");
});

test("route straight-leg sum is explicitly different from actual road distance",()=>{
  const result=plan({origin,stations:[eastGoal,...eastStations],
                     distanceKm:50,count:5,random:()=>0});
  const expected=result.points.reduce((sum,p,index)=>
    sum + km(index===0?origin:result.points[index-1],p),0);
  assert.ok(Math.abs(result.straightLegKm-expected)<0.001);
  assert.ok(result.straightLegKm>=result.goalDistanceKm-0.001);
});

test("northbound sugoroku may go northeast, northwest, then north without southward backtracking",()=>{
  const start={lat:35,lng:132};
  const goal=entry("北ゴール",35.5,132);
  const northeast=entry("北東駅",35.18,132.09);
  const northwest=entry("北西駅",35.35,131.95);
  const r=plan({origin:start,stations:[goal,northeast,northwest],
                distanceKm:56,count:3,random:()=>0});
  assert.equal(r.ok,true);
  assert.deepEqual(r.points.map(s=>s.id),["北東駅","北西駅","北ゴール"]);
  assert.equal(r.directionName,"北");
  assert.ok(r.straightDetourRatio<=1.30);
});

test("invalid count and distance do not generate a route",()=>{
  assert.equal(plan({origin,stations:[eastGoal],distanceKm:0,count:5}).ok,false);
  assert.equal(plan({origin,stations:[eastGoal],distanceKm:50,count:7}).ok,false);
  assert.equal(plan({origin,stations:[eastGoal],distanceKm:50,count:0}).ok,false);
});


test("public sugoroku never loads or offers rate-limited road-distance services",()=>{
  const fs=require("node:fs");
  const path=require("node:path");
  const root=path.resolve(__dirname,"..");
  const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
  const app=fs.readFileSync(path.join(root,"app.js"),"utf8");
  const worker=fs.readFileSync(path.join(root,"service-worker.js"),"utf8");
  for(const source of [html,app,worker]) {
    assert.doesNotMatch(source,/sugoroku-road-distance|sugRoadDistance|showSugorokuRoadDistance|routing\.openstreetmap\.de/);
  }
  assert.match(app,/const o=window\.SugorokuRoute\.plan/);
  assert.match(html,/ゴールまでの目安直線距離/);
  assert.doesNotMatch(html,/id="sugTravel"/);
});
