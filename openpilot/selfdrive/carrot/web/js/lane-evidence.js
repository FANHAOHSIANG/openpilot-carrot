// Read-only normalized lane evidence. No control outputs; no provider index assumptions.
function createLaneEvidence() {
  let scope=null, lastSeq=-1, lastMono=-1, sample=null, received=-1;
  const ended=new Set();
  const token=v=>typeof v==="string"&&v.length>0&&v.length<=128;
  const integer=(v,a,b)=>Number.isSafeInteger(v)&&v>=a&&v<=b;
  const number=(v,a,b)=>typeof v==="number"&&Number.isFinite(v)&&v>=a&&v<=b;
  const key=f=>JSON.stringify([f.sessionId,f.routeId,f.routeEpoch]);
  function ingest(f,now) {
    if(!f||!number(now,0,Number.MAX_SAFE_INTEGER)||!token(f.sessionId)||!token(f.routeId)||!integer(f.routeEpoch,0,Number.MAX_SAFE_INTEGER)||!integer(f.seq,0,Number.MAX_SAFE_INTEGER)||!number(f.monoMs,0,Number.MAX_SAFE_INTEGER)) {sample=null;return false;}
    const k=key(f);
    if(ended.has(k))return false;
    if(scope&&scope.key!==k){
      if(f.sessionId===scope.session&&f.routeEpoch<=scope.epoch)return false;
      if(f.kind!=="bind")return false;
    }
    if(!scope||scope.key!==k){
      if(f.kind!=="bind"||ended.size>=1024){sample=null;return false;}
      if(scope)ended.add(scope.key);
      scope={key:k,session:f.sessionId,epoch:f.routeEpoch};lastSeq=-1;lastMono=-1;sample=null;received=-1;
    }
    if(f.seq<=lastSeq||f.monoMs<lastMono||now<received)return false;
    lastSeq=f.seq;lastMono=f.monoMs;received=now;
    if(f.kind==="end"){ended.add(k);sample=null;return true;}
    if(f.kind==="bind"||f.kind==="hide"){sample=null;return true;}
    if(f.kind!=="snapshot"){sample=null;return false;}
    const guide=f.guide, hd=f.hd;
    const guideOK=guide&&integer(guide.count,1,32)&&Array.isArray(guide.flags)&&guide.flags.length===guide.count&&guide.flags.every(v=>integer(v,-32768,32767))&&number(guide.ageMs,0,6000);
    const hdOK=hd&&integer(hd.egoIndexRaw,-1,128)&&number(hd.ageMs,0,1000);
    sample={guide:guideOK?{count:guide.count,flags:guide.flags.slice(),ageMs:guide.ageMs}:null,hd:hdOK?{egoIndexRaw:hd.egoIndexRaw,egoBase:"unknown",physicalCount:integer(hd.physicalCount,1,32)?hd.physicalCount:null,laneId:token(hd.laneId)?hd.laneId:null,ageMs:hd.ageMs}:null};
    return true;
  }
  function observe(now,vision) {
    const elapsed=now-received;
    const fresh=sample&&number(elapsed,0,1500);
    const g=fresh&&sample.guide&&sample.guide.ageMs+elapsed<=6000?sample.guide:null;
    const h=fresh&&sample.hd&&sample.hd.ageMs+elapsed<=1000?sample.hd:null;
    const count=vision&&number(vision.ageMs,0,600)&&integer(vision.visibleCount,1,3)?vision.visibleCount:null;
    return {guide:g?{count:g.count,flags:g.flags.slice()}:null,hd:h?{egoIndexRaw:h.egoIndexRaw,egoBase:h.egoBase,physicalCount:h.physicalCount,laneId:h.laneId}:null,visualCount:count,association:g&&h&&count!==null?"co_observed_not_matched":"insufficient_evidence",recommendedLane:null,absoluteLaneIndex:null,controlUsable:false};
  }
  return {ingest,observe};
}
globalThis.CarrotLaneEvidence={createLaneEvidence};
