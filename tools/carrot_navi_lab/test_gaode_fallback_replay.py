import unittest
from types import SimpleNamespace as S
from gaode_fallback_replay import Shadow, summarize


def geo(side='dual', edge=True, change=False, native=0.):
  y=[-5.4,-1.8,1.8,5.4]
  if side=='left': y[2]=None
  if side=='none': y[1]=y[2]=None
  return {'samples':[{'x_m':x,'lane_y_m':y[:],'edge_y_m':[-7.,7.],
                       'center_y_m':0. if side=='dual' else None,
                       'ego_width_m':3.6 if side=='dual' else None,'reason':'candidate' if side=='dual' else 'inner_unavailable'} for x in (10,20,30)],
          'model_path':{'x':[0,10,20,30,40],'y':[native]*5},'road_edge_stds':[.2,.2] if edge else [1.,1.],
          'lane_change_state':'laneChangeStarting' if change else 'off','lane_change_direction':'none'}

class Tests(unittest.TestCase):
  def step(self,s,t,d,blinker=False):
    s.observe_car(S(logMonoTime=t,valid=True,carState=S(canValid=True,leftBlinker=blinker,rightBlinker=False)))
    return s.evaluate(d,t)
  def primed(self):
    s=Shadow()
    for t in (200_000_000,400_000_000,600_000_000):self.step(s,t,geo())
    return s
  def test_dual(self):
    r=self.step(Shadow(),200_000_000,geo());self.assertEqual(r['source'],'dual_line');self.assertFalse(r['control_usable'])
  def test_short_memory(self):
    r=self.step(self.primed(),800_000_000,geo('left'));self.assertEqual(r['source'],'single_line_memory');self.assertEqual(r['candidate_y_m'],[0.,0.,0.])
  def test_no_edges(self):
    r=self.step(self.primed(),800_000_000,geo('left',False));self.assertEqual(r['source'],'native_unverified_reference');self.assertIsNone(r['candidate_y_m'])
  def test_mismatch(self):
    r=self.step(self.primed(),800_000_000,geo('left',native=1.));self.assertIsNone(r['candidate_y_m'])
  def test_gap(self):
    r=self.step(self.primed(),1_200_000_000,geo('left'));self.assertIsNone(r['candidate_y_m'])
  def test_blinker(self):
    r=self.step(self.primed(),800_000_000,geo('left'),True);self.assertIsNone(r['candidate_y_m'])
  def test_change(self):
    r=self.step(self.primed(),800_000_000,geo('left',change=True));self.assertIsNone(r['candidate_y_m'])
  def test_expiry(self):
    s=self.primed()
    for t in (800_000_000,1_000_000_000,1_200_000_000,1_400_000_000,1_600_000_000): self.step(s,t,geo('left'))
    self.assertIsNone(self.step(s,1_800_000_000,geo('left'))['candidate_y_m'])
  def test_native_not_center(self):
    r=self.step(Shadow(),200_000_000,geo('none'));self.assertEqual(r['source'],'native_two_edge_reference');self.assertIsNone(r['candidate_y_m'])
  def test_conflict_clears(self):
    s=self.primed();d=geo();d['samples'][0]['reason']='road_edge_conflict'
    self.assertIsNone(self.step(s,800_000_000,d)['candidate_y_m']);self.assertEqual(len(s.memory),0)
  def test_no_car(self):
    s=self.primed();r=s.evaluate(geo('left'),950_000_000);self.assertIsNone(r['candidate_y_m'])
  def test_missing_both_clears(self):
    s=self.primed();self.step(s,800_000_000,geo('none'));self.assertIsNone(self.step(s,1_000_000_000,geo('left'))['candidate_y_m'])
  def test_summary(self):
    self.assertFalse(summarize([])['accuracy_verified'])
if __name__=='__main__':unittest.main()
