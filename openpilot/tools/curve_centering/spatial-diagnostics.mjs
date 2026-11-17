// Mechanism probes of the original surrogate, NOT a candidate vehicle policy.
import {trial} from './spatial-ramp.mjs';
const probes=[
  ['original',.3,.3,{}], ['zero_bias',.3,0,{}], ['zero_transport_delay',0,.3,{}],
  ['zero_actuator_lag',.3,.3,{lag:0}], ['zero_command_smoothing',.3,.3,{smoothing:0}],
  // Oracle look-ahead equals the known artificial transport+lag+smoothing times.
  // Real road preview and plant timing are NOT known/calibrated this way.
  ['oracle_feedforward_preview',.3,.3,{oraclePreviewSeconds:.3+.15+.1}],
];
const results=probes.map(([name,delay,bias,options])=>{
  const result=trial(true,delay,bias,{...options,trace:true});
  const peak=result.trace.reduce((a,b)=>Math.abs(b.yAfter)>Math.abs(a.yAfter)?b:a);
  const exceed=result.trace.filter(r=>Math.abs(r.yAfter)>.85);
  const {trace,...metrics}=result;
  return {name,delay,bias,options,...metrics,peakState:peak,
    assumedClearance:.85,exceedanceSteps:exceed.length,firstExceedance:exceed[0]??null};
});
console.log(JSON.stringify({scope:'synthetic_surrogate_ablations_not_vehicle_causality',
  candidateCOrUUsed:false,deployment_approved:false,results},null,2));
