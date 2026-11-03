import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
const source=readFileSync(new URL('../js/pages/google_share.js',import.meta.url),'utf8');
function browser() {
  const elements=new Map(), calls=[], storage=new Map([['carrotGoogleShareToken','paired']]);
  const make=()=>({value:'',hidden:false,textContent:'',disabled:false,children:[],listeners:{},
    addEventListener(k,fn){this.listeners[k]=fn;},append(c){this.children.push(c);},replaceChildren(){this.children=[];}});
  const get=id=>{if(!elements.has(id))elements.set(id,make());return elements.get(id);};
  const place={latitude:24.8,longitude:121,place_name:'<img src=x onerror=alert(1)>'};
  const context={URLSearchParams,location:{hash:'#url='+encodeURIComponent('https://maps.app.goo.gl/test'),pathname:'/navigation/share',origin:'http://carrot.test:7000'},
    history:{replaceState(...args){calls.push(['history',...args]);}},
    localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    document:{getElementById:get,querySelectorAll:()=>[],createElement:make},
    fetch:async(url,opts)=>{calls.push([url,opts]);return {ok:true,status:200,json:async()=>({destination:place,results:[place]})};}};
  vm.runInNewContext(source,context);
  return {get,calls,place,storage,async event(id,type='click'){get(id).listeners[type]({preventDefault(){}});await new Promise(setImmediate);}};
}
test('share fragment is removed, never auto-resolves or writes destination',()=>{
  const b=browser();assert.equal(b.get('shared').value,'https://maps.app.goo.gl/test');
  assert.equal(b.get('shortcutBase').value,'http://carrot.test:7000/navigation/share#url=');
  assert.equal(b.calls.length,1);assert.equal(b.calls[0][0],'history');
});
test('resolution displays text safely and requires separate explicit confirmation',async()=>{
  const b=browser();await b.event('importForm','submit');
  assert.equal(b.get('place').textContent,b.place.place_name);
  assert.equal(b.calls.filter(x=>x[0].endsWith?.('/confirm')).length,0);
  assert.equal(b.get('preview').hidden,false);
  await b.event('confirm');
  const confirm=b.calls.find(x=>x[0].endsWith?.('/confirm'));
  assert.equal(JSON.parse(confirm[1].body).latitude,24.8);
  assert.equal(confirm[1].headers.Authorization,'Bearer paired');
  assert.equal(b.get('preview').hidden,true);
});
test('forget clears browser credential and pending destination',async()=>{
  const b=browser();await b.event('importForm','submit');await b.event('forget');
  assert.equal(b.storage.size,0);assert.equal(b.get('pairPanel').hidden,false);
  await b.event('confirm');assert.equal(b.calls.filter(x=>x[0].endsWith?.('/confirm')).length,0);
});
