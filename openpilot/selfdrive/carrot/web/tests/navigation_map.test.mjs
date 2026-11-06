import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../js/pages/navigation_map.js", import.meta.url), "utf8");
const settle = () => new Promise((resolve) => setImmediate(resolve));

async function page(responses, language = "en", confirm = true) {
  const elements = new Map(), timers = [], revoked = [], requests = [];
  let blobs = 0;
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {
      hidden: false, textContent: "", value: "", listeners: {},
      addEventListener(name, callback) { this.listeners[name] = callback; },
      removeAttribute(name) { delete this[name]; },
    });
    return elements.get(id);
  };
  vm.runInNewContext(source, {
    document: { hidden: false, getElementById: element },
    window: { confirm: () => confirm },
    localStorage: { getItem: () => language }, navigator: {},
    URL: { createObjectURL: () => `blob:${++blobs}`, revokeObjectURL: (url) => revoked.push(url) },
    setTimeout: (callback) => timers.push(callback),
    fetch: async (url, options = {}) => {
      requests.push({ url, ...options });
      if (url.endsWith("destination")) return { ok: true, json: async () => ({ destination: options.body ? JSON.parse(options.body) : null }) };
      const response = responses.shift();
      if (response instanceof Error) throw response;
      assert.ok(response, "unexpected map request");
      return { status: response.status, headers: { get: () => response.reason }, blob: async () => ({}) };
    },
  });
  await settle();
  return { element, revoked, requests, blobs: () => blobs, next: async () => { await timers.shift()(); } };
}

test("keys without a route show destination instructions instead of a black image", async () => {
  const p = await page([{ status: 200, reason: "route" }]);
  assert.equal(p.element("map").hidden, true);
  assert.equal(p.element("mapStatus").hidden, false);
  assert.match(p.element("mapStatus").textContent, /Enter destination coordinates below/);
  assert.match(p.element("mapStatus").textContent, /Saving keys alone/);
  assert.equal(p.blobs(), 0);
});

test("offroad explains when the route map becomes available", async () => {
  const p = await page([{ status: 204, reason: "offroad" }]);
  assert.equal(p.element("mapStatus").hidden, false);
  assert.match(p.element("mapStatus").textContent, /driving screen is active/);
  assert.equal(p.element("map").hidden, true);
});

test("ready map replaces instructions and GPS loss removes the stale image", async () => {
  const p = await page([{ status: 200, reason: "ready" }, { status: 200, reason: "position" }]);
  assert.equal(p.element("map").hidden, false);
  assert.equal(p.element("map").src, "blob:1");
  assert.equal(p.element("mapStatus").hidden, true);
  await p.next();
  assert.equal(p.element("map").hidden, true);
  assert.equal(p.element("map").src, undefined);
  assert.equal(p.element("mapStatus").hidden, false);
  assert.match(p.element("mapStatus").textContent, /GPS/);
  assert.deepEqual(p.revoked, ["blob:1"]);
});

test("network failure displays a localized connection message", async () => {
  const p = await page([new Error("offline")], "ko");
  assert.equal(p.element("map").hidden, true);
  assert.equal(p.element("mapStatus").hidden, false);
  assert.match(p.element("mapStatus").textContent, /차량과의 연결/);
});

test("coordinates submit a destination directly without address search", async () => {
  const p = await page([{ status: 204, reason: "waiting" }]);
  p.element("latitude").value = "24.8";
  p.element("longitude").value = "121.0";
  await p.element("form").listeners.submit({ preventDefault() {} });
  const sent = p.requests.filter((r) => r.method === "POST");
  assert.equal(sent.length, 1);
  assert.match(sent[0].url, /\/destination$/);
  assert.deepEqual(JSON.parse(sent[0].body), { latitude: 24.8, longitude: 121, place_name: "24.8, 121" });
  assert.equal(p.requests.some((r) => /search|geocod/.test(r.url)), false);
});

test("invalid coordinates do not write a destination or use address search", async () => {
  const p = await page([{ status: 204, reason: "waiting" }]);
  for (const [latitude, longitude] of [["91", "121"], ["24.8", "181"], ["NaN", "121"], ["Taipei", "121"], ["", "121"]]) {
    p.element("latitude").value = latitude;
    p.element("longitude").value = longitude;
    await p.element("form").listeners.submit({ preventDefault() {} });
  }
  assert.equal(p.requests.filter((r) => r.method === "POST").length, 0);
  assert.equal(p.requests.some((r) => /search|geocod/.test(r.url)), false);
});

test("cancelled coordinate confirmation does not change the destination", async () => {
  const p = await page([{ status: 204, reason: "waiting" }], "en", false);
  p.element("latitude").value = "24.8";
  p.element("longitude").value = "121";
  await p.element("form").listeners.submit({ preventDefault() {} });
  assert.equal(p.requests.filter((r) => r.method === "POST").length, 0);
});
