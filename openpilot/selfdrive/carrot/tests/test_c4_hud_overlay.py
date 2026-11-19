import json
import math
import os
import signal
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cluster"))
from hud_objects import HudObjectReader, pair_objects


def calibration(**changes):
  fields = dict(calStatus="calibrated", rpyCalib=[0., 0., 0.], wideFromDeviceEuler=[0., 0., 0.], height=[1.25])
  return SimpleNamespace(**(fields | changes))


def row(kind, u=.52, v=.72):
  return [kind, u, v, .04, .10, .92]


def write(path, objects=(), t=10., **fields):
  data = {"version": 1, "camera": "road", "t": t, "objects": objects}
  path.write_text(json.dumps(data | fields))


def read(reader, now=10., **changes):
  return reader.read(now, "mici", "os04c10", calibration(**changes))


def test_camera_ground_position_with_mici_lens_and_yaw(tmp_path):
  # An independent forward projection of the known contact point through the ROAD lens.
  forward, right, height, yaw = 12., .8, 1.25, .05
  x_device = math.cos(yaw) * forward - math.sin(yaw) * right
  y_device = math.sin(yaw) * forward + math.cos(yaw) * right
  u = .5 + 1141.5 * y_device / (1344 * x_device)
  v = .5 + 1141.5 * height / (760 * x_device)
  path = tmp_path / "objects.json"
  write(path, [row("person", u, v), row("cone", u, .40)])
  objects = read(HudObjectReader(path), rpyCalib=[0., 0., yaw])
  assert [obj.kind for obj in objects] == ["person"]
  assert objects[0].forward == pytest.approx(forward)
  assert objects[0].right == pytest.approx(right)


def test_both_lenses_use_their_own_geometry_and_capture_time(tmp_path):
  path = tmp_path / "objects.json"
  write(path, t=10., batches=[
    {"camera": "wideRoad", "t": 9.4, "objects": [row("truck")]},
    {"camera": "road", "t": 10., "objects": [row("cone")]},
  ])
  reader = HudObjectReader(path)
  values = {obj.kind: obj for obj in read(reader, now=10.1)}
  assert values.keys() == {"truck", "cone"}
  assert values["truck"].camera == "wideRoad"
  assert values["truck"].t == 9.4
  assert values["cone"].camera == "road"
  assert values["truck"].forward / values["cone"].forward == pytest.approx(425.25 / 1141.5)
  assert [obj.kind for obj in read(reader, now=10.45)] == ["cone"]
  assert not read(reader, now=11.01)


def test_missing_wide_extrinsics_hides_only_wide_detections(tmp_path):
  path = tmp_path / "objects.json"
  write(path, batches=[
    {"camera": "wideRoad", "t": 10., "objects": [row("car")]},
    {"camera": "road", "t": 10., "objects": [row("motorcycle")]},
  ])
  assert [obj.kind for obj in read(HudObjectReader(path), wideFromDeviceEuler=[])] == ["motorcycle"]


@pytest.mark.parametrize("device,sensor,cal", [
  ("mici", "new_sensor", calibration()), ("mici", "os04c10", calibration(calStatus="uncalibrated")),
  ("mici", "os04c10", calibration(height=[])), ("mici", "os04c10", calibration(rpyCalib=[0., float("nan"), 0.])),
])
def test_invalid_calibration_or_unknown_lens_never_places_target(tmp_path, device, sensor, cal):
  path = tmp_path / "objects.json"
  write(path, [row("car")])
  assert not HudObjectReader(path).read(10., device, sensor, cal)


def test_dropped_invalid_and_future_observations_do_not_create_hud_targets(tmp_path):
  path = tmp_path / "objects.json"
  assert not read(HudObjectReader(path))
  write(path, [row("car")], t=18.)
  assert not read(HudObjectReader(path))
  path.write_text("{unfinished")
  assert not read(HudObjectReader(path))
  write(path, [row("bogus"), row("person", u=-.2), row("car", v=2.), row("cone")])
  assert [obj.kind for obj in read(HudObjectReader(path))] == ["cone"]


def test_nonregular_or_linked_snapshot_clears_objects_without_blocking(tmp_path):
  path = tmp_path / "objects"
  reader = HudObjectReader(path)
  write(path, [row("person")])
  assert read(reader)
  path.unlink()
  os.mkfifo(path)

  def timeout(*_):
    pytest.fail("HUD renderer blocked while reading the object snapshot")

  old_handler = signal.signal(signal.SIGALRM, timeout)
  signal.alarm(3)
  try:
    assert not read(reader, now=10.11)
  finally:
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old_handler)
  path.unlink()
  other = tmp_path / "other"
  write(other, [row("car")])
  path.symlink_to(other)
  assert not read(reader, now=10.22)
  path.unlink()
  write(path, [row("cone")])
  assert [o.kind for o in read(reader, now=10.33)] == ["cone"]


