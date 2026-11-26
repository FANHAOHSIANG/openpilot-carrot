# GaodeLaneShadow (observation only)

This opt-in tool reads the existing modelV2 stream or rlog, extracts visual lane geometry at up to 5 Hz, and writes a new JSONL file. No control or planner modules are changed, no bus messages are published, no manager process is registered. Default driving behavior is unchanged. Use offline rlog replay first. Live capture is manual, only for stationary/controlled diagnostic use; the operator should not use the terminal while driving. A separate data alignment implementation is still required: raw Gaode coordinate data is not accepted. Map comparison is offline only and requires independently validated geometry, timestamps and local frame. No claimed NOO improvement. Synthetic tests provided; device runtime and performance remain unverified.

From repository root:
`python3 tools/carrot_navi_lab/gaode_lane_shadow.py --rlog /path/to/rlog.zst --out /tmp/gaode-vision.jsonl`
`python3 tools/carrot_navi_lab/gaode_lane_shadow.py --live --seconds 60 --out /tmp/gaode-vision-live.jsonl`

The C4 output does not automatically become an rlog entry. Export separately. Use unique output path; file creation refuses overwrite. Do not share raw logs publicly.
