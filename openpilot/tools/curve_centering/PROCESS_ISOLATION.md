# Isolated controlsd shadow observer, 2026-11-18

Historical isolation qualification report at a7c66231. Its measurements and
limitations remain. The later owner-requested default-on behavior and logging
verification supersede the default-off decision below: see [DEFAULT_SHADOW.md](DEFAULT_SHADOW.md).

The actual opt-in `Controls` constructor now starts a separate spawned process,
replacing the analysis thread. The existing post-control observation point is
unchanged. No candidate result returns to controlsd and no actuator calculation,
CAN protection, steering limit, parameter, manager entry or default is changed.
`CURVE_CENTERING_SHADOW=1` remains an explicit constructor-time opt-in; unset or
any other value disables it on the next process start. This delivers executable
desktop shadow observation, not candidate vehicle control or default-on C4 use.

## Transport and failure behavior

The control side reads scalar values and sends one 128-byte AF_UNIX datagram with
`setblocking(False)`. It does not traverse geometry, serialize whole messages,
run an analysis thread, wait for space or join a child. The socket send buffer is
requested as 1024 bytes (the OS may round it); it is bounded, not a four-frame
queue contract. A full buffer drops the new sample and increments generation.
After a two-second startup grace, 200 ms of continuous full-buffer observations
closes the transport and signals child termination. A broken peer fails closed.
These limits bound work/retention, not OS scheduling or syscall execution time.

The child independently subscribes to modelV2 and lateralPlan. It caches at most
64 entries per service, drains at most 32 messages per service per refresh and
at most eight telemetry packets per iteration, retaining the newest packet.
It refreshes sources both before and after waiting for telemetry. It requires
exact timestamps of the sources actually consumed by controlsd and exact
plan.modelMonoTime matching. Missing, invalid or mutated sources never fall back
to the latest model. Sequence/generation gaps reset candidate stability. Scalar
telemetry includes the actual LaC active flag separately from requested latActive.
Both pre-analysis and post-analysis age are limited to 200 ms; expired work cannot
report a candidate. Existing geometry, mode, driver, saturation and quality gates
are retained. Two seconds without packets exits the worker.

Close signals termination without waiting in controlsd. There is no automatic
restart after observer failure: the existing controlsd handler removes the failed
monitor. Benchmark recreation is explicitly test-only. Child diagnostics use the
existing cloudlog event `curve_centering_shadow` at most once per second, now with
`mode=process_shadow_only`, `vehicle_output=false`, observation age, worker wall/CPU,
sequence/generation and baseline/policy/history differences. They are not actuator
commands. Normal log collection is required to retain cloudlog; this patch adds
no persistent file or web dashboard. The desktop benchmark separately saves
synthetic per-frame metrics to its requested output directory.

## Reproduce without a vehicle

Requires the native desktop dependencies described in VALIDATION and PROCESS_BENCH.
Use a new Params root, msgq prefix and output directory for every trial:

```sh
OPENPILOT_PREFIX=pr52synthetic-example PARAMS_ROOT=/tmp/pr52-example-params \
  PYTHONPATH="$PWD" python -m openpilot.tools.curve_centering.process_bench \
  --output /tmp/pr52-example --seconds 40 --mode on --backend process \
  --load-location worker
python -m openpilot.tools.curve_centering.process_bench_summary \
  /tmp/pr52-example --output /tmp/pr52-example-summary.json
```

The benchmark enables shadow only in its isolated synthetic controlsd process.
Use `--mode off` for baseline, `--backend thread` for the retained historical
implementation, and `--stall-seconds 1` for sustained backpressure. It refuses
non-PC hardware, reused Params roots/output directories or a non-test IPC prefix.
Files are child.json (control measurements), worker.jsonl (synthetic analysis),
receiver.json and stderr.txt. It cleans its own IPC namespace. No panda/card/CAN
consumer, vehicle or private log is used. Receiver polling is 10 ms; input-to-
receiver latency includes collector scheduling. Native VM/torque/long controllers,
Params and IPC execute, but this is not a complete vehicle stack. There is no C4
CPU affinity/FIFO scheduling, camera/model load, thermal load or disk log service.

