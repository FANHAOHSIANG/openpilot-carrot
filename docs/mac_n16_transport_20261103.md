# Mac N16 transport and HUD alignment, 2026-11-03

## Evidence and scope

The supplied November 3 drive used N16 model `01effc679eb46d60...` on the
Mac ANE. Across the seven complete segments, `livePose.inputsOK` was false
in 2801/7125 messages while `sensorsOK` and `posenetOK` remained true.
There were real model-consumer camera frame skips and invalid odometry
samples. This does not establish that all invalid pose/calibration/parameter
messages have the same cause. The camera producers' frame IDs were consecutive.

Runtime timing window means showed approximately 35.2 ms server execution,
47.8 ms USB exchange and 54.1 ms model inference, plus postprocessing. The
50 ms camera cadence therefore had insufficient margin. USB exchange includes
transfer and inference; HUD work overlaps inference, and loop time can include
idle waiting. Do not add separate maxima or treat Mac blocking send time as
compute time. These are observations, not an A/B performance measurement.

## Paired transport correction

The existing Carrot protocol-2 host supports exact N16 output projection and
lossless integer navigation pixels. Adapt those contracts to a separately
negotiated protocol-3 **Mac** extension, implemented over official Jetlink
0.8.12's Swift Session/StateLoop. This is an optional Carrot extension, not an
upstream 0.8.12 feature.

Both peers must explicitly exchange `carrot_mac_n16_transport_v1` with the exact
existing descriptor, model SHA and canonical spec SHA. Different models/specs,
other hosts, unmodified/older Apps and new HELLOs retain/reset the original
full protocol. No protocol version change or silent flag activation.

For this exact model, canonical float32 map pixels 0..255 are transported as
uint8 and expanded to the **same float32 bits** before official staging.
Fractional, negative-zero or out-of-range pixels keep the original packet.
The frame payload becomes 458996 rather than 655604 bytes (headers of the
outer transport and any USB padding are excluded).

The engine still executes the full graph, retains all recurrent feedback and
validates every driving output. Only a successful, explicitly requested reply
is shortened to the existing 2066-float driving prefix, which includes pose,
plan, lane/edge, lead, desire and action outputs. Hidden/map/navigation feature
feedback remains host-side. A NaN in an omitted output remains an error.
Reply payload is 8284 rather than 74340 bytes before telemetry/outer framing.
`SEND_RAW_PRED` continues to request full output. No camera/pose/comm validity,
frame-drop thresholds, model weights or control logic is changed.

## HUD alignment

The Mac helper separately restores the actual model path on the left and
retains the official mapsd PNG on the right. A GPS road-center polyline cannot
be assumed to coincide with the vehicle's lane and must not replace model_path.
No arbitrary centering, GPS offset adjustment, or smoothing of model controls.

## Validation and limits

Python tests cover protocol 2/3 legacy compatibility, exact model pinning,
map-bit reconstruction and fallback, full/compact/full transitions, response
corruption, parser equivalence and recurrent feedback. The paired Swift tests
exercise HELLO revocation, truncated/unnegotiated packets before queue reset,
full/compact/full output, input reconstruction and omitted non-finite outputs.
Official tiny queued/stateful CPU inference tests are also required by the Mac
installer before installing the App.

These checks prove contract preservation and reduced bytes, not a particular
millisecond improvement or a cure for all three alerts. Verification on the
same Mac/C4/model must confirm `active=true`, `execution.compact_reply=true`,
actual timing/drop counts and pose/service validity. Keep warnings visible.
The Mac installer bundles App/supervisor/model-path updates with backups and
rollback; it does not install the paired C4 commit or switch the device branch.
