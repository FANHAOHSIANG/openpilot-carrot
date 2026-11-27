# Lane-level navigation evidence — experimental
Read-only offline prototype. Not wired to live navigation or HUD. No steering, speed or lane-change commands.
The normalized input is an explicit integration contract, not a claimed Tencent wire format. An authorized source adapter must supply sessionId, routeId, routeEpoch, seq, monoMs and bind/snapshot/hide/end. Snapshot guide has count, flags and ageMs; HD has egoIndexRaw, physicalCount, laneId and ageMs. Missing fields clear instead of carrying forward. Source ages must be derived at source; receiver residence is measured with a local monotonic clock.
Guide icon count is not physical lane count. Raw ego index has unknown origin and never becomes an absolute index. C4 visibleCount is local visual candidates only; co-observation does not prove correspondence. All outputs are non-control.
Next: validate real recorded source frames and coordinate/index semantics, then connect a display-only adapter and calibrated HUD. No live provider access or road validation yet.
Run: node --test tests/lane-evidence.test.mjs
