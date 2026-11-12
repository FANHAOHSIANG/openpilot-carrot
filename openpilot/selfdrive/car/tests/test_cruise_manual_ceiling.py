"""Exercise the production automatic-speed policy without native vehicle bindings."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


def helper():
  tree = ast.parse(Path(__file__).parents[1].joinpath('cruise.py').read_text())
  cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VCruiseCarrot')
  method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_auto_speed_up')
  namespace = {}
  exec(compile(ast.Module(body=[method], type_ignores=[]), 'cruise.py', 'exec'), namespace)
  obj = SimpleNamespace(_pause_auto_speed_up=False, applyModelSpeed=0., model_v_kph=90.,
                        nRoadLimitSpeed=100, nRoadLimitSpeed_last=100, autoSpeedUptoRoadSpeedLimit=1.,
                        autoRoadSpeedLimitOffset=6, _v_cruise_kph_at_brake=0.,
                        v_lead_kph=80., d_rel=25., autoRoadSpeedAdjust=.5,
                        autoNaviSpeedSafetyFactor=1.05, _add_log=lambda _: None)
  return obj, lambda speed, **kw: namespace['_auto_speed_up'](obj, speed, **kw)


def test_lead_acceleration_cannot_raise_manual_speed_or_poison_resume():
  obj, update = helper()
  speed = 50.
  for _ in range(500):
    speed = update(speed)
  assert speed == 50.
  assert obj._v_cruise_kph_at_brake == 0.


@pytest.mark.parametrize('factor', [1., -1.])
@pytest.mark.parametrize('road_factor', [0., 1.])
def test_model_and_early_return_cannot_raise_selection(factor, road_factor):
  obj, update = helper()
  obj.applyModelSpeed, obj.autoSpeedUptoRoadSpeedLimit = factor, road_factor
  assert update(50.) == 50.


def test_lower_road_limit_still_reduces_speed():
  obj, update = helper()
  obj.nRoadLimitSpeed, obj.d_rel = 30, 100
  assert update(50.) == 40.


def test_explicit_speed_command_can_raise_selection():
  obj, update = helper()
  assert update(50., explicit=True) == 55.


def test_increased_road_limit_sync_cannot_raise_selection():
  obj, update = helper()
  obj.autoRoadSpeedAdjust, obj.d_rel, obj.nRoadLimitSpeed_last = -1, 100, 30
  assert update(50.) == 50.
