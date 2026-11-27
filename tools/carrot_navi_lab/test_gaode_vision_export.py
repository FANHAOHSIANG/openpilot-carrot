import unittest
from types import SimpleNamespace as S
from gaode_vision_export import geometry, records, curvature, nav

def model(probs=(.9,.9,.9,.9),ys=(-5.4,-1.8,1.8,5.4),edge=(-7.,7.)):
  x=[0,10,20,30,40,60]
  def line(y):return S(x=x,y=[y]*len(x),z=[0]*len(x),t=[],yStd=[])
  return S(laneLines=[line(y) for y in ys],laneLineProbs=probs,laneLineStds=[.1]*4,
           roadEdges=[line(y) for y in edge],roadEdgeStds=[.2,.2],position=line(0))
def event(k,t,v,valid=True):
  return S(which=lambda:k,logMonoTime=t,valid=valid,**{k:v})

class Vision(unittest.TestCase):
  def test_counts(self):
    d=geometry(model())
    self.assertEqual(len(d["center"]),5)
    self.assertEqual(d["samples"][0]["visible_contiguous_lane_count"],3)
    self.assertIsNone(d["total_road_lane_count"])
    self.assertAlmostEqual(d["samples"][0]["ego_width_m"],3.6)
    self.assertEqual(d["curvature"][0]["signed_curvature_1_m"],0)
  def test_inner_invalid(self):
    d=geometry(model((.9,.1,.9,.9)))
    self.assertEqual(d["center"],[])
    self.assertIsNone(d["samples"][0]["visible_contiguous_lane_count"])
  def test_outer_missing(self):
    d=geometry(model((.2,.9,.9,.9)))
    self.assertEqual(d["samples"][0]["visible_contiguous_lane_count"],2)
  def test_crossed_outer(self):
    d=geometry(model(ys=(0.,-1.8,1.8,5.4)))
    self.assertEqual(d["samples"][0]["visible_contiguous_lane_count"],2)
  def test_edge_conflict(self):
    d=geometry(model(edge=(0.,7.)))
    self.assertEqual(d["center"],[])
    self.assertEqual(d["samples"][0]["reason"],"road_edge_conflict")
  def test_reversed_order(self):
    m=model()
    m.laneLines[1].y=[-1.8,-1.8,-1.8,1.8,1.8,1.8]
    m.laneLines[2].y=[1.8,1.8,1.8,-1.8,-1.8,-1.8]
    self.assertEqual(geometry(m)["center"],[])
  def test_nonfinite(self):
    m=model((.9,float("nan"),.9,.9))
    self.assertIsNone(geometry(m)["lane_probs"][1])
    self.assertEqual(geometry(m)["center"],[])
  def test_clock_and_rate(self):
    wall=1_800_000_000_000_000_000
    out=list(records([event("clocks",1_000_000_000,S(wallTimeNanos=wall)),
      event("modelV2",1_100_000_000,model()),
      event("modelV2",1_150_000_000,model()),
      event("modelV2",1_400_000_000,model(),False),
      event("modelV2",17_000_000_000,model())],0))
    self.assertEqual(out[1]["wall_est_ns"],wall+100_000_000)
    self.assertFalse(out[1]["phone_clock_alignment_verified"])
    self.assertFalse(out[1]["control_usable"])
    self.assertIsNone(out[2]["wall_est_ns"])
    self.assertEqual(out[-1]["counts"]["modelV2"],2)
    self.assertEqual(out[-1]["counts"]["modelV2:invalid"],1)
  def test_clock_reset(self):
    out=list(records([event("clocks",100,S(wallTimeNanos=1_800_000_000_000_000_000)),
      event("modelV2",50,model())],1))
    self.assertIsNone(out[1]["wall_est_ns"])
    self.assertEqual(out[-1]["counts"]["clock_reset"],1)
  def test_missing_navi(self):
    m=S(present=False,sequence=0,sourceTimestampMillis=0,receivedMonoTimeNanos=0)
    n=S(connected=False,generation=0,publishMonoTimeNanos=0,
        **{k:S(meta=m) for k in ("vehicle","guidanceCurrent","guidanceNext","laneCurrent","route")})
    self.assertNotIn("count",nav(n)["items"]["laneCurrent"])
  def test_curvature(self):
    self.assertAlmostEqual(curvature((1,0),(0,1),(-1,0)),1)
if __name__=="__main__":unittest.main()
