import unittest
from curve_trace_audit import audit


def row(t=0, **kw):
    r = dict(t=t, seg='1', desired='100', set='100', src='vturn', longActive='True', gas='False', brake='False')
    r.update(kw)
    return r


class AuditTests(unittest.TestCase):
    def test_manual_cap_masks_raw_jump(self):
        out = audit([row(desired=180), row(.1, desired=150)])
        self.assertEqual((out['raw_steps'], out['capped_steps']), (1, 0))

    def test_active_source_switch(self):
        out = audit([row(desired=40), row(.1, desired=22, src='atc')])
        event, = out['active_steps']
        self.assertEqual((event['cap_before_kph'], event['cap_after_kph'], event['source_after']), (40, 22, 'atc'))

    def test_driver_override_excluded(self):
        for k in ('gas', 'brake'):
            self.assertEqual(audit([row(), row(.1, desired=60, **{k:'True'})])['active_steps'], [])
        self.assertEqual(audit([row(), row(.1, desired=60, longActive='False')])['active_steps'], [])

    def test_no_cross_gap_or_segment(self):
        for b in (row(1, desired=60), row(.1, seg='2', desired=60), row(0, desired=60)):
            self.assertEqual(audit([row(), b])['raw_steps'], 0)

    def test_missing_data(self):
        out = audit([row(), row(.1, desired='nan')])
        self.assertEqual(out['raw_steps'], 0)
        self.assertIn('steerRequest', out['missing_torque_fields'])

    def test_set_speed_change_visible(self):
        event, = audit([row(), row(.1, set=80)])['active_steps']
        self.assertEqual(event['manual_set_after_kph'], 80)
        self.assertIsNone(event['target_accel_after'])


if __name__ == '__main__':
    unittest.main()
