# Desktop full-process shadow timing, 2026-11-18

Decision: retain `CURVE_CENTERING_SHADOW` default OFF. The requested default-on
change is not supported by these measurements. No production control, limit,
startup, vehicle installation or base-branch change was made.

## What executed

Six independent desktop trials in off/on/on/off/off/on order, each with fresh
private Params and an isolated native msgq prefix. The child imports and runs the
actual `controlsd.main()`, `Controls.__init__`, update/state_control/publish/run,
actual VM/torque/long controllers and native Params/IPC. It receives synthetic
MOCK car parameters with explicitly synthetic torque tuning and generated service
messages. There is no panda, card, CAN consumer, manager, vehicle or raw-log input.
The benchmark wraps methods to measure time and inject observer faults; it does
not replace the control equations or IPC implementation. This is a full
**controlsd process** experiment, not a complete vehicle stack or physical plant.

The host is x86_64 with ordinary desktop scheduling; no C4 affinity/FIFO behavior
is reproduced. The input producer and receiver run in a second process. The
receiver polls at 10 ms, so its latency includes collector scheduling. Original
cloudlog IPC sends execute, but logmessaged/disk logging does not. Measurement
wrappers and retained in-memory samples add overhead. Runs do not have identical
message arrival schedules; do not claim command-by-command A/B equivalence here.
Separate deterministic state_control regressions cover that property.

## Measurements, including failures

All milliseconds below are observed maxima, not deadline guarantees. The original
13.255 ms capture-only spike remains retained in README/VALIDATION. These six
trials did not reproduce that capture spike; they do not invalidate it.

| Condition | Shadow off, three trials | Shadow on, three trials |
| --- | --- | --- |
| Nominal publication-interval maximum | 13.219 / 21.381 / 16.431 ms | 26.072 / 13.061 / 14.185 ms |
| Injected GIL-load publication maximum | 86.371 / 88.641 / 109.957 ms | 94.256 / 85.680 / 83.581 ms |
| Slow observer publication maximum | 14.516 / 13.940 / 11.797 ms | 16.748 / 34.673 / 18.860 ms |

The normal cycle is 10 ms. Both off and on trials overrun; therefore neither a
hard deadline guarantee nor an exclusively shadow-caused explanation follows.
In the first four trials nominal input-to-publication maxima were 4.785/12.340 ms
(off), 16.635/4.534 ms (on). Corresponding input-to-receiver maxima were
12.007/20.433 ms and 19.476/11.770 ms. Full per-phase distributions, counts above
10 and 15 ms, input pacing and receiver misses are in
[process-bench-20261118.json](process-bench-20261118.json).

Across on trials capture wall/CPU maxima were 2.572/2.211 ms. This identifies
bounded sample costs in this run only. Worker processing, scheduling, native
calls and other control work still share the interpreter/process. The publication
tails demonstrate why small capture percentiles cannot qualify default-on.

## Faults, stopping and recovery

- 0..6 s warmup; 6..12 nominal; 12..16 synthetic Python busy thread in the control
  process (both modes); 16..20 recovery; 20..24 an injected 60 ms sleep in observer
  processing (on only); 24..28 recovery; 28..32 closed observer; 32..36 recreated
  observer. The final pair continues to 40 s with an observer exception at 36 s.
- Slow-worker trials caused 116, 114 and 115 cumulative dropped captures. Queued
  generations invalidate and fresh evidence/warmup is required; nonzero candidate
  policy steps reappeared in each post-overflow window. No missing interval is
  counted as a successful observation.
- In the final on trial `close()` returned in 0.00675 ms. The first sampled
  publication with the worker thread stopped occurred 109.153 ms later. Closing
  does not synchronously join or cancel an already executing calculation. One
  worker completion may straddle the close boundary; do not equate close with an
  instantaneous cancellation of all computation.
- The benchmark explicitly recreates an observer at 32 s. That is a test-only
  action, not a UI/environment hot-toggle supported by production. Warmup and
  nonzero policy output reoccurred, still only in the observer.
- Injected worker RuntimeError at 36.010 s was recorded as `worker_RuntimeError`.
  The real state_control error path removed the monitor by the next sampled
  publication, 9.994 ms later. All worker threads stopped by trial termination.
  The 36..40 s window continued 401 publications, with a maximum interval of
  12.287 ms; the monitor was present for the first two boundary-window frames.
  There is no automatic restart following this failure.
- These are observation lifecycle results, not evidence of safe physical control
  handover. Existing candidate margin and withdrawal failures remain unchanged.

## Reproduction on an isolated desktop

Native dependencies and build prerequisites are described in VALIDATION. In
addition to params_pyx, build `msgq_repo/msgq/ipc_pyx.so` and
`msgq_repo/msgq/visionipc/visionipc_pyx.so` with SCons. Importing complete controlsd
also requires the repository's Python dependencies (this environment additionally
installed tqdm/scipy/cffi). Use the virtualenv and capnproto bin directories on
PATH, and absolute checkout PYTHONPATH when building. No vehicle deployment is
part of these commands.

Choose fresh names for output, Params and IPC prefix on every run:

```sh
OPENPILOT_PREFIX=pr52synthetic-example-off \
PARAMS_ROOT=/tmp/pr52-example-params-off \
python -m openpilot.tools.curve_centering.process_bench \
  --mode off --seconds 40 --output /tmp/pr52-example-off

OPENPILOT_PREFIX=pr52synthetic-example-on \
PARAMS_ROOT=/tmp/pr52-example-params-on \
python -m openpilot.tools.curve_centering.process_bench \
  --mode on --seconds 40 --output /tmp/pr52-example-on

python -m openpilot.tools.curve_centering.process_bench_summary \
  /tmp/pr52-example-off /tmp/pr52-example-on --output /tmp/pr52-example-summary.json
```

`--mode on` sets the environment only for the synthetic child. It does not enable
an existing controlsd or persist a setting. The tool refuses non-PC hardware,
non-isolated prefixes, non-scratch Params/output paths and reused trial paths.
Native IPC requires write access to its unique `/dev/shm/msgq_pr52synthetic-*`
directory; the final tool cleans its own directory after the child exits.
`child.json` contains instrumented publication/capture/worker results;
`receiver.json` contains producer/receiver times; `stderr.txt` captures failures.
No source/raw vehicle data is used. Example results are not road geometry truth.

Remaining default-on blockers: no qualified C4 end-to-end deadline/load evidence,
no hard time budget enforcement or proven isolation from the control process,
and only short synthetic desktop trials. A reactive disable after a slow capture
cannot undo that already-delayed publication. Keep explicit opt-in and default off.
