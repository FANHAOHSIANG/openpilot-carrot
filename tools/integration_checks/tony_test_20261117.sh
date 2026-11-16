#!/usr/bin/env bash
# Focused offline checks. Known inherited failures are documented separately.
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH=.:opendbc_repo:tools/jetlink
python -m pytest -c /dev/null --rootdir=. --noconftest -q \
  openpilot/selfdrive/carrot/tests/test_osm_curve.py \
  openpilot/selfdrive/carrot/tests/test_route_curve.py \
  openpilot/selfdrive/carrot/tests/test_route_curve_integration.py \
  openpilot/selfdrive/carrot/tests/test_curve_speed.py \
  openpilot/selfdrive/controls/tests/test_turn_accel.py \
  openpilot/selfdrive/controls/tests/test_longitudinal_preview.py \
  openpilot/selfdrive/controls/tests/test_longitudinal_preview_release.py
python tools/signal_validation/run.py \
  openpilot/selfdrive/carrot/server/tests/test_navigation_map.py \
  openpilot/selfdrive/carrot/server/tests/test_google_share.py \
  openpilot/selfdrive/carrot/tests/test_external_navigation_priority.py \
  openpilot/selfdrive/carrot/tests/test_radar_motion_predictor.py \
  tools/jetlink/test_spas_check.py tools/jetlink/tests/test_spas_identity.py
python tools/signal_validation/run.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_stopping.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_stop_object.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_casper_fault_reporting.py \
  opendbc_repo/opendbc/safety/tests/test_hyundai_canfd_alt_buttons.py \
  openpilot/selfdrive/controls/tests/test_controlsd_publish.py \
  openpilot/selfdrive/selfdrived/tests/test_vehicle_faults.py
python tools/signal_validation/run.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_low_speed_steer_reserve.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_optional_acan_lanes.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_hda2_raw_radar.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_sorento_2024.py
python tools/signal_validation/run.py \
  openpilot/common/tests/test_steering_learning.py \
  openpilot/selfdrive/carrot/server/tests/test_steering_learning_api.py \
  openpilot/selfdrive/controls/tests/test_live_lateral_geometry.py
python -m unittest discover -s tools/docs/wiki_settings/tests -p 'test_*.py' -q
cd openpilot/selfdrive/carrot/web
node --test tests/navigation_map.test.mjs 'tests/settings_*.test.mjs' tests/traditional_chinese.test.mjs
npm run build
