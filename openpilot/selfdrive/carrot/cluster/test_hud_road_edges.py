from dataclasses import dataclass, replace
from types import SimpleNamespace as NS
from unittest import TestCase
from hud_road_edges import filter_live_targets, outside_road


def curve(start, end):
    return (NS(forward_m=10., lateral_m=start), NS(forward_m=20., lateral_m=end))


@dataclass
class State:
    left_road_edge_points: tuple = curve(-6., -2.)
    right_road_edge_points: tuple = curve(2., 6.)
    left_road_edge_confidence: float = .91
    right_road_edge_confidence: float = .91
    road_edge_filter_active: bool = True
    detected_vehicles: tuple = ()
    radar_points: tuple = ()


class RoadEdgesTest(TestCase):
    def test_curved_edges_are_measured_at_object_distance(self):
        state = State()
        self.assertFalse(outside_road(state, 5., 15.))
        self.assertTrue(outside_road(state, 5.5, 15.))
        self.assertTrue(outside_road(state, -5.5, 15.))
        self.assertFalse(outside_road(state, 5.5, 20.))

    def test_missing_weak_crossed_and_extrapolated_edge(self):
        state = State(right_road_edge_confidence=.3)
        self.assertFalse(outside_road(state, 9., 15.))
        self.assertFalse(outside_road(state, -9., 25.))
        self.assertTrue(outside_road(state, -9., 15.))
        self.assertFalse(outside_road(State(right_road_edge_points=curve(-7., -8.)), -10., 15.))
        self.assertFalse(outside_road(State(left_road_edge_points=()), -9., 15.))

    def test_stale_input_and_lead_and_cut_in(self):
        objs = [NS(lateral_m=6., longitudinal_m=15., primary=i==1, cut_in=i==2) for i in range(3)]
        state=State(detected_vehicles=tuple(objs), radar_points=(objs[0],), road_edge_filter_active=False)
        self.assertIs(filter_live_targets(state, 9., 10.), state)
        output=filter_live_targets(state, 9.7, 10.)
        self.assertEqual(output.detected_vehicles, tuple(objs[1:]))
        self.assertFalse(output.radar_points)
        self.assertTrue(output.road_edge_filter_active)
