"""Catch cross-environment cffi Python/backend skew before SCons Params build.

On the affected C4: cffi Python 2.1.1 from /usr/local/venv was paired with
_cffi_backend 2.0.0 from /data/openpilot/pydeps. cffi.FFI() then raised
"Version mismatch" even after every native vendor package was valid.
"""
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from openpilot.system.manager import native_dependency_audit as audit

ROOT = Path(__file__).resolve().parents[3]


def _fake_import(name, python_version="2.1.1", backend_version="2.0.0", ffi=None):
  assert name in ("cffi", "_cffi_backend")
  if name == "cffi":
    return SimpleNamespace(__file__="/usr/local/venv/lib/python3.12/site-packages/cffi/__init__.py",
                           __version__=python_version, FFI=ffi or (lambda: object()))
  return SimpleNamespace(__file__="/data/openpilot/pydeps/_cffi_backend.cpython-312-aarch64-linux-gnu.so",
                         __version__=backend_version)


def test_mixed_cffi_versions_detected_and_diagnosed(monkeypatch):
  monkeypatch.setattr(audit.importlib, "import_module", _fake_import)
  info = audit.diagnose_cffi()
  assert info["version"] == "2.1.1"
  assert info["backend_version"] == "2.0.0"
  assert info["origin"].startswith("/usr/local/venv/")
  assert info["backend_origin"].startswith("/data/openpilot/pydeps/")
  assert any("version mismatch" in error for error in info["errors"])
  assert info["wheel"] == "cffi==2.0.0"
  with pytest.raises(RuntimeError, match="cffi invalid"):
    audit.check_or_raise("cffi")


def test_matching_cffi_version_must_also_construct_ffi(monkeypatch):
  exercised = []
  def loader(name):
    return _fake_import(name, python_version="2.0.0", backend_version="2.0.0",
                        ffi=lambda: exercised.append(True))
  monkeypatch.setattr(audit.importlib, "import_module", loader)
  assert audit.diagnose_cffi()["errors"] == []
  assert exercised == [True]
  audit.check_or_raise("cffi")
  assert exercised == [True, True]


def test_backend_import_or_ffi_failure_is_fatal(monkeypatch):
  def loader(name):
    if name == "_cffi_backend":
      raise ImportError("cannot load extension")
    return _fake_import(name, python_version="2.0.0", backend_version="2.0.0")
  monkeypatch.setattr(audit.importlib, "import_module", loader)
  assert any("ImportError" in x for x in audit.diagnose_cffi()["errors"])

  def broken_ffi():
    raise RuntimeError("native ABI is unusable")
  monkeypatch.setattr(audit.importlib, "import_module",
                      lambda name: _fake_import(name, python_version="2.0.0",
                                                backend_version="2.0.0", ffi=broken_ffi))
  assert any("native ABI is unusable" in x for x in audit.diagnose_cffi()["errors"])


def test_offline_cffi_wheel_contains_both_python_and_native_halves():
  wheels = list((ROOT / "third_party/wheels").glob("cffi-2.0.0-*aarch64.whl"))
  assert wheels, "Need pinned ARM64 cffi 2.0.0 wheel for C4 offline recovery"
  with ZipFile(wheels[0]) as wheel:
    names = wheel.namelist()
    assert any(p.endswith("cffi/__init__.py") for p in names)
    assert any("_cffi_backend" in p and p.endswith(".so") for p in names)
  pycparser = list((ROOT / "third_party/wheels").glob("pycparser-3.0-*.whl"))
  assert pycparser, "Need bundled pycparser to initialize native cffi.FFI() offline"
  with ZipFile(pycparser[0]) as wheel:
    assert any(p.endswith("pycparser/__init__.py") for p in wheel.namelist())


def test_cffi_repair_is_prior_to_python_runtime_and_scons():
  launcher = (ROOT / "launch_chffrplus.sh").read_text(encoding="utf-8")
  block = launcher.split("function bootstrap_runtime_dependencies {", 1)[1]
  assert 'native_dependency_audit --check cffi' in block
  assert 'cffi==2.0.0' in block
  assert 'pycparser==3.0' in block
  assert '--no-index --no-deps' in block
  assert 'install_runtime_python_package' in block
  assert block.index("native_dependency_audit --check cffi") < block.index("ensure_python_package serial")
  assert launcher.index("run_startup_command bootstrap_runtime_dependencies") < launcher.index(
    'run_startup_command bash "$DIR/scripts/ensure_params_build.sh"')
