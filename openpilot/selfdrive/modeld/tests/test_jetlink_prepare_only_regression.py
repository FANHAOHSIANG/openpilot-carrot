"""Exercise the real JoiningModel.run with mocked hardware and transport.

No vehicle processes, Params, camera devices or USB are started. Import mocks are
scoped to each test and restored afterwards, so collection cannot poison other
openpilot tests. This is not a hardware timing or vehicle safety certification.
"""
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

MODEL_PATH = Path(__file__).resolve().parents[1] / 'jetlink' / 'model.py'


def fake_module(name, **attributes):
  module = ModuleType(name)
  module.__dict__.update(attributes)
  return module


class JetlinkPrepareOnlyRegressionTest(unittest.TestCase):
  def setUp(self):
    self.parse = Mock(side_effect=lambda parser, spec, result: {'prediction': result.copy()})
    self.fill = Mock()
    self.fault = Mock()
    self.logger = Mock()
    modules = {
      'openpilot.selfdrive.modeld.jetlink.link': fake_module(
        'link', ClientConnection=Mock(), SPEC=SimpleNamespace(), FAULT=self.fault, state=Mock(), peer_ready=Mock(return_value=True)),
      'openpilot.selfdrive.modeld.jetlink.prepare': fake_module('prepare', WarpPreparation=Mock()),
      'openpilot.selfdrive.modeld.jetlink.contracts': fake_module(
        'contracts', model_name=Mock(return_value='test-model'), parse_outputs=self.parse),
      'openpilot.selfdrive.modeld.jetlink.inputs': fake_module('inputs', fill_inputs=self.fill),
      'openpilot.selfdrive.modeld.model_join': fake_module('model_join', may_join=Mock()),
      'openpilot.common.swaglog': fake_module('swaglog', cloudlog=self.logger),
    }
    imports = patch.dict(sys.modules, modules)
    imports.start()
    self.addCleanup(imports.stop)
    env = patch.dict(os.environ, {'SEND_RAW_PRED': '', 'JETLINK_CPU_OVERLAP': '1'})
    env.start()
    self.addCleanup(env.stop)

    spec = importlib.util.spec_from_file_location('_jetlink_prepare_only_under_test', MODEL_PATH)
    self.module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(self.module)
    # Replace the module's clock reference, not the global time module.
    self.module.time = SimpleNamespace(monotonic=Mock(return_value=100.0))
    self.model = self.module.JoiningModel.__new__(self.module.JoiningModel)
    m = self.model
    m.small = Mock()
    m.small.run.return_value = {'local': True}
    m.preparation = m.connection = None
    m.ready = m.join_allowed = m.active = True
    m.prepare_allowed = True
    m.preparation_failed = False
    m.small_runs = 3
    m.frame = 0
    m.reset = False
    m.next_join = m.next_status = m.last_slow_log = 0.0
    m.error = ''
    m.source_sof = 1_234_567_890
    m.spec = SimpleNamespace(output_slices={'hidden_state': slice(0, 2)}, sha256='test-sha')
    m.parser = object()
    m.packed = np.zeros(4, dtype=np.float32)
    m.views = {'prev_feat': np.zeros(2, dtype=np.float32)}
    m.prev_desire = np.zeros(8, dtype=np.float32)
    self.sequence = 0
    self.client = Mock()
    self.client.deferred_nav = False
    self.client.timings = (1000, 0, 1000)
    self.client.image_buffer.return_value = np.zeros(8, dtype=np.uint8)
    self.client.infer.side_effect = self.infer
    m.client = self.client
    m.warp = Mock(side_effect=self.warp)
    m.warp.timings = (0.001, 0.001, 0.001)

  def infer(self, *args, **kwargs):
    self.sequence += 1
    return np.array([self.sequence, self.sequence + 10, self.sequence + 20], dtype=np.float32)

  @staticmethod
  def warp(bufs, transforms, *, prepare=None, output_buffer=None):
    if prepare is not None:
      prepare()
    return output_buffer

  def run_frame(self, prepare_only=False):
    return self.model.run({'img': object(), 'big_img': object()}, {}, {}, prepare_only)

  def test_normal_frame_returns_current_prediction(self):
    result = self.run_frame()
    np.testing.assert_array_equal(result['prediction'], [1, 11, 21])
    self.assertEqual(self.parse.call_count, 1)
    self.model.small.run.assert_not_called()

  def test_gap_updates_remote_and_parser_history_without_publishable_output(self):
    self.assertIsNone(self.run_frame(True))
    self.client.infer.assert_called_once()
    self.parse.assert_called_once()
    self.fill.assert_called_once()
    np.testing.assert_array_equal(self.model.views['prev_feat'], [1, 11])
    self.model.small.run.assert_not_called()
    self.client.close.assert_not_called()
    self.fault.write_text.assert_not_called()

  def test_next_contiguous_frame_resumes_with_fresh_prediction(self):
    first = self.run_frame()
    gap = self.run_frame(True)
    next_frame = self.run_frame()
    self.assertIsNone(gap)
    np.testing.assert_array_equal(first['prediction'], [1, 11, 21])
    np.testing.assert_array_equal(next_frame['prediction'], [3, 13, 23])
    self.assertIsNot(first, next_frame)
    self.assertEqual(self.parse.call_count, 3)
    self.assertEqual(self.model.frame, 3)

  def test_consecutive_gaps_never_repeat_or_fabricate_a_prediction(self):
    for _ in range(40):
      self.assertIsNone(self.run_frame(True))
    self.assertEqual(self.client.infer.call_count, 40)
    self.assertEqual(self.parse.call_count, 40)
    np.testing.assert_array_equal(self.model.views['prev_feat'], [40, 50])
    # No fake result can refresh the caller's publication/freshness clocks.
    self.model.small.run.assert_not_called()

  def test_raw_prediction_option_does_not_publish_recovery_frame(self):
    with patch.dict(os.environ, {'SEND_RAW_PRED': '1'}):
      self.assertIsNone(self.run_frame(True))
    self.assertEqual(self.parse.call_count, 1)

  def test_normal_raw_prediction_is_preserved(self):
    with patch.dict(os.environ, {'SEND_RAW_PRED': '1'}):
      result = self.run_frame()
    np.testing.assert_array_equal(result['raw_pred'], [1, 11, 21])
    self.assertIsNot(result['prediction'], result['raw_pred'])

  def test_models_without_external_hidden_state_still_advance_parser(self):
    self.model.views = {}
    self.assertIsNone(self.run_frame(True))
    self.parse.assert_called_once()

  def test_transport_reset_and_timestamp_contract_unchanged(self):
    self.model.reset = True
    self.assertIsNone(self.run_frame(True))
    self.run_frame()
    first, second = self.client.infer.call_args_list
    self.assertTrue(first.args[3])
    self.assertFalse(second.args[3])
    self.assertEqual(first.kwargs['source_sof'], 1_234_567_890)
    self.assertFalse(self.model.reset)

  def test_nav_metadata_and_lossless_transport_call_are_preserved(self):
    self.client.deferred_nav = True
    nav = {'route': 'test'}
    self.model.set_nav_metadata(nav)
    result = self.run_frame()
    self.assertIsNotNone(result)
    self.assertIs(self.client.infer.call_args.kwargs['nav_metadata'], nav)
    self.assertIs(self.client.infer.call_args.args[0], self.client.image_buffer.return_value)
    self.assertIs(self.client.infer.call_args.args[1], self.model.packed)

  def test_remote_timeout_keeps_fault_signal_and_local_fallback(self):
    self.client.infer.side_effect = TimeoutError('USB timeout')
    self.assertEqual(self.run_frame(), {'local': True})
    self.fault.write_text.assert_called_once()
    self.client.close.assert_called_once()
    self.model.small.reset.assert_called_once()
    self.assertFalse(self.model.active)
    self.assertIsNone(self.model.client)
    self.assertFalse(self.model.small.run.call_args.args[3])

  def test_remote_timeout_during_gap_passes_prepare_only_to_fallback(self):
    self.client.infer.side_effect = TimeoutError('USB timeout')
    self.model.small.run.return_value = None
    self.assertIsNone(self.run_frame(True))
    self.fault.write_text.assert_called_once()
    self.model.small.reset.assert_called_once()
    self.assertTrue(self.model.small.run.call_args.args[3])

  def test_parser_failure_keeps_fault_and_fallback(self):
    self.parse.side_effect = ValueError('bad model result')
    self.assertEqual(self.run_frame(), {'local': True})
    self.fault.write_text.assert_called_once()
    self.model.small.reset.assert_called_once()

  def test_local_prepare_only_is_unchanged(self):
    self.model.client = None
    self.model.ready = False
    self.model.small.run.return_value = None
    self.assertIsNone(self.run_frame(True))
    self.assertEqual(self.model.small_runs, 3)
    self.assertTrue(self.model.small.run.call_args.args[3])
    self.parse.assert_not_called()

  def test_local_normal_inference_is_unchanged(self):
    self.model.client = None
    self.model.ready = False
    self.assertEqual(self.run_frame(), {'local': True})
    self.assertEqual(self.model.small_runs, 4)
    self.assertFalse(self.model.small.run.call_args.args[3])
    self.parse.assert_not_called()

  def test_cpu_overlap_off_still_updates_inputs_on_recovery(self):
    with patch.dict(os.environ, {'JETLINK_CPU_OVERLAP': '0'}):
      self.assertIsNone(self.run_frame(True))
    self.fill.assert_called_once()
    self.assertIsNone(self.model.warp.call_args.kwargs['prepare'])


if __name__ == '__main__':
  unittest.main()
