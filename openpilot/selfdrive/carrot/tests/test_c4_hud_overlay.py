import json
import math
import os
import signal
from pathlib import Path
from dataclasses import replace
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


@pytest.fixture
def icon_calls(monkeypatch):
  import hud_objects
  calls = []
  def record(anchors, bounds, size, metric_rects=()):
    values = list(anchors)
    calls.append((values, bounds, size))
    return len(values)
  monkeypatch.setattr(hud_objects, "draw_class_icons", record)
  for name in ("begin_scissor_mode", "end_scissor_mode"):
    monkeypatch.setattr(hud_objects.rl, name, lambda *_: None)
  return calls


def test_road_boxes_require_matching_lens_and_camera_capture_time(tmp_path, monkeypatch, icon_calls):
  import pyray as rl
  from hud_objects import draw_road_objects

  path = tmp_path / "objects.json"
  write(path, batches=[
    {"camera": "wideRoad", "t": 10., "objects": [row("truck", .7)]},
    {"camera": "road", "t": 10., "objects": [row("car", .4)]},
  ])
  objects = read(HudObjectReader(path))
  dest = rl.Rectangle(10, 20, 500, 300)
  clipped = rl.Rectangle(30, 50, 410, 230)
  projection = SimpleNamespace(video_dest=dest, dest=clipped)
  scene = SimpleNamespace(vehicles=(), scene_shift_x_m=0.)
  rectangles = []
  monkeypatch.setattr(rl, "draw_rectangle_lines_ex", lambda rect, *_: rectangles.append(rect))

  def boxes(t, is_wide, now):
    rectangles.clear()
    icon_calls.clear()
    count = draw_road_objects(objects, scene, projection, (1, t, 1344, 760, is_wide), now, 24.)
    assert count == len(rectangles)
    if count:
      (anchors, bounds, size), = icon_calls
      assert bounds == (30, 50, 440, 280) and size == 24.
      kind, center_x, top_y = anchors[0]
      assert kind == ("truck" if is_wide else "car")
      assert (center_x, top_y) == pytest.approx((360. if is_wide else 210., 206.))
    else:
      assert not icon_calls
    return [(r.x + r.width / 2, r.y + r.height) for r in rectangles]

  (narrow_center,) = boxes(10.10, False, 10.11)
  (wide_center,) = boxes(10.10, True, 10.11)
  assert narrow_center == pytest.approx((210., 236.))
  assert wide_center == pytest.approx((360., 236.))
  assert not boxes(10.4, False, 10.4)
  assert not boxes(10., False, 11.5)


def test_disabled_live_hud_does_not_read_packets_and_enabled_hud_receives_calibrated_objects(tmp_path, monkeypatch):
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


def test_road_motorcycle_tag_only_on_contemporaneous_matching_lens(detected_motorcycle, monkeypatch, icon_calls):
  import pyray as rl
  from hud_objects import draw_road_objects

  obj, native, scene = detected_motorcycle
  # The wrong-lens row and out-of-sync row would both fit the native vehicle more closely.
  other = replace(obj, kind="car", right=native.center.x + scene.scene_shift_x_m, forward=native.longitudinal_m)
  objects = (replace(other, camera="wideRoad"), replace(other, t=9.61), obj)
  dest = rl.Rectangle(10, 20, 500, 300)
  projection = SimpleNamespace(video_dest=dest, dest=dest)
  monkeypatch.setattr(rl, "draw_rectangle_lines_ex", lambda *_: pytest.fail("Matched motorcycle got a second body"))
  assert draw_road_objects(objects, scene, projection, (1, 10.05, 1344, 760, False), 10.1, 24.) == 1
  (anchors, _, _), = icon_calls
  assert len(anchors) == 1 and anchors[0][0] == "motorcycle"
  assert anchors[0][1:] == pytest.approx((10 + 500*obj.u, 20 + 300*(obj.v-obj.h)))
  for t, wide, now in ((10.05, True, 10.1), (10.4, False, 10.41), (10., False, 11.1)):
    icon_calls.clear()
    assert draw_road_objects((obj,), scene, projection, (1, t, 1344, 760, wide), now, 24.) == 0
    assert not icon_calls


