import copy
from openpilot.tools.curve_centering.control_audit import audit, summarize


def fixture():
  records = []
  def add(k, ns, data):
    records.append({'kind':k, 'ns':ns, 'data':data, 'valid':True})
  add('modelV2', 990_000_000, {'action':{'desiredCurvature':0.001}})
  # Newer model is visible to the logger but not consumed by this control step.
  add('modelV2', 999_000_000, {'action':{'desiredCurvature':0.1}})
  add('liveParameters', 990_000_000, {'roll':0})
  for ns in (1_000_000_000, 1_010_000_000, 1_020_000_000):
    add('carState', ns-1000, {'vEgo':20, 'steeringPressed':False})
    add('controlsState', ns, {'lateralPlanMonoTime':990_000_000, 'desiredCurvature':0.001,
                            'curvature':0.001, 'activeLaneLine':False})
    add('carControl', ns+1000, {'latActive':True, 'actuators':{'curvature':0.001, 'torque':0.1}})
  return records


def test_exact_consumed_model_not_latest():
  rows = audit(fixture())
  assert 'control_gap_or_initial' in rows[0]['reasons']
  assert rows[1]['model_action'] == 0.001
  assert abs(rows[1]['error']) < 1e-12
  assert summarize(rows)['computed_steps'] == 2


def test_missing_model_never_substitutes_nearest():
  data = [r for r in fixture() if r['ns'] != 990_000_000 or r['kind'] != 'modelV2']
  rows = audit(data)
  assert all('model_missing_or_stale' in r['reasons'] for r in rows)
  assert summarize(rows)['computed_steps'] == 0


def test_invalid_state_and_lane_mode_excluded():
  data = copy.deepcopy(fixture())
  for r in data:
    if r['kind'] == 'carState':
      r['valid'] = False
    if r['kind'] == 'controlsState':
      r['data']['activeLaneLine'] = True
  row = audit(data)[1]
  assert 'invalid_message' in row['reasons']
  assert 'lane_baseline_pending' in row['reasons']
  assert 'error' not in row


def test_command_pair_mismatch_excluded():
  data = fixture()
  for r in data:
    if r['kind'] == 'controlsState':
      r['data']['desiredCurvature'] = 0.2
  assert all('paired_command_mismatch' in r['reasons'] for r in audit(data))


def test_old_vehicle_state_excluded():
  data = [r for r in fixture() if r['kind'] != 'carState']
  assert all('carState_missing_or_stale' in r['reasons'] for r in audit(data))
