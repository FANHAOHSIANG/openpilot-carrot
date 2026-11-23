"""Regression guard for the C4 native model compile/runtime artifact ABI.

The Tony ModelState loader uses helpers.load_oob and direct run_policy /
per-camera warp keys. A separate Cheddar worker uses a different persistent-
buffer bundle and may not be substituted into the native default build.
"""
import ast
from pathlib import Path
import unittest


MODELD = Path(__file__).resolve().parents[1]
BUILD = MODELD / "SConscript"
RUNTIME = MODELD / "modeld.py"
COMPILER = MODELD / "compile_modeld.py"
LEGACY_SERIALIZER = MODELD / "helpers.py"


class TestInternalModelBuilderAbi(unittest.TestCase):
  def test_c4_internal_build_uses_matching_tony_compiler(self):
    builder = BUILD.read_text(encoding="utf-8")
    # Both native and optional GPU branches use the out-of-band native compiler.
    self.assertIn("python3 {modeld_dir}/compile_modeld.py", builder)
    self.assertIn("--frame-skip {frame_skip}", builder)
    self.assertIn("tinygrad_files + compile_modeld_script + driving_onnx_deps", builder)
    self.assertNotIn("cheddar_runtime.py", builder)

  def test_modelstate_reader_matches_compiler_format_and_keys(self):
    loader = RUNTIME.read_text(encoding="utf-8")
    compiler = COMPILER.read_text(encoding="utf-8")
    serializer = LEGACY_SERIALIZER.read_text(encoding="utf-8")
    self.assertIn("jits = load_oob(open_file_chunked(", loader)
    self.assertIn("self.run_policy = jits['run_policy']", loader)
    self.assertIn("self.warp = jits[(cam_w,cam_h)]", loader)
    self.assertIn("out['run_policy'] =", compiler)
    self.assertIn("out[(cam_w,cam_h)] =", compiler)
    self.assertIn("dump_oob(out, f)", compiler)
    self.assertIn("def load_oob(", serializer)
    self.assertIn("def dump_oob(", serializer)
    # Syntax-check without importing GPU runtime on a CI host.
    ast.parse(loader, filename=str(RUNTIME))
    ast.parse(compiler, filename=str(COMPILER))


if __name__ == "__main__":
  unittest.main()
