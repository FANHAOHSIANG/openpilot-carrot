"""Compare with actual source helpers without importing a control process."""
import ast
import math
from pathlib import Path
import random

import numpy as np
import pytest
from openpilot.tools.curve_centering.model_baseline import model_step

ROOT = Path(__file__).resolve().parents[3]


def original_helpers():
  path = ROOT / 'selfdrive/controls/lib/drive_helpers.py'
  tree = ast.parse(path.read_text())
  names = {'MIN_SPEED', 'MAX_LATERAL_JERK', 'MAX_LATERAL_ACCEL_NO_ROLL',
           'MAX_LATERAL_ACCEL_NO_ROLL_LOW_SPEED', 'MAX_CURVATURE'}
  nodes = [n for n in tree.body if
           (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))
           or (isinstance(n, ast.FunctionDef) and n.name in ('clamp', 'clip_curvature'))]
  ns = {'np': np, 'DT_CTRL': 0.01, 'ACCELERATION_DUE_TO_GRAVITY': 9.81}
  exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
  tree = ast.parse((ROOT / 'selfdrive/controls/controlsd.py').read_text())
  smooth = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'smooth_value')
  exec(compile(ast.Module(body=[smooth], type_ignores=[]), 'controlsd smooth_value', 'exec'), ns)
  return ns


def test_against_original_helpers():
  source = original_helpers()
  rng = random.Random(52)
  for _ in range(2000):
    speed = rng.choice([0, 1, 5, 80/3.6, 100/3.6, 120/3.6, 40])
    previous, action, feedback = [rng.uniform(-0.02, 0.02) for _ in range(3)]
    roll = rng.uniform(-0.1, 0.1)
    active, started = rng.choice([True, False]), rng.choice([True, False])
    result = model_step(speed=speed, previous=previous, action=action, feedback=feedback,
                        roll=roll, active=active, lateral_started=started)
    prev = feedback if active and not started else previous
    requested = source['smooth_value'](action, prev, 0.1) if active else feedback
    expected, limited = source['clip_curvature'](speed, prev, requested, roll)
    assert result.curvature == pytest.approx(expected, abs=1e-15)
    assert result.curvature_limited == limited


def test_rate_limit_not_reported_by_original_flag():
  r = model_step(speed=30, previous=0, action=0.01, feedback=0, roll=0, active=True, lateral_started=True)
  assert r.curvature == pytest.approx(5 / 30**2 * 0.01)
  assert r.rate_limited
  assert not r.curvature_limited


def test_first_engagement_and_reengagement_are_distinct():
  args = {'speed': 20, 'previous': 0.001, 'action': 0.002, 'feedback': -0.001, 'roll': 0, 'active': True}
  assert model_step(**args, lateral_started=False).curvature < 0
  assert model_step(**args, lateral_started=True).curvature > 0


@pytest.mark.parametrize('bad', [math.nan, math.inf, -math.inf])
def test_invalid_input_rejected(bad):
  with pytest.raises(ValueError, match='non-finite'):
    model_step(speed=bad, previous=0, action=0, feedback=0, roll=0, active=True, lateral_started=True)


@pytest.mark.parametrize('mode', ['lane_mode', 'vw_meb'])
def test_unimplemented_sources_not_silently_model(mode):
  with pytest.raises(ValueError, match='separate verified baseline'):
    model_step(speed=20, previous=0, action=0, feedback=0, roll=0, active=True, lateral_started=True, **{mode: True})
