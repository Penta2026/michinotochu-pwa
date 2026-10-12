"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const tour = fs.readFileSync(path.join(root, "tour-plan.js"), "utf8");
const start = app.indexOf("function interestStationEventCard(");
const end = app.indexOf("function uiCategoryTags(", start);
assert.ok(start > 0 && end > start, "interest code must be present in actual app.js");
const interestCode = app.slice(start, end);
const syncStart = app.indexOf("function syncInterestFeature(){");
const syncEnd = app.indexOf("function syncRidersCategory(){", syncStart);
assert.ok(syncStart > 0 && syncEnd > syncStart, "interest filter sync must be present");
const interestSyncCode = app.slice(syncStart, syncEnd);
const roads = [
  { id: "road-tokyo", name: "北100", prefecture: "東京都", lat: 35.9, lng: 139 },
  { id: "road-chiba", name: "東100", prefecture: "千葉県", lat: 35, lng: 140.1 },
  { id: "road-other", name: "未開催", prefecture: "東京都", lat: 35.8, lng: 139 },
  { id: "road-cancelled", name: "中止の駅", prefecture: "東京都", lat: 35.85, lng: 139 },
];
const makeEvent = (roadName, prefecture, overrides = {}) => ({
  roadName, prefecture, title: roadName + " 秋まつり",
  startDate: "2099-10-18", endDate: "2099-10-18", status: "scheduled",
  url: "https://official.example/event", ...overrides
});
const events = [
  makeEvent("北100", "東京都"),
  makeEvent("東100", "千葉県", { startDate: "2099-10-11", endDate: "2099-10-11" }),
  makeEvent("未開催", "東京都", { startDate: "2000-10-10", endDate: "2000-10-11" }),
  makeEvent("中止の駅", "東京都", { status: "cancelled" })
];
function fixture({ cached = true, online = events, cachedEvents = events } = {}) {
  const elements = new Map();
  const handlers = new Map();
  const alerts = [];
  const store = new Map();
  if (cached) {
    store.set("michino_road_events_cache_v1", JSON.stringify({ events: cachedEvents }));
    store.set("michino_road_events_checked_v1", "2026-10-12T09:00:00Z");
  }
  const node = id => {
    if (!elements.has(id)) {
      const listeners = {};
      elements.set(id, {
        id, value: "", checked: false, hidden: false, disabled: false,
        innerHTML: "", textContent: "", firstChild: { textContent: "" },
        listeners,
        addEventListener(name, fn) { listeners[name] = fn; },
        setAttribute(name, v) { this[name] = v; }
      });
    }
    return elements.get(id);
  };
  for (const [id, value] of Object.entries({
    tourGroup: "road", tourCategory: "", tourDistance: "100",
    tourTolerance: "20", tourDirection: "all", tourRadius: "20",
    tourNearGroup: "all", tourNearCategory: "", tourVehicle: "250",
    interestPref: "全国", interestType: "roadEvent", interestFeature: "",
    interestRiderDetail: ""
  })) node(id).value = value;
  node("tourEventList").hidden = true;
  node("tourReturnSame").checked = true;
  const ctx = {
    window: { APP_DATA: { roads, landmarks: [] }, RIDERS_CAFES: [] },
    origins: { ride: { lat: 35, lng: 139 } },
    document: { getElementById: node, addEventListener(name, fn) { handlers.set(name, fn); } },
    localStorage: { getItem(k) { return store.get(k) ?? null; }, setItem(k, v) { store.set(k, v); } },
    fetch: async () => ({
      ok: true, json: async () => ({ schemaVersion: 1, events: online })
    }),
    alert(value) { alerts.push(value); },
    console,
    Date, Intl, URLSearchParams,
    RIDERS_CAFES: [],
    FEATURES: [["", "すべて"]],
    RIDERS_SPOT_CATEGORIES: [["", "すべて"]],
    RIDERS_CAFE_FILTERS: [["", "すべて"]],
    featureMatch: () => true,
    ridersCafeFilterMatch: () => true,
    esc: value => String(value ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c])),
    escJs: value => String(value ?? "").replace(/\\/g, "\\\\").replace(/'/g, "\\'"),
    spotCard: station => '<div class="spot-card">' +
      String(station.name).replace(/</g, "&lt;") + '</div>'
  };
  ctx.$ = node;
  vm.runInNewContext(tour, ctx, { filename: "tour-plan.js" });
  handlers.get("DOMContentLoaded")();
  vm.runInNewContext(interestSyncCode+"\n"+interestCode, ctx, { filename: "app-interest-functions.js" });
  ctx.window.runInterest = ctx.runInterest;
  ctx.syncInterestFeature();
  return { ctx, node, alerts, store, html: () => node("interestResult").innerHTML };
}

