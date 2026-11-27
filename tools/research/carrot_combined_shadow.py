"""Offline combined PRE + ROAD evidence regression. No vehicle interfaces.
Only classifies recorded data and illustrates comfort transitions with synthetic
inputs. Never emits a vehicle speed command; no live planner integration.
"""
import argparse, collections, csv, math, unittest
from dataclasses import dataclass


def review(source, ego, target, road_valid, route_active, exit_verified):
    if source not in ('pre', 'road', 'read'):
        return 'outside_scope'
    if not all(math.isfinite(v) and v >= 0 for v in (ego, target)):
        return 'invalid_display_only'
    if source == 'read':
        return 'unknown_source_display_only'
    if source == 'road' and target >= 200:
        return 'no_limit_sentinel'
    valid = road_valid if source == 'road' else route_active and exit_verified
    if not valid:
        if ego > 0 and (ego-target)/ego > .2 + 1e-12:
            return 'large_unverified_gap_display_only'
        return 'unverified_road_display_only' if source == 'road' else 'unbound_pre_display_only'
    return 'verified_candidate_requires_planner'

@dataclass(frozen=True)
class ExitEvidence:
    session: str
    route: str
    exit_id: str
    active: bool = True
    matched: bool = True
    fresh: bool = True
    on_route: bool = True
    next_exit: bool = True

    def valid(self):
        return bool(self.session and self.route and self.exit_id and self.active and self.matched and self.fresh and self.on_route and self.next_exit)

class ComfortPreview:
    """Synthetic visual trace only; cap is an independent safety/legal input.
    Rates are illustrative, not recommended driving parameters."""
    def __init__(self): self.key = self.prev = self.t = None
    def reset(self): self.key = self.prev = self.t = None
    def step(self, t, evidence, phase, comfort_goal, independent_cap, initial):
        if not all(math.isfinite(v) and v >= 0 for v in (t, comfort_goal, independent_cap, initial)):
            self.reset(); return None, 'invalid'
        if phase not in ('approach','exit','recovery') or not evidence.valid():
            self.reset(); return None, 'inactive_or_unverified'
        key = (evidence.session,evidence.route,evidence.exit_id)
        if self.key is None:
            if phase != 'approach': return None, 'no_prior_approach'
            self.key, self.t, self.prev = key,t,min(initial, independent_cap)
            return self.prev,'start'
        if key != self.key or not 0 < t-self.t <= 1:
            self.reset(); return None,'boundary_reset'
        dt=t-self.t
        preview = min(independent_cap, min(self.prev+2*dt,max(self.prev-3*dt,comfort_goal)))
        self.prev,self.t=preview,t
        return preview,'cap' if preview == independent_cap else phase

