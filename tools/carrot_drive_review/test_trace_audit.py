import unittest
from trace_audit import audit


class Tests(unittest.TestCase):
    def test_reserve(self):
        a = dict(t=0, reserve_ceiling=409, steer_request=1, lat_active=1)
        b = dict(a, t=.1, reserve_ceiling=270, reserve_reason='invalid', wheel_fl_kph=24, wheel_fr_kph=20, wheel_rl_kph=20, wheel_rr_kph=20)
        self.assertEqual(audit([a,b]), [dict(t=.1, kind='reserve_ceiling_fell', old=409, new=270, reason='invalid', wheel_spread_kph=4)])

    def test_separate_requests(self):
        a = dict(t=0, steer_request=1, lat_active=1)
        b = dict(t=.1, steer_request=0, lat_active=0, steering_angle_deg=90)
        self.assertEqual([x['kind'] for x in audit([a,b])], ['lateral_deactivated', 'request_fell'])

    def test_pre_step_and_jerk(self):
        a = dict(t=0, desired_kph=100, source='road', a_ego_mps2=0)
        b = dict(t=.1, desired_kph=90, source='pre', a_ego_mps2=-.3)
        e, = audit([a,b]); self.assertEqual(e['new']-e['old'], -10); self.assertAlmostEqual(e['measured_jerk_mps3'], -3)

    def test_missing_never_invents(self):
        a = dict(t=0, desired_kph=100, source='pre')
        b = dict(t=.1, desired_kph=90, source='pre')
        self.assertIsNone(audit([a,b])[0]['measured_jerk_mps3'])
        self.assertEqual(audit([a,dict(t=1, desired_kph=60, source='pre')]), [])
        self.assertEqual(audit([a,dict(t=.1, desired_kph='nan', source='pre')]), [])


if __name__ == '__main__':
    unittest.main()
