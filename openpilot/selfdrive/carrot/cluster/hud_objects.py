"""Read display-only C4 detections and place them in the calibrated cluster scene."""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
import os
import stat
import time
from pathlib import Path

import numpy as np
import pyray as rl

from openpilot.common.transformations.camera import DEVICE_CAMERAS, view_frame_from_device_frame
from openpilot.common.transformations.orientation import rot_from_euler

MAX_AGE_S = 1.0
MAX_BYTES = 32768
MAX_ROWS = 48
CLASSES = {
    'car': (100, 183, 215, 235), 'bus': (98, 175, 207, 235), 'truck': (98, 175, 207, 235),
    'motorcycle': (226, 174, 67, 245), 'bicycle': (93, 203, 162, 245),
    'person': (248, 202, 111, 245), 'cone': (255, 122, 53, 250),
}
MOTOR_VEHICLES = ('car', 'truck', 'bus', 'motorcycle')


@dataclass(frozen=True, slots=True)
class HudObject:
    kind: str
    u: float
    v: float
    w: float
    h: float
    score: float
    t: float
    camera: str
    forward: float
    right: float


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


@lru_cache(maxsize=8)
def _ground_transform(device, sensor, rpy, height, wide_rpy):
    cameras = DEVICE_CAMERAS.get((device, sensor))
    if cameras is None or sensor == 'unknown':
        return None
    camera = cameras.ecam if wide_rpy is not None else cameras.fcam
    if camera.focal_length <= 0:
        return None
    rotation = rot_from_euler(rpy)
    if wide_rpy is not None:
        rotation = rot_from_euler(wide_rpy) @ rotation
    # Invert the cluster camera projection for a point on the ground. The focal
    # lengths are in native pixels; the detector sends full-frame fractions.
    calib_from_view = (view_frame_from_device_frame @ rotation).T
    offset = calib_from_view[:, 1] * height
    return camera, calib_from_view, offset


def _angles(values):
    vals = tuple(values)
    return vals if len(vals) == 3 and all(_number(v) for v in vals) else None


def _project_packet(packet, now, device, sensor, calibration):
    if not isinstance(packet, dict) or packet.get('version') != 1 or packet.get('camera') not in ('road', 'wideRoad'):
        return ()
    batches = packet.get('batches', [packet])
    if not isinstance(batches, list) or len(batches) > 2:
        return ()
    if str(getattr(calibration, 'calStatus', '')) not in ('1', 'calibrated'):
        return ()
    rpy = _angles(getattr(calibration, 'rpyCalib', ()))
    heights = tuple(getattr(calibration, 'height', ()))
    if rpy is None or not heights or not _number(heights[0]) or not .5 <= heights[0] <= 3:
        return ()
    result = []
    for batch in batches:
        if not isinstance(batch, dict):
            continue
        t, rows = batch.get('t'), batch.get('objects')
        if not _number(t) or not 0 <= now - t <= MAX_AGE_S or not isinstance(rows, list):
            continue
        lens = batch.get('camera', packet['camera'])
        if lens not in ('road', 'wideRoad'):
            continue
        wide_rpy = _angles(getattr(calibration, 'wideFromDeviceEuler', ())) if lens == 'wideRoad' else None
        if lens == 'wideRoad' and wide_rpy is None:
            continue
        transform = _ground_transform(device, sensor, rpy, heights[0], wide_rpy)
        if transform is None:
            continue
        camera, calib_from_view, offset = transform
        for row in rows[:MAX_ROWS]:
            if not isinstance(row, list) or len(row) != 6:
                continue
            kind, u, v, w, h, score = row
            if not isinstance(kind, str) or kind not in CLASSES or not all(_number(q) for q in row[1:]):
                continue
            if not (0 < w <= 1 and 0 < h <= 1 and .5 <= score <= 1
                    and w / 2 - .001 <= u <= 1 - w / 2 + .001 and h - .001 <= v < .997):
                continue
            ray = calib_from_view @ ((u - .5) * camera.width / camera.focal_length,
                                     (v - .5) * camera.height / camera.focal_length, 1.)
            if ray[2] < .02:
                continue
            forward, right, _ = ray * (offset[2] / ray[2]) - offset
            if 1.0 <= forward <= 75.0 and abs(right) <= 16.0:
                result.append(HudObject(kind, u, v, w, h, score, t, lens, float(forward), float(right)))
    return tuple(result)


