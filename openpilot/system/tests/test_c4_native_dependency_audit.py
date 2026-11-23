"""Cover the entire C4 native build dependency contract, not one missing lib."""
import ast
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from openpilot.system.manager import native_dependency_audit as audit


ROOT = Path(__file__).resolve().parents[3]


def test_matches_entire_sconstruct_vendor_package_list():
  scons = ast.parse((ROOT / "SConstruct").read_text(encoding="utf-8"))
  packages = next(
    ast.literal_eval(node.value)
    for node in scons.body if isinstance(node, ast.Assign)
    for target in node.targets if isinstance(target, ast.Name) and target.id == "pkg_names"
  )
  assert tuple(packages) == audit.SCONS_PACKAGES
  assert audit.required_packages(c4=True, extras=False) == tuple(
    package for package in packages if package not in ("bzip2", "libyuv")
  )
  assert audit.required_packages(c4=True, extras=True)[-1] == "catch2"


def test_detects_incomplete_native_module_and_preserves_origin(monkeypatch, tmp_path):
  broken = SimpleNamespace(__file__=str(tmp_path / "acados" / "__init__.py"),
                           INCLUDE_DIR=str(tmp_path / "invalid-include"))
  monkeypatch.setattr(audit.importlib, "import_module", lambda name: broken)
  report = audit.diagnose_one("acados")
  assert report["origin"] == broken.__file__
  assert "missing LIB_DIR attribute" in report["errors"]
  assert any("INCLUDE_DIR directory absent" in err for err in report["errors"])
  assert any("TERA_PATH file absent" in err for err in report["errors"])
  assert report["wheel"] == "comma-deps-acados==0.2.2.post103"
  with pytest.raises(RuntimeError, match="acados invalid"):
    audit.check_or_raise("acados")


def test_detects_incomplete_libjpeg_even_when_it_imports(monkeypatch, tmp_path):
  (tmp_path / "include").mkdir()
  (tmp_path / "lib").mkdir()
  broken = SimpleNamespace(__file__=str(tmp_path / "libjpeg" / "__init__.py"),
                           INCLUDE_DIR=str(tmp_path / "include"),
                           LIB_DIR=str(tmp_path / "lib"))
  monkeypatch.setattr(audit.importlib, "import_module", lambda name: broken)
  report = audit.diagnose_one("libjpeg")
  assert "native asset absent: INCLUDE_DIR/jpeglib.h" in report["errors"]
  assert "native asset absent: LIB_DIR/libjpeg.a" in report["errors"]


def test_malformed_import_report_does_not_crash_preflight(monkeypatch):
  def fail(_):
    raise ImportError("AGNOS wrapper unavailable")
  monkeypatch.setattr(audit.importlib, "import_module", fail)
  report = audit.diagnose_one("ffmpeg")
  assert report["errors"] == ["import failed: ImportError: AGNOS wrapper unavailable"]
  assert report["origin"] is None
  assert report["wheel"] is None


def test_full_preflight_reports_all_modules_without_writing_over_user_settings(monkeypatch, tmp_path):
  monkeypatch.setattr(audit, "required_packages", lambda **_: ("acados", "ffmpeg"))
  monkeypatch.setattr(audit, "diagnose_one", lambda name: {
    "name": name, "origin": "/tmp/native", "errors": [] if name == "ffmpeg" else ["bad include"],
    "wheel": audit.LOCAL_WHEEL_PACKAGES.get(name),
  })
  monkeypatch.setattr(audit, "diagnose_cffi", lambda: {"name": "cffi", "origin": "/tmp/native", "backend_origin": "/tmp/native", "version": "2.0.0", "backend_version": "2.0.0", "errors": [], "wheel": "cffi==2.0.0"})
  report = tmp_path / "c4-native-dependency-audit.json"
  assert audit.run_all(c4=True, extras=False, report_path=report) == 1
  import json
  result = json.loads(report.read_text(encoding="utf-8"))
  assert result["ok"] is False
  assert len(result["packages"]) == 3
  assert result["packages"][-1]["name"] == "cffi"


@pytest.mark.parametrize("package,prefix,required", [
  ("acados", "comma_deps_acados-",
   ("acados/__init__.py", "acados/install/include/acados_c/ocp_nlp_interface.h",
    "acados/install/include/blasfeo/include/blasfeo.h",
    "acados/install/include/hpipm/include/hpipm_common.h")),
  ("eigen", "eigen-", ("eigen/__init__.py",)),
  ("libjpeg", "libjpeg-", ("libjpeg/__init__.py", "libjpeg/install/include/jpeglib.h",
                          "libjpeg/install/lib/libjpeg.a")),
  ("json11", "comma_deps_json11-", ("json11/__init__.py",)),
  ("catch2", "comma_deps_catch2-", ("catch2/__init__.py",)),
])
def test_all_bundled_native_wheels_have_required_build_assets(package, prefix, required):
  directory = ROOT / "third_party" / "wheels"
  archives = list(directory.glob(f"{prefix}*.whl"))
  assert archives, f"Missing offline wheel for {package}"
  with ZipFile(archives[0]) as z:
    files = z.namelist()
    for suffix in required:
      assert any(name.endswith(suffix) for name in files), (
        f"{package} wheel lacks {suffix}; cannot repair C4 offline"
      )
    init = next(name for name in files if name.endswith(required[0]))
    source = z.read(init).decode("utf-8")
    assert "INCLUDE_DIR" in source, f"{package} wheel does not expose INCLUDE_DIR"
    assert "LIB_DIR" in source, f"{package} wheel does not expose LIB_DIR"
    if package == "acados":
      for attr in ("DIR", "TEMPLATE_DIR", "TERA_PATH"):
        assert attr in source


def test_bootstrap_checks_full_registry_before_first_scons():
  launch = (ROOT / "launch_chffrplus.sh").read_text(encoding="utf-8")
  assert 'for native_pkg in acados eigen libjpeg json11' in launch
  assert "python3 -m openpilot.system.manager.native_dependency_audit" in launch
  assert "/data/c4-native-dependency-audit.json" in launch
  assert launch.index("run_startup_command bootstrap_runtime_dependencies") < launch.index(
    'run_startup_command bash "$DIR/scripts/ensure_params_build.sh"'
  )
