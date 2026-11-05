"""Presentation data checks: avoid guessed ranges, targets and control state."""
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import pytest

CLUSTER = Path(__file__).resolve().parents[2]/'openpilot/selfdrive/carrot/cluster'
sys.path.insert(0,str(CLUSTER))
from cluster_henry_layout import HenryLayout, metric_values, project, formatted


@pytest.mark.parametrize('d,lat', [(None,1),(0,1),(float('nan'),1),(20,float('inf')),(101,0),(2,31)])
def test_unavailable_or_invalid_range_is_not_placed(d,lat):
  assert project(d,lat) is None


def test_perspective_keeps_real_distance_order_and_lateral_direction():
  assert project(11,-2)[0] < 960 < project(19,3)[0]
  assert project(11,0)[1] > project(19,0)[1]


def test_unknown_metrics_do_not_become_fake_zeroes():
  state = NS(detected_vehicles=(),speed_kph=44.)
  assert metric_values(state) == (None,)*5
  assert formatted(None) == '—' and formatted(float('nan')) == '—'
  assert formatted(0) == '0'


def test_metrics_use_primary_lead_and_actual_available_inputs():
  state = NS(detected_vehicles=(NS(primary=False,longitudinal_m=12,relative_speed_mps=5),
                               NS(primary=True,longitudinal_m=20,relative_speed_mps=-2)),
             speed_kph=36,planned_accel_mps2=-.4,steering_output_normalized=.05,
             planned_curvature_m_inv=.002,vision_yaw_rate_rps=.01)
  assert metric_values(state) == pytest.approx((-7.2,-.4,.05,.2,.1))


def test_plain_app_is_unchanged_and_trial_requires_explicit_layout(monkeypatch):
  monkeypatch.delenv('CARROT_HUD_LAYOUT',raising=False)
  assert HenryLayout().draw(None,None) is False
  monkeypatch.setenv('CARROT_HUD_LAYOUT','henry-v2')
  assert HenryLayout().enabled
