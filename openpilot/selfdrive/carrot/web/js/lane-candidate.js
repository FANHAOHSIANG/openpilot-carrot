// Offline evidence parser; candidate semantics only, no live HUD or control integration.
function parseLaneCandidate(source,input){
  const invalid=reason=>({source,status:reason,guide:null,absoluteLaneIndex:null,controlUsable:false});
  const isInt=(x,min,max)=>Number.isSafeInteger(x)&&x>=min&&x<=max;
  const flag=x=>x===true||x===1||x==="1"||x==="true"?true:x===false||x===0||x==="0"||x==="false"?false:null;
  const icon=x=>isInt(x,0,65535)?x:typeof x==="string"&&/^\d{1,5}$/.test(x)&&isInt(Number(x),0,65535)?Number(x):null;
  let lanes=[];
  if(source==="amap_auto_13012"){
    if(typeof input==="string"){if(input.length>65536)return invalid("oversize");try{input=JSON.parse(input)}catch{return invalid("invalid_json")}}
    const enabled=flag(input?.drive_way_enabled);
    if(enabled===false)return invalid("withdrawn");
    if(enabled!==true)return invalid("missing_enabled");
    const n=input.drive_way_size,rows=input.drive_way_info;
    if(!isInt(n,1,32)||!Array.isArray(rows)||rows.length!==n)return invalid("invalid_count");
    for(const r of rows){
      const index=r?.drive_way_number,code=icon(r?.drive_way_lane_Back_icon),advised=flag(r?.trafficLaneAdvised);
      if(!isInt(index,0,n-1)||code===null)return invalid("invalid_lane");
      lanes.push({index,backCode:code,frontCode:null,advised});
    }
    lanes.sort((a,b)=>a.index-b.index);
    if(lanes.some((r,i)=>r.index!==i))return invalid("invalid_order");
  }else if(source==="amap_link_14"){
    const n=input?.laneCount,back=input?.backLane,front=input?.frontLane;
    if(n===0)return invalid("withdrawn");
    if(!isInt(n,1,32)||!Array.isArray(back)||!Array.isArray(front)||back.length!==n||front.length!==n)return invalid("invalid_count");
    if(!back.every(x=>isInt(x,0,255))||!front.every(x=>isInt(x,0,255)))return invalid("invalid_lane");
    lanes=back.map((code,index)=>({index,backCode:code,frontCode:front[index],advised:front[index]!==255}));
  }else return invalid("unknown_source");
  return {source,status:lanes.some(r=>r.advised===true)?"recommendation_candidate":"no_positive_advice",guide:{count:lanes.length,lanes,adviceSemantics:"cross_reference_pending_screen_validation",absoluteMappingVerified:false},absoluteLaneIndex:null,controlUsable:false};
}
globalThis.CarrotLaneCandidate={parseLaneCandidate};
