// Synthetic spatial ramp, ideal preview, fixed analytic steering surrogate.
// Run with node spatial-ramp.mjs. Positive y follows positive curvature.
const clip=(x,l,h)=>Math.max(l,Math.min(h,x));
function road(s){return .01*(s<90||s>=350?0:s<150?(1-Math.cos(Math.PI*(s-90)/60))/2:s<=290?1:(1+Math.cos(Math.PI*(s-290)/60))/2);}
function trial(preview,delay,bias){
  const dt=.01, queue=Array(Math.round(delay/dt)).fill(0);
  let s=0,v=18,a=0,y=0,h=0,k=0,cmd=0,exit=0,peak=0,minSpeed=v;
  for(let i=0;i<6000&&s<450;i++){
    let target=18;
    if(preview) for(let d=0;d<=100;d+=2){
      const c=road(s+d); if(!c) continue;
      const cap=Math.sqrt(2.4/c);
      target=Math.min(target,Math.max(cap,Math.sqrt(cap*cap+.36+4*d)-.6));
    }
    a+=clip(clip((target-v)/.5,-2,1)-a,-2*dt,2*dt);
    v=clip(v+a*dt,.1,18);
    minSpeed=Math.min(minSpeed,v);
    const r=road(s),wanted=r-2*(y+20*h-bias)/400;
    cmd+=clip((wanted-cmd)*(1-Math.exp(-dt/.1)),-5*dt/v**2,5*dt/v**2);
    queue.push(cmd);
    k+=(clip(queue.shift(),-3/v**2,3/v**2)-k)*(1-Math.exp(-dt/.15));
    const ds=v*Math.cos(h)/(1-r*y);
    if(!Number.isFinite(ds)||ds<=0||Math.abs(y)>10)break;
    y+=v*Math.sin(h)*dt;h+=(v*k-r*ds)*dt;s+=ds*dt;
    peak=Math.max(peak,Math.abs(y));if(s>=290)exit=Math.max(exit,Math.abs(y));
  }
  return {completed:s>=450,peak,exit,minSpeed};
}
for(const delay of [.1,.3]) for(const bias of [0,.3]) for(const preview of [false,true])
  console.log(JSON.stringify({delay,bias,preview,...trial(preview,delay,bias)}));
