"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const read = file => fs.readFileSync(path.join(root, file), "utf8");

test("home no longer offers donations but keeps contact and updates", () => {
  const html = read("index.html");
  assert.doesNotMatch(html, /support-open-btn|openSupport\(\)|活動を応援する/);
  assert.match(html, /class="contact-open-btn"/);
  assert.match(html, /id="pwaUpdateButton"/);
  assert.match(html, /id="interest"/);
  assert.match(html, /id="ride"/);
});

test("no obsolete JS navigation to retired support page remains", () => {
  const app = read("app.js");
  assert.doesNotMatch(app, /function openSupport\(/);
  assert.doesNotMatch(app, /location\.href="support\.html"/);
  assert.match(app, /function openContact\(/);
});

test("bookmarked support page no longer offers a payment action", () => {
  const html = read("support.html");
  assert.match(html, /現在、活動支援・寄付の受付を行っていません/);
  assert.match(html, /href="\.\/"/);
  assert.doesNotMatch(html, /buy\.stripe\.com|support-pay|Stripeで活動を応援する/);
  assert.doesNotMatch(html, /<form[^>]+action=/i);
});

test("payment cache entries and current-term solicitations are retired", () => {
  const sw = read("service-worker.js");
  const terms = read("terms.html");
  const privacy = read("privacy.html");
  const legal = read("legal.html");
  assert.doesNotMatch(sw, /["']\.\/support\.html["']/);
  assert.match(terms, /現在、アプリ内での活動支援・寄付の受付は行っていません/);
  assert.match(privacy, /現在、アプリ内での活動支援・寄付の受付は行っていません/);
  assert.match(legal, /以下は過去に提供していた活動支援に関する表示です/);
  assert.match(legal, /キャンセル・返金/);
});

test("PWA app and service-worker versions stay consistent after updates", () => {
  const ver = JSON.parse(read("data/version.json"));
  const html = read("index.html");
  const pwa = read("pwa.js");
  const worker = read("service-worker.js");
  assert.equal(ver.appVersion, "1.6.30");
  assert.match(html, /app\.js\?v=1\.6\.30/);
  assert.match(pwa, /PWA_APP_VERSION="1\.6\.30"/);
  assert.match(worker, /michino-shell-v1\.6\.30/);
  assert.match(worker, /app\.js\?v=1\.6\.30/);
});
