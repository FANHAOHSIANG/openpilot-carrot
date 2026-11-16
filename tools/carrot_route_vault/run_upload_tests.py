"""Test the real upload stack without importing unrelated vehicle IPC features."""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
name = 'openpilot.selfdrive.carrot.server.features'
package = types.ModuleType(name)
package.__path__ = [str(ROOT / 'openpilot/selfdrive/carrot/server/features')]
sys.modules[name] = package

if __name__ == '__main__':
  import pytest
  raise SystemExit(pytest.main(['--noconftest', '-c', '/dev/null', '-q',
                               str(ROOT / 'tools/carrot_route_vault/tests/test_server.py'),
                               str(ROOT / 'openpilot/selfdrive/carrot/server/tests/test_web_upload.py')]))
