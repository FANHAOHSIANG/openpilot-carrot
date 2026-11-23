"""Check the native model bundle's graph inputs before C4 launch builds it.

The fused Cheddar ONNX did not define 'desire_pulse'. Restoring only the
Tony compiler therefore crashed SCons with KeyError before the C4 could boot.
"""
import hashlib
from pathlib import Path

from openpilot.selfdrive.modeld.get_model_metadata import make_metadata_dict


MODEL = Path(__file__).parents[1] / "models/driving_supercombo.onnx"
TONY_NATIVE_GIT_BLOB_SHA1 = "1aac351ca371f1f68c565470e07a530c7a65f185"
TONY_NATIVE_SIZE = 60792584


def test_internal_default_matches_tony_native_model_blob():
  assert MODEL.stat().st_size == TONY_NATIVE_SIZE
  digest = hashlib.sha1(f"blob {TONY_NATIVE_SIZE}\\0".encode())
  with MODEL.open("rb") as stream:
    for piece in iter(lambda: stream.read(1024 * 1024), b""):
      digest.update(piece)
  assert digest.hexdigest() == TONY_NATIVE_GIT_BLOB_SHA1


def test_native_model_has_required_compiler_inputs():
  # Use the same ONNX metadata parser as the native SCons build. A source-only
  # test that checks compile_modeld.py will not catch an incompatible model file.
  metadata = make_metadata_dict(MODEL)
  required = {"img", "big_img", "desire_pulse", "traffic_convention", "action_t", "features_buffer"}
  assert required <= metadata["input_shapes"].keys(), (
    f"Native compiler inputs absent: {sorted(required - metadata['input_shapes'].keys())}"
  )
  assert metadata["input_shapes"]["desire_pulse"][2] == 8
  assert metadata["output_slices"]
