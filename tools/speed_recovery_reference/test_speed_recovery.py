import unittest
from speed_recovery import SpeedRecoveryReference

class Tests(unittest.TestCase):
    def test_release(self):
        p=SpeedRecoveryReference()
        def s(t,raw,ego=40,source='vturn',gas=False,brake=False,active=True,set_speed=90):
            return p.update(now=t,raw=raw,set_speed=set_speed,ego=ego,source=source,active=active,gas=gas,brake=brake)
        self.assertEqual(s(1,40),40)
        self.assertAlmostEqual(s(1.1,80),40.216)
        self.assertEqual(s(1.2,30),30)
        self.assertEqual(s(1.3,70,ego=45),45)
        self.assertEqual(s(1.4,70,source='cam'),70)
        self.assertEqual(s(1.5,40),40)
        self.assertEqual(s(1.6,70,gas=True),70)
        self.assertEqual(s(1.7,40),40)
        self.assertEqual(s(2.0,70),70)
        self.assertEqual(s(2.1,40),40)
        self.assertEqual(s(2.2,70,set_speed=30),30)
        self.assertEqual(s(2.3,70,active=False),70)
        self.assertIsNone(s(2.4,float('nan')))
    def test_no_arm_on_road(self):
        p=SpeedRecoveryReference()
        self.assertEqual(p.update(now=1,raw=50,set_speed=90,ego=45,source='road',active=True,gas=False,brake=False),50)
        self.assertEqual(p.update(now=1.1,raw=80,set_speed=90,ego=45,source='road',active=True,gas=False,brake=False),80)
if __name__=='__main__':unittest.main()