def test_ambiguous_road_match_keeps_both_measured_class_locations(detected_motorcycle, monkeypatch, icon_calls):
  import pyray as rl
  from hud_objects import draw_road_objects

  bike, _, scene = detected_motorcycle
  car = replace(bike, kind="car", u=.64, right=bike.right+.3)
  rect = rl.Rectangle(10, 20, 500, 300)
  projection = SimpleNamespace(video_dest=rect, dest=rect)
  boxes = []
  monkeypatch.setattr(rl, "draw_rectangle_lines_ex", lambda rect, *_: boxes.append(rect))
  assert draw_road_objects((bike, car), scene, projection, (1, 10., 1344, 760, False), 10.1, 24.) == 2
  assert len(boxes) == 1  # One native vehicle supplies the other body.
  (anchors, _, _), = icon_calls
  positions = {kind: (x, y) for kind, x, y in anchors}
  assert set(positions) == {"motorcycle", "car"}
  for obj in (bike, car):
    assert positions[obj.kind] == pytest.approx((10 + obj.u*500, 20 + (obj.v-obj.h)*300))


@pytest.mark.parametrize("view", [0, 2])
def test_driving_panel_confirms_a_fresh_visual_match_once_in_3d_and_camera(view, detected_motorcycle, monkeypatch, icon_calls):
  import cluster_renderer as cr
  from cluster_live import standby_state

  bike, _, scene = detected_motorcycle
  car = replace(bike, kind="car")
  assert pair_objects((car,), scene, 10.1) == ((), ())  # The native lead already supplies its body.
  state = replace(standby_state(), onroad=True, camera_view_mode=view, hud_objects=(car,))
  renderer = cr.ClusterUiRenderer(screen_mode=5)
  t = 10.1
  camera = SimpleNamespace(display_frame=(5, 10.05, 1344, 760, False), draw=lambda area: True)
  rect = cr.rl.Rectangle(0, 0, 1124, 462)
  texts = []
  monkeypatch.setattr(cr.time, "monotonic", lambda: t)
  monkeypatch.setattr(cr.time, "clock_gettime", lambda clock: t)
  monkeypatch.setattr(renderer, "_scene_for_state", lambda *_: scene)
  monkeypatch.setattr(renderer, "_draw_scene", lambda _scene, state, _lights: renderer._draw_scene_class_icons(
    state, None, (0, 0, renderer.width, renderer.height)))
  monkeypatch.setattr(cr, "world_to_screen_label_anchor", lambda *_: SimpleNamespace(x=300., y=100.))
  monkeypatch.setattr(renderer, "_select_camera_overlay_stream", lambda *_: False)
  monkeypatch.setattr(renderer, "_camera_overlay_projection", lambda *_: SimpleNamespace(dest=rect, video_dest=rect))
  monkeypatch.setattr(renderer, "_live_road_camera_view", lambda: camera)
  monkeypatch.setattr(renderer, "_draw_signal_detections", lambda *_: None)
  def native_overlay(*_):
    assert not icon_calls  # Draw class icons after the projected native lane and vehicle geometry.
  monkeypatch.setattr(renderer, "_draw_camera_projected_overlay", native_overlay)
  monkeypatch.setattr(renderer, "_draw_text_with_stroke", lambda text, *_, **kw: texts.append(text))
  for op in ("clear_background", "begin_scissor_mode", "end_scissor_mode", "draw_rectangle_rec"):
    monkeypatch.setattr(cr.rl, op, lambda *_: None)
  monkeypatch.setattr(cr.rl, "draw_rectangle_lines_ex", lambda *_: pytest.fail("Matched car got a second box"))

  def render(objects):
    texts.clear()
    icon_calls.clear()
    renderer._render_world(replace(state, hud_objects=objects), (False, False))
    return list(texts)

  assert render((car,)) == ["AI 1"]
  if view == 2:
    assert [a[0] for a in icon_calls[0][0]] == ["car"]
  assert not render(())  # A native lead with no camera confirmation.
  t = 11.2
  assert not render((car,))
  if view == 2:
    t = 10.1
    assert not render((replace(car, camera="wideRoad"),))
    camera.display_frame = (6, 9.6, 1344, 760, False)
    assert not render((car,))  # The HUD is displaying a different capture.


