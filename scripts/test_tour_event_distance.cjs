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

function fixture({ ride = { lat: 35, lng: 139 }, events = fixtureEvents, roadsData = roads, onFormatter = () => {} } = {}) {
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
    window: { APP_DATA: { roads: roadsData, landmarks: [] }, RIDERS_CAFES: [] },
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

test("the web entry point and service worker both deploy the new PWA version", () => {
  const index = fs.readFileSync(path.join(root, "index.html"), "utf8");
  const worker = fs.readFileSync(path.join(root, "service-worker.js"), "utf8");
  const version = JSON.parse(fs.readFileSync(path.join(root, "data/version.json"), "utf8"));
  assert.match(index, /tour-plan\.js\?v=1\.6\.21/);
  assert.match(index, /目標距離内のイベント開催駅を見る/);
  assert.match(worker, /michino-shell-v1\.6\.21/);
  assert.match(worker, /tour-plan\.js\?v=1\.6\.21/);
  assert.equal(version.appVersion, "1.6.21");
});