def test_native_lead_matches_at_most_one_visual_car_and_never_a_pedestrian(tmp_path):
  path = tmp_path / "objects.json"
  write(path, [row("car", .50), row("car", .53), row("person", .50), row("motorcycle", .85)])
  objects = read(HudObjectReader(path))
  lead = SimpleNamespace(center=SimpleNamespace(x=-1.4), longitudinal_m=objects[0].forward,
                         source="radarState", label="L1", primary=True)
  ego = SimpleNamespace(center=SimpleNamespace(x=0.), longitudinal_m=None, source="", label="", primary=False)
  scene = SimpleNamespace(scene_shift_x_m=1.4, vehicles=(ego, lead))
  retained, _ = pair_objects(objects, scene, 10.)
  assert sorted(obj.kind for obj in retained) == ["car", "motorcycle", "person"]
  assert next(obj.u for obj in retained if obj.kind == "car") == pytest.approx(.53)
  assert not any(pair_objects(objects, scene, 11.1))


def test_road_boxes_require_matching_lens_and_camera_capture_time(tmp_path, monkeypatch):
  import pyray as rl
  from hud_objects import draw_road_boxes

  path = tmp_path / "objects.json"
  write(path, batches=[
    {"camera": "wideRoad", "t": 10., "objects": [row("truck", .7)]},
    {"camera": "road", "t": 10., "objects": [row("car", .4)]},
  ])
  objects = read(HudObjectReader(path))
  dest = rl.Rectangle(10, 20, 500, 300)
  projection = SimpleNamespace(video_dest=dest, dest=dest)
  rectangles = []
  monkeypatch.setattr(rl, "draw_rectangle_lines_ex", lambda rect, *_: rectangles.append(rect))

  def boxes(t, is_wide, now):
    rectangles.clear()
    draw_road_boxes(objects, projection, (1, t, 1344, 760, is_wide), now)
    return [(r.x + r.width / 2, r.y + r.height) for r in rectangles]

  (narrow_center,) = boxes(10.10, False, 10.11)
  (wide_center,) = boxes(10.10, True, 10.11)
  assert narrow_center == pytest.approx((210., 236.))
  assert wide_center == pytest.approx((360., 236.))
  assert not boxes(10.4, False, 10.4)
  assert not boxes(10., False, 11.5)


def test_disabled_live_hud_does_not_read_packets_and_enabled_hud_receives_calibrated_objects(tmp_path, monkeypatch):
  from dataclasses import replace
  import cluster_live
  from cluster_live import OpenpilotLiveSource, standby_state

  source = object.__new__(OpenpilotLiveSource)
  source._energy_gauge_label = "fuel"
  source._max_lateral_accel = 3.
  source._carrot_navi_media = None
  source._current_carrot_navi = lambda _: None
  enabled = False
  source.params = SimpleNamespace(get_bool=lambda key: key == "C4HudObjects" and enabled, external_compute_label=lambda: "")
  now = 10.
  monkeypatch.setattr(cluster_live.time, "monotonic", lambda: now)
  services = {"deviceState": SimpleNamespace(started=True, deviceType="mici"), "liveCalibration": calibration(),
              "roadCameraState": SimpleNamespace(sensor="os04c10")}
  source._service_alive = lambda service: service in services
  source._service_valid = lambda service: service in services
  source._service_receive_time = lambda service: now
  source._service_data = services.get
  state = replace(standby_state(), camera_device_type="mici", camera_sensor="os04c10")
  calls = []
  path = tmp_path / "objects.json"
  real_reader = HudObjectReader(path)

  def record(*args, **kwargs):
    calls.append(1)
    return real_reader.read(*args, **kwargs)

  source._hud_objects_reader = SimpleNamespace(read=record)
  assert not source._with_live_hud_state(state).hud_objects
  assert not calls
  enabled = True
  now = 11.1
  write(path, [row("person")], t=now)
  assert [item.kind for item in source._with_live_hud_state(state).hud_objects] == ["person"]
  assert calls == [1]