@pytest.mark.parametrize("swapped", [False, True])
def test_mode_five_class_icons_share_world_coordinates_and_vehicle_viewport(swapped, detected_motorcycle, monkeypatch):
  import cluster_renderer as cr
  import hud_objects
  from cluster_live import standby_state
  from cluster_scene import Vec3, render_scene_forward_m

  bike, native, scene = detected_motorcycle
  car = replace(bike, kind="car")
  person = replace(bike, kind="person", right=-1.8, forward=bike.forward+4.)
  expired = replace(bike, kind="truck", t=8.)
  state = replace(standby_state(), onroad=True, camera_view_mode=0, hud_objects=(car, person, expired))
  scene.camera = SimpleNamespace(position=Vec3(0, -5, 4), target=Vec3(0, 20, 0), fovy_deg=60.)
  scene.lane_markings = scene.road_edges = scene.highlight_lanes = scene.planned_path = scene.radar_points = ()
  renderer = cr.ClusterUiRenderer(screen_mode=5, panel_layout=int(swapped))
  assert not pair_objects((car,), scene, 10.1)[0]  # Only one native body for the car.
  projected = []
  icons = []
  viewport = []
  translations = []
  events = []
  monkeypatch.setattr(cr.time, "monotonic", lambda: 10.1)
  monkeypatch.setattr(cr, "clean_ui_enabled", lambda: False)
  monkeypatch.setattr(cr.rl, "rl_viewport", lambda x, *_: viewport.append(x))
  monkeypatch.setattr(cr.rl, "rl_translatef", lambda x, *_: translations.append(x))
  for method in ("begin_mode_3d", "end_mode_3d", "rl_push_matrix", "rl_pop_matrix"):
    monkeypatch.setattr(cr.rl, method, lambda *_: None)
  monkeypatch.setattr(renderer, "_draw_vehicle", lambda v: events.append(v))
  monkeypatch.setattr(hud_objects, "draw_scene_objects", lambda *_: None)
  monkeypatch.setattr(renderer, "_draw_radar_point_labels", lambda *_: None)
  label_rect = (486., 201., 94., 56.)
  def native_metrics(_vehicles, _camera, _shift, _info_mode, _color_mode, metric_rects):
    metric_rects.append(label_rect)
    events.append("metrics")
  monkeypatch.setattr(renderer, "_draw_vehicle_badges", native_metrics)

  def project(point, camera, width, height):
    projected.append((point.x, point.y, point.z))
    return SimpleNamespace(x=renderer.width / 2 + point.x*10, y=height / 2 - point.y)

  def record(anchors, bounds, size, metric_rects=()):
    assert metric_rects == [label_rect]  # Already in the translated label matrix.
    offset = translations[-1]
    assert viewport[-1] == 0  # Now drawing with the translated 2D label matrix.
    events.append("icons")
    icons.extend((kind, x+offset, y) for kind, x, y in anchors)
    left, top, right, bottom = bounds
    panel_start = cr.NAVI_LIVE_PANEL_W if swapped else 0.
    assert (left+offset, top, right+offset, bottom) == pytest.approx(
      (panel_start, 0, panel_start+cr.NAVI_LIVE_PANEL_X, renderer.height))
    return len(icons)

  monkeypatch.setattr(cr, "world_to_screen_label_anchor", project)
  monkeypatch.setattr(hud_objects, "draw_class_icons", record)
  assert renderer._draw_scene(scene, state, (False, False)) == 2
  assert events == [native, "metrics", "icons"]
  assert [kind for kind, _, _ in icons] == ["car", "person"]
  assert translations[0] == pytest.approx(scene.scene_shift_x_m)
  assert translations[-1] == pytest.approx(viewport[0])
  for (wx, wy, wz), (_, x, y), obj in zip(projected, icons, (car, person), strict=True):
    assert wx == pytest.approx(obj.right)
    assert wy == pytest.approx(render_scene_forward_m(obj.forward, state))
    assert wz > 0.
    assert (x, y) == pytest.approx((renderer.width / 2 + obj.right*10 + viewport[0], renderer.height / 2 - wy))


