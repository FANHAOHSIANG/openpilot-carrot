"""C4 native SCons dependency preflight.

Builds on AGNOS import vendor modules through PYTHONPATH. A successful import
is not enough: stale/namespace packages can lack INCLUDE_DIR or native assets,
causing repeated Params registry build failures. This module is intentionally
standalone (Python standard library only) and runs before any SCons build.
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCONS_PACKAGES = (
  "acados", "bzip2", "capnproto", "eigen", "ffmpeg", "json11",
  "libjpeg", "libyuv", "ncurses", "zeromq", "zstd",
)
LOCAL_WHEEL_PACKAGES = {
  "acados": "comma-deps-acados==0.2.2.post103",
  "eigen": "eigen",
  "libjpeg": "libjpeg",
  "json11": "comma-deps-json11==20170411.0.post103",
  "catch2": "comma-deps-catch2==2.13.10.post96",
  "cffi": "cffi==2.0.0",
}


def required_packages(*, c4: bool, extras: bool) -> tuple[str, ...]:
  names = [n for n in SCONS_PACKAGES if not (c4 and n in ("bzip2", "libyuv"))]
  if extras:
    names.append("catch2")
  return tuple(names)


def diagnose_one(name: str) -> dict:
  """Return module provenance, missing SCons attributes and missing assets."""
  result: dict = {"name": name, "origin": None, "errors": [], "wheel": LOCAL_WHEEL_PACKAGES.get(name)}
  try:
    module = importlib.import_module(name)
    result["origin"] = getattr(module, "__file__", None)
  except Exception as exc:
    result["errors"].append(f"import failed: {type(exc).__name__}: {exc}")
    return result

  for attr in ("INCLUDE_DIR", "LIB_DIR"):
    value = getattr(module, attr, None)
    if not isinstance(value, (str, os.PathLike)) or not value:
      result["errors"].append(f"missing {attr} attribute")
    elif not Path(value).is_dir():
      result["errors"].append(f"{attr} directory absent: {value}")

  if name == "acados":
    for attr, kind in (("DIR", "directory"), ("TEMPLATE_DIR", "directory"), ("TERA_PATH", "file")):
      value = getattr(module, attr, None)
      valid = bool(value) and (Path(value).is_dir() if kind == "directory" else Path(value).is_file())
      if not valid:
        result["errors"].append(f"{attr} {kind} absent: {value}")
    include = getattr(module, "INCLUDE_DIR", None)
    if include:
      for rel in ("acados_c/ocp_nlp_interface.h", "blasfeo/include/blasfeo.h", "hpipm/include/hpipm_common.h"):
        if not (Path(include) / rel).is_file():
          result["errors"].append(f"native header absent: {rel}")
    try:
      from acados.acados_template import AcadosOcpSolver  # noqa: F401
      from casadi import SX  # noqa: F401
    except Exception as exc:
      result["errors"].append(f"acados solver/casadi imports failed: {type(exc).__name__}: {exc}")
  elif name == "libjpeg":
    for attr, rel in (("INCLUDE_DIR", "jpeglib.h"), ("LIB_DIR", "libjpeg.a")):
      base = getattr(module, attr, None)
      if not base or not (Path(base) / rel).is_file():
        result["errors"].append(f"native asset absent: {attr}/{rel}")
  elif name == "eigen":
    base = getattr(module, "INCLUDE_DIR", None)
    if base and not any((Path(base) / path).is_file() for path in ("Eigen/Core", "eigen3/Eigen/Core")):
      result["errors"].append("Eigen/Core header absent")
  return result


def diagnose_cffi() -> dict:
  """Check that cffi Python sources and its native _cffi_backend agree.

  AGNOS may have cffi 2.1.1 in /usr/local/venv while an old cffi 2.0.0
  _cffi_backend remains in /data/openpilot/pydeps. An import of cffi alone
  succeeds, but constructing FFI then fails with "Version mismatch".
  """
  result: dict = {"name": "cffi", "origin": None, "backend_origin": None,
                  "version": None, "backend_version": None, "errors": [],
                  "wheel": LOCAL_WHEEL_PACKAGES["cffi"]}
  try:
    module = importlib.import_module("cffi")
    result["origin"] = getattr(module, "__file__", None)
    result["version"] = getattr(module, "__version__", None)
    backend = importlib.import_module("_cffi_backend")
    result["backend_origin"] = getattr(backend, "__file__", None)
    result["backend_version"] = getattr(backend, "__version__", None)
    if not result["version"] or not result["backend_version"]:
      result["errors"].append("cffi or _cffi_backend missing version metadata")
    elif result["version"] != result["backend_version"]:
      result["errors"].append(
        f"cffi version mismatch: Python {result['version']} vs native {result['backend_version']}")
    if not result["errors"]:
      # Exercise the real native binding; string-version comparison alone
      # cannot prove that the backend can actually be used by SCons.
      module.FFI()
  except Exception as exc:
    result["errors"].append(f"cffi FFI initialization failed: {type(exc).__name__}: {exc}")
  return result


def check_or_raise(name: str) -> None:
  result = diagnose_cffi() if name == "cffi" else diagnose_one(name)
  if result["errors"]:
    raise RuntimeError(
      f"C4 native dependency {name} invalid (origin={result['origin']}): " +
      "; ".join(result["errors"]))


def run_all(*, c4: bool = True, extras: bool | None = None, report_path: Path | None = None) -> int:
  if extras is None:
    extras = (ROOT / ".gitattributes").exists()
  results = [diagnose_one(name) for name in required_packages(c4=c4, extras=extras)]
  results.append(diagnose_cffi())  # Detect mixed system-venv/pydeps Python/native cffi ABI.
  ok = all(not row["errors"] for row in results)
  data = {
    "ok": ok, "platform": sys.platform, "c4": c4, "extras": extras,
    "packages": results,
  }
  for row in results:
    label = "OK" if not row["errors"] else "FAIL"
    print(f"[native-deps] {label}: {row['name']} | {row['origin'] or 'no module'}", flush=True)
    if row["name"] == "cffi":
      print(f"  Python version: {row['version']} | native version: {row['backend_version']}", flush=True)
      print(f"  Native backend: {row['backend_origin']}", flush=True)
    for error in row["errors"]:
      print(f"  - {error}", flush=True)
    if row["errors"] and row["wheel"]:
      print(f"  - bundled repair candidate: {row['wheel']}", flush=True)
  if report_path is not None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  print("[native-deps] All SCons dependencies valid" if ok else
        "[native-deps] Native dependency preflight failed; refusing Params SCons build",
        flush=True)
  return 0 if ok else 1


if __name__ == "__main__":
  args = sys.argv[1:]
  if len(args) == 2 and args[0] == "--check":
    check_or_raise(args[1])
  elif not args or (len(args) == 2 and args[0] == "--report"):
    path = Path(args[1]) if args else None
    raise SystemExit(run_all(c4=Path("/TICI").exists() or Path("/AGNOS").exists(), report_path=path))
  else:
    raise SystemExit("Usage: python3 -m openpilot.system.manager.native_dependency_audit [--check PACKAGE | --report FILE]")
