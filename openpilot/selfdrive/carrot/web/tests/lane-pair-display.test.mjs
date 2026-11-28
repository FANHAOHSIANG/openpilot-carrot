import "../js/lane-observe.js";
const {lanePairDisplay,duplicateNavInvalid}=globalThis.CarrotLaneObserve;
function regression(){
 const base=()=>({map_candidate:{source:"amap_auto_13012",count:3,lanes:[{index:0,advised:false},{index:1,advised:true},{index:2,advised:null}],control_usable:false},relative_position:{status:"local_candidate",reference:"model_origin_x0",offset_m:.2,width_m:3.6,control_usable:false},geometry:{samples:[{reason:"dual_line_candidate",visible_lane_candidates:2}]},model_nav_message_delta_ms:120});
 const tests=[];const ok=(x,n)=>{if(!x)throw Error(n);tests.push(n)};
 let s=base(),p=lanePairDisplay(s);ok(p.status==="co_observed_unmapped"&&p.positive_icons[0]===2&&p.icons[2].advised===null,"positive and unknown icon");
 ok(p.absolute_lane_index===null&&p.mapped_target_lane===null&&!p.control_usable,"never assign physical lane");
 s=base();s.model_nav_message_delta_ms=251;ok(lanePairDisplay(s).status==="time_mismatch","time mismatch");
 s=base();s.map_candidate=null;ok(lanePairDisplay(s).icons.length===0,"withdrawal clears icons");
 s=base();s.geometry.samples[0].reason="edge_conflict";ok(lanePairDisplay(s).local_offset_m===null,"geometry conflict");
 s=base();s.map_candidate.lanes[1].index=0;ok(lanePairDisplay(s).status==="no_candidate","duplicate index");
 s=base();s.map_candidate.lanes[1].advised="true";ok(lanePairDisplay(s).icons.length===0,"strict bool");
 s=base();s.map_candidate.lanes[1].advised=false;ok(lanePairDisplay(s).positive_icons.length===0,"no explicit recommendation");
 s=base();s.relative_position.offset_m=3;ok(lanePairDisplay(s).status==="no_local_geometry","invalid offset");
 const e={service:"carrotNavi",valid:true,decoded:{connected:true,sessionId:"a",generation:1,navigationStatus:{guidanceActive:true,offRoute:false},amapLaneCandidate:{valid:true},laneCurrent:{present:true,visible:true}}};
 ok(!duplicateNavInvalid(e,JSON.parse(JSON.stringify(e))),"same envelope");
 let b=JSON.parse(JSON.stringify(e));b.decoded.amapLaneCandidate.valid=false;ok(duplicateNavInvalid(e,b),"same timestamp candidate withdrawal");
 b=JSON.parse(JSON.stringify(e));b.decoded.navigationStatus.offRoute=true;ok(duplicateNavInvalid(e,b),"same timestamp off route");
 b=JSON.parse(JSON.stringify(e));b.decoded.sessionId="b";ok(duplicateNavInvalid(e,b),"same timestamp session change");
 b=JSON.parse(JSON.stringify(e));b.decoded.generation=2;ok(duplicateNavInvalid(e,b),"same timestamp generation change");
 ok(lanePairDisplay(null).status==="no_candidate","missing streams");
 return tests;
}
import test from "node:test";
test("read-only live lane pairing regression",()=>regression());
