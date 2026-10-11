"use strict";
// Browser UI regression checks without extra npm dependencies.
// node --test scripts/test_tour_event_distance.cjs
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const tourCode = fs.readFileSync(path.join(root, "tour-plan.js"), "utf8");

const roads = [
  { name: "北100", prefecture: "東京都", lat: 35.9, lng: 139 },
  { name: "東100", prefecture: "千葉県", lat: 35, lng: 140.1 },
  { name: "遠方の駅", prefecture: "秋田県", lat: 39, lng: 139 },
  { name: "近すぎる駅", prefecture: "東京都", lat: 35.10, lng: 139 },
  { name: "終了済み駅", prefecture: "東京都", lat: 35.8, lng: 139 },
  { name: "中止の駅", prefecture: "東京都", lat: 35.85, lng: 139 },
];
const schedule = (roadName, overrides = {}) => ({
  roadName, prefecture: roads.find(r => r.name === roadName).prefecture,
  title: roadName + " のイベント",
  startDate: "2099-01-01", endDate: "2099-12-31",
  status: "scheduled", url: "https://official.example/event",
  ...overrides
});
const fixtureEvents = [
  schedule("北100"),
  schedule("東100"),
  schedule("遠方の駅"),
  schedule("近すぎる駅"),
  schedule("終了済み駅", { startDate: "2000-01-01", endDate: "2000-01-02" }),
  schedule("中止の駅", { status: "cancelled" })
];

function fixture({ ride = { lat: 35, lng: 139 }, events = fixtureEvents, roadsData = roads, landmarksData = [], onFormatter = () => {} } = {}) {
  const elements = new Map();
  const domEvents = new Map();
  const storage = new Map([
    ["michino_road_events_cache_v1", JSON.stringify({ events })],
    ["michino_road_events_checked_v1", "2026-10-12T00:00:00Z"],
  ]);
  const node = id => {
    if (!elements.has(id)) {
      const listeners = new Map();
      elements.set(id, {
        id, value: "", checked: false, hidden: false, disabled: false,
        innerHTML: "", textContent: "", listeners,
        addEventListener(type, handler) { listeners.set(type, handler); },
        setAttribute(name, value) { this[name] = value; }
      });
    }
    return elements.get(id);
  };
  const preset = {
    tourDistance: "100", tourTolerance: "20", tourDirection: "all",
    tourGroup: "roadEvent", tourCategory: "", tourNearGroup: "all",
    tourNearCategory: "", tourRadius: "20", tourVehicle: "250"
  };
  for (const [id, value] of Object.entries(preset)) node(id).value = value;
  node("tourEventList").hidden = true;
  node("tourReturnSame").checked = true;
  const ctx = {
    window: { APP_DATA: { roads: roadsData, landmarks: landmarksData }, RIDERS_CAFES: [] },
    origins: { ride },
    document: {
      getElementById: node,
      addEventListener(type, callback) { domEvents.set(type, callback); }
    },
    localStorage: {
      getItem(key) { return storage.get(key) || null; },
      setItem(key, value) { storage.set(key, value); }
    },
    alert(message) { throw new Error("Unexpected alert: " + message); },
    console, Date, Intl: { DateTimeFormat: class extends Intl.DateTimeFormat { constructor(...args) { super(...args); onFormatter(); } } }, URLSearchParams
  };
  vm.runInNewContext(tourCode, ctx, { filename: "tour-plan.js" });
  domEvents.get("DOMContentLoaded")();
  return {
    ctx, node,
    openEvents() { ctx.window.tourToggleEventList(); },
    search() {
      ctx.window.tourSearch();
      return Array.from(ctx.window.tourCandidates || [], x => x.name);
    },
    change(id, value) {
      const element = node(id);
      element.value = value;
      element.listeners.get("input")?.();
      element.listeners.get("change")?.();
    },
    html() { return node("tourEventList").innerHTML; }
  };
}

test("event list and target candidates use exactly the same distance filter", () => {
  const f = fixture();
  const expected = f.search();
  f.openEvents();
  assert.deepEqual(expected.slice().sort(), ["北100", "東100"].sort());
  for (const name of expected) assert.ok(f.html().includes(name), name);
  for (const name of ["遠方の駅", "近すぎる駅", "終了済み駅", "中止の駅"])
    assert.ok(!f.html().includes(name), "unexpected out-of-scope: " + name);
  assert.match(f.html(), /直線80〜120km/);
  assert.match(f.html(), /該当2駅/);
  assert.doesNotMatch(f.html(), /距離・方角による絞り込みなし/);
});

test("direction filtering updates the open event list just like search", () => {
  const f = fixture();
  f.openEvents();
  f.change("tourDirection", "north");
  assert.deepEqual(f.search(), ["北100"]);
  assert.ok(f.html().includes("北100"));
  assert.ok(!f.html().includes("東100"));
  f.change("tourDirection", "east");
  assert.deepEqual(f.search(), ["東100"]);
  assert.ok(f.html().includes("東100"));
  assert.ok(!f.html().includes("北100"));
});

