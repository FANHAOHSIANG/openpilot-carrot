import math
import pytest
from openpilot.selfdrive.carrot.carrot_navi_cereal import build_carrot_navi_payload
from openpilot.selfdrive.carrot.carrot_navi_control import parse_carrot_navi_control


def _snapshot(points):
  return {"connected": True, "session_id": "route-test", "items": {
    "route": {"present": True, "sequence": 1, "value": {"polyline": points}},
  }}


@pytest.mark.parametrize("size", [300, 4096])
def test_route_keeps_destination_beyond_legacy_256_points(size):
  points = [{"lat": 24 + i * .000001, "lon": 121} for i in range(size)]
  result = parse_carrot_navi_control(build_carrot_navi_payload(_snapshot(points)))
  assert result.route.present
  assert len(result.route.polyline) == size
  assert result.route.polyline[-1] == (points[-1]["lat"], points[-1]["lon"])


def test_over_budget_route_is_withdrawn_instead_of_truncated():
  points = [{"lat": 24, "lon": 121}] * 4097
  result = parse_carrot_navi_control(build_carrot_navi_payload(_snapshot(points)))
  assert not result.route.present
  assert result.route.polyline == ()


@pytest.mark.parametrize("bad", [None, True, "24.5", math.nan, math.inf, 91, -91, 10**400])
def test_bad_coordinate_invalidates_whole_geometry(bad):
  points = [{"lat": 24, "lon": 121}, {"lat": bad, "lon": 121}]
  result = parse_carrot_navi_control(build_carrot_navi_payload(_snapshot(points)))
  assert not result.route.present
  assert result.route.polyline == ()


def test_consumer_also_rejects_over_budget_cereal_message():
  result = parse_carrot_navi_control({"schemaVersion": 1, "connected": True,
    "route": {"meta": {"present": True}, "polyline": [{"latitude": 24, "longitude": 121}] * 4097}})
  assert not result.route.present
  assert result.route.polyline == ()


def test_consumer_withdraws_unreadable_polyline():
  result = parse_carrot_navi_control({"schemaVersion": 1, "connected": True,
    "route": {"meta": {"present": True}, "polyline": 42}})
  assert not result.route.present
  assert result.route.polyline == ()
