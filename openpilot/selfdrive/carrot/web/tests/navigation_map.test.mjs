import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../js/pages/navigation_map.js", import.meta.url), "utf8");
const traditionalSource = await readFile(new URL("../js/pages/navigation_zh_tw.js", import.meta.url), "utf8");
const settle = () => new Promise((resolve) => setImmediate(resolve));

async function page(responses, language = "en", handleApi = null) {
  const elements = new Map(), timers = [], revoked = [];
  let blobs = 0;
  const makeElement = () => ({
      hidden: false, textContent: "", value: "", children: [], handlers: {},
      addEventListener(name, handler) { this.handlers[name] = handler; },
      replaceChildren(...children) { this.children = children; }, append(...children) { this.children.push(...children); }, focus() {},
      async trigger(name) { await this.handlers[name]?.({preventDefault() {}}); await settle(); },
      removeAttribute(name) { delete this[name]; },
      setAttribute(name, value) { this[name] = value; },
    });
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, makeElement());
    return elements.get(id);
  };
  const target = {
    document: { documentElement: {}, hidden: false, getElementById: element, createElement: makeElement },
    window: { confirm: () => true },
    localStorage: { getItem: () => language }, navigator: {},
    URL: { createObjectURL: () => `blob:${++blobs}`, revokeObjectURL: (url) => revoked.push(url) },
    setTimeout: (callback) => timers.push(callback),
    fetch: async (url, options) => {
      if (url.endsWith('/config')) return {ok:true,json:async()=>({provider:'mapbox',google_key:''})};
      if (handleApi && !url.endsWith('map.png')) {
        const result = await handleApi(url, options || {});
        return {ok: !result.error, json: async () => result};
      }
      if (url.endsWith("destination")) return { ok: true, json: async () => ({ destination: null }) };
      if (url.endsWith("favorites")) return { ok: true, json: async () => ({ favorites: [] }) };
      const response = responses.shift();
      if (response instanceof Error) throw response;
      assert.ok(response, "unexpected map request");
      return { status: response.status, headers: { get: () => response.reason }, blob: async () => ({}) };
    },
  };
  vm.runInNewContext(traditionalSource + "\n" + source, target);
  await settle();
  return { target, element, revoked, blobs: () => blobs, next: async () => { await timers.shift()(); } };
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


test("Traditional navigation explains route and network problems", async () => {
  const p = await page([{ status: 200, reason: "route" }, new Error("offline")], "zh-Hant-TW");
  assert.equal(p.element("title").textContent, "Carrot 導航");
  assert.match(p.element("mapStatus").textContent, /輸入目的地座標/);
  await p.next();
  assert.match(p.element("mapStatus").textContent, /檢查與車輛的連線/);
  assert.equal(p.element("clear").textContent, "結束當前導航");
});

test("favorites edit requires validated coordinates and keeps errors in the editor", async () => {
  const saved = {id:'a'.repeat(32), name:'家', place_name:'臺北地址', latitude:25, longitude:121};
  const requests = [];
  const p = await page([{status:204, reason:'offroad'}], 'zh-TW', async (url, options) => {
    requests.push({url, options});
    if (url.includes('search?')) return {results:[{place_name:'新竹地址', latitude:24, longitude:120, permanent:true}]};
    if (options.method === 'PUT') return {error:'Favorites are unavailable. Please try again.'};
    return url.endsWith('favorites') ? {favorites:[saved]} : {destination:null};
  });
  const row = p.element('favorites').children[0];
  await row.children[2].children[0].trigger('click');
  assert.equal(p.element('favoriteName').value, '家');
  assert.equal(p.element('saveFavorite').disabled, false);
  p.element('favoriteQuery').value = '24,120';
  await p.element('favoriteQuery').trigger('input');
  assert.equal(p.element('saveFavorite').disabled, true);
  await p.element('favoriteForm').trigger('submit');
  assert.equal(requests.some(r => r.options.method === 'PUT'), false);
  await p.element('favoriteSearch').trigger('click');
  assert.equal(requests.some(r => r.url.includes('search?')), false);
  assert.equal(p.element('saveFavorite').disabled, false);
  p.element('favoriteName').value = '公司';
  await p.element('favoriteForm').trigger('submit');
  const body = JSON.parse(requests.find(r => r.options.method === 'PUT').options.body);
  assert.equal(body.coordinate_source, 'manual'); assert.equal(body.name, '公司'); assert.equal(body.latitude, 24); assert.equal(body.longitude, 120);
  assert.equal(p.element('favoriteForm').hidden, false);
  assert.match(p.element('editorStatus').textContent, /無法讀取或儲存最愛/);
  assert.equal(p.element('saveFavorite').disabled, false);
});

test("favorite navigation uses its ID and deletion requires an explicit second click", async () => {
  const saved = {id:'b'.repeat(32), name:'公司', place_name:'地址', latitude:25, longitude:121};
  const requests = [];
  const p = await page([{status:204,reason:'offroad'}], 'zh-TW', async (url, options) => {
    requests.push({url, options});
    if (url.endsWith('/destination')) return {destination:options.method === 'POST' ? saved : null};
    return {favorites:options.method === 'DELETE' ? [] : [saved]};
  });
  let row = p.element('favorites').children[0];
  await row.children[0].trigger('click');
  assert.ok(requests.some(r => r.url.endsWith(`/favorites/${saved.id}/destination`) && r.options.method === 'POST'));
  await row.children[2].children[1].trigger('click');
  assert.equal(requests.some(r => r.options.method === 'DELETE'), false);
  row = p.element('favorites').children[0];
  assert.equal(row.children[2].children[1].textContent, '確認刪除');
  await row.children[2].children[1].trigger('click');
  assert.equal(requests.filter(r => r.options.method === 'DELETE').length, 1);
  assert.equal(p.element('favorites').children.length, 0);
  assert.match(p.element('favoritesStatus').textContent, /尚未加入最愛/);
});


