import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import assert from "node:assert/strict";
import "../../openpilot/selfdrive/carrot/web/js/lane-observe.js";
const core=globalThis.CarrotLaneObserve;
if(process.argv.length!==3)throw Error("Usage: node lane_continuity_replay.mjs <decoded directory>");
const root=process.argv[2],counts={};const add=k=>counts[k]=(counts[k]||0)+1;
for(const s of fs.readdirSync(root).filter(x=>/^\d\d$/.test(x)).sort()){
 add('segments');const tracker=core.createLocalLaneTracker();
 const rows=zlib.gunzipSync(fs.readFileSync(path.join(root,s,'modelV2.jsonl.gz'))).toString().trim().split('\n').map(JSON.parse);
 for(const row of rows){const {data,logMonoTimeNs,eventValid}=row;const p=tracker.observe({model_mono_ns:logMonoTimeNs,relative_position:core.relativePosition(eventValid?core.geometry(data):null)});add('frames');add(p.status);assert.equal(p.absolute_lane_index,null);assert.equal(p.control_usable,false);assert.equal(p.confirmed_lane_changes,null);if(p.status==='unavailable')assert.equal(p.frames,0);}
 tracker.reset();assert.equal(tracker.observe(null).frames,0);
}
console.log(JSON.stringify(counts,null,2));
