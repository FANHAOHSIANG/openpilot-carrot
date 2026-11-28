# Low-speed steering oscillation: shadow recording only

Default OFF. With the vehicle parked, use Settings > Toggles > 低速防搖擺（僅紀錄）.
This starts an independent, low-priority read-only observer on the next onroad session. No controlsd, CAN, Panda, steering limits or existing controller settings changed. It never sends actuator messages. Mode 2 is not provided.

The model-only experimental candidate uses the 11/28 medium replay constants (tau 0.1s, 75ms gap) with measured car speed and a conservative turn proxy. These are research parameters, not calibrated for driving. It observes raw model curvature, not a replacement for the selected planner or the applied vehicle path. Sample times identify original messages. The report is limited to about 5 Hz at low speed; raw rlog retains the full-rate original streams. Missing data or exceptions reset shadow state. Existing manager health checks remain in force.

Look for logMessage events lowSpeedOscillationShadowStart, lowSpeedOscillationShadow and lowSpeedOscillationShadowSkipped in an ordinary rlog upload. Confirm these events in a parked startup/device bench check before collecting on-road data. Upload full rlog (not qlog only). If the observer causes a process alert or device load/latency regression, disable it while parked. No deployment approval or vehicle testing is claimed by this commit.
