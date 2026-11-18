# Shadow scheduler inheritance correction

A reported photo shows Camera Frame Rate Low. The photo does not establish the
installed commit, onset, reboot outcome, camera service frequencies, resource
load or root cause. No device was accessed or restarted for this investigation.

Code inspection found a concrete resource-isolation defect in 062e8159:
controlsd.main sets FIFO53 and core6 before creating Controls. multiprocessing
spawn does not clear OS scheduling/affinity; its Python bootstrap can also import
the controlsd main module before worker_main. The observer never demoted itself.
This repository's camerad runs at normal scheduling on core6. A runnable FIFO53
observer can therefore delay camera work. Earlier PC benchmarks skip device
realtime/affinity setup and did not test this condition. Separate processes alone
were insufficient isolation. This is a plausible camera-alert contributor, not
proof of the particular photo's cause.

The observer now uses os.posix_spawn with an explicit SCHED_OTHER/priority0
scheduler applied before exec. There is no multiprocessing helper or controlsd
main-module re-import. The bootstrap lowers nice priority to19 and, on /TICI,
sets affinity to background cores0–3 before importing observer/native analysis.
The worker checks its scheduler and device affinity; failures exit observation,
with no inherited-realtime fallback. The existing bounded transport detects a
broken peer and removes the observer. Parent control/camera scheduling is unchanged.
Default-on recording and explicit environment0 opt-out remain as requested.

The child lifecycle uses nonblocking waitpid for status and SIGTERM for close;
there is no join in the control path. Idle timeout also exits an orphan after
telemetry stops. Benchmark hooks are passed as local JSON configuration, forbidden
on /TICI, and use an atomically replaced epoch file; no pickle or callable from
untrusted input is loaded. The production launch has no benchmark configuration.

## Evidence

- A disposable desktop parent switched to SCHED_BATCH and one CPU; old spawn
  inherited policy3/priority0/nice0 and affinity. The new scheduler contract
  produced policy0/priority0/nice19. This avoids introducing FIFO workloads on the
  shared desktop and does not claim an on-device FIFO53 reproduction.
- Tests verify the atomic spawn scheduler argument, background-affinity/priority
  bootstrap before observer import, and fail-closed spawn failure. Focused suite:
  208 passed, three configuration warnings; Ruff passed after correcting a
  string-concatenation style failure.
- Forty-second full synthetic controlsd/default-on run with actual logmessaged:
  24 saved observer events, 11 nonzero comparisons, two stop events. Every recorded
  observer scheduler was SCHED_OTHER(0), nice19. One-second worker stall and worker
  exception yielded transport_TimeoutError and transport_ConnectionRefusedError;
  both workers stopped. Max publication interval26.664ms is retained as a negative,
  alongside the older33.519ms and13.255ms timing findings. These are not bounds.
- C4 background affinity0–3, camera/frame-rate recovery, thermal/resource load and
  actual camera/vehicle data have NOT been tested. Original candidate/geometric
  failures are unchanged. No actuator output or camera alert threshold changed.

Aggregate: [SCHEDULER_FIX_VALIDATION.json](SCHEDULER_FIX_VALIDATION.json).
Diagnostics now include worker_scheduler, worker_nice and worker_affinity so a
record can establish which scheduling configuration actually ran. The local
exporter preserves those fields without outer device/host context. An absent
record cannot prove that the observer ran or that the camera issue is resolved.
