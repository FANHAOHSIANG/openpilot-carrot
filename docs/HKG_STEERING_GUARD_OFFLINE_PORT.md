# HKG steering safety port — offline review only

Source: fusion `62a5fd51177688ce6251fbb58252cf8d5067da2e`. Independent Test baseline: `bea74346a56eb2eef11950eb4602189900f94fe3`.

This isolated branch stages the fusion Panda steering guard, TX/forwarding hooks, explicit vehicle flags, and matching native regression fixtures. The reserve module is present but is not connected to the independent Test controller; this branch must not be installed on C4 or used on public roads. Existing Test and fusion branches remain unchanged.

Acceptance: native compilation; production TX and forwarding checks; driver override, stale/invalid wheel data, request interruption and separate angle/torque authorization; existing B1 and vehicle-family regressions; controller-to-Panda parity; controlled bench/HIL verification. Do not merge on the strength of CI alone. Existing scoped HKG workflow intentionally requires unchanged Panda code; its scope must not be bypassed. Full controller integration and hardware compatibility are not established.