def test_four_object_classes_draw_at_their_calibrated_lateral_position(tmp_path, monkeypatch):
  import pyray as rl
  from cluster_live import standby_state
  from hud_objects import draw_scene_objects

  path = tmp_path / "objects.json"
  kinds = ("person", "car", "motorcycle", "cone")
  write(path, [row(kind, u) for kind, u in zip(kinds, (.20, .40, .60, .80), strict=True)])
  objects = read(HudObjectReader(path))
  scene = SimpleNamespace(scene_shift_x_m=2.2, vehicles=())
  centers = []

  def record(position, *_):
    centers.append(position.x + scene.scene_shift_x_m)

  for function in ("draw_sphere_ex", "draw_cube", "draw_cylinder_ex"):
    monkeypatch.setattr(rl, function, record)
  draw_scene_objects(objects, scene, standby_state(), 10.1)
  assert {obj.kind for obj in objects} == set(kinds)
  for obj in objects:
    assert any(abs(x - obj.right) < .02 for x in centers)
  centers.clear()
  draw_scene_objects(objects, scene, standby_state(), 11.1)
  assert not centers


@pytest.fixture
def detected_motorcycle(tmp_path):
  from cluster_scene import Vec3, VehicleBox

  path = tmp_path / "objects.json"
  write(path, [row("motorcycle")])
  (bike,) = read(HudObjectReader(path))
  shift = 1.3
  warning = (255, 76, 43, 255)
  native = VehicleBox(center=Vec3(bike.right - shift + .2, 27., .80),
                      width_m=1.8, length_m=4.5, height_m=1.6,
                      right_x=1., right_y=0., forward_x=0., forward_y=1.,
                      body_color=warning, rear_color=warning, outline_color=warning,
                      side_color=warning, top_highlight=warning, source="radarState",
                      label="L1", longitudinal_m=bike.forward + .2, absolute_speed_kph=32., primary=True, cut_in=True)
  return bike, native, SimpleNamespace(scene_shift_x_m=shift, vehicles=(native,))


def test_a_single_motorcycle_tag_keeps_the_original_lead_pose_warning_and_metrics(detected_motorcycle):

  bike, native, scene = detected_motorcycle
  bodies, tags = pair_objects((bike,), scene, 10.1)
  assert not bodies
  assert len(tags) == 1
  assert tags[0][0] is bike
  assert tags[0][1] is native
  assert native.primary and native.cut_in
  assert native.body_color == (255, 76, 43, 255)
  assert native.label == "L1" and native.absolute_speed_kph == 32.
  assert not any(pair_objects((bike,), scene, 11.1))


@pytest.mark.parametrize("ambiguity", ("two_visuals", "two_native_vehicles"))
def test_ambiguous_matching_does_not_assign_motorcycle_class(ambiguity, detected_motorcycle):
  from dataclasses import replace

  bike, native, scene = detected_motorcycle
  visuals = (bike,)
  if ambiguity == "two_visuals":
    visuals += (replace(bike, kind="car", right=bike.right + .3),)
  else:
    neighboring = replace(native, center=replace(native.center, x=native.center.x + .4), label="L2")
    scene = SimpleNamespace(scene_shift_x_m=scene.scene_shift_x_m, vehicles=(native, neighboring))
  assert not pair_objects(visuals, scene, 10.1)[1]


def test_matched_motorcycle_draws_only_a_tag_above_the_native_body(detected_motorcycle, monkeypatch):
  import pyray as rl
  from cluster_live import standby_state
  from hud_objects import draw_scene_objects

  obj, native, scene = detected_motorcycle
  centers = []

  def record(pos, *_):
    centers.append((pos.x, pos.y, pos.z))

  for method in ("draw_cube", "draw_cylinder_ex"):
    monkeypatch.setattr(rl, method, record)
  draw_scene_objects((obj,), scene, standby_state(), 10.1)
  assert centers
  assert all(abs(x - native.center.x) < .6 and abs(y - native.center.y) < .10 and z > native.height_m
             for x, y, z in centers)


def test_road_motorcycle_tag_only_on_contemporaneous_matching_lens(detected_motorcycle, monkeypatch):
  import pyray as rl
  from hud_objects import draw_road_boxes

  obj, native, scene = detected_motorcycle
  bodies, tags = pair_objects((obj,), scene, 10.1)
  assert not bodies
  assert tags == ((obj, native),)
  dest = rl.Rectangle(10, 20, 500, 300)
  projection = SimpleNamespace(video_dest=dest, dest=dest)
  calls = []
  for method in ("draw_circle_lines", "draw_line_ex"):
    monkeypatch.setattr(rl, method, lambda *args: calls.append(args))
  monkeypatch.setattr(rl, "draw_rectangle_lines_ex", lambda *_: pytest.fail("Matched motorcycle got a second body"))
  draw_road_boxes(bodies, projection, (1, 10.05, 1344, 760, False), 10.1, motorcycle_tags=tags)
  assert calls
  for t, wide, now in ((10.05, True, 10.1), (10.4, False, 10.41), (10., False, 11.1)):
    calls.clear()
    draw_road_boxes(bodies, projection, (1, t, 1344, 760, wide), now, motorcycle_tags=tags)
    assert not calls
