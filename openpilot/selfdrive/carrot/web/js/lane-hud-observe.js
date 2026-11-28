// Read-only optional live HUD event panel. It never changes the driven path.
// Optional dual-source raw subscription because compact lane messages
// omit the original receipt timestamp. No media ownership or control writes.
(function(root){
"use strict";
const KEY="carrot.laneHudObserve.v1";
const mode=v=>["auto","always","off"].includes(v)?v:"off";
function view(core,cache,now,displayMode,visible,tracker){
  if(!visible||mode(displayMode)==="off")return null;
  const s=core.snapshot(cache,now);
  const p=core.presentation(s,displayMode);
  const pair=core.lanePairDisplay(s),continuity=tracker?tracker.observe(s):null;
  if(!p.visible&&!s.map_candidate)return null;
  return {count:p.count,distance:p.distance_m,
    flags:p.raw_flags,active:p.event_active,mapCandidate:s.map_candidate,pair,continuity,
    visualCount:p.visual_count,visualWidth:p.visual_width_m,
    synchronized:p.event_active&&p.visual_count!==null&&Number.isFinite(s.model_nav_message_delta_ms)&&Math.abs(s.model_nav_message_delta_ms)<=250,
    recommendation_status:p.recommendation_status,recommendedLane:null,
    note:p.event_active?"導航車道資料 · 尚未匹配自車位置":s.map_candidate?"獨立推薦圖示 · 尚未匹配自車位置":"等待有效車道引導",
    control_usable:false};
}
function boot(doc,win){
  const core=win.CarrotLaneObserve,decoder=win.CarrotRawCapnp;
  if(!core||!decoder)return;
  let cache={},socket=null,panel=null,host=null,nextConnect=0,lastText="";
  const tracker=core.createLocalLaneTracker();
  function setting(){try{return mode(win.localStorage.getItem(KEY));}catch(_){return "off";}}
  function hide(){if(panel)panel.hidden=true;}
  function close(){tracker.reset();const s=socket;socket=null;cache={};if(s){try{s.close();}catch(_){}}hide();}
  function connect(){
    const url=new URL("/ws/raw_multiplex",win.location.href);
    url.protocol=win.location.protocol==="https:"?"wss:":"ws:";
    url.searchParams.set("services","carrotNavi,modelV2");
    const s=new win.WebSocket(url);socket=s;s.binaryType="arraybuffer";
    s.onmessage=e=>{if(socket!==s||typeof e.data==="string")return;
      try{const event=core.decodeWire(e.data,decoder);if(["carrotNavi","modelV2"].includes(event?.service)){if(cache[event.service]&&event.logMonoTime<cache[event.service].event.logMonoTime)tracker.reset();if(event.service==="modelV2"&&event.valid!==true)tracker.reset();core.ingest(cache,event,win.performance.now());}}catch(_){tracker.reset();cache={};hide();}};
    s.onclose=()=>{if(socket!==s)return;tracker.reset();socket=null;cache={};hide();nextConnect=win.performance.now()+2000;};
    s.onerror=()=>{try{s.close();}catch(_){}};
  }
  function mount(target){
    if(host===target&&panel?.isConnected)return;
    panel?.remove();host=target;
    panel=doc.createElement("div");panel.hidden=true;
    panel.setAttribute("data-lane-guide-observe","true");
    panel.setAttribute("aria-label","導航車道觀察，非變道指示");
    Object.assign(panel.style,{position:"absolute",top:"19%",left:"50%",transform:"translateX(-50%)",
      maxWidth:"52%",padding:"5px 9px",border:"1px solid #68849a",borderRadius:"7px",
      background:"rgba(15,25,35,.88)",color:"#e7eef5",textAlign:"center",
      font:"600 clamp(10px,1.5vw,14px)/1.35 system-ui",pointerEvents:"none",zIndex:"1"});
    host.appendChild(panel);lastText="";
  }
  function tick(){
    const m=setting(),overlay=win.CarrotHudOverlay;
    const visible=m!=="off"&&!doc.hidden&&!win.CarrotVisionReplay?.isActive?.()&&
      overlay?.status?.()?.visible===true&&overlay.root?.isConnected===true;
    if(!visible){close();return;}
    mount(overlay.root);
    const now=win.performance.now();
    if(!socket&&now>=nextConnect){try{connect();}catch(_){nextConnect=now+2000;}}
    const p=view(core,cache,now,m,true,tracker);
    if(!p){hide();return;}
    const vision=p.visualCount==null?"視覺車道資料不足":("視覺 "+p.visualCount+" 條局部候選"+(p.synchronized?" · 時間接近":" · 時間未對齊"));
    const mc=p.mapCandidate;
    const pair=p.pair;
    const candidate=mc?"\n推薦圖示 "+(pair.positive_icons.length?pair.positive_icons.join("、"):"無明確推薦")+" / "+mc.count+" · 未配對":"";
    const local=pair.local_offset_m===null?"":"\n模型原點偏移 "+pair.local_offset_m.toFixed(2)+" m"+(p.continuity?.status==="continuous"?" · 局部連續":" · 建立觀察中");
    const association=mc?"\n"+({no_candidate:"無有效候選",no_local_geometry:"局部幾何不足",time_mismatch:"時間未對齊",co_observed_unmapped:"時間接近 · 空間未配對"})[pair.status]:"";
    const txt=(p.active?("導航 "+p.count+" 車道"+(p.distance==null?"":" · "+p.distance+" m")+"\n"+vision+"\n"+p.note):p.note)+candidate+local+association;
    if(lastText!==txt){panel.textContent=txt;panel.style.whiteSpace="pre-line";lastText=txt;}
    panel.hidden=false;
  }
  doc.addEventListener("visibilitychange",()=>{if(doc.hidden)close();else tick();});
  win.addEventListener("pagehide",close);
  win.setInterval(tick,200);
}
root.CarrotLaneHudObserve={KEY,mode,view};
if(typeof document!=="undefined")document.addEventListener("DOMContentLoaded",()=>boot(document,window));
})(globalThis);
