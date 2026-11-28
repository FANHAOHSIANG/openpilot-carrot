"use strict";
(function(){
const finite=x=>typeof x==="number"&&Number.isFinite(x);
function parseDebug(s){
  if(typeof s!=="string"||s.length>8192)return {raw:null,preview:null,gate:"unavailable"};
  const number=k=>{const m=s.match(new RegExp("(?:^|\\s)"+k+"=(\\d{1,3}(?:\\.\\d+)?)(?=\\s|$|route=)"));const v=m?Number(m[1]):null;return finite(v)&&v>=0&&v<250?v:null};
  const g=s.match(/(?:^|\s)pre_gate=(no_session|inactive|session_latched|ego_unavailable|gap_over_20pct|within_gap_not_exit_verified)(?=\s|$|route=)/);
  return {raw:number("pre_raw"),preview:number("pre_preview"),gate:g?g[1]:"unavailable"};
}
function estimate(ego,target){
  if(!finite(ego)||!finite(target)||ego<0||target<0||ego>300||target>300||ego<=target)return null;
  const seconds=(ego-target)/3;
  return {seconds,metres:(ego+target)/7.2*seconds};
}
function sample(cache,now){
  const fresh=(key,ttl)=>{const x=cache[key];return x&&x.event.valid===true&&finite(x.received)&&now>=x.received&&now-x.received<=ttl?x.event:null};
  const man=fresh("carrotMan",1500),car=fresh("carState",600);
  if(!man)return null;
  const m=man.decoded||{},c=car?.decoded||{};
  const paired=car&&Math.abs(car.logMonoTime-man.logMonoTime)<=500e6;
  const ego=paired&&c.canValid===true&&finite(c.vEgo)&&c.vEgo>=0&&c.vEgo<=100?c.vEgo*3.6:null;
  const {raw,preview,gate}=parseDebug(m.szPosRoadName);
  const cap=finite(m.desiredSpeed)&&m.desiredSpeed>=0&&m.desiredSpeed<=250?m.desiredSpeed:null;
  const distance=finite(m.xDistToTurn)&&m.xDistToTurn>=0&&m.xDistToTurn<=2000000?m.xDistToTurn:null;
  const e=estimate(ego,raw);
  return {mono_ns:man.logMonoTime,car_mono_ns:paired?car.logMonoTime:null,ego_kph:ego,pre_raw_kph:raw,pre_preview_kph:preview,desired_cap_kph:cap,source:typeof m.desiredSource==="string"&&/^[a-zA-Z0-9_]{1,32}$/.test(m.desiredSource)?m.desiredSource:"unknown",gate,guide_distance_m:distance,ideal_seconds:e?.seconds??null,ideal_distance_m:e?.metres??null,exit_verified:false};
}
function csv(rows){
  const keys=["mono_ns","car_mono_ns","ego_kph","pre_raw_kph","pre_preview_kph","desired_cap_kph","source","gate","guide_distance_m","ideal_seconds","ideal_distance_m","exit_verified"];
  return keys.join(",")+"\n"+rows.map(r=>keys.map(k=>r[k]===null||r[k]===undefined?"":String(r[k])).join(",")).join("\n")+"\n";
}
function boot(doc,win){
  const $=id=>doc.getElementById(id),cache={};let sock=null,retry=0,enabled=false,record=false,rows=[],history=[],last=null,dropped=0;
  const clear=()=>{for(const k of Object.keys(cache))delete cache[k];last=null;};
  function stop(){win.clearTimeout(retry);retry=0;const old=sock;sock=null;if(old)old.close();clear();}
  function connect(){
    if(!enabled||doc.hidden||sock)return;
    const decoder=win.CarrotRawCapnp;if(!decoder){$("status").textContent="缺少原生解碼器";return}
    const u=new URL("/ws/raw_multiplex",win.location.href);u.protocol=win.location.protocol==="https:"?"wss:":"ws:";u.searchParams.set("services","carrotMan,carState");
    const s=new win.WebSocket(u);sock=s;s.binaryType="arraybuffer";
    s.onopen=()=>{if(sock===s)$("status").textContent="已連線，等待資料"};
    s.onmessage=e=>{if(sock!==s||typeof e.data==="string")return;try{
      const b=new Uint8Array(e.data),n=b[0];if(b.length<12||b.length>1048576||n<1||n>32||n+9>b.length)throw Error();
      const k=new TextDecoder().decode(b.subarray(1,n+1));if(!["carrotMan","carState"].includes(k))return;
      const p=b.subarray(n+1);if(decoder.framedMessageByteLength(p)!==p.length)throw Error();
      const ev=decoder.decodeReplayEvent(p,k,"",null,true);if(!ev||ev.service!==k||!finite(ev.logMonoTime)||ev.logMonoTime<=0)throw Error();
      const prev=cache[k];if(prev&&ev.logMonoTime<prev.event.logMonoTime){clear();history=[];}
      else if(prev&&ev.logMonoTime===prev.event.logMonoTime){if(ev.valid!==true)cache[k]={event:ev,received:prev.received};return;}
      cache[k]={event:ev,received:win.performance.now()};
    }catch(_){clear();}};
    s.onclose=()=>{if(sock!==s)return;sock=null;clear();$("status").textContent="連線中斷";if(enabled&&!doc.hidden)retry=win.setTimeout(connect,2000);};
    s.onerror=()=>s.close();
  }
  const series=[["ego_kph","#77b9ff"],["pre_raw_kph","#f3b758"],["pre_preview_kph","#62dda9"],["desired_cap_kph","#ec8ca6"]];
  function draw(){
    const canvas=$("plot"),ctx=canvas.getContext("2d"),W=canvas.width,H=canvas.height;
    ctx.clearRect(0,0,W,H);ctx.fillStyle="#101820";ctx.fillRect(0,0,W,H);
    const max=Math.max(120,...history.flatMap(r=>series.map(([k])=>finite(r[k])&&r[k]<200?r[k]:0))),left=42,right=W-12,bottom=H-22,top=12;
    const newest=history.at(-1)?.mono_ns??0;const X=r=>right-(newest-r.mono_ns)/30e9*(right-left),Y=v=>bottom-v/max*(bottom-top);
    ctx.font="12px system-ui";ctx.fillStyle="#a6b8c8";for(let i=0;i<=4;i++){const v=max*i/4,y=Y(v);ctx.strokeStyle="#30414e";ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText(v.toFixed(0),5,y+4);}
    for(const [k,color] of series){ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();let prev=null;for(const r of history){const v=r[k];if(!finite(v)||v>=200||X(r)<left){prev=null;continue;}if(!prev||r.mono_ns-prev.mono_ns>1e9)ctx.moveTo(X(r),Y(v));else ctx.lineTo(X(r),Y(v));prev=r;}ctx.stroke();}
  }
  const fmt=(v,d=1)=>finite(v)?v.toFixed(d):"—";
  function tick(){
    if(!enabled||doc.hidden)return;
    const r=sample(cache,win.performance.now());
    const fields={ego:r?.ego_kph,raw:r?.pre_raw_kph,preview:r?.pre_preview_kph,cap:r?.desired_cap_kph,distance:r?.guide_distance_m,seconds:r?.ideal_seconds,ideal:r?.ideal_distance_m};
    for(const [k,v] of Object.entries(fields))$(k).textContent=k==="cap"&&finite(v)&&v>=200?"無低速上限":fmt(v,k==="distance"||k==="ideal"?0:1);
    $("gate").textContent=r?.gate??"等待有效資料";$("source").textContent=r?.source??"—";
    if(r&&r.mono_ns!==last){last=r.mono_ns;history.push(r);history=history.filter(x=>r.mono_ns-x.mono_ns<=30e9).slice(-300);if(record){if(rows.length>=9000){rows.shift();dropped++;}rows.push(r);}}
    $("count").textContent=`已記錄 ${rows.length} 筆；輪替 ${dropped} 筆`;draw();
  }
  $("connect").onclick=()=>{enabled=!enabled;$("connect").textContent=enabled?"停止連線":"開始連線";if(enabled)connect();else{stop();history=[];for(const k of ["ego","raw","preview","cap","distance","seconds","ideal","gate","source"])$(k).textContent="—";$("status").textContent="未連線";draw();}};
  $("record").onclick=()=>{record=!record;$("record").textContent=record?"停止紀錄":"開始紀錄";};
  $("export").onclick=()=>{const url=win.URL.createObjectURL(new Blob([csv(rows)],{type:"text/csv;charset=utf-8"}));const a=doc.createElement("a");a.href=url;a.download="pre-observe-"+Date.now()+".csv";a.click();win.setTimeout(()=>win.URL.revokeObjectURL(url),1000);};
  doc.addEventListener("visibilitychange",()=>{if(doc.hidden){stop();history=[];}else if(enabled)connect();});win.addEventListener("pagehide",stop);win.setInterval(tick,200);
}
if(typeof module!=="undefined"&&module.exports)module.exports={parseDebug,estimate,sample,csv};
if(typeof document!=="undefined")boot(document,window);
})();
