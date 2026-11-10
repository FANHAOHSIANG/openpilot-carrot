from types import SimpleNamespace

import numpy as np
import pytest

from openpilot.tools.clearance_shadow.perception import detections_from_result, project_detection
from openpilot.tools.clearance_shadow.policy import OffsetObserver
from openpilot.tools.clearance_shadow.tests.test_policy import run, truck


def camera():
  # u = 500 + 1000*y/x, v = 300 + 1500/x; image is 1000x700.
  h = np.array([[500, 1000, 0], [300, 0, 1500], [1, 0, 0]], dtype=float)
  return {'valid': True, 'image_size': [1000, 700], 'ground_from_image': np.linalg.inv(h).tolist()}


def detection():
  return {'label': 'truck', 'confidence': 0.9, 'track_id': 3, 'box': [700, 200, 900, 400]}


def test_positive_y_is_right_and_geometry_uncertainty_expands_box():
  out = project_detection(detection(), camera())
  assert out['geometry_valid']
  assert out['x_m'] == pytest.approx(15)
  assert out['y_min_m'] < 3 and out['y_max_m'] > 6


@pytest.mark.parametrize('box', [[700, 200, 999, 400], [0, 200, 900, 400], [700, 200, 900, 300],
                               [700, 200, 900, 699], [700, 200, float('nan'), 400], [900, 200, 700, 400]])
def test_truncation_horizon_and_bad_boxes_reject(box):
  assert not project_detection(dict(detection(), box=box), camera())['geometry_valid']


def test_missing_calibration_rejects():
  assert not project_detection(detection(), {'valid': False})['geometry_valid']
  assert not project_detection(detection(), dict(camera(), ground_from_image=[[0] * 3] * 3))['geometry_valid']


def test_model_metadata_names_used_instead_of_coco_ids():
  box = SimpleNamespace(cls=np.array(42), id=np.array(7), conf=np.array(0.9), xyxy=np.array([[1, 2, 3, 4]]))
  result = SimpleNamespace(names={42: 'bus'}, boxes=[box])
  out = detections_from_result(result)
  assert out[0]['label'] == 'bus' and out[0]['track_id'] == 7
  result.names = {42: 'traffic light'}
  assert detections_from_result(result) == []


def test_untracked_box_is_not_fabricated_as_track_zero():
  box = SimpleNamespace(cls=np.array(0), id=None, conf=np.array(0.9), xyxy=np.array([[1, 2, 3, 4]]))
  assert detections_from_result(SimpleNamespace(names={0: 'truck'}, boxes=[box]))[0]['track_id'] is None


@pytest.mark.parametrize(('raw', 'canonical'), [
  ('rider', 'person'), ('motor', 'motorcycle'), ('bike', 'bicycle'), ('train', 'train'),
  ('person', 'person'), ('motorcycle', 'motorcycle'), ('bicycle', 'bicycle'),
])
def test_bdd_and_coco_road_actor_names_are_retained(raw, canonical):
  box = SimpleNamespace(cls=np.array(3), id=np.array(7), conf=np.array(0.9), xyxy=np.array([[1, 2, 3, 4]]))
  detection = detections_from_result(SimpleNamespace(names={3: raw}, boxes=[box]))[0]
  assert detection['label'] == canonical
  assert detection['raw_label'] == raw


@pytest.mark.parametrize('raw', ['rider', 'motor', 'bike', 'train'])
def test_bdd_actor_on_opposite_side_blocks_candidate(raw):
  box = SimpleNamespace(cls=np.array(3), id=np.array(7), conf=np.array(0.9), xyxy=np.array([[1, 2, 3, 4]]))
  actor = detections_from_result(SimpleNamespace(names={3: raw}, boxes=[box]))[0]
  actor.update(x_m=12, y_min_m=-4.5, y_max_m=-2.1, geometry_valid=True)
  outcome = run(OffsetObserver(), [truck(), actor])[-1]
  assert outcome['reason'] == 'actors on both sides'
  assert outcome['candidate_offset_m'] == 0 and outcome['applied_offset_m'] == 0
