import json, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"cluster"))
from cluster_navi import parse_carrot_navi, fresh_carrot_navi
def sample():
    meta={"present":True,"sequence":1,"sourceTimestampMillis":1000,"receivedMonoTimeNanos":49_500_000_000}
    c={"source":"amap_link_14","count":2,"lanes":[{"index":0,"advised":False},{"index":1,"advised":True}],"control_input":False,"absolute_mapping_verified":False}
    return {"schemaVersion":1,"connected":True,"sessionId":"test","guidanceCurrent":{"meta":meta,"distanceM":800,"turnType":51},"navigationStatus":{"meta":meta,"guidanceActive":True,"offRoute":False},"amapLaneCandidate":{"valid":True,"deadlineMonoTimeNanos":51_000_000_000,"fieldsJson":json.dumps(c)}}
class Native(unittest.TestCase):
    def test_live(self):
        a=parse_carrot_navi(sample(),50.)
        self.assertEqual(a.amap_lane_candidate_text,"車道候選 1/2 未配對")
        self.assertEqual(fresh_carrot_navi(a,51.)[0].amap_lane_candidate_text,"")
    def test_off_route(self):
        a=sample();a["navigationStatus"]["offRoute"]=True
        self.assertEqual(parse_carrot_navi(a,50.).amap_lane_candidate_text,"")
    def test_legacy(self):
        a=sample();del a["amapLaneCandidate"]
        self.assertEqual(parse_carrot_navi(a,50.).amap_lane_candidate_text,"")
if __name__=="__main__":unittest.main()
