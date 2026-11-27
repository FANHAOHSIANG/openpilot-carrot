// Read-only diagnostic display. No control request, no navigation ownership.
(function(root){
"use strict";
const DIST=[10,20,30,40,60], MAX_RECORDS=9000;
const finite=n=>typeof n==="number"&&Number.isFinite(n);
const bounded=(v,lo,hi)=>finite(v)&&v>=lo&&v<=hi;
function points(line){
  const x=line?.x,y=line?.y;
  if(!Array.isArray(x)||!Array.isArray(y)||x.length!==y.length||x.length<2||x.length>512)return null;
  if(x.some((v,i)=>!bounded(v,-1,500)||!bounded(y[i],-100,100)||(i>0&&v<=x[i-1])))return null;
  return x.map((v,i)=>[v,y[i]]);
}
function at(p,x){
  if(!p||x<p[0][0]||x>p[p.length-1][0])return null;
  for(let i=0;i<p.length;i++){
    if(p[i][0]===x)return p[i][1];
    if(p[i][0]>x){const [a,b]=p[i-1],[c,d]=p[i];return b+(d-b)*(x-a)/(c-a);}
  }
  return null;
}
function geometry(m){
  const lines=Array.from({length:4},(_,i)=>points(m?.laneLines?.[i]));
  const edges=Array.from({length:2},(_,i)=>points(m?.roadEdges?.[i]));
  const probs=Array.from({length:4},(_,i)=>bounded(m?.laneLineProbs?.[i],0,1)?m.laneLineProbs[i]:null);
  const stds=Array.from({length:2},(_,i)=>bounded(m?.roadEdgeStds?.[i],0,100)?m.roadEdgeStds[i]:null);
  const path=points(m?.position);
  const samples=DIST.map(x=>{
    const l=lines.map((p,i)=>probs[i]!==null&&probs[i]>=.65?at(p,x):null);
    const e=edges.map(p=>at(p,x));const native=at(path,x);
    let reason="inner_unavailable",center=null,width=null,count=null;
    if(l[1]!==null&&l[2]!==null){
      const w=l[2]-l[1]; // model local +y to right; never repair crossed lines
      if(!bounded(w,2.2,5))reason="invalid_width_or_order";
      else if((stds[0]!==null&&stds[0]>0&&stds[0]<=.5&&e[0]!==null&&e[0]>l[1]+.3)||
        (stds[1]!==null&&stds[1]>0&&stds[1]<=.5&&e[1]!==null&&e[1]<l[2]-.3))reason="edge_conflict";
      else{width=w;center=(l[1]+l[2])/2;count=1+Number(l[0]!==null&&bounded(l[1]-l[0],2.2,5))+Number(l[3]!==null&&bounded(l[3]-l[2],2.2,5));reason="dual_line_candidate";}
    }
    return {x_m:x,lane_y_m:l,edge_y_m:e,center_y_m:center,width_m:width,visible_lane_candidates:count,native_y_m:native,reason};
  });
  return {lines,edges,probs,stds,path,samples,control_usable:false};
}
function decodeWire(buffer,decoder){
  const bytes=new Uint8Array(buffer);
  if(bytes.length<12||bytes.length>1024*1024)throw new Error("invalid frame size");
  const n=bytes[0];if(n<1||n>32||n+9>bytes.length)throw new Error("invalid prefix");
  const service=new TextDecoder().decode(bytes.subarray(1,1+n));
  if(!["modelV2","carrotNavi","carState","controlsState"].includes(service))return null;
  const payload=bytes.subarray(n+1);
  if(decoder.framedMessageByteLength(payload)!==payload.length)throw new Error("incomplete event");
  const event=decoder.decodeReplayEvent(payload,service,"",null,true);
  return event&&event.service===service&&finite(event.logMonoTime)&&event.logMonoTime>0?event:null;
}
function snapshot(cache,now){
  const fresh=(k,ttl)=>{const v=cache[k];return v&&v.event.valid===true&&now>=v.received&&now-v.received<=ttl?v.event:null};
  const model=fresh("modelV2",600),nav=fresh("carrotNavi",1500),car=fresh("carState",600),ctrl=fresh("controlsState",600);
  const geom=model?geometry(model.decoded):null;
  let lane=null,navReason=nav?"no_lane":"stale_or_disconnected";
  if(nav&&nav.decoded?.connected===true){
    const a=nav.decoded.laneCurrent,meta=a?.meta;
    const age=meta&&finite(meta.receivedMonoTimeNanos)?(nav.logMonoTime-meta.receivedMonoTimeNanos)/1e6:null;
    if(a?.present===true&&a.visible===true&&Number.isInteger(a.count)&&a.count>0&&a.count<=32&&age!==null&&age>=0&&age<=6000){
      lane={count:a.count,distance_m:bounded(a.distanceM,0,2000000)?a.distanceM:null,
        available_raw:Array.isArray(a.available)&&a.available.length===a.count&&a.available.every(v=>Number.isInteger(v)&&v>=-32768&&v<=32767)?a.available.slice():[],
        receipt_age_ms:Math.round(age),source_wall_ms:meta.sourceTimestampMillis||null,received_mono_ns:meta.receivedMonoTimeNanos};
      navReason="lane_present";
    }else if(a?.present===true&&a.visible===true)navReason="invalid_or_expired_lane";
  }
  const gap=model&&nav?(model.logMonoTime-nav.logMonoTime)/1e6:null;
  const laneGap=model&&lane?(model.logMonoTime-lane.received_mono_ns)/1e6:null;
  const carGap=model&&car?Math.abs(model.logMonoTime-car.logMonoTime)/1e6:null;
  const ctrlGap=model&&ctrl?Math.abs(model.logMonoTime-ctrl.logMonoTime)/1e6:null;
  return {geometry:geom,lane,nav_reason:navReason,nav_connected:nav?.decoded?.connected===true,
    model_mono_ns:model?.logMonoTime??null,nav_mono_ns:nav?.logMonoTime??null,
    model_nav_message_delta_ms:gap===null?null:Math.round(gap),
    model_lane_receipt_delta_ms:laneGap===null?null:Math.round(laneGap),
    speed_kph:carGap!==null&&carGap<=250&&car.decoded?.canValid===true&&bounded(car.decoded?.vEgo,0,100)?car.decoded.vEgo*3.6:null,
    steering_deg:carGap!==null&&carGap<=250&&car.decoded?.canValid===true&&bounded(car.decoded?.steeringAngleDeg,-1000,1000)?car.decoded.steeringAngleDeg:null,
    desired_curvature:ctrlGap!==null&&ctrlGap<=250&&bounded(ctrl.decoded?.desiredCurvature,-2,2)?ctrl.decoded.desiredCurvature:null,
    phone_clock_alignment_verified:false,absolute_lane_index:null,control_usable:false};
}
function ingest(cache,event,received){
  if(!event||!finite(received))return;
  const old=cache[event.service];
  if(old&&event.logMonoTime<old.event.logMonoTime){for(const key of Object.keys(cache))delete cache[key];}
  cache[event.service]={event,received};
}

function presentation(s,mode){
  const lane=s?.lane;
  const valid=lane!=null&&Number.isInteger(lane.count)&&lane.count>=1&&lane.count<=32;
  const modeValue=["off","auto","always"].includes(mode)?mode:"off";
  const near=s?.geometry?.samples?.[0];
  return {visible:modeValue==="always"||(modeValue==="auto"&&valid),
    event_active:valid, mode:modeValue, count:valid?lane.count:null,
    distance_m:valid?lane.distance_m:null,
    raw_flags:valid&&Array.isArray(lane.available_raw)&&lane.available_raw.length===lane.count?lane.available_raw.slice():[],
    visual_count:near?.visible_lane_candidates??null,
    visual_width_m:near?.width_m??null,
    // Source semantics and absolute lane association are not verified.
    recommended_lane:null,absolute_lane_index:null,control_usable:false,
    recommendation_status:valid?(lane.available_raw?.length===lane.count?"raw_flags_unverified":"no_recommendation_data"):"no_active_guidance"};
}

function boot(doc,win){
  const $=id=>doc.getElementById(id);
  const cache={};let socket=null,enabled=false,recording=false,records=[],dropped=0,lastRecord=null,retry=0,decodeErrors=0;
  const status=$("status"),canvas=$("plot"),ctx=canvas.getContext("2d");
  function clear(){for(const k of Object.keys(cache))delete cache[k];$("guidePanel").hidden=$("displayMode").value!=="always";$("lanes").replaceChildren();$("nav").textContent="—";$("distance").textContent="—";$("guideStatus").textContent="無有效車道引導";$("guideNote").textContent="等待引導";$("matchStatus").textContent="等待雙來源";}
  function disconnect(){win.clearTimeout(retry);retry=0;const s=socket;socket=null;if(s)s.close();clear();}
  function connect(){
    if(!enabled||doc.hidden||socket)return;
    if(!win.CarrotRawCapnp){status.textContent="缺少原生解碼器，請確認 C4 版本";return;}
    const url=new URL("/ws/raw_multiplex",win.location.href);url.protocol=win.location.protocol==="https:"?"wss:":"ws:";
    url.searchParams.set("services","modelV2,carrotNavi,carState,controlsState");
    const s=new WebSocket(url);socket=s;s.binaryType="arraybuffer";
    s.onopen=()=>{if(socket===s)status.textContent="已連線 · 等待資料";};
    s.onmessage=e=>{if(socket!==s||typeof e.data==="string")return;try{const ev=decodeWire(e.data,win.CarrotRawCapnp);if(ev)ingest(cache,ev,win.performance.now());}catch(_){decodeErrors++;clear();}};
    s.onclose=()=>{if(socket!==s)return;socket=null;clear();status.textContent="連線中斷";if(enabled&&!doc.hidden)retry=win.setTimeout(connect,2000);};
    s.onerror=()=>s.close();
  }
  function draw(g){
    const W=canvas.width,H=canvas.height;
    ctx.clearRect(0,0,W,H);ctx.fillStyle="#17212a";ctx.fillRect(0,0,W,H);
    const X=y=>W/2+y*W/24,Y=x=>H-20-x*(H-32)/60;
    ctx.lineWidth=1;ctx.font="13px system-ui";ctx.fillStyle="#8194a7";
    for(const x of DIST){ctx.strokeStyle="#354553";ctx.beginPath();ctx.moveTo(0,Y(x));ctx.lineTo(W,Y(x));ctx.stroke();ctx.fillText(x+"m",8,Y(x)-3);}
    function line(p,color,dash=[],width=2){
      if(!p)return;ctx.save();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();
      for(let i=0;i<p.length;i++){let [x,y]=p[i];if(i===0)ctx.moveTo(X(y),Y(x));else ctx.lineTo(X(y),Y(x));}
      ctx.stroke();ctx.restore();
    }
    if(g){
      g.edges.forEach((p,i)=>line(p,g.stds[i]!==null&&g.stds[i]>0&&g.stds[i]<=.5?"#fa8c86":"#82696a",[6,5]));
      g.lines.forEach((p,i)=>line(p,g.probs[i]!==null&&g.probs[i]>=.65?"#e6d283":"#65717b",[5,4]));
      line(g.path,"#64aaff",[],3);
      for(let i=1;i<g.samples.length;i++){const a=g.samples[i-1],b=g.samples[i];if(a.center_y_m!==null&&b.center_y_m!==null)line([[a.x_m,a.center_y_m],[b.x_m,b.center_y_m]],"#61dfae",[],3);}
    }
    ctx.fillStyle="#e8edf1";ctx.fillRect(X(0)-10,H-29,20,26);
  }
  const fmt=(v,d=1)=>finite(v)?v.toFixed(d):"—";
  function update(){
    const t=win.performance.now(),s=snapshot(cache,t),p=presentation(s,$("displayMode").value);
    $("guidePanel").hidden=!p.visible;
    $("guideStatus").textContent=p.event_active?"導航車道引導":"無有效車道引導";
    $("guideNote").textContent=p.recommendation_status==="no_recommendation_data"?"推薦車道尚未傳入 C4":p.recommendation_status==="raw_flags_unverified"?"車道旗標語意未驗證":"等待引導";
    $("matchStatus").textContent=p.event_active&&p.visual_count!==null?"地圖與視覺同時可見 · 尚未空間匹配":"等待雙來源";
    if(socket?.readyState===1)status.textContent=s.geometry?"即時 C4 視覺 · 只讀":"等待有效 C4 視覺";
    $("nav").textContent=s.lane?s.lane.count+" 車道":s.nav_connected?"暫無有效車道引導":"導航未連線";
    $("distance").textContent=s.lane&&s.lane.distance_m!==null?s.lane.distance_m+" m":"—";
    const strip=$("lanes");strip.replaceChildren();
    if(s.lane){for(let i=0;i<s.lane.count;i++){
      const tile=doc.createElement("span");const flag=s.lane.available_raw[i];
      tile.className="tile";tile.textContent=(i+1)+"｜"+(flag===undefined?"—":flag);strip.append(tile);
    }}
    const near=s.geometry?.samples[0];$("vision").textContent=near?.visible_lane_candidates==null?"—":near.visible_lane_candidates+" 條候選";
    $("width").textContent=fmt(near?.width_m,2)+" m";
    $("probs").textContent=s.geometry?s.geometry.probs.map(p=>fmt(p,2)).join(" / "):"—";
    $("edges").textContent=s.geometry?s.geometry.stds.map(p=>fmt(p,2)).join(" / "):"—";
    $("delta").textContent=fmt(s.model_nav_message_delta_ms,0)+" ms";
    $("laneage").textContent=s.lane?fmt(s.model_lane_receipt_delta_ms,0)+" ms":"—";
    $("speed").textContent=fmt(s.speed_kph)+" km/h";
    $("steer").textContent=fmt(s.steering_deg)+"°";
    $("curvature").textContent=fmt(s.desired_curvature,6);
    draw(s.geometry);
    if(recording&&s.model_mono_ns!==null&&s.model_mono_ns!==lastRecord){
      lastRecord=s.model_mono_ns;
      if(records.length<MAX_RECORDS){
        records.push({schema:2,wall_ms:Date.now(),...s,presentation:p,geometry:s.geometry?{samples:s.geometry.samples,probs:s.geometry.probs,stds:s.geometry.stds}:null});
      }else{dropped++;recording=false;$("record").textContent="紀錄已滿";}
    }
    $("count").textContent=records.length+" 筆"+(dropped?"（上限停止）":"")+" · 解碼失敗 "+decodeErrors;
  }
  const hudMode=$("mainHudMode");if(hudMode){try{hudMode.value=win.localStorage.getItem("carrot.laneHudObserve.v1")||"off";}catch(_){}hudMode.onchange=()=>{try{win.localStorage.setItem("carrot.laneHudObserve.v1",hudMode.value);}catch(_){status.textContent="無法儲存主 HUD 設定";}};}
  $("connect").onclick=()=>{enabled=!enabled;if(enabled){$("connect").textContent="停止連線";connect();}else{disconnect();$("connect").textContent="開始連線";status.textContent="已停止";}};
  $("displayMode").onchange=()=>update();
  $("record").onclick=()=>{if(records.length>=MAX_RECORDS)return;recording=!recording;$("record").textContent=recording?"停止紀錄":"開始紀錄";};
  $("export").onclick=()=>{
    if(!records.length)return;const blob=new Blob([records.map(r=>JSON.stringify(r)).join("\n")+"\n"],{type:"application/x-ndjson"});
    const href=URL.createObjectURL(blob),a=doc.createElement("a");a.href=href;a.download="carrot-lane-observe-"+Date.now()+".jsonl";a.click();win.setTimeout(()=>URL.revokeObjectURL(href),2000);
  };
  doc.addEventListener("visibilitychange",()=>{if(doc.hidden){disconnect();status.textContent="頁面隱藏，已暫停";}else if(enabled)connect();});
  win.addEventListener("pagehide",()=>{enabled=false;disconnect();});
  win.setInterval(update,200);update();
}
root.CarrotLaneObserve={points,at,geometry,decodeWire,snapshot,ingest,presentation};
if(typeof document!=="undefined")document.addEventListener("DOMContentLoaded",()=>{if(document.getElementById("plot")&&document.getElementById("displayMode"))boot(document,window);});
})(globalThis);
