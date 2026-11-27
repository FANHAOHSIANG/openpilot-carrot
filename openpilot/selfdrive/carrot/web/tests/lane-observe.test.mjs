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
