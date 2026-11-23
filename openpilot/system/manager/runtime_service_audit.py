"""Preflight import APIs used by long-running Carrot services.

A successful 'import aiohttp' or 'import serial' is insufficient when pydeps
contains incomplete/shadowing package directories. Keep this module stdlib-only
so it can run before the full openpilot runtime or SCons is loaded.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys


REQUIRED_APIS = {
  "aiohttp": (
    ("aiohttp", "WSMsgType"),
    ("aiohttp", "ClientSession"),
    ("aiohttp.web", "Application"),
    ("aiohttp.web", "WebSocketResponse"),
    ("aiohttp.web", "run_app"),
  ),
  "serial": (
    ("serial", "Serial"),
    ("serial", "VTIMESerial"),
    ("serial", "serial_for_url"),
  ),
}

OFFLINE_WHEELS = {
  "aiohttp": "aiohttp==3.13.3",
  "serial": "pyserial==3.5",
}


def diagnose(name: str) -> dict:
  if name not in REQUIRED_APIS:
    raise ValueError(f"Unknown runtime package: {name}")
  result = {"name": name, "origin": None, "version": None,
            "errors": [], "repair": OFFLINE_WHEELS[name]}
  for module_name, attr in REQUIRED_APIS[name]:
    try:
      module = importlib.import_module(module_name)
      if module_name == name and result["origin"] is None:
        result["origin"] = getattr(module, "__file__", None)
        result["version"] = getattr(module, "__version__", None)
      if not hasattr(module, attr):
        result["errors"].append(f"{module_name} missing {attr}")
    except Exception as exc:
      result["errors"].append(f"{module_name} import failed: {type(exc).__name__}: {exc}")
  if result["origin"] is None:
    result["errors"].append(f"{name} has no concrete package __file__ (namespace/shadowed import)")
  return result


def check_or_raise(name: str) -> None:
  result = diagnose(name)
  if result["errors"]:
    raise RuntimeError(
      f"Carrot service dependency {name} invalid at {result['origin']}: " +
      "; ".join(result["errors"]))


def run_all(report: Path | None = None) -> int:
  results = [diagnose(name) for name in REQUIRED_APIS]
  ok = not any(result["errors"] for result in results)
  for result in results:
    print(f"[carrot-service-deps] {'PASS' if not result['errors'] else 'FAIL'}: "
          f"{result['name']} ({result['origin']})", flush=True)
    for error in result["errors"]:
      print(f"  - {error}", flush=True)
  if report is not None:
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"ok": ok, "packages": results}, indent=2) + "\n",
                      encoding="utf-8")
  print("CARROT SERVICE DEPS PASSED" if ok else "CARROT SERVICE DEPS FAILED", flush=True)
  return 0 if ok else 1


if __name__ == "__main__":
  args = sys.argv[1:]
  if len(args) == 2 and args[0] == "--check":
    check_or_raise(args[1])
  elif not args:
    raise SystemExit(run_all())
  elif len(args) == 2 and args[0] == "--report":
    raise SystemExit(run_all(Path(args[1])))
  else:
    raise SystemExit("Usage: python3 -m openpilot.system.manager.runtime_service_audit "
                     "[--check aiohttp|serial | --report PATH]")