test("distance changes update the open list without nationwide fallback", () => {
  const f = fixture();
  f.openEvents();
  f.change("tourDistance", "445");
  assert.deepEqual(f.search(), ["遠方の駅"]);
  assert.ok(f.html().includes("遠方の駅"));
  assert.ok(!f.html().includes("北100"));
  f.change("tourDistance", "700");
  assert.match(f.html(), /開催予定イベントのある道の駅はありません/);
  assert.doesNotMatch(f.html(), /<strong>📍/);
});

test("missing start location never shows nationwide events", () => {
  const f = fixture({ ride: null });
  f.openEvents();
  assert.match(f.html(), /先に出発地点を設定してください/);
  assert.ok(!f.html().includes("遠方の駅"));
});

test("invalid numeric limits never show unfiltered events", () => {
  const f = fixture();
  f.openEvents();
  f.change("tourDistance", "0");
  assert.match(f.html(), /距離の入力値を確認してください/);
  assert.ok(!f.html().includes("東100"));
  f.change("tourDistance", "100");
  f.change("tourTolerance", "301");
  assert.match(f.html(), /距離の入力値を確認してください/);
  assert.ok(!f.html().includes("東100"));
});

test("change of start location can refresh the visible event list", () => {
  const f = fixture();
  f.openEvents();
  f.ctx.origins.ride = { lat: 38.15, lng: 139 };
  f.ctx.window.tourRefreshEventList();
  assert.ok(f.html().includes("遠方の駅"));
  assert.ok(!f.html().includes("北100"));
});

