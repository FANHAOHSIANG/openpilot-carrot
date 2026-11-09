import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from openpilot.tools.clearance_shadow.export_rlog import export_events, latest_before
from openpilot.tools.clearance_shadow.policy import OffsetObserver
from openpilot.tools.clearance_shadow.run import evaluate
from openpilot.tools.clearance_shadow.tests.test_policy import scene, truck


def test_json_replay_end_to_end(tmp_path):
  rows = [{'video_index': i, 'snapshot': scene(i * 0.05), 'observations': [truck()], 'perception_valid': True} for i in range(100)]
  path = tmp_path / 'out.jsonl'
  result = evaluate(rows, path, OffsetObserver())
  assert result['frames'] == 100 and result['nonzero_candidate_frames'] > 0
  out = [json.loads(line) for line in path.read_text().splitlines()]
  assert out[-1]['candidate_offset_m'] == pytest.approx(-0.15)
  assert all(row['applied_offset_m'] == 0 and row['control_eligible'] is False for row in out)


def test_missing_detections_not_reused(tmp_path):
  rows = [{'video_index': i, 'snapshot': scene(i * 0.05), 'observations': [truck()], 'perception_valid': True} for i in range(100)]
  rows.append({'video_index': 100, 'snapshot': scene(5)})
  path = tmp_path / 'out.jsonl'
  evaluate(rows, path, OffsetObserver())
  last = json.loads(path.read_text().splitlines()[-1])
  assert last['reason'] == 'perception unavailable'
  assert last['target_offset_m'] == 0


def test_exporter_is_causal_and_expires_data():
  events = [SimpleNamespace(valid=True), SimpleNamespace(valid=True)]
  assert latest_before(events, [100, 200], 199, 100) is events[0]
  assert latest_before(events, [100, 200], 99, 100) is None
  assert latest_before(events, [100, 200], 301, 100) is None
  events[1].valid = False
  assert latest_before(events, [100, 200], 210, 100) is None


def test_duplicate_video_index_rejected(tmp_path):
  row = {'video_index': 0, 'snapshot': scene()}
  with pytest.raises(ValueError, match='unique'):
    evaluate([row, row], tmp_path / 'out.jsonl', OffsetObserver())


def index_event(segment, index, t):
  idx = SimpleNamespace(segmentNum=segment, segmentId=index, frameId=100 + index, timestampEof=t)
  return SimpleNamespace(valid=True, which=lambda: 'roadEncodeIdx', roadEncodeIdx=idx)


def test_export_uses_encoder_presentation_index_and_marks_missing_state(tmp_path):
  output = tmp_path / 'geometry.jsonl'
  summary = export_events([index_event(4, 2, 2000000000), index_event(4, 0, 1900000000)], output)
  rows = [json.loads(line) for line in output.read_text().splitlines()]
  assert [r['video_index'] for r in rows] == [0, 2]
  assert rows[0]['snapshot']['t'] == pytest.approx(1.9)
  assert summary['invalid_snapshots'] == 2
  assert all(not row['snapshot']['valid'] for row in rows)
  assert OffsetObserver().update(rows[0]['snapshot'])['reason'] == 'missing or stale modelV2'


@pytest.mark.parametrize('events', [[], [index_event(0, 0, 10), index_event(1, 0, 20)],
                                   [index_event(0, 0, 10), index_event(0, 0, 20)]])
def test_export_rejects_wrong_segment_inputs(events, tmp_path):
  with pytest.raises(ValueError):
    export_events(events, tmp_path / 'geometry.jsonl')


def test_observer_has_no_control_transport_or_runtime_integration():
  root = Path(__file__).resolve().parents[1]
  for path in root.glob('*.py'):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
      if isinstance(node, ast.Attribute):
        assert node.attr not in {'PubMaster', 'pub_sock', 'put_bool', 'put_int', 'apply_offset'}
      if isinstance(node, (ast.Import, ast.ImportFrom)):
        names = [n.name for n in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
        assert not any('controlsd' in name or 'lateral_planner' in name for name in names)
