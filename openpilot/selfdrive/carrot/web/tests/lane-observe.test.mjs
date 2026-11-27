import test from "node:test";
import assert from "node:assert/strict";
import "../js/lane-observe.js";
import "../js/realtime/raw_capnp.js";
const {geometry, snapshot, ingest, decodeWire}=globalThis.CarrotLaneObserve;
const line=y=>({x:[0,10,20,30,40,60],y:[y,y,y,y,y,y]});
const model={laneLines:[line(-5.4),line(-1.8),line(1.8),line(5.4)],laneLineProbs:[.9,.9,.9,.9],roadEdges:[line(-7),line(7)],roadEdgeStds:[.2,.2],position:line(.1)};
const event=(service,decoded,t=10e9,valid=true)=>({service,decoded,logMonoTime:t,valid});
test("geometry, count distinct from absolute index",()=>{
 const g=geometry(model);assert.equal(g.samples[0].visible_lane_candidates,3);assert.equal(g.samples[0].center_y_m,0);assert.equal(g.samples[0].width_m,3.6);assert.equal(g.control_usable,false);
});
test("missing and conflicting geometry",()=>{
 assert.equal(geometry({...model,laneLineProbs:[.9,.1,.9,.9]}).samples[0].center_y_m,null);
 assert.equal(geometry({...model,roadEdges:[line(0),line(7)]}).samples[0].reason,"edge_conflict");
 assert.equal(geometry({...model,laneLines:[line(5),line(2),line(-2),line(-5)]}).samples[0].reason,"invalid_width_or_order");
 assert.equal(geometry({}).samples[0].center_y_m,null);
});
test("expired nav and data invalidation",()=>{
 const c={},nav={connected:true,laneCurrent:{present:true,visible:true,count:4,distanceM:140,available:[0,1,1,0],meta:{receivedMonoTimeNanos:9e9,sourceTimestampMillis:1800000000000}}};
 ingest(c,event("modelV2",model),100);ingest(c,event("carrotNavi",nav),100);
 let s=snapshot(c,200);assert.equal(s.lane.count,4);assert.equal(s.model_lane_receipt_delta_ms,1000);assert.equal(s.absolute_lane_index,null);assert.equal(s.phone_clock_alignment_verified,false);
 assert.equal(snapshot(c,800).geometry,null);assert.equal(snapshot(c,1800).lane,null);
 ingest(c,event("carrotNavi",{...nav,laneCurrent:{...nav.laneCurrent,meta:{receivedMonoTimeNanos:1e9}}}),500);assert.equal(snapshot(c,600).lane,null);
 ingest(c,event("modelV2",model,11e9,false),600);assert.equal(snapshot(c,600).geometry,null);
});
test("withdrawn lane and unavailable meta are not reused",()=>{
 const c={};ingest(c,event("carrotNavi",{connected:true,laneCurrent:{present:true,visible:true,count:3}}),100);assert.equal(snapshot(c,100).lane,null);
 ingest(c,event("carrotNavi",{connected:true,laneCurrent:{present:false,visible:false,count:3}}),200);assert.equal(snapshot(c,200).lane,null);
});
test("car and controls timestamps, resets, no default speed",()=>{
 const c={};ingest(c,event("modelV2",model),100);ingest(c,event("carState",{canValid:true,vEgo:5,steeringAngleDeg:1}),100);
 assert.equal(snapshot(c,200).speed_kph,18);
 ingest(c,event("carState",{canValid:false,vEgo:0},11e9),200);assert.equal(snapshot(c,200).speed_kph,null);
 ingest(c,event("modelV2",model,1e9),200);assert.equal(snapshot(c,200).nav_connected,false);assert.equal(snapshot(c,200).speed_kph,null);
});
test("malformed wire fails closed",()=>assert.throws(()=>decodeWire(new ArrayBuffer(5),globalThis.CarrotRawCapnp)));

