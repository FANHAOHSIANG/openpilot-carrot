"""C4 boot: catch importable but unusable aiohttp/serial before daemons launch."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from openpilot.system.manager import runtime_service_audit as audit

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("name,expected", [
  ("aiohttp", ["WSMsgType", "ClientSession", "Application", "WebSocketResponse", "run_app"]),
  ("serial", ["Serial", "VTIMESerial", "serial_for_url"]),
])
def test_strict_service_api_contract(name, expected):
  assert [attr for _module, attr in audit.REQUIRED_APIS[name]] == expected


def test_missing_aiohttp_websocket_api_detected(monkeypatch):
  def broken_import(name):
    if name == "aiohttp":
      return SimpleNamespace(__file__=None, __version__=None)
    if name == "aiohttp.web":
      raise ModuleNotFoundError("aiohttp.web missing")
    raise AssertionError(name)

  monkeypatch.setattr(audit.importlib, "import_module", broken_import)
  result = audit.diagnose("aiohttp")
  assert any("WSMsgType" in e for e in result["errors"])
  assert any("aiohttp.web import failed" in e for e in result["errors"])
  assert any("no concrete package __file__" in e for e in result["errors"])
  with pytest.raises(RuntimeError, match="aiohttp invalid"):
    audit.check_or_raise("aiohttp")


def test_importable_serial_without_serial_constructor_detected(monkeypatch):
  monkeypatch.setattr(audit.importlib, "import_module",
                      lambda name: SimpleNamespace(__file__="/data/openpilot/pydeps/serial/__init__.py"))
  result = audit.diagnose("serial")
  assert any("serial missing Serial" in e for e in result["errors"])
  assert any("serial missing VTIMESerial" in e for e in result["errors"])


@pytest.mark.parametrize("name", ["aiohttp", "serial"])
def test_valid_service_apis(monkeypatch, name):
  def valid_import(module_name):
    attrs = dict(__file__=f"/data/openpilot/pydeps/{module_name.replace('.', '/')}/__init__.py",
                 __version__="0.0")
    for module, attr in audit.REQUIRED_APIS[name]:
      if module == module_name:
        attrs[attr] = object()
    return SimpleNamespace(**attrs)

  monkeypatch.setattr(audit.importlib, "import_module", valid_import)
  assert audit.diagnose(name)["errors"] == []
  audit.check_or_raise(name)


def test_audit_report_separates_broken_packages(monkeypatch, tmp_path):
  monkeypatch.setattr(audit, "diagnose", lambda name: {
    "name": name, "origin": f"/mock/{name}", "version": None,
    "errors": ["bad"] if name == "serial" else [], "repair": audit.OFFLINE_WHEELS[name],
  })
  report = tmp_path / "c4-runtime-service-audit.json"
  assert audit.run_all(report) == 1
  data = json.loads(report.read_text())
  assert not data["ok"]
  assert [p["name"] for p in data["packages"]] == ["aiohttp", "serial"]


@pytest.mark.parametrize("wheel_prefix,required", [
  ("aiohttp-3.13.3-", ("aiohttp/__init__.py", "aiohttp/web.py")),
  ("pyserial-3.5-", ("serial/__init__.py", "serial/serialposix.py")),
])
def test_offline_wheels_have_actual_service_implementation(wheel_prefix, required):
  wheels = list((ROOT / "third_party/wheels").glob(wheel_prefix + "*.whl"))
  assert wheels, f"No offline wheel: {wheel_prefix}"
  with ZipFile(wheels[0]) as archive:
    names = archive.namelist()
    for target in required:
      assert any(name.endswith(target) for name in names), (
        f"{wheels[0].name} does not include {target}"
      )


def test_startup_checks_apis_not_plain_import():
  launcher = (ROOT / "launch_chffrplus.sh").read_text(encoding="utf-8")
  assert "audit.check_or_raise('aiohttp')" in launcher
  assert "audit.check_or_raise('serial')" in launcher
  assert '"aiohttp==3.13.3" 1 1' in launcher
  assert '"pyserial==3.5" 1' in launcher
  assert "c4-runtime-service-audit.json" in launcher
  assert 'ensure_python_package aiohttp aiohttp' not in launcher
  assert 'ensure_python_package serial pyserial' not in launcher
  assert launcher.index("audit.check_or_raise('aiohttp')") < launcher.index("run_startup_command bootstrap_runtime_dependencies")
