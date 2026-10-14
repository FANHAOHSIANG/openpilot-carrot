"""Native-independent regression checks executing the production methods.

AST loading only bypasses native module imports; method bodies are not replaced.
Navigation serialization uses the full real cereal schema and pycapnp.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import threading

import capnp
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def method(path, cls, name, namespace):
  tree = ast.parse((ROOT / path).read_text())
  owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls) if cls else tree
  node = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)
  node.decorator_list = []
  unit = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
  exec(compile(ast.fix_missing_locations(unit), str(ROOT / path), 'exec'), namespace)
  return namespace[name]


@pytest.fixture(scope='module')
def schema():
  return capnp.load(str(ROOT / 'openpilot/cereal/log.capnp'), imports=[
    str(ROOT / 'openpilot/cereal'), str(ROOT / 'opendbc_repo/opendbc/car')])


@pytest.mark.parametrize('along', [0., 27.29389298261073, 99.999])
def test_route_instructions_serialize_numpy_cumulative_distances(schema, along):
  def new_message(service, valid):
    msg = schema.Event.new_message(valid=valid)
    msg.init(service)
    return msg
  published = []
  send = method('openpilot/selfdrive/navd/navd.py', 'RouteEngine', 'send_instruction', {
    'np': np, 'messaging': NS(new_message=new_message), 'log': schema,
    'distance_along_geometry': lambda *_: along,
    'parse_banner_instructions': lambda *_: {'maneuverType': 'turn', 'maneuverModifier': 'right'},
    'MANEUVER_TRANSITION_THRESHOLD': 10,
  })
  point = NS(distance_to=lambda _: 0., annotations={})
  steps = [{'distance': x, 'duration': 10., 'duration_typical': None, 'bannerInstructions': [{}]} for x in [100., 200.]]
  engine = NS(step_idx=0, route=steps, route_geometry=[[point], [point]], last_position=point,
              localizer_valid=True, pm=NS(send=lambda name, msg: published.append(msg.to_bytes())))
  send(engine)
  with schema.Event.from_bytes(published[0]) as msg:
    assert msg.valid
    assert [m.distance for m in msg.navInstruction.allManeuvers] == pytest.approx([100.-along, 300.-along])
    assert [m.modifier for m in msg.navInstruction.allManeuvers] == ['right', 'right']
    assert msg.navInstruction.distanceRemaining == pytest.approx(300.-along)


def test_idle_broadcaster_skips_serialization_and_new_client_gets_next_tick():
  calls = []
  broadcaster = NS(server_running=False, clients={}, clients_lock=threading.Lock(), sequence=0,
                   start_tcp_server=lambda: None, start_vision_server=lambda: None,
                   sm=NS(update=lambda _: calls.append('update'), alive={'carState':True,'modelV2':False,'selfdriveState':False,'controlsState':False}),
                   collect_car_state=lambda _: {'vEgo': 3.}, collect_tesla_das_road=lambda:None,
                   create_packet=lambda data: calls.append(('packet',data)) or b'packet',
                   broadcast_to_clients=lambda _: calls.append('send'), shutdown=lambda:calls.append('shutdown'))
  class SM:
    alive = broadcaster.sm.alive
    def update(self, _): calls.append('update')
    def __getitem__(self, _): return NS(vEgo=3.)
  broadcaster.sm = SM()
  class Rate:
    def __init__(self, *_, **__): self.ticks=0
    def keep_time(self):
      self.ticks += 1
      if self.ticks==1: broadcaster.clients['client']=object()
      else: broadcaster.server_running=False
  class Thread:
    def __init__(self, **_): pass
    def start(self): pass
  run = method('openpilot/selfdrive/carrot/xiaoge_data.py', 'XiaogeDataBroadcaster', 'broadcast_data',
               {'threading':NS(Thread=Thread),'Ratekeeper':Rate})
  run(broadcaster)
  assert calls.count('update')==2 and calls.count('send')==1
  assert len([c for c in calls if isinstance(c,tuple)])==1
  assert broadcaster.sequence==2


def test_pose_reason_is_logged_with_existing_throttle():
  messages=[]
  report=method('openpilot/selfdrive/locationd/locationd.py', None, 'print_live_pose_invalid_reasons',
                {'time':NS(monotonic=lambda:20.), 'INVALID_PRINT_INTERVAL':1., 'cloudlog':NS(warning=messages.append)})
  assert report(False, True, ['cameraOdometry msg.valid=False'], [], 0.)==20.
  assert 'cameraOdometry' in messages[0]
  assert report(False, True, ['cameraOdometry msg.valid=False'], [], 19.5)==19.5
  assert len(messages)==1
  assert report(True, True, [], [], 0.)==0.


def test_lane_upper_half_crop_never_runs_mask_contraction(monkeypatch):
  from openpilot.selfdrive.carrot.xiaoge.lane_inference import LaneInference
  predictions=np.zeros((1,42,1),np.float32)
  predictions[0,:4,0]=[208,40,100,30]
  predictions[0,4,0]=.9
  class Net:
    def setInput(self,_):pass
    def getUnconnectedOutLayersNames(self):return ['output0','output1']
    def forward(self,_):return [predictions,np.ones((1,32,104,104),np.float32)]
  engine=LaneInference();engine.net=Net();engine.valid=True
  def forbidden(*_,**__): raise AssertionError('unusable upper-half mask was evaluated')
  monkeypatch.setattr(np,'tensordot',forbidden)
  result=engine.infer(np.zeros((416,416),np.uint8),416,416)
  assert result['valid'] and result['candidatesCount']==0 and result['leftLine']==-1 and result['rightLine']==-1


@pytest.mark.parametrize('existing,expected', [(0,15),(19,19)])
def test_auxiliary_workers_keep_low_priority_and_single_cv_thread(monkeypatch,existing,expected):
  import sys
  from types import ModuleType
  calls=[]
  realtime=ModuleType('openpilot.common.realtime')
  realtime.set_core_affinity=lambda cores:calls.append(('cores',cores))
  monkeypatch.setitem(sys.modules,'openpilot.common.realtime',realtime)
  class Thread:
    def __init__(self, **kwargs): calls.append(('thread',kwargs))
    def start(self):pass
  class HTTP:
    def __init__(self,*_):pass
  service=NS(run_camera=lambda:None,run_road_camera=lambda:None)
  create=method('openpilot/selfdrive/carrot/xiaoge/v_asm_server.py',None,'create_server',{
    'HOST':'127.0.0.1','PORT':8082,'DEFAULT_MODEL_PATH':Path('unused'),
    'sys':NS(platform='linux'),'os':NS(PRIO_PROCESS=0,getpriority=lambda *_:existing,
                                     setpriority=lambda *args:calls.append(('nice',args[-1]))),
    'cv2':NS(setNumThreads=lambda n:calls.append(('cvthreads',n))),
    'VASMService':lambda _:service,'Handler':NS(),'ThreadingHTTPServer':HTTP,
    'threading':NS(Thread=Thread)})
  assert create()[0] is service
  assert calls[:3]==[('cores',[0,1,2,3]),('nice',expected),('cvthreads',1)]
  assert len([c for c in calls if c[0]=='thread'])==2