test("prefecture filter returns only event-hosting road stations and dates with official links", () => {
  const f=fixture();
  f.node("interestPref").value="東京都";
  f.ctx.runInterest();
  assert.match(f.html(),/東京都 \/ イベント開催駅 1駅・開催終了前 1件/);
  assert.match(f.html(),/北100/);
  assert.match(f.html(),/2099-10-18/);
  assert.match(f.html(),/北100 秋まつり/);
  assert.match(f.html(),/https:\/\/official.example\/event/);
  assert.doesNotMatch(f.html(),/東100|未開催|中止の駅/);
  assert.equal(f.node("interestEventsTools").hidden,false);
  assert.equal(f.node("interestFeatureLabel").hidden,true);
});

test("nationwide selection lists all matching stations, ordered by nearest event date", () => {
  const f=fixture();
  f.ctx.runInterest();
  assert.match(f.html(),/全国 \/ イベント開催駅 2駅・開催終了前 2件/);
  assert.ok(f.html().indexOf("東100") < f.html().indexOf("北100"));
  assert.doesNotMatch(f.html(),/未開催|中止の駅/);
});

test("empty prefecture shows clear zero-result message instead of nationwide fallback", () => {
  const f=fixture();
  f.node("interestPref").value="愛媛県";
  f.ctx.runInterest();
  assert.match(f.html(),/愛媛県 \/ イベント開催駅 0駅・開催終了前 0件/);
  assert.match(f.html(),/この地域で確認できる開催予定イベントはありません/);
  assert.doesNotMatch(f.html(),/北100|東100/);
});

test("missing shared event cache prompts update, never invents results", () => {
  const f=fixture({cached:false});
  f.ctx.runInterest();
  assert.match(f.html(),/イベント情報が未取得です/);
  assert.match(f.html(),/イベント情報を更新/);
  assert.equal(f.node("interestEventCacheStatus").textContent,"イベント情報は未取得です");
  assert.doesNotMatch(f.html(),/北100|東100/);
});

test("interest update uses touring's shared event download and refreshes results", async () => {
  const f=fixture({cached:false});
  f.ctx.runInterest();
  await f.ctx.updateInterestRoadEvents();
  assert.match(f.html(),/イベント開催駅 2駅/);
  assert.match(f.html(),/北100/);
  assert.match(f.node("interestEventCacheStatus").textContent,/最終取得：/);
  assert.equal(f.ctx.window.tourEventCacheStatus().total, 4);
  assert.equal(f.store.has("michino_road_events_cache_v1"),true);
  assert.equal(f.node("interestEventUpdateBtn").disabled,false);
});

test("unsafe event titles are escaped and non-https event URLs never display", () => {
  const unsafe=[makeEvent("北100","東京都",{
    title:'<img src=x onerror="alert(1)"> 開催イベント',
    url:"javascript:alert(1)"
  })];
  const f=fixture({cachedEvents:unsafe});
  f.node("interestPref").value="東京都";
  f.ctx.runInterest();
  assert.match(f.html(),/&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  assert.doesNotMatch(f.html(),/<img|javascript:alert/);
  assert.match(f.html(),/開催イベント/);
});

test("ordinary places remain available, with event-specific UI hidden", () => {
  const f=fixture();
  f.node("interestType").value="road";
  f.ctx.syncInterestFeature();
  f.ctx.runInterest();
  assert.equal(f.node("interestEventsTools").hidden,true);
  assert.equal(f.node("interestFeatureLabel").hidden,false);
  assert.match(f.html(),/未開催/);
  assert.match(f.html(),/中止の駅/);
  assert.doesNotMatch(f.html(),/開催予定イベント|イベント開催駅/);
  f.node("interestType").value="roadEvent";
  f.ctx.syncInterestFeature();
  f.ctx.runInterest();
  assert.doesNotMatch(f.html(),/未開催|中止の駅/);
});

test("HTML offers the roadside station event choice and safe refresh controls", () => {
  const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
  const interest=html.slice(html.indexOf('<section id="interest"'),
    html.indexOf("</section>",html.indexOf('<section id="interest"')));
  assert.match(interest,/<option value="roadEvent">📅 道の駅（イベント開催）<\/option>/);
  assert.match(interest,/id="interestEventsTools"/);
  assert.match(interest,/id="interestEventCacheStatus"/);
  assert.match(interest,/onclick="updateInterestRoadEvents\(\)"/);
  assert.match(interest,/id="interestResult"/);
  assert.match(interest,/onclick="runInterest\(\)"/);
  assert.ok(interest.indexOf('id="interestEventsTools"') < interest.indexOf('id="interestResult"'));
  const sw=fs.readFileSync(path.join(root,"service-worker.js"),"utf8");
  const version=JSON.parse(fs.readFileSync(path.join(root,"data/version.json"),"utf8"));
  assert.match(html,/app\.js\?v=1\.6\.26/);
  assert.match(html,/tour-plan\.js\?v=1\.6\.26/);
  assert.match(sw,/michino-shell-v1\.6\.26/);
  assert.equal(version.appVersion,"1.6.26");
});
