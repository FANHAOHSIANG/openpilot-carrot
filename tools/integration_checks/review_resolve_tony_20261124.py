"""Exact, fail-closed one-shot semantic resolver for pinned Tony f8517762.

Only runs in an isolated GitHub Actions merge worktree after git-ort reports
precisely the reviewed 12 conflict files. Vehicle-control conflict decisions
are explicit and preserve both sets of guards. Never call on a live C4.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

PATTERN = re.compile(r"(?ms)^<<<<<<< HEAD\n(.*?)^=======\n(.*?)^>>>>>>> [^\n]+\n")

ROOT = pathlib.Path(".")
EXPECTED = {
  "opendbc_repo/opendbc/car/car.capnp": 1,
  "opendbc_repo/opendbc/car/hyundai/carcontroller.py": 1,
  "opendbc_repo/opendbc/car/hyundai/hyundaicanfd.py": 4,
  "opendbc_repo/opendbc/car/hyundai/tests/test_ccnc_cluster.py": 1,
  "openpilot/selfdrive/car/cruise.py": 1,
  "openpilot/selfdrive/car/hyundai_spas.py": 1,
  "openpilot/selfdrive/car/tests/test_hyundai_spas.py": 1,
  "openpilot/selfdrive/carrot/web/cockpit.html": 1,
  "openpilot/selfdrive/carrot/web/docs/settings/Settings-Catalog.json": 3,
  "openpilot/selfdrive/carrot/web/generated/asset-manifest.json": 1,
  "openpilot/selfdrive/carrot/web/js/generated/cockpit.js": 1,
  "openpilot/selfdrive/controls/lib/longitudinal_planner.py": 1,
}


def require(test: bool, reason: str) -> None:
  if not test:
    raise AssertionError(reason)


def resolve(path: str, index: int, ours: str, theirs: str) -> str:
  if path.endswith("/car/car.capnp"):
    require("lightingStateValid @120" in ours and "speedLimitClusterKph @123" in ours,
            "Schema: fused deployed wire IDs were modified")
    require("turnLampState @119" in theirs and "enum TurnLampState" in theirs,
            "Schema: unexpected Tony field block")
    new = theirs[theirs.index("  turnLampState"):]
    for old, new_tag in (
        ("turnLampState @119", "turnLampState @124"),
        ("displayRearLeftDistance @120", "displayRearLeftDistance @125"),
        ("displayRearLeftLateral @121", "displayRearLeftLateral @126"),
        ("displayRearRightDistance @122", "displayRearRightDistance @127"),
        ("displayRearRightLateral @123", "displayRearRightLateral @128"),
    ):
      require(old in new, f"Schema: missing {old}")
      new = new.replace(old, new_tag)
    return ours.rstrip() + "\n" + new

  if path.endswith("/hyundai/carcontroller.py"):
    require("now_nanos=now_nanos" in ours and "show_stock_signs=self.show_stock_signs" in theirs,
            "Controller: unexpected stock sign argument")
    return theirs

  if path.endswith("/hyundai/hyundaicanfd.py"):
    if index == 0:
      require("now_nanos=None" in ours and "show_stock_signs=True" in theirs,
              "Hyundai signature unexpected")
      return theirs.replace("now_nanos=0", "now_nanos=None")
    if index == 1:
      require("lat_icon" in ours and "if not (ev6_display and stock)" in theirs,
              "Hyundai stock icon conflict unexpected")
      require('values["FCA_ALT_ICON"] = 0' in ours, "FCA icon missing")
      preserved = ours.replace(
          '        values["FCA_ALT_ICON"] = 0\n',
          '        stock = _fresh_ev6_cluster_rx(getattr(CS, "cp_cam", None), "ADRV_0x161", 0x161) if ev6_display else {}\n'
          '        if not (ev6_display and stock):\n'
          '          values["FCA_ALT_ICON"] = 0\n')
      return preserved
    if index == 2:
      require("ENGAGE_POPUP" in ours and "_suppress_trailer_mode_warning" in ours,
              "Fused CCNC alerts missing")
      require("_suppress_trailer_mode_warning" in theirs,
              "Tony CCNC alerts block unexpectedly changed")
      return ours.replace(
          "        _suppress_trailer_mode_warning(values, CS)",
          "        if not (ev6_display and stock):\n          _suppress_trailer_mode_warning(values, CS)")
    if index == 3:
      require("HDP_ICON_BIT" in ours and "fresh_signs" in theirs and "show_stock_signs" in theirs,
              "CCNC sign/raw HDP conflict unexpected")
      prefix = theirs.split('        ret.append(packer.make_can_msg("CCNC_0x162"', 1)[0]
      require("now_nanos - parser.ts_nanos" in prefix, "Stock sign freshness check missing")
      prefix = prefix.replace(
          "stock and 0 <= now_nanos - parser.ts_nanos",
          "stock and now_nanos is not None and 0 <= now_nanos - parser.ts_nanos")
      return prefix + ours
    raise AssertionError("Unexpected Hyundai CCNC hunk index")

  if path.endswith("/hyundai/tests/test_ccnc_cluster.py"):
    require("test_hdp_gap_bars_and_popup" in ours and "test_unseen_lane_lines_send_14" in ours,
            "Previous Hyundai regression tests unexpectedly absent")
    require("test_pv5" in theirs or "test_ev6" in theirs,
            "New Tony cluster tests unexpectedly absent")
    return ours.rstrip() + "\n\n" + theirs.lstrip()

  if path.endswith("/car/cruise.py"):
    require("explicit=False" in ours and "selected_speed = v_cruise_kph" in ours,
            "Fused driver cruise ceiling missing")
    require("self.vision_only" in theirs, "Tony vision-only cruise gate missing")
    return ours.replace(
        "    selected_speed = v_cruise_kph\n",
        "    selected_speed = v_cruise_kph\n"
        "    if getattr(self, 'vision_only', False):\n"
        "      return v_cruise_kph\n", 1)

  if path.endswith("/car/hyundai_spas.py"):
    require("self.trial_rejection" in ours and "model_specific_trial" in ours,
            "Fused SPAS diagnostic and non-PE gate missing")
    require("web_request" in theirs and "self.web_active = web_request" in theirs,
            "Tony parked Web SPAS admission missing")
    start = ours.index("        if parked and")
    require("        accepted = parked" in theirs, "Tony SPAS accepted gate missing")
    return ours[:start] + theirs

  if path.endswith("/car/tests/test_hyundai_spas.py"):
    require("test_non_pe_trial_rejection_explained" in ours and
            "test_web_lamp_tap_deadline_and_driver_override" in theirs,
            "SPAS regressions missing from either source")
    return ours.rstrip() + "\n\n" + theirs.lstrip()

  if path.endswith("/web/cockpit.html"):
    require('id="scene-surface"' in ours and 'id="sceneTurn"' in theirs,
            "Cockpit scene-turn anchor missing")
    require('id="visionInstruments"' in ours, "Fused cockpit instrumentation missing")
    return ours.replace('<div id="scene-surface">', '<div id="scene-surface"><output id="sceneTurn" class="cockpit-turn-cue" hidden></output>', 1)

  if path.endswith("/web/docs/settings/Settings-Catalog.json"):
    # Generated from merged source once the source merge finishes.
    return ours

  if path.endswith("/web/generated/asset-manifest.json") or path.endswith("/web/js/generated/cockpit.js"):
    # Never hand-edit build outputs. Regenerate together from merged sources.
    return ours

  if path.endswith("/controls/lib/longitudinal_planner.py"):
    require("InputValidityDiagnostics" in ours and "modelV2" in theirs,
            "Cannot preserve telemetry and Tony model input validity")
    return (
      "    required = ['carState', 'controlsState', 'selfdriveState']\n"
      "    if self.CP.openpilotLongitudinalControl:\n"
      "      required.append('modelV2')\n"
      "    plan_send.valid = sm.all_checks(service_list=required)\n"
      "    if not hasattr(self, '_validity_diagnostics'):\n"
      "      self._validity_diagnostics = InputValidityDiagnostics('longitudinalPlan', cloudlog.event)\n"
      "    self._validity_diagnostics.record(sm, plan_send.valid, required)\n"
    )

  raise AssertionError(f"Unreviewed conflict: {path}")


def main() -> None:
  conflicts = subprocess.check_output(
      ["git", "diff", "--name-only", "--diff-filter=U"], text=True).splitlines()
  require(set(conflicts) == set(EXPECTED),
          f"Unexpected conflict set, refusing: missing {set(EXPECTED)-set(conflicts)}, "
          f"extra {set(conflicts)-set(EXPECTED)}")
  for file in conflicts:
    data = (ROOT / file).read_text(encoding="utf-8")
    matches = list(PATTERN.finditer(data))
    require(len(matches) == EXPECTED[file],
            f"Unexpected hunk count in {file}: {len(matches)} != {EXPECTED[file]}")
    resolved = PATTERN.sub(
        lambda match, path=file, counter=iter(range(len(matches))):
          resolve(path, next(counter), match.group(1), match.group(2)),
        data)
    require("<<<<<<< HEAD" not in resolved and ">>>>>>> " not in resolved,
            f"Unresolved markers in {file}")
    if file.endswith(".py"):
      compile(resolved, file, "exec")
    (ROOT / file).write_text(resolved, encoding="utf-8")
    subprocess.run(["git", "add", "--", file], check=True)
    print(f"Resolved {file}: {len(matches)} reviewed hunks", flush=True)
  remaining = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=U"], text=True).strip()
  require(not remaining, f"Unexpected unresolved merge entries: {remaining}")


if __name__ == "__main__":
  main()
