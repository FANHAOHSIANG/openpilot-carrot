"""Avoid C4 recovery loops from a shadowed or incomplete libjpeg module."""
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[3]


def test_launcher_checks_real_native_libjpeg_files_not_import_alone():
  launch = (ROOT / "launch_chffrplus.sh").read_text(encoding="utf-8")
  assert "assert os.path.isfile(os.path.join(libjpeg.INCLUDE_DIR, 'jpeglib.h'))" in launch
  assert "assert os.path.isfile(os.path.join(libjpeg.LIB_DIR, 'libjpeg.a'))" in launch
  assert "ensure_python_package" in launch
  assert '--no-index --no-deps --find-links "$wheel_dir"' in launch
  assert '--target "$PYDEPS" --upgrade' in launch


def test_bundled_offline_libjpeg_wheel_contains_expected_headers_and_archive():
  wheels = sorted((ROOT / "third_party/wheels").glob("libjpeg-*.whl"))
  assert wheels, "Bundled offline libjpeg wheel missing; C4 cannot repair when offline"
  with ZipFile(wheels[0]) as wheel:
    entries = set(wheel.namelist())
    # AGNOS-targeted wheels may carry the module under .data/purelib;
    # pip relocates it to the import root when installing into pydeps.
    init_path = next((name for name in entries if name.endswith("libjpeg/__init__.py")), None)
    assert init_path is not None
    prefix = init_path[:-len("libjpeg/__init__.py")]
    init = wheel.read(init_path).decode("utf-8")
    assert "INCLUDE_DIR" in init
    assert "LIB_DIR" in init
    assert f"{prefix}libjpeg/install/include/jpeglib.h" in entries
    assert f"{prefix}libjpeg/install/lib/libjpeg.a" in entries