## Measurements and retained failures

Aggregate evidence: [process-isolation-20261118.json](process-isolation-20261118.json).
Five 40-second trials ran off/thread/process/process/thread. Each enabled trial
injects 30 ms of Python analysis work per worker sample during seconds 12–16,
60 ms sleeps during 20–24, close at 28, explicit recreation at 32 and a worker
exception at 36. The historical six-trial experiment in PROCESS_BENCH is retained;
it injected contention in the control process and is a different protocol.

| Four-second analysis-load window | Old thread (two trials) | New process (two trials) |
| --- | --- | --- |
| Control publications | 130 / 128 | 400 / 400 |
| Maximum publication interval, ms | 56.403 / 50.670 | 12.361 / 12.200 |
| Intervals above 15 ms | 125 / 126 | 0 / 0 |

This supports removing the shared-GIL coupling, not a hard deadline claim.
Nominal publication maxima were 15.983 ms with shadow off, 14.376/14.722 ms with
the old thread, and **23.402/14.587 ms** with the new process. New-process capture
peaked at **2.431 ms**, worse than the old thread's 1.083 ms in these trials.
New-process recreation and exception windows reached **28.559 and 30.907 ms**.
The historical 13.255 ms capture spike remains evidence; it is not erased.

The new process dropped 18/19 startup samples and cumulative 63/68 samples by the
end of the short-overflow recovery phase. It resumed positive shadow comparisons
(179/190 steps) after that transient. Explicit close calls took 0.097/0.082 ms;
workers were first observed stopped about 8.82/8.86 ms later. Worker exceptions
removed monitors at the next sampled control iterations, about 11.40/10.58 ms
from injection. All workers stopped by test completion, with no partial JSONL.
Deterministic tests compare all CarControl fields and state across 300 steps per
mode; asynchronous full-process runs are not command-for-command A/B inputs.

A separate one-second stall removed the monitor at t=20.276 s, after buffer fill
and the persistent-full threshold. The four-second stall window still published
400 controls but had a **33.519 ms maximum interval**. The observer stayed absent
until explicit benchmark recreation; that recreation produced 159 positive shadow
steps. This verifies fail-closed observation, not zero performance impact.

The final 12-second run verifies the final actual-LaC flag and observation-age
payload: nominal 600/600 positive shadow comparisons, zero unmatched nominal
sources, no worker failure; nominal max publication interval 11.872 ms, capture
0.728 ms and observation age 1.441 ms. Startup dropped 29 samples and warmup worker
wall time peaked at 14.778 ms. It does not repeat the 40-second fault protocol;
those runs preceded only the explicit LaC activity/age-report additions.

An initial instrumented prototype processed no positive candidate because source
refresh happened only before its wait. Refreshing after the wait fixed recurring
missing-exact-source abstention; exact matching was not relaxed. An earlier
benchmark monkeypatch missed the constructor's local import; it was corrected
before the five reported trials. Neither prototype is counted as a successful
candidate test.

## Qualification still missing

Default remains off. Desktop improvement does not qualify C4 scheduling, startup,
thermal/resource contention, sustained operation or end-to-end vehicle timing.
The original C candidate's 33/96 regressions, 24/96 assumed-margin failures,
0.8670168 m spatial exit counterexample against assumed 0.85 m and 212 historical
smoothing residual steps remain. R is offline-only and has additional full-domain
failures. No thresholds or negative cases were removed. Geometry is still
same-model evidence, not independent vehicle/road truth. Private raw-log replay
remains unavailable; the denied download was not retried. No vehicle deployment,
actuation qualification or road-safety claim is made.