class HudObjectReader:
    def __init__(self, path=None):
        if path is None:
            try:
                from openpilot.selfdrive.carrot.hud_objects.transport import HUD_PATH
                path = HUD_PATH
            except ImportError:
                pass  # A standalone desktop replay does not have a native C4 producer.
        self.path = Path(path) if path is not None else None
        self.next_read = 0.
        self.signature = None
        self.projection_key = None
        self.packet = None
        self.objects = ()

    def read(self, now, device, sensor, calibration):
        if self.path is None or str(getattr(calibration, 'calStatus', '')) not in ('1', 'calibrated'):
            self.objects = ()
            self.projection_key = None
            return ()
        try:
            if now >= self.next_read:
                self.next_read = now + .10
                flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
                with os.fdopen(os.open(self.path, flags), 'rb') as handle:
                    st = os.fstat(handle.fileno())
                    signature = (st.st_ino, st.st_mtime_ns, st.st_size)
                    if signature != self.signature:
                        self.projection_key = None
                        self.packet = None
                        self.signature = signature
                        if stat.S_ISREG(st.st_mode) and st.st_size <= MAX_BYTES:
                            raw = handle.read(MAX_BYTES + 1)
                            if len(raw) <= MAX_BYTES:
                                self.packet = json.loads(raw)
            key = (device, sensor, tuple(calibration.rpyCalib), tuple(calibration.height),
                   tuple(getattr(calibration, 'wideFromDeviceEuler', ())))
            if key != self.projection_key:
                self.objects = _project_packet(self.packet, now, device, sensor, calibration)
                self.projection_key = key
        except (AttributeError, OSError, ValueError, TypeError, RecursionError, OverflowError):
            self.packet = self.signature = self.projection_key = None
            self.objects = ()
        return tuple(obj for obj in self.objects if 0 <= now - obj.t <= MAX_AGE_S)


def pair_objects(objects, scene, now):
    """Pair at most one visual vehicle per native body in physical road coordinates."""
    fresh = tuple(obj for obj in objects if 0 <= now - obj.t <= MAX_AGE_S)
    if not fresh:
        return (), ()
    candidates = []
    for i, obj in enumerate(fresh):
        if obj.kind not in MOTOR_VEHICLES:
            continue
        for j, native in enumerate(scene.vehicles):
            if not native.source or native.longitudinal_m is None or native.longitudinal_m <= 0:
                continue
            dx = abs(obj.right - (native.center.x + scene.scene_shift_x_m))
            dy = abs(obj.forward - native.longitudinal_m)
            depth_gate = min(3.2, 1.5 + .045 * obj.forward)
            if dx < .90 and dy < depth_gate:
                candidates.append(((dx / .90)**2 + (dy / depth_gate)**2, i, j))
    hidden, used = set(), set()
    motorcycle_tags = []
    for _, i, j in sorted(candidates):
        if i not in hidden and j not in used:
            hidden.add(i)
            used.add(j)
            if fresh[i].kind == 'motorcycle' and not any(
                (other_i == i or other_j == j) and (other_i, other_j) != (i, j)
                for _, other_i, other_j in candidates
            ):
                motorcycle_tags.append((fresh[i], scene.vehicles[j]))
    return tuple(obj for i, obj in enumerate(fresh) if i not in hidden), tuple(motorcycle_tags)


def monotonic_display_frame(camera_frame):
    if not camera_frame:
        return None
    # VisionIPC reports CLOCK_BOOTTIME while snapshots use CLOCK_MONOTONIC.
    fid, eof, width, height, wide = camera_frame
    stamp = time.monotonic() + (eof - time.clock_gettime(time.CLOCK_BOOTTIME))
    return fid, stamp, width, height, wide


