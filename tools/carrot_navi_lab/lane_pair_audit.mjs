// Offline read-only audit of C4 lane-observe schema 3 JSONL. No actuator or messaging imports.
function inspect(row) {
  const finite = x => typeof x === "number" && Number.isFinite(x);
  const ns = x => Number.isSafeInteger(x) && x > 0;
  const result = (status, extra={}) => ({status, ...extra, absolute_lane_index:null, mapped_target_lane:null, control_usable:false});
  if (!row || row.schema!==3 || row.control_usable!==false) return result("invalid_record");
  if (!ns(row.model_mono_ns) || !ns(row.nav_mono_ns) || row.nav_connected!==true) return result("missing_stream");
  const gap = (row.model_mono_ns-row.nav_mono_ns)/1e6;
  if (Math.abs(gap)>250) return result("time_mismatch");
  const c=row.map_candidate;
  if (!c || !["amap_auto_13012","amap_link_14"].includes(c.source) || c.control_usable!==false ||
    !Number.isInteger(c.count)||c.count<1||c.count>32||!Array.isArray(c.lanes)||c.lanes.length!==c.count||
    c.lanes.some((r,i)=>!r||r.index!==i||![true,false,null].includes(r.advised))) return result("no_valid_candidate");
  const recommended=c.lanes.filter(r=>r.advised===true).map(r=>r.index);
  const unknown=c.lanes.filter(r=>r.advised===null).length;
  const evidence={source:c.source, icon_count:c.count, advised_icon_indices:recommended, unknown_icon_count:unknown, model_nav_delta_ms:gap};
  if (!recommended.length) return result("no_positive_advice",evidence);
  const g=row.geometry, rel=row.relative_position;
  if (!g||!Array.isArray(g.probs)||g.probs.length!==4||!g.probs.slice(1,3).every(p=>finite(p)&&p>=.65&&p<=1)||
      !rel||rel.status!=="local_candidate"||rel.reference!=="model_origin_x0"||rel.control_usable!==false||
      ![rel.left_m,rel.right_m,rel.width_m,rel.offset_m].every(finite)||
      rel.left_m<.15||rel.right_m<.15||rel.width_m<2.2||rel.width_m>5||
      Math.abs(rel.left_m+rel.right_m-rel.width_m)>.05||
      Math.abs((rel.left_m-rel.right_m)/2-rel.offset_m)>.05) return result("no_local_position",evidence);
  const near=Array.isArray(g.samples)?g.samples.find(x=>x&&x.x_m===10):null;
  if (!near||near.reason!=="dual_line_candidate"||!Number.isInteger(near.visible_lane_candidates)||
      near.visible_lane_candidates<1||near.visible_lane_candidates>3) return result("no_visual_topology",evidence);
  return result("co_observed_unmapped",{...evidence, local_offset_m:rel.offset_m, local_width_m:rel.width_m,
    visible_contiguous_count:near.visible_lane_candidates, count_equal:near.visible_lane_candidates===c.count});
}
function audit(rows) {
  const counts={}, uniqueNav=new Set(), positiveNav=new Set(), pairedNav=new Set();
  let lastModel=null,lastNav=null,epoch=0,duplicateFrames=0,clockResets=0;
  for(const row of rows){
    const m=row?.model_mono_ns,n=row?.nav_mono_ns;
    if(Number.isSafeInteger(m)&&m>0&&Number.isSafeInteger(n)&&n>0){
      if((lastModel!==null&&m<lastModel)||(lastNav!==null&&n<lastNav)){epoch++;clockResets++;lastModel=null;lastNav=null;}
      if(m===lastModel&&n===lastNav){duplicateFrames++;continue;}
      lastModel=m;lastNav=n;
    }
    const item=inspect(row);
    counts[item.status]=(counts[item.status]||0)+1;
    if(item.source&&Number.isSafeInteger(n)){
      const key=JSON.stringify([epoch,n,item.source]);
      uniqueNav.add(key);
      if(item.advised_icon_indices.length)positiveNav.add(key);
      if(item.status==="co_observed_unmapped")pairedNav.add(key);
    }
  }
  return {schema:1,counts,unique_candidate_envelopes:uniqueNav.size,unique_positive_envelopes:positiveNav.size,
    unique_paired_envelopes:pairedNav.size,duplicate_frames:duplicateFrames,clock_resets:clockResets,
    route_identity_verified:false,absolute_mapping_verified:false,control_usable:false};
}
function regression(){
  const check=(ok,name)=>{if(!ok)throw Error(name);passed.push(name);};
  const passed=[];
  const fixture=()=>({schema:3,control_usable:false,model_mono_ns:1e9,nav_mono_ns:9e8,nav_connected:true,
    map_candidate:{source:"amap_auto_13012",count:3,lanes:[{index:0,advised:false},{index:1,advised:true},{index:2,advised:null}],control_usable:false},
    geometry:{probs:[.9,.9,.9,.9],samples:[{x_m:10,reason:"dual_line_candidate",visible_lane_candidates:3}]},
    relative_position:{status:"local_candidate",reference:"model_origin_x0",left_m:1.8,right_m:1.8,width_m:3.6,offset_m:0,control_usable:false}});
  let r=fixture();let x=inspect(r);check(x.status==="co_observed_unmapped"&&x.advised_icon_indices[0]===1&&x.unknown_icon_count===1,"positive advice paired");
  check(x.absolute_lane_index===null&&x.mapped_target_lane===null&&x.control_usable===false,"no invented mapping");
  r=fixture();r.nav_mono_ns=5e8;check(inspect(r).status==="time_mismatch","stale pair");
  r=fixture();r.nav_connected=false;check(inspect(r).status==="missing_stream","disconnected");
  r=fixture();r.map_candidate=null;check(inspect(r).status==="no_valid_candidate","withdrawal");
  r=fixture();r.map_candidate.lanes[1].index=0;check(inspect(r).status==="no_valid_candidate","duplicate icon index");
  r=fixture();r.map_candidate.lanes[1].advised="true";check(inspect(r).status==="no_valid_candidate","strict boolean");
  r=fixture();r.map_candidate.lanes[1].advised=false;check(inspect(r).status==="no_positive_advice","no positive advice");
  r=fixture();r.geometry.probs[1]=.2;check(inspect(r).status==="no_local_position","low visual confidence");
  r=fixture();r.relative_position.offset_m=1;check(inspect(r).status==="no_local_position","inconsistent geometry");
  r=fixture();r.geometry.samples[0].reason="edge_conflict";check(inspect(r).status==="no_visual_topology","road edge conflict");
  r=fixture();r.geometry.samples[0].visible_lane_candidates=2;check(inspect(r).status==="co_observed_unmapped"&&!inspect(r).count_equal,"count mismatch not physical mapping");
  r=fixture();let r2=fixture();r2.model_mono_ns+=5e7;let a=audit([r,r,r2]);check(a.duplicate_frames===1&&a.unique_paired_envelopes===1&&a.counts.co_observed_unmapped===2,"dedup model and navigation envelope");
  a=audit([r2,r]);check(a.clock_resets===1&&a.unique_paired_envelopes===2,"clock reset scope");
  check(inspect(null).status==="invalid_record"&&audit([]).unique_paired_envelopes===0,"empty malformed");
  return passed;
}
export {inspect,audit,regression};
