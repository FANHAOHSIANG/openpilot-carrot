import unittest
from openpilot.selfdrive.carrot.amap_lane_display import lane_display_payload, candidate_count

def sample():
  c={"source":"amap_link_14","count":2,"lanes":[{"index":0,"back_code":0,"front_code":255,"advised":False},{"index":1,"back_code":0,"front_code":0,"advised":True}],"control_input":False,"absolute_mapping_verified":False,"absolute_lane_index":None}
  r={"present":True,"source_timestamp_ms":1000,"sent_at_ms":1100,"received_mono_ns":10_000_000_000}
  return {"connected":True,"items":{"guidance_current":{**r,"value":{"amap_lane_candidate":{"version":1,"scope":"display_only","generated_at_ms":1000,"candidate":c}}},"navigation_status":{**r,"value":{"guidance_active":True,"off_route":False}}}}
class Checks(unittest.TestCase):
  def test_valid(self):
    x=lane_display_payload(sample(),10_100_000_000)
    self.assertTrue(x["valid"])
    self.assertEqual(candidate_count(x["fieldsJson"]),(1,2,0))
  def test_expired(self):
    self.assertFalse(lane_display_payload(sample(),12_000_000_000)["valid"])
  def test_off_route(self):
    s=sample();s["items"]["navigation_status"]["value"]["off_route"]=True
    self.assertFalse(lane_display_payload(s,10_100_000_000)["valid"])
  def test_semantics(self):
    s=sample();s["items"]["guidance_current"]["value"]["amap_lane_candidate"]["candidate"]["lanes"][0]["advised"]=True
    self.assertFalse(lane_display_payload(s,10_100_000_000)["valid"])
  def test_original_event_age_separate_from_lease(self):
    s=sample();info=s["items"]["guidance_current"]["value"]["amap_lane_candidate"]; c=info["candidate"]
    c.update(source="amap_auto_13012")
    for row in c["lanes"]:row["front_code"]=None
    # source wall values are deliberately synthetic
    g=s["items"]["guidance_current"]; g.update(source_timestamp_ms=152000,sent_at_ms=152100)
    info.update(generated_at_ms=152000,observed_at_ms=1000,observation_age_ms=151100)
    self.assertTrue(lane_display_payload(s,10_100_000_000)["valid"])
    info["observation_age_ms"]=180000
    self.assertFalse(lane_display_payload(s,10_100_000_000)["valid"])
if __name__=="__main__":unittest.main()
