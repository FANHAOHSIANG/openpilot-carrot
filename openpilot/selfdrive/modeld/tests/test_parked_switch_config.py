import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('parked_config', ROOT / 'openpilot/tools/jetlink/configure_parked_switch.py')
CONFIG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIG)


class ConfigurationTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.params = self.root / 'params'; self.params.mkdir()
    (self.params / 'IsOffroad').write_bytes(b'1')
    (self.params / 'IsOnroad').write_bytes(b'0')
    self.flag = self.root / 'flag'

  def configure(self, enabled):
    CONFIG.configure(enabled, params=self.params, flag=self.flag, root=ROOT)

  def test_enable_runs_cpu_checks_then_writes_marker(self):
    with patch.object(CONFIG.subprocess, 'run') as run:
      self.configure(True)
      self.assertTrue(run.called)
      self.assertEqual(self.flag.read_bytes(), b'1\n')

  def test_disable_removes_marker_without_changing_source(self):
    self.flag.write_bytes(b'1\n')
    with patch.object(CONFIG.subprocess, 'run') as run:
      self.configure(False)
      self.assertFalse(run.called)
      self.assertFalse(self.flag.exists())

  def test_onroad_rejects_enable_and_disable(self):
    for enabled in (True, False):
      self.flag.write_bytes(b'previous')
      (self.params / 'IsOnroad').write_bytes(b'1')
      with self.assertRaises(ValueError): self.configure(enabled)
      self.assertEqual(self.flag.read_bytes(), b'previous')

  def test_missing_params_do_not_enable(self):
    (self.params / 'IsOffroad').unlink()
    with self.assertRaises(OSError): self.configure(True)
    self.assertFalse(self.flag.exists())

  def test_cpu_failure_does_not_enable(self):
    with patch.object(CONFIG.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'test')):
      with self.assertRaises(subprocess.CalledProcessError): self.configure(True)
    self.assertFalse(self.flag.exists())

  def test_offroad_lost_during_cpu_tests_does_not_enable(self):
    with patch.object(CONFIG, 'require_offroad', side_effect=[None, ValueError('onroad')]), \
         patch.object(CONFIG.subprocess, 'run'):
      with self.assertRaises(ValueError): self.configure(True)
    self.assertFalse(self.flag.exists())

  def test_offroad_lost_after_write_restores_previous_marker(self):
    self.flag.write_bytes(b'previous')
    with patch.object(CONFIG, 'require_offroad', side_effect=[None, None, ValueError('onroad')]), \
         patch.object(CONFIG.subprocess, 'run'):
      with self.assertRaises(ValueError): self.configure(True)
    self.assertEqual(self.flag.read_bytes(), b'previous')

  def test_offroad_lost_after_disable_restores_marker(self):
    self.flag.write_bytes(b'previous')
    with patch.object(CONFIG, 'require_offroad', side_effect=[None, None, ValueError('onroad')]):
      with self.assertRaises(ValueError): self.configure(False)
    self.assertEqual(self.flag.read_bytes(), b'previous')


if __name__ == '__main__':
  unittest.main(verbosity=2)
