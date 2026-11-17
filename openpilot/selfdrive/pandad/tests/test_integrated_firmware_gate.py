"""Exercise the production startup signature gate with an entirely fake USB device."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import pytest


@pytest.mark.parametrize('initial,after,accepted', [(b'old', b'old', False), (b'old', b'new', True), (b'new', b'new', True)])
def test_mismatched_safety_firmware_cannot_finish_startup(initial, after, accepted):
  path = Path('openpilot/selfdrive/pandad/pandad.py')
  node = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'flash_panda')
  class FakePanda:
    bootstub = False
    closed = False
    flashed = False
    signature = initial
    def __init__(self, serial): pass
    def get_version(self): return 'offline-fixture'
    def get_signature(self): return self.signature
    def is_internal(self): return False
    def flash(self, fn): self.flashed = True; self.signature = after
    def close(self): self.closed = True
  device = FakePanda('fixture')
  namespace = dict(Panda=lambda serial: device, Params=object, PandaProtocolMismatch=RuntimeError,
                   get_firmware_path=lambda *a: '/offline/fixture.bin.signed', get_expected_signature=lambda *a: b'new',
                   cloudlog=NS(info=lambda *a: None, warning=lambda *a: None))
  exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
  if accepted:
    assert namespace['flash_panda']('fixture', object()) is device
    assert not device.closed
  else:
    with pytest.raises(AssertionError): namespace['flash_panda']('fixture', object())
    assert device.closed
  assert device.flashed is (initial != b'new')
