// Offline replay of decoded user logs; no vehicle/device IO. Process each trip separately.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import assert from "node:assert/strict";
import "../../openpilot/selfdrive/carrot/web/js/lane-observe.js";
const core=globalThis.CarrotLaneObserve;
if(process.argv.length!==3)throw Error("Usage: node lane_live_replay.mjs <decoded directory>");
const root=process.argv[2],counts={};
const add=k=>counts[k]=(counts[k]||0)+1;
const load=(s,k)=>zlib.gunzipSync(fs.readFileSync(path.join(root,s,k+".jsonl.gz"))).toString().trim().split("\n").filter(Boolean).map(JSON.parse);
for(const s of fs.readdirSync(root).filter(x=>/^\d\d$/.test(x)).sort()){
  add("segments");const cache={};
  const rows=[...load(s,"modelV2"),...load(s,"carrotNavi")].sort((a,b)=>a.logMonoTimeNs-b.logMonoTimeNs);
  for(const row of rows){
    const {data,service,logMonoTimeNs,eventValid}=row;
    assert.equal(typeof eventValid,"boolean");assert(Number.isSafeInteger(logMonoTimeNs));
    if(service==="carrotNavi")for(const k of ["vehicle","guidanceCurrent","guidanceNext","laneCurrent","route"])if(data[k])data[k].present=data[k].meta?.present===true;
    const e={service,logMonoTime:logMonoTimeNs,valid:eventValid,decoded:data},now=logMonoTimeNs/1e6;
    core.ingest(cache,e,now);const snap=core.snapshot(cache,now),p=core.presentation(snap,"auto");
    assert.equal(snap.control_usable,false);assert.equal(snap.absolute_lane_index,null);
    if(service==="modelV2"){add("model_frames");if(snap.relative_position.status==="local_candidate")add("local_geometry");continue;}
    add("nav_frames");if(snap.lane)add("legacy_lane");
    if(data.navigationStatus?.guidanceActive!==true||data.navigationStatus?.offRoute!==false||data.connected!==true){
      assert.equal(snap.lane,null);assert.equal(snap.map_candidate,null);add("inactive_cleared");
    }
    if(snap.map_candidate){
      add("candidate");if(!snap.lane)add("candidate_without_legacy");if(snap.map_candidate.advised_count>0)add("positive");
      assert(p.visible);if(snap.relative_position.status==="local_candidate"&&Math.abs(snap.model_nav_message_delta_ms)<=250)add("coobserved");
    }
    const before=JSON.stringify(snap.map_candidate);
    core.ingest(cache,e,now+1);
    assert.equal(JSON.stringify(core.snapshot(cache,now).map_candidate),before);
    assert.equal(cache.carrotNavi.received,now);
    if(snap.map_candidate){const expired=core.snapshot(cache,now+2001);assert.equal(expired.map_candidate,null);assert.equal(expired.lane,null);add("expiry_checks");}
  }
}
console.log(JSON.stringify(counts,null,2));