class Checks(unittest.TestCase):
    def test_road36(self): self.assertEqual(review('road',90,36,False,True,False),'large_unverified_gap_display_only')
    def test_road_invalid_small_gap(self): self.assertEqual(review('road',100,95,False,True,False),'unverified_road_display_only')
    def test_road_valid(self): self.assertEqual(review('road',100,36,True,True,False),'verified_candidate_requires_planner')
    def test_boundary(self): self.assertEqual(review('pre',100,80,False,True,False),'unbound_pre_display_only')
    def test_more_than_boundary(self): self.assertEqual(review('pre',100,79.9,False,True,False),'large_unverified_gap_display_only')
    def test_pre_straight(self): self.assertEqual(review('pre',100,100,False,True,False),'unbound_pre_display_only')
    def test_no_route(self): self.assertEqual(review('pre',90,80,False,False,True),'unbound_pre_display_only')
    def test_verified_exit(self): self.assertEqual(review('pre',100,60,False,True,True),'verified_candidate_requires_planner')
    def test_sentinel(self): self.assertEqual(review('road',80,200,False,True,False),'no_limit_sentinel')
    def test_read(self): self.assertEqual(review('read',90,36,False,True,False),'unknown_source_display_only')
    def test_safety_sources(self):
        for s in ('atc','vturn','route','cam','hda','gas','lead','aeb'):
            self.assertEqual(review(s,90,36,False,True,False),'outside_scope')
    def test_preview_approach_exit_recovery(self):
        p=ComfortPreview(); e=ExitEvidence('s','r','e')
        self.assertEqual(p.step(0,e,'approach',60,100,100)[0],100)
        for t in range(1,15): p.step(t,e,'approach',60,100,100)
        self.assertEqual(p.prev,60)
        self.assertEqual(p.step(15,e,'exit',60,60,60)[0],60)
        self.assertEqual(p.step(16,e,'recovery',100,100,60)[0],62)
        self.assertEqual(p.step(17,e,'recovery',100,100,60)[0],64)
    def test_cap_immediate(self):
        p=ComfortPreview();e=ExitEvidence('s','r','e');p.step(0,e,'approach',60,100,100)
        self.assertEqual(p.step(1,e,'approach',60,36,100),(36,'cap'))
    def test_route_change(self):
        p=ComfortPreview();p.step(0,ExitEvidence('s','r','e'),'approach',60,100,100)
        self.assertEqual(p.step(1,ExitEvidence('s','new','e'),'approach',60,100,100),(None,'boundary_reset'))
    def test_not_next_exit(self): self.assertEqual(ComfortPreview().step(0,ExitEvidence('s','r','e',next_exit=False),'approach',60,100,100),(None,'inactive_or_unverified'))
    def test_stale(self): self.assertEqual(ComfortPreview().step(0,ExitEvidence('s','r','e',fresh=False),'approach',60,100,100),(None,'inactive_or_unverified'))
    def test_off_route(self): self.assertEqual(ComfortPreview().step(0,ExitEvidence('s','r','e',on_route=False),'approach',60,100,100),(None,'inactive_or_unverified'))
    def test_session_change(self):
        p=ComfortPreview();p.step(0,ExitEvidence('s','r','e'),'approach',60,100,100)
        self.assertEqual(p.step(1,ExitEvidence('new','r','e'),'approach',60,100,100),(None,'boundary_reset'))
    def test_time_gap(self):
        p=ComfortPreview();e=ExitEvidence('s','r','e');p.step(0,e,'approach',60,100,100)
        self.assertEqual(p.step(2,e,'approach',60,100,100),(None,'boundary_reset'))
    def test_no_route_geometry_proof(self): self.assertEqual(ComfortPreview().step(0,ExitEvidence('s','r','e',matched=False),'approach',60,100,100),(None,'inactive_or_unverified'))

def replay(path, output):
    counts=collections.Counter(); high36=0; pre=0
    with open(path,newline='') as src,open(output,'w',newline='') as dst:
        rows=csv.DictReader(src); w=csv.DictWriter(dst,fieldnames=['time','source','ego_kph','target_kph','road_valid','evidence_review','decision']);w.writeheader()
        for r in rows:
            ego,target=float(r['ego_kph']),float(r['target_kph']);s=r['source']
            # No independently confirmed exit match exists in this captured dataset.
            d=review(s,ego,target,r['road_valid']=='True',r['route_active']=='True',False)
            counts[s,d]+=1
            if s=='road' and ego>80 and target==36:
                high36+=1;assert d=='large_unverified_gap_display_only'
            if s=='pre':
                pre+=1;assert d.endswith('display_only')
            w.writerow({k:r[k] for k in ('time','source','ego_kph','target_kph','road_valid','evidence_review')} | {'decision':d})
    print('rows',sum(counts.values()),'high-speed ROAD36',high36,'unverified PRE',pre)
    for (s,d),n in sorted(counts.items()):print(s,d,n)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input');p.add_argument('output');a=p.parse_args()
    if not unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks)).wasSuccessful():raise SystemExit(1)
    replay(a.input,a.output)