test("inactive or unpublished events are excluded; event text is escaped", () => {
  const events = [
    schedule("北100", { title: "<img src=x onerror=alert(1)> 安全な案内" }),
    schedule("東100", { publishedAt: "2099-12-31" }),
    schedule("遠方の駅")
  ];
  const f = fixture({ events });
  f.openEvents();
  assert.match(f.html(), /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(f.html(), /<img /);
  assert.ok(!f.html().includes("東100"));
});

test("full station inventory does not rebuild Intl formatters or scan 500 events per station", () => {
  const near = roads.slice(0, 2);
  const manyRoads = [...near, ...Array.from({ length: 1234 }, (_, i) => ({
    name: "遠方のダミー駅" + i, prefecture: "北海道",
    lat: 43 + (i % 150) / 150, lng: 140 + (i % 150) / 50
  }))];
  const manyEvents = [
    schedule("北100"), schedule("東100"),
    ...Array.from({ length: 500 }, (_, i) => ({
      roadName: "遠方のダミー駅" + i, prefecture: "北海道",
      title: "テスト用開催イベント" + i, startDate: "2099-01-01",
      endDate: "2099-12-31", status: "scheduled"
    }))
  ];
  let formatterCreations = 0;
  const f = fixture({
    roadsData: manyRoads, events: manyEvents,
    onFormatter() { formatterCreations++; }
  });
  const start = performance.now();
  f.openEvents();
  for (let i = 0; i < 3; i++) {
    assert.deepEqual(f.search().sort(), ["北100", "東100"].sort());
  }
  assert.ok(!f.html().includes("遠方のダミー駅"));
  assert.ok(formatterCreations <= 2, "Intl.DateTimeFormat repeatedly created: " + formatterCreations);
  // Loose wall-clock protection against accidentally reintroducing O(stations * events)
  assert.ok(performance.now() - start < 5000, "event filtering unexpectedly slow");
});

test("event stations and regular spots BOTH keep the same destination picker visible", () => {
  const f = fixture();
  assert.equal(f.node("tourCandidatePicker").hidden, false);
  assert.deepEqual(Array.from(f.ctx.window.tourCandidates, x=>x.name).sort(),
    ["北100","東100"].sort());
  assert.match(f.node("tourTargetSelect").innerHTML,/北100/);
  f.change("tourGroup", "road");
  f.ctx.window.tourGroupChanged();
  assert.equal(f.node("tourCandidatePicker").hidden, false);
  assert.deepEqual(
    Array.from(f.ctx.window.tourCandidates, x=>x.name).sort(),
    ["北100", "東100", "終了済み駅", "中止の駅"].sort());
  f.change("tourGroup", "roadEvent");
  f.ctx.window.tourGroupChanged();
  assert.equal(f.node("tourCandidatePicker").hidden, false);
  assert.deepEqual(Array.from(f.ctx.window.tourCandidates, x=>x.name).sort(),
    ["北100","東100"].sort());
});

test("event mode target can be selected directly in the BOTTOM dropdown", () => {
  const f = fixture();
  assert.equal(f.node("tourCandidatePicker").hidden,false);
  assert.match(f.node("tourTargetSelect").innerHTML,/北100/);
  f.node("tourTargetSelect").value="0";
  f.ctx.window.tourChooseSelected();
  assert.match(f.node("tourTargetNotice").textContent,/北100/);
  assert.match(f.node("tourPlanState").innerHTML,/🎯 目標：北100/);
  assert.equal(f.node("tourTargetMapBtn").hidden,false);
  assert.match(f.node("tourTargetEventNotice").innerHTML,/この道の駅の開催予定イベント/);
});

test("event mode dropdown follows distance and direction and never lists nationwide stations", () => {
  const f=fixture();
  assert.equal(f.node("tourCandidatePicker").hidden,false);
  f.change("tourDirection","east");
  assert.deepEqual(Array.from(f.ctx.window.tourCandidates,x=>x.name),["東100"]);
  assert.match(f.node("tourTargetSelect").innerHTML,/東100/);
  assert.doesNotMatch(f.node("tourTargetSelect").innerHTML,/北100|遠方の駅/);
  f.change("tourDistance","700");
  assert.equal(f.ctx.window.tourCandidates.length,0);
  assert.doesNotMatch(f.node("tourTargetSelect").innerHTML,/東100|遠方の駅/);
});

test("distance and direction changes refresh normal goal picker immediately", () => {
  const f=fixture();
  f.change("tourGroup","road");
  f.ctx.window.tourGroupChanged();
  f.change("tourDistance","445");
  assert.deepEqual(Array.from(f.ctx.window.tourCandidates,x=>x.name),["遠方の駅"]);
  assert.match(f.node("tourTargetSelect").innerHTML,/遠方の駅/);
  f.change("tourDirection","east");
  assert.equal(f.ctx.window.tourCandidates.length,0);
  assert.doesNotMatch(f.node("tourTargetSelect").innerHTML,/遠方の駅/);
  f.change("tourDistance","0");
  assert.equal(f.ctx.window.tourCandidates.length,0);
  assert.match(f.node("tourCandidateCount").textContent,/距離の入力値を確認してください/);
});

test("spot category switching also refreshes the selectable candidates", () => {
  const landmarks=[
    {name:"北の定番",prefecture:"東京都",level:"A",lat:35.92,lng:139},
    {name:"東の寄り道",prefecture:"千葉県",level:"B",lat:35,lng:140.06}
  ];
  const f=fixture({landmarksData:landmarks});
  f.change("tourGroup","A");
  f.ctx.window.tourGroupChanged();
  assert.deepEqual(Array.from(f.ctx.window.tourCandidates,x=>x.name),["北の定番"]);
  f.change("tourGroup","B");
  f.ctx.window.tourGroupChanged();
  assert.deepEqual(Array.from(f.ctx.window.tourCandidates,x=>x.name),["東の寄り道"]);
  assert.match(f.node("tourTargetSelect").innerHTML,/東の寄り道/);
  f.change("tourGroup","A");
  f.ctx.window.tourGroupChanged();
  assert.doesNotMatch(f.node("tourTargetSelect").innerHTML,/東の寄り道/);
});

test("missing origin clears stale dropdown choices instead of leaving an old list", () => {
  const f=fixture();
  f.change("tourGroup","road");
  f.ctx.window.tourGroupChanged();
  assert.ok(f.ctx.window.tourCandidates.length>0);
  f.ctx.origins.ride=null;
  f.ctx.window.tourRefreshCandidates();
  assert.equal(f.ctx.window.tourCandidates.length,0);
  assert.match(f.node("tourCandidateCount").textContent,/先に出発地点を設定してください/);
  assert.doesNotMatch(f.node("tourTargetSelect").innerHTML,/北100/);
});

test("event list lets user register its station as touring goal without second search", () => {
  const f = fixture();
  f.openEvents();
  assert.match(f.html(), /onclick="tourChooseEvent\(0\)"/);
  assert.match(f.html(), /🎯 この道の駅を目標に登録/);
  f.ctx.window.tourChooseEvent(0);
  assert.match(f.node("tourTargetNotice").textContent, /北100/);
  assert.match(f.node("tourPlanState").innerHTML, /🎯 目標：北100/);
  assert.equal(f.node("tourTargetMapBtn").hidden, false);
  assert.match(f.html(), /✅ 目標に登録済み/);
  // The original registration action remains available for other groups.
  f.change("tourGroup", "road");
  f.ctx.window.tourGroupChanged();
  f.search();
  f.node("tourTargetSelect").value = "1";
  f.ctx.window.tourChooseSelected();
  assert.match(f.node("tourTargetNotice").textContent, /東100/);
});

test("the web entry point and service worker both deploy the new PWA version", () => {
  const index = fs.readFileSync(path.join(root, "index.html"), "utf8");
  const worker = fs.readFileSync(path.join(root, "service-worker.js"), "utf8");
  const version = JSON.parse(fs.readFileSync(path.join(root, "data/version.json"), "utf8"));
  assert.match(index, /tour-plan\.js\?v=1\.6\.24/);
  assert.match(index, /目標距離内のイベント開催駅を見る/);
  assert.doesNotMatch(index, /id="tourSearchBtn"/);
  assert.doesNotMatch(index, /🎯 目標地点の候補を見る/);
  assert.match(index, /id="tourCandidatePicker"/);
  assert.match(worker, /michino-shell-v1\.6\.24/);
  assert.match(worker, /tour-plan\.js\?v=1\.6\.24/);
  assert.equal(version.appVersion, "1.6.24");
});
