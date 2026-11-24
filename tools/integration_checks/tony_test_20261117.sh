#!/usr/bin/env bash
# Focused offline checks. Known inherited failures are documented separately.
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH=.:opendbc_repo:tools/jetlink
bash -n launch_chffrplus.sh
python -m pytest -c /dev/null --rootdir=. --noconftest -q openpilot/system/tests/test_c4_libjpeg_bootstrap.py
python -m pytest -c /dev/null --rootdir=. --noconftest -q openpilot/system/tests/test_c4_native_dependency_audit.py
python -m pytest -c /dev/null --rootdir=. --noconftest -q openpilot/system/tests/test_c4_cffi_abi.py
python -m pytest -c /dev/null --rootdir=. --noconftest -q openpilot/system/tests/test_c4_runtime_service_deps.py
python -m unittest -q openpilot.selfdrive.ui.tests.test_c4_scene_style
python -m unittest -q openpilot.selfdrive.modeld.tests.test_internal_builder_abi_contract
python -m pytest -c /dev/null --rootdir=. --noconftest -q openpilot/selfdrive/modeld/tests/test_internal_model_selection.py
python -m pytest -c /dev/null --rootdir=. --noconftest -q openpilot/selfdrive/carrot/server/tests/test_c4_scene_style_web.py
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
python tools/signal_validation/run.py \
  openpilot/selfdrive/car/tests/test_hyundai_kick.py \
  tools/jetlink/test_blinker_boundary.py \
  tools/jetlink/test_boundary_recent_intent.py \
  tools/jetlink/test_manual_turn_indicator.py \
  tools/jetlink/test_indicator_reconstruction.py \
  openpilot/selfdrive/car/tests/test_card_diagnostics.py \
  openpilot/selfdrive/carrot/server/tests/test_cockpit_page.py \
  openpilot/selfdrive/carrot/server/tests/test_road_detector_mime.py \
  openpilot/selfdrive/carrot/server/tests/test_web_settings_road_detector.py
python tools/signal_validation/run.py \
  opendbc_repo/opendbc/safety/tests/test_hyundai_canfd_steering_guard.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_classic_safety_stream.py \
  opendbc_repo/opendbc/safety/tests/test_hyundai_canfd_integrated_flags.py \
  opendbc_repo/opendbc/safety/tests/test_hyundai_canfd_spas_piggyback.py \
  openpilot/selfdrive/car/tests/test_canfd_steering_safety_config.py \
  openpilot/selfdrive/car/tests/test_cruise_settings.py \
  openpilot/selfdrive/car/tests/test_cruise_timing.py \
  openpilot/selfdrive/controls/tests/test_desire_helper_stalk.py \
  openpilot/selfdrive/controls/tests/test_lane_change_completion.py \
  openpilot/selfdrive/controls/tests/test_lane_change_takeover.py \
  openpilot/selfdrive/controls/tests/test_hkg_phase1.py \
  openpilot/selfdrive/controls/tests/test_low_speed_steer_reserve.py \
  openpilot/selfdrive/controls/tests/test_lateral_startup_control.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_steering_observations.py \
  openpilot/selfdrive/ui/tests/test_steering_learning_view.py \
  openpilot/selfdrive/pandad/tests/test_integrated_firmware_gate.py
python tools/signal_validation/run.py \
  formosalink/tests/test_training_contributions.py formosalink/tests/test_training_api.py \
  tools/training_studio/tests \
  openpilot/selfdrive/carrot/server/tests/test_training_data_http.py \
  openpilot/selfdrive/carrot/server/tests/test_navigation_google.py \
  openpilot/selfdrive/carrot/server/tests/test_compact_heartbeat.py
# Upstream 2026-11-24 source merge safety gate (Ioniq 5/EV6/PV5 cluster,
# parked SPAS, driver cruise ceiling, E2E/Autospeed). Preserve in long-term CI.
python tools/signal_validation/run.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_ccnc_cluster.py \
  opendbc_repo/opendbc/car/hyundai/tests/test_pv5_stock_cluster_lanes.py \
  openpilot/selfdrive/car/tests/test_hyundai_spas.py \
  openpilot/selfdrive/controls/tests/test_autospeed.py \
  openpilot/selfdrive/controls/tests/test_camera_e2e.py \
  openpilot/selfdrive/carrot/server/tests/test_planner_status.py \
  openpilot/selfdrive/carrot/server/tests/test_parked_indicator.py
python -m unittest discover -s tools/docs/wiki_settings/tests -p 'test_*.py' -q
cd openpilot/selfdrive/carrot/web
node --test tests/navigation_map.test.mjs 'tests/settings_*.test.mjs' tests/traditional_chinese.test.mjs 'tests/cockpit_*.test.mjs' tests/hud_constant_heartbeat.test.mjs tests/training_data.test.mjs tests/compact_connection.test.mjs tests/navigation_google.test.mjs
npm run build
