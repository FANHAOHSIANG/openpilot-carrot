"""Run against actual Navi v2 publisher, schema and HUD parser. No hardware I/O."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "openpilot/selfdrive/carrot/cluster"))
from openpilot.selfdrive.carrot.amap_exit_display import amap_exit_display_payload
from openpilot.selfdrive.carrot.carrot_navi_cereal import build_carrot_navi_payload
from cluster_navi import parse_carrot_navi, fresh_carrot_navi

NOW=10_100_000_000

def sample():
    def record(value):
        return dict(present=True,sequence=1,source_timestamp_ms=10000,sent_at_ms=10500,received_mono_ns=10_000_000_000,value=value)
    return dict(connected=True,items={'guidance_current':record({'distance_m':800,'turn_type':51,'amap_exit_info':{'source':'amap_auto','scope':'display_only','generated_at_ms':10000,'fields':{'EXIT_NAME_INFO':'竹北交流道','CUR_SEG_NUM':12,'CUR_POINT_NUM':2,'SEG_REMAIN_DIS':800,'EXTRA_DRIVE_WAY':[1,2]}}}),'navigation_status':record({'guidance_active':True,'off_route':False})})

class DisplayInfoTests(unittest.TestCase):
    def test_valid_and_immutable(self):
        s=sample(); old=copy.deepcopy(s); p=amap_exit_display_payload(s,NOW)
        self.assertEqual(s,old); self.assertTrue(p['valid']); self.assertEqual(p['deadlineMonoTimeNanos'],11_500_000_000)
        self.assertEqual(json.loads(p['fieldsJson'])['EXIT_NAME_INFO'],'竹北交流道')
    def test_reject_missing_stale_future_or_disconnected(self):
        for change in ('disconnect','stop','offroute','wrongsource','wrongscope','future','mismatch','missing','expired','status_expired'):
            s=sample(); g=s['items']['guidance_current']; st=s['items']['navigation_status']; info=g['value']['amap_exit_info']; now=NOW
            if change=='disconnect': s['connected']=False
            elif change=='stop': st['value']['guidance_active']=False
            elif change=='offroute': st['value']['off_route']=True
            elif change=='wrongsource': info['source']='amap_phone'
            elif change=='wrongscope': info['scope']='control'
            elif change=='future': info['generated_at_ms']=11000
            elif change=='mismatch': info['generated_at_ms']=9400
            elif change=='missing': g['value'].pop('amap_exit_info')
            elif change=='expired': now=11_500_000_000
            elif change=='status_expired': st['source_timestamp_ms']=8000
            with self.subTest(change=change): self.assertFalse(amap_exit_display_payload(s,now)['valid'])
    def test_unknown_and_invalid_fields_removed(self):
        s=sample(); f=s['items']['guidance_current']['value']['amap_exit_info']['fields']; f.update(CUR_SEG_NUM=True,CUR_POINT_NUM=-1,EXIT_NAME_INFO='bad\nname',EXTRA_DRIVE_WAY=[True],target_kph=10)
        self.assertEqual(json.loads(amap_exit_display_payload(s,NOW)['fieldsJson']),{'SEG_REMAIN_DIS':800})
    def test_publisher_and_hud_preserve_original_navigation(self):
        s=sample()
        before=copy.deepcopy(s); before['items']['guidance_current']['value'].pop('amap_exit_info')
        old=build_carrot_navi_payload(before,NOW)
        new=build_carrot_navi_payload(s,NOW)
        self.assertNotEqual(old.pop('amapExitInfo'),new['amapExitInfo'])
        self.assertEqual(old,{k:v for k,v in new.items() if k!='amapExitInfo'})
        n= parse_carrot_navi(new,NOW/1e9)
        self.assertEqual(n.amap_exit_name,'竹北交流道')
        self.assertEqual(n.current.distance_m,800)
        self.assertEqual(n.current.turn_type,51)
        self.assertEqual(fresh_carrot_navi(n,11.5)[0].amap_exit_name,'')
        self.assertEqual(parse_carrot_navi(old,NOW/1e9).amap_exit_name,'')
    def test_capnp_roundtrip(self):
        import capnp
        root=ROOT/'openpilot/cereal'
        schema=capnp.load(str(root/'custom.capnp'),imports=[str(root)])
        msg=schema.CarrotNaviState.new_message(**build_carrot_navi_payload(sample(),NOW))
        with schema.CarrotNaviState.from_bytes(msg.to_bytes()) as reader:
            self.assertEqual(parse_carrot_navi(reader,NOW/1e9).amap_exit_name,'竹北交流道')

if __name__=='__main__': unittest.main()