def draw_road_boxes(objects, projection, camera_frame, now, motorcycle_tags=()):
    if not camera_frame:
        return
    _, frame_t, _, _, wide = camera_frame
    if not 0 <= now - frame_t <= MAX_AGE_S:
        return
    lens = 'wideRoad' if wide else 'road'
    dest = projection.video_dest

    def frame_matches(obj):
        return obj.camera == lens and abs(obj.t - frame_t) <= .25 and 0 <= now - obj.t <= MAX_AGE_S

    for obj in objects:
        if frame_matches(obj):
            rect = rl.Rectangle(dest.x + (obj.u - obj.w / 2) * dest.width, dest.y + (obj.v - obj.h) * dest.height,
                                obj.w * dest.width, obj.h * dest.height)
            rl.draw_rectangle_lines_ex(rect, 2., rl.Color(*CLASSES[obj.kind]))
    for obj, _ in motorcycle_tags:
        if frame_matches(obj):
            x = int(dest.x + (obj.u - obj.w / 2) * dest.width)
            y = int(dest.y + (obj.v - obj.h) * dest.height) - 5
            color = rl.Color(*CLASSES['motorcycle'])
            rl.draw_circle_lines(x + 4, y, 3., color)
            rl.draw_circle_lines(x + 16, y, 3., color)
            rl.draw_line_ex(rl.Vector2(x + 4, y), rl.Vector2(x + 10, y - 4), 2., color)
            rl.draw_line_ex(rl.Vector2(x + 10, y - 4), rl.Vector2(x + 13, y - 4), 2., color)
            rl.draw_line_ex(rl.Vector2(x + 12, y - 7), rl.Vector2(x + 16, y), 2., color)


def draw_motorcycle_tag(native):
    # A side-view motorcycle pictogram above the native body leaves its geometry,
    # current warning tint and distance/speed label intact.
    x, y = native.center.x, native.center.y
    z = native.height_m + .33
    color = rl.Color(*CLASSES['motorcycle'])
    for dx in (-.38, .38):
        rl.draw_cylinder_ex(rl.Vector3(x + dx, y, z), rl.Vector3(x + dx, y + .06, z), .16, .16, 10, color)
        rl.draw_cylinder_ex(rl.Vector3(x + dx, y - .012, z), rl.Vector3(x + dx, y, z),
                            .076, .076, 8, rl.Color(42, 50, 62, 255))
    rl.draw_cylinder_ex(rl.Vector3(x - .35, y, z), rl.Vector3(x - .03, y, z + .17), .044, .044, 6, color)
    rl.draw_cube(rl.Vector3(x + .03, y, z + .18), .34, .10, .12, color)
    rl.draw_cylinder_ex(rl.Vector3(x + .19, y, z + .32), rl.Vector3(x + .38, y, z), .042, .042, 6, color)


def draw_scene_objects(objects, scene, state, now):
    from cluster_scene import render_scene_forward_m
    visible, tags = pair_objects(objects, scene, now)
    for _, native in tags:
        draw_motorcycle_tag(native)
    for obj in visible:
        x = obj.right - scene.scene_shift_x_m
        y = render_scene_forward_m(obj.forward, state)
        body = rl.Color(*CLASSES[obj.kind])
        dark = rl.Color(49, 63, 79, 245)
        if obj.kind == 'cone':
            rl.draw_cube(rl.Vector3(x, y, .04), .45, .45, .08, body)
            rl.draw_cylinder_ex(rl.Vector3(x, y, .08), rl.Vector3(x, y, .67), .20, .025, 8, body)
            rl.draw_cylinder_ex(rl.Vector3(x, y, .33), rl.Vector3(x, y, .43), .132, .101, 8, rl.RAYWHITE)
        elif obj.kind == 'person':
            for side in (-1., 1.):
                rl.draw_cylinder_ex(rl.Vector3(x + side * .14, y, .06), rl.Vector3(x + side * .09, y, .81),
                                    .065, .085, 6, dark)
            rl.draw_cylinder_ex(rl.Vector3(x, y, .73), rl.Vector3(x, y, 1.39), .16, .205, 8, body)
            rl.draw_sphere_ex(rl.Vector3(x, y, 1.6), .168, 4, 8, body)
        elif obj.kind in ('bicycle', 'motorcycle'):
            for dy in (0., 1.2):
                rl.draw_cylinder_ex(rl.Vector3(x - .09, y + dy, .31), rl.Vector3(x + .09, y + dy, .31),
                                    .31, .31, 10, dark)
            rl.draw_cube(rl.Vector3(x, y + .6, .61), .34, .98, .31, body)
            rl.draw_cube(rl.Vector3(x, y + .82, .91), .38, .35, .29, body)
        else:
            width, length, height = (1.68, 3.6, .72) if obj.kind == 'car' else (1.95, 5., 1.5)
            rl.draw_cube(rl.Vector3(x, y + length / 2, .15 + height / 2), width, length, height, body)
            rl.draw_cube(rl.Vector3(x, y + length * .55, .15 + height + .23), width * .82, length * .59, .46, dark)
