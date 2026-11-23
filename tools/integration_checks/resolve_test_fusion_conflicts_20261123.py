#!/usr/bin/env python3
"""Resolve the known Nov 23 Test->fusion conflicts in an isolated candidate only.

Fail closed for any unexpected conflict. Never invoke on a deployed branch.
"""
import re
import subprocess
from pathlib import Path

EXPECTED = {
  "AGENTS.md",
  "openpilot/selfdrive/car/tests/test_hyundai_kick.py",
  "openpilot/selfdrive/carrot/web/generated/asset-manifest.json",
  "openpilot/selfdrive/carrot/web/js/generated/tools.js",
  "openpilot/selfdrive/modeld/SConscript",
  "tools/docs/wiki_settings/tests/test_ci_check.py",
  "tools/docs/wiki_settings/tests/test_generate.py",
}

def git(*args):
  return subprocess.check_output(["git", *args], text=True)

actual = set(git("diff", "--name-only", "--diff-filter=U").splitlines())
if actual != EXPECTED:
  raise SystemExit(f"Refusing unexpected conflict set: missing={EXPECTED-actual}, extra={actual-EXPECTED}")

RX = re.compile(r"(?ms)^<<<<<<< HEAD\n(?P<ours>.*?)^\|\|\|\|\|\|\| [^\n]*\n(?P<base>.*?)^=======\n(?P<theirs>.*?)^>>>>>>> [^\n]*\n")

def resolve_hunks(name, fn, expected):
  p = Path(name)
  source = p.read_text(encoding="utf-8")
  count = [0]
  def apply(m):
    count[0] += 1
    return fn(m.group("ours"), m.group("theirs"))
  dest = RX.sub(apply, source)
  if count[0] != expected or any(marker in dest for marker in ("<<<<<<< HEAD", ">>>>>>> origin/", "||||||| merged common ancestors")):
    raise SystemExit(f"{name}: unsafe conflict structure ({count[0]} hunks)")
  p.write_text(dest, encoding="utf-8")
  print(f"Resolved {name}: {count[0]} hunks")

def merge_kick(ours, theirs):
  key = "spas_signals=NS(enabled=False, diagnostics=lambda *args:{}), native_voice_indicator=None"
  if ours.count(key) != 1 or "spas_diagnostic_at=float('inf')" not in theirs:
    raise SystemExit("Hyundai Kick fixture changed; manual review needed")
  return ours.replace(key, "spas_signals=NS(enabled=False, diagnostics=lambda *args:{}), spas_diagnostic_at=float('inf'), native_voice_indicator=None")

resolve_hunks("openpilot/selfdrive/car/tests/test_hyundai_kick.py", merge_kick, 1)
# The Test branch restores the owner-preferred CD210 compilation path. Keep all
# non-conflicting SConscript edits and remove only the old Cheddar override.
resolve_hunks("openpilot/selfdrive/modeld/SConscript", lambda ours, theirs: theirs, 1)
resolve_hunks("tools/docs/wiki_settings/tests/test_ci_check.py", lambda ours, theirs: ours, 1)
resolve_hunks("tools/docs/wiki_settings/tests/test_generate.py", lambda ours, theirs: ours, 4)

# Both historical AGENTS notes are retained, but do not touch runtime logic.
ours = git("show", ":2:AGENTS.md")
theirs = git("show", ":3:AGENTS.md")
Path("AGENTS.md").write_text(ours.rstrip() + "\n\n## Imported long-term Test notes — 2026-11-23\n\n" + theirs.rstrip() + "\n", encoding="utf-8")

# Bundled web assets must be rebuilt from merged sources, never merged by line.
subprocess.run(["git", "checkout", "--ours", "--",
  "openpilot/selfdrive/carrot/web/generated/asset-manifest.json",
  "openpilot/selfdrive/carrot/web/js/generated/tools.js"], check=True)

if git("diff", "--name-only", "--diff-filter=U").strip():
  raise SystemExit("Unresolved Git index entries remain")
print("All expected conflict markers reconciled; regenerate assets and test before commit.")
