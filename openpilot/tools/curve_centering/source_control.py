"""Execute pinned production curvature-selection statements in an IO-free namespace.

This is the pre-LaC scalar path, NOT Controls, a torque controller or CAN safety.
No imports from controlsd (which would load Params/messaging/native processes).
"""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PINNED_BLOBS = {
  'selfdrive/controls/controlsd.py': '49bc2329df2ef9536725ebd73e6b77ce454ab274',
  'selfdrive/controls/lib/drive_helpers.py': 'be7247ad61664ffa011bc4ad14a1c30b2172a036',
}


def load_source(root=ROOT):
  trees = {}
  for name, expected in PINNED_BLOBS.items():
    raw = (root / name).read_bytes()
    digest = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if digest != expected:
      raise ValueError('unreviewed production source: ' + name)
    trees[name] = ast.parse(raw)
  helpers = trees['selfdrive/controls/lib/drive_helpers.py']
  names = {'MIN_SPEED', 'MAX_LATERAL_JERK', 'MAX_LATERAL_ACCEL_NO_ROLL',
           'MAX_LATERAL_ACCEL_NO_ROLL_LOW_SPEED', 'MAX_CURVATURE'}
  nodes = [n for n in helpers.body if
           (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))
           or (isinstance(n, ast.FunctionDef) and n.name in ('clamp', 'clip_curvature'))]
  ns = {'np': np, 'DT_CTRL': 0.01, 'ACCELERATION_DUE_TO_GRAVITY': 9.81}
  exec(compile(ast.Module(body=nodes, type_ignores=[]), 'pinned drive_helpers', 'exec'), ns)
  controls = next(n for n in trees['selfdrive/controls/controlsd.py'].body if isinstance(n, ast.ClassDef) and n.name == 'Controls')
  body = next(n.body for n in controls.body if isinstance(n, ast.FunctionDef) and n.name == 'state_control')
  start = next(i for i, n in enumerate(body) if isinstance(n, ast.FunctionDef) and n.name == 'smooth_value')
  end = next(i for i, n in enumerate(body) if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'actuators.curvature')
  engagement = next(n for n in body if isinstance(n, ast.If) and ast.unparse(n.test) == 'CC.latActive and (not self.lateral_started)')
  mode = next(n for n in body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'self.lanefull_mode_enabled')
  return ns, compile(ast.Module(body=[mode], type_ignores=[]), 'production mode selection', 'exec'), compile(
    ast.Module(body=[engagement, *body[start:end+1]], type_ignores=[]), 'production curvature selection', 'exec')


class SourceControl:
  def __init__(self):
    self.namespace, self.mode_code, self.step_code = load_source()

  def step(self, *, speed, previous, action, feedback, roll, active, lateral_started,
           use_lane_lines=False, curve_speed=0.0, lane_threshold=0.0, vw_meb=False):
    state = NS(desired_curvature=previous, curvature=feedback, lateral_started=lateral_started,
               is_vw_meb=vw_meb, params=NS(get_int=lambda key: lane_threshold))
    ns = dict(self.namespace, self=state, CS=NS(vEgo=speed), CC=NS(latActive=active),
              model_v2=NS(action=NS(desiredCurvature=action)), lp=NS(roll=roll),
              lat_plan=NS(useLaneLines=use_lane_lines), curve_speed_abs=abs(curve_speed), actuators=NS())
    exec(self.mode_code, ns)
    if state.is_vw_meb or state.lanefull_mode_enabled:
      raise ValueError('lane/VW control path unsupported by isolated model bench')
    exec(self.step_code, ns)
    return {'curvature': ns['actuators'].curvature, 'curvature_limited': bool(ns['curvature_limited']),
            'lateral_started': state.lateral_started}