def test_partly_visible_video_box_keeps_an_icon_at_visible_intersection(detected_motorcycle, monkeypatch, icon_calls):
  import pyray as rl
  from hud_objects import draw_road_objects

  bike, _, _ = detected_motorcycle
  video = rl.Rectangle(-50, -20, 600, 400)
  crop = rl.Rectangle(100, 100, 350, 200)
  projection = SimpleNamespace(video_dest=video, dest=crop)
  scene = SimpleNamespace(vehicles=(), scene_shift_x_m=0.)
  # [70,130] x [80,160] intersects the displayed video at [100,130] x [100,160].
  partial = replace(bike, kind="person", u=.25, v=.45, w=.1, h=.2)
  outside = replace(bike, kind="cone", u=.1, v=.1, w=.02, h=.02)
  monkeypatch.setattr(rl, "draw_rectangle_lines_ex", lambda *_: None)
  assert draw_road_objects((partial, outside), scene, projection, (1, 10., 1344, 760, False), 10.1, 24) == 1
  (anchors, _, _), = icon_calls
  assert len(anchors) == 1 and anchors[0][0] == "person"
  assert anchors[0][1:] == pytest.approx((115., 100.))


def test_seven_coincident_video_classes_remain_legible_and_count_only_visible_icons(detected_motorcycle, monkeypatch):
  from itertools import combinations
  import cluster_renderer as cr
  import hud_objects
  from cluster_live import standby_state

  baseline, _, _ = detected_motorcycle
  kinds = ("person", "car", "motorcycle", "cone", "bicycle", "bus", "truck")
  objects = tuple(replace(baseline, kind=kind) for kind in kinds)
  rect = cr.rl.Rectangle(100, 20, 600, 300)
  video = cr.rl.Rectangle(0, 0, 800, 350)
  projection = SimpleNamespace(dest=rect, video_dest=video)
  state = replace(standby_state(), onroad=True, camera_view_mode=2, hud_objects=objects)
  renderer = cr.ClusterUiRenderer(screen_mode=5)
  scene = SimpleNamespace(vehicles=(), scene_shift_x_m=0.)
  icons, texts, leaders = [], [], []
  monkeypatch.setattr(cr.time, "monotonic", lambda: 10.1)
  monkeypatch.setattr(renderer, "_scene_for_state", lambda *_: scene)
  monkeypatch.setattr(renderer, "_select_camera_overlay_stream", lambda *_: False)
  monkeypatch.setattr(renderer, "_camera_overlay_projection", lambda *_: projection)
  monkeypatch.setattr(renderer, "_draw_camera_background", lambda *_: (1, 10., 1344, 760, False))
  # This native camera label occupies the first pictogram position for this target.
  metric = (baseline.u*video.width - 39., (baseline.v-baseline.h)*video.height - 42., 36., 36.)
  def native_overlay(_scene, _state, _projection, metric_rects):
    metric_rects.append(metric)
  monkeypatch.setattr(renderer, "_draw_camera_projected_overlay", native_overlay)
  monkeypatch.setattr(renderer, "_draw_text_with_stroke", lambda text, *_, **kw: texts.append(text))
  for method in ("clear_background", "draw_rectangle_lines_ex", "begin_scissor_mode", "end_scissor_mode"):
    monkeypatch.setattr(cr.rl, method, lambda *_: None)
  monkeypatch.setattr(cr.rl, "draw_line_ex", lambda start, end, *_: leaders.append((start.x, start.y, end.x, end.y)))
  monkeypatch.setattr(hud_objects, "draw_object_icon", lambda *args: icons.append(args))

  renderer._render_world(state, (False, False))
  assert texts == ["AI 7"]
  assert {kind for kind, x, y, size in icons} == set(kinds) and len(icons) == 7
  for (_, x, y, size), (_, other_x, other_y, _) in combinations(icons, 2):
    assert max(abs(other_x-x), abs(other_y-y)) >= size
  for _, x, y, size in icons:
    assert not cr.rectangles_overlap((x-size/2, y-size/2, size, size), metric)
    assert rect.x <= x-size/2 <= x+size/2 <= rect.x+rect.width
    assert rect.y <= y-size/2 <= y+size/2 <= rect.y+rect.height
  assert leaders
  for x0, y0, x1, y1 in leaders:
    assert (x0, y0) == pytest.approx((baseline.u*video.width, (baseline.v-baseline.h)*video.height))
    assert any((x1, y1) == pytest.approx((x, y)) for _, x, y, _ in icons)

  icons.clear()
  texts.clear()
  leaders.clear()
  renderer._render_world(replace(state, hud_objects=tuple(replace(obj, u=.03) for obj in objects)), (False, False))
  assert not icons and not texts and not leaders