test("event presentation hides absent and withdrawn guide, always and off override",()=>{
 const {presentation}=globalThis.CarrotLaneObserve;
 const state={lane:{count:4,distance_m:140,available_raw:[]},geometry:geometry(model)};
 const p=presentation(state,"auto");assert.equal(p.visible,true);assert.equal(p.count,4);assert.equal(p.recommended_lane,null);assert.equal(p.recommendation_status,"no_recommendation_data");assert.equal(p.control_usable,false);
 assert.equal(presentation({lane:null},"auto").visible,false);
 assert.equal(presentation(state,"off").visible,false);
 assert.equal(presentation({lane:null},"always").visible,true);
 assert.equal(presentation(state,"invalid").visible,false);
});
test("raw flags never become verified recommendation or ego lane",()=>{
 const p=globalThis.CarrotLaneObserve.presentation({lane:{count:3,distance_m:20,available_raw:[0,1,0]}},"auto");
 assert.deepEqual(p.raw_flags,[0,1,0]);assert.equal(p.recommended_lane,null);assert.equal(p.absolute_lane_index,null);assert.equal(p.recommendation_status,"raw_flags_unverified");
});
test("actual snapshot expiration clears event overlay",()=>{
 const c={},nav={connected:true,laneCurrent:{present:true,visible:true,count:4,distanceM:140,available:[],meta:{receivedMonoTimeNanos:9e9}}};
 ingest(c,event("carrotNavi",nav),100);
 assert.equal(globalThis.CarrotLaneObserve.presentation(snapshot(c,200),"auto").visible,true);
 assert.equal(globalThis.CarrotLaneObserve.presentation(snapshot(c,1800),"auto").visible,false);
 ingest(c,event("carrotNavi",{...nav,laneCurrent:{...nav.laneCurrent,visible:false}},11e9),1900);
 assert.equal(globalThis.CarrotLaneObserve.presentation(snapshot(c,1900),"auto").visible,false);
});

import "../js/lane-hud-observe.js";
test("main HUD observes only current valid lane and never suggests a maneuver",()=>{
 const core=globalThis.CarrotLaneObserve,hud=globalThis.CarrotLaneHudObserve,c={};
 ingest(c,event("carrotNavi",{connected:true,laneCurrent:{present:true,visible:true,count:4,distanceM:140,available:[0,1,1,0],meta:{receivedMonoTimeNanos:9e9}}}),100);
 const p=hud.view(core,c,200,"auto",true);assert.equal(p.count,4);assert.equal(p.distance,140);assert.equal(p.control_usable,false);assert.equal(p.note,"導航車道資料 · 尚未匹配自車位置");
 assert.equal(hud.view(core,c,200,"off",true),null);assert.equal(hud.view(core,c,200,"auto",false),null);
 assert.equal(hud.view(core,c,1800,"auto",true),null);
 assert.equal(hud.view(core,c,1800,"always",true).active,false);
 ingest(c,event("carrotNavi",{connected:true,laneCurrent:{present:false,visible:false,count:4}},11e9),300);
 assert.equal(hud.view(core,c,300,"auto",true),null);
});


test("duplicate envelopes cannot refresh browser freshness",()=>{
 const c={},nav={connected:true,laneCurrent:{present:true,visible:true,count:3,meta:{receivedMonoTimeNanos:9e9}}};
 ingest(c,event("carrotNavi",nav),100);
 ingest(c,event("carrotNavi",nav),1400);
 assert.equal(snapshot(c,1601).lane,null);
 ingest(c,event("modelV2",model),100);
 ingest(c,event("modelV2",model),500);
 assert.equal(snapshot(c,701).geometry,null);
});
test("source receipt age includes browser residence and withdrawal cannot be revived by duplicate",()=>{
 const c={},nav={connected:true,laneCurrent:{present:true,visible:true,count:3,meta:{receivedMonoTimeNanos:4.1e9}}};
 ingest(c,event("carrotNavi",nav),100);
 assert.equal(snapshot(c,150).lane.receipt_age_ms,5950);
 assert.equal(snapshot(c,201).lane,null);
 ingest(c,event("carrotNavi",{...nav,laneCurrent:{...nav.laneCurrent,visible:false}}),220);
 ingest(c,event("carrotNavi",nav),230);
 assert.equal(snapshot(c,230).lane,null);
});


test("main HUD co-observes live local geometry without assigning lane",()=>{
 const core=globalThis.CarrotLaneObserve,hud=globalThis.CarrotLaneHudObserve,c={};
 const nav={connected:true,laneCurrent:{present:true,visible:true,count:4,available:[],meta:{receivedMonoTimeNanos:9e9}}};
 ingest(c,event("carrotNavi",nav),100);ingest(c,event("modelV2",model),100);
 let p=hud.view(core,c,200,"auto",true);assert.equal(p.count,4);assert.equal(p.visualCount,3);assert.equal(p.synchronized,true);assert.equal(p.recommendedLane,null);assert.equal(p.control_usable,false);
 p=hud.view(core,c,701,"auto",true);assert.equal(p.visualCount,null);assert.equal(p.synchronized,false);
 assert.equal(hud.view(core,c,1601,"auto",true),null);
});
test("main HUD rejects temporal association when model and nav times diverge",()=>{
 const core=globalThis.CarrotLaneObserve,hud=globalThis.CarrotLaneHudObserve,c={};
 ingest(c,event("carrotNavi",{connected:true,laneCurrent:{present:true,visible:true,count:3,meta:{receivedMonoTimeNanos:9e9}}}),100);
 ingest(c,event("modelV2",model,11e9),100);
 const p=hud.view(core,c,200,"auto",true);assert.equal(p.visualCount,3);assert.equal(p.synchronized,false);assert.equal(p.recommendedLane,null);
});
