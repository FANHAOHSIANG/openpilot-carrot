from types import SimpleNamespace as S
import unittest
from gaode_lane_shadow import visual,compare,line_points
def model(p=0.9):
  x=[0,10,20,30,40,60]
  line=lambda y:S(x=x,y=[y]*len(x))
  return S(laneLines=[line(-5),line(-1.8),line(1.8),line(5)],laneLineProbs=[p]*4,roadEdges=[line(-6),line(6)],position=line(0))
class Tests(unittest.TestCase):
  def test_visual(self):
    v=visual(model(),1000000000);self.assertEqual(len(v["center"]),5);self.assertFalse(v["control_usable"])
  def test_low_confidence(self):self.assertEqual(visual(model(.1),1)["center"],[])
  def test_bad_line(self):self.assertIsNone(line_points([1,1],[0,0]))
  def test_unverified(self):self.assertEqual(compare(visual(model(),1),{"points":[[10,0],[60,0]]})["status"],"alignment_unverified")
  def test_match(self):
    v=visual(model(),1000000000);m={"frame":"c4_model_local","clock":"c4_monotonic_ns","alignment_verified":True,"source":"gaode_native_centerline","mono_ns":1000000000,"points":[[0,.3],[60,.3]]}
    self.assertEqual(compare(v,m)["samples"][0]["delta_y_m"],.3)
    m["mono_ns"]=1;self.assertEqual(compare(v,m)["status"],"time_mismatch")
if __name__=="__main__":unittest.main()