test("coordinate form rejects invalid inputs and posts confirmed valid coordinates without search", async () => {
  const calls = [];
  const p = await page([{status: 204, reason: "offroad"}], "zh-TW", async (url, options) => {
    calls.push({url, options});
    if (url.endsWith("favorites")) return {favorites: []};
    if (options.method === "POST") return {destination: JSON.parse(options.body)};
    return {destination: null};
  });
  p.element("latitude").value = "91"; p.element("longitude").value = "121";
  await p.element("form").trigger("submit");
  assert.equal(calls.filter(c => c.options.method === "POST").length, 0);
  p.element("latitude").value = "25.03";
  await p.element("form").trigger("submit");
  const posts = calls.filter(c => c.options.method === "POST");
  assert.equal(posts.length, 1);
  assert.deepEqual(JSON.parse(posts[0].options.body), {latitude: 25.03, longitude: 121, place_name: "25.03, 121"});
  assert.ok(calls.every(c => !c.url.includes("search")));
});

test('legacy Google favorite opens explicit address migration and replaces it with explicit manual coordinates',async()=>{
  const old={id:'c'.repeat(32),provider:'google',google_place_id:'legacy_id',name:'我的家'},requests=[];
  const selected={latitude:25,longitude:121,place_name:'臺北測試地址',permanent:true};
  const p=await page([{status:204,reason:'offroad'}],'zh-TW',async(url,options)=>{
    requests.push({url,options});
    if(url.includes('/search?'))return {results:[selected]};
    if(url.endsWith('/destination'))return {destination:null};
    return {favorites:[old]};
  });
  await p.element('favorites').children[0].children[0].trigger('click');
  assert.equal(p.element('favoriteForm').hidden,false);assert.equal(p.element('favoriteName').value,'我的家');
  assert.match(p.element('editorStatus').textContent,/輸入經緯度/);
  assert.equal(requests.some(r=>r.options.method==='POST'),false);
  p.element('favoriteQuery').value='25, 121';
  await p.element('favoriteSearch').trigger('click');
  await p.element('favoriteForm').trigger('submit');
  const update=requests.find(r=>r.options.method==='PUT'),body=JSON.parse(update.options.body);
  assert.equal(body.name,'我的家');assert.equal(body.latitude,25);assert.equal(body.coordinate_source,'manual');
  assert.ok(requests.every(r=>!r.url.includes('/search?')));
  assert.equal(body.provider,undefined);assert.equal(body.google_place_id,undefined);
});


test('opening navigation restores an existing destination and ending reports the actual response',async()=>{
 const place={place_name:'既有目的地',latitude:25,longitude:121},calls=[];
 const p=await page([{status:204,reason:'offroad'}],'zh-TW',async(url,options)=>{
  if(url.endsWith('favorites'))return {favorites:[]};calls.push(options.method||'GET');return {destination:options.method==='DELETE'?null:place};
 });
 const api=p.target.CarrotNavigationView;assert.equal(api.snapshot().active,true);assert.equal(api.snapshot().label,'既有目的地');assert.equal(p.element('clear').disabled,false);
 assert.equal((await api.end()).ended,true);assert.equal(api.snapshot().active,false);assert.equal(p.element('clear').disabled,true);assert.match(p.element('status').textContent,/已結束/);assert.deepEqual(calls,['GET','DELETE']);
});

test('late initial read cannot overwrite a new destination and duplicate writes are blocked',async()=>{
 let read,write;const calls=[],old={place_name:'舊位置'},place={place_name:'新位置',latitude:25,longitude:121};
 const p=await page([{status:204,reason:'offroad'}],'zh-TW',async(url,options)=>{
  if(url.endsWith('favorites'))return {favorites:[]};if(url.includes('/search?'))throw Error('Unexpected paid search');
  calls.push(options.method||'GET');if(options.method==='POST')return await new Promise(r=>write=r);return await new Promise(r=>read=r);
 });
 p.element('latitude').value='25';p.element('longitude').value='121';
 const request=p.element('form').trigger('submit');await settle();assert.equal(p.target.CarrotNavigationView.snapshot().busy,true);
 await assert.rejects(p.target.CarrotNavigationView.end());read({destination:old});await settle();assert.equal(p.target.CarrotNavigationView.snapshot().known,false);
 write({destination:place});await request;assert.equal(p.target.CarrotNavigationView.snapshot().label,'新位置');assert.deepEqual(calls,['GET','POST']);
});

test('lost end response is unknown, never automatically replayed, and can be reconciled with a read',async()=>{
 let destination={place_name:'測試目的地'},writes=0;
 const p=await page([{status:204,reason:'offroad'}],'zh-TW',async(url,options)=>{
  if(url.endsWith('favorites'))return {favorites:[]};if(options.method==='DELETE'){writes++;destination=null;throw Error('lost');}return {destination};
 });
 const api=p.target.CarrotNavigationView;await assert.rejects(api.end());assert.equal(api.snapshot().known,false);assert.equal(p.element('clear').disabled,false);assert.equal(p.element('clear').textContent,'重新讀取導航狀態');
 await assert.rejects(api.end());assert.equal(writes,1);await p.element('clear').trigger('click');assert.equal(api.snapshot().known,true);assert.equal(api.snapshot().active,false);assert.equal(writes,1);
});
