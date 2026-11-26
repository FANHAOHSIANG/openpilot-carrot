import unittest
from types import SimpleNamespace as NS
from openpilot.selfdrive.carrot.carrot_pre_adjust import shared_pre_adjust_payload, shared_pre_adjust_candidate, pre_adjust_candidate

NOW=10_100_000_000

def records(**extra):
    return ({'present':True,'sent_at_ms':10500,'received_mono_ns':10_000_000_000,'value':{'guidance_active':True,'pre_adjust_control':{'source':'amap_auto','enabled':True,'generated_at_ms':10000,**extra}}}, {'present':True,'sent_at_ms':10500,'received_mono_ns':10_000_000_000,'source_timestamp_ms':10000})

class Protocol(unittest.TestCase):
    def test_legacy_shared_compatibility(self):
        self.assertEqual(shared_pre_adjust_payload(*records(),NOW),('amap_auto',11_500_000_000))
    def test_new_permission(self):
        self.assertEqual(shared_pre_adjust_payload(*records(protocol_version=2,scope='turn_only'),NOW),('amap_auto',11_500_000_000))
    def test_wrong_version(self):
        for v in [True,2.0,'2',1,3,None]:
            self.assertEqual(shared_pre_adjust_payload(*records(protocol_version=v,scope='turn_only'),NOW),('',0))
    def test_wrong_scope(self):
        for s in ['ramp','all',None,True]:
            self.assertEqual(shared_pre_adjust_payload(*records(protocol_version=2,scope=s),NOW),('',0))
    def test_partial_version(self):
        for x in [{'protocol_version':2},{'scope':'turn_only'}]:
            self.assertEqual(shared_pre_adjust_payload(*records(**x),NOW),('',0))
    def test_stale_and_stop(self):
        a,b=records(protocol_version=2,scope='turn_only'); a['value']['guidance_active']=False
        self.assertEqual(shared_pre_adjust_payload(a,b,NOW),('',0))
        self.assertEqual(shared_pre_adjust_payload(*records(protocol_version=2,scope='turn_only'),11_500_000_000),('',0))
    def test_scope_cannot_enable_ramp(self):
        for code in (6,7,43,44,73,74,101,102):
            n=NS(guidance_active=True,off_route=False,shared_pre_adjust_source='amap_auto',shared_pre_adjust_deadline_ns=11_500_000_000,current=NS(present=True,distance_m=150,turn_type=code))
            self.assertEqual(shared_pre_adjust_candidate(n,True,NOW,45),250)
    def test_old_native_quarantined(self):
        self.assertEqual(pre_adjust_candidate(NS(),True,NOW),250)

if __name__=='__main__': unittest.main()
