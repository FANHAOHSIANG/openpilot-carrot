"""Hide unambiguous off-road objects in the cluster display's road coordinates."""
from dataclasses import replace
from math import isfinite


def edge_at(points, forward):
    # model_line_points orders these samples by forward distance. Never extend
    # the first or last segment: an unseen road edge can turn in either direction.
    for left, right in zip(points, points[1:]):
        if left.forward_m <= forward <= right.forward_m:
            span = right.forward_m - left.forward_m
            if 0 < span <= 15:
                fraction = (forward - left.forward_m) / span
                return left.lateral_m + fraction * (right.lateral_m - left.lateral_m)
            break
    return None


def outside_road(state, right, forward, margin=1.25):
    if not getattr(state, "road_edge_filter_active", False) or not 0 < forward or not isfinite(right):
        return False
    left = (edge_at(state.left_road_edge_points, forward)
            if state.left_road_edge_confidence >= .75 else None)
    edge = (edge_at(state.right_road_edge_points, forward)
            if state.right_road_edge_confidence >= .75 else None)
    if left is not None and edge is not None and not left < edge:
        return False
    return ((left is not None and right < left - margin)
            or (edge is not None and right > edge + margin))


def filter_live_targets(state, received, now):
    if received is None or not 0 <= now - received < .5:
        return state
    state = replace(state, road_edge_filter_active=True)
    vehicles = tuple(v for v in state.detected_vehicles if v.primary or v.cut_in
                     or not outside_road(state, v.lateral_m, v.longitudinal_m))
    radar = tuple(p for p in state.radar_points if not outside_road(state, p.lateral_m, p.longitudinal_m))
    return replace(state, detected_vehicles=vehicles, radar_points=radar)
