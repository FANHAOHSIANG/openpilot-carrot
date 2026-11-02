"""CPU-only regression checks of JoiningModel.run control flow.

Extract the real class without importing C4 GPU/runtime dependencies. These
checks do not validate recurrent model numerics, estimator replay, or hardware.
Run: python3 tools/jetlink/test_prepare_only_contract.py
"""
import ast
import os
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'openpilot/selfdrive/modeld/jetlink/model.py'


class PrepareOnlyContract(unittest.TestCase):
  def setUp(self):
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'JoiningModel')
    self.parse = Mock(return_value={'prediction': 123})
    self.fault = Mock()
    scope = dict(time=time, os=os, fill_inputs=Mock(), parse_outputs=self.parse,
                 model_name=lambda spec: 'test', FAULT=self.fault)
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(SOURCE), 'exec'), scope)
    model_class = scope['JoiningModel']
    self.model = m = model_class.__new__(model_class)
    m.preparation = None
    m.ready = m.join_allowed = m.active = True
    m.connection = None
    m.small_runs = 3
    m.frame = 0
    m.next_join = m.next_status = m.last_slow_log = 0
    m.source_sof = 123
    m.reset = True
    m.views = {'prev_feat': [0, 0]}
    m.prev_desire = []
    m.packed = []
    m.spec = SimpleNamespace(output_slices={'hidden_state': slice(0, 2)}, sha256='test')
    m.parser = object()
    m.warp = Mock(return_value='images')
    m.warp.timings = (0, 0, 0)
    m.client = Mock(deferred_nav=False)
    m.client.infer.return_value = [7, 8]
    m.client.timings = (0, 0, 0)
    m.small = Mock()
    m.small.run.return_value = None
    self.client = m.client
    self.log = ModuleType('openpilot.common.swaglog')
    self.log.cloudlog = Mock()
    self.modules = patch.dict(sys.modules, {'openpilot.common.swaglog': self.log})
    self.modules.start()
    self.addCleanup(self.modules.stop)

  def run_frame(self, prepare_only):
    return self.model.run({}, {}, {}, prepare_only)

  def test_normal_frame_publishes(self):
    self.assertEqual(self.run_frame(False), {'prediction': 123})
    self.assertEqual(self.model.views['prev_feat'], [7, 8])
    self.assertFalse(self.model.reset)

  def test_recovery_advances_state_without_publishing_then_resumes(self):
    self.assertIsNone(self.run_frame(True))
    self.client.infer.assert_called_once()
    self.parse.assert_called_once()
    self.assertEqual(self.model.views['prev_feat'], [7, 8])
    self.assertFalse(self.model.reset)
    self.assertEqual(self.run_frame(False), {'prediction': 123})
    self.assertEqual(self.client.infer.call_count, 2)
    self.assertEqual(self.client.infer.call_args.args[2:4], (2, False))

  def test_consecutive_recovery_frames_never_fabricate_output(self):
    for _ in range(5):
      self.assertIsNone(self.run_frame(True))
    self.assertEqual(self.client.infer.call_count, 5)
    self.assertEqual(self.parse.call_count, 5)

  def test_remote_failure_still_records_fault_and_falls_back(self):
    self.client.infer.side_effect = RuntimeError('USB failed')
    self.assertIsNone(self.run_frame(True))
    self.client.close.assert_called_once()
    self.fault.write_text.assert_called_once()
    self.model.small.reset.assert_called_once()
    self.model.small.run.assert_called_once_with({}, {}, {}, True)
    self.assertIsNone(self.model.client)
    self.assertFalse(self.model.active)


if __name__ == '__main__':
  unittest.main()
