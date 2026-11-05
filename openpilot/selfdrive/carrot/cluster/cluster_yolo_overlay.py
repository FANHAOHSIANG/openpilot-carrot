"""Read-only semantic HUD overlay. Enabled only by CARROT_HUD_YOLO_FILE.

No model imports, inference, camera ownership, or vehicle publications here.
The separate host worker owns the small, expiring JSON result.
"""
import json
import math
import os
from pathlib import Path
import time

LABELS = {0: 'PERSON', 1: 'BIKE', 2: 'CAR', 3: 'MOTO', 5: 'BUS', 7: 'TRUCK'}
COLORS = {0: (255, 100, 100), 1: (255, 205, 75), 2: (90, 200, 255),
          3: (255, 170, 60), 5: (190, 145, 255), 7: (115, 235, 170)}


def valid_result(value, now):
  try:
    if (value.get('version') != 1 or value.get('mode') != 'live' or value.get('status') != 'ready' or
        not 0 <= now - value['captured_mono'] < .8 or
        not value['captured_mono'] <= value['written_mono'] <= now or
        not now < value['expires_mono'] <= value['captured_mono'] + .801 or
        type(value['frame_id']) is not int or not 0 <= value['frame_id'] < 2**32 or
        not isinstance(value['objects'], list) or len(value['objects']) > 32):
      return None
    for obj in value['objects']:
      box = obj['box']
      if (obj['cls'] not in LABELS or not math.isfinite(obj['conf']) or not .35 <= obj['conf'] <= 1 or
          len(box) != 4 or not all(math.isfinite(v) and 0 <= v <= 1 for v in box) or
          box[0] >= box[2] or box[1] >= box[3]):
        return None
      if 'd' in obj or 'lat' in obj:
        if (obj.get('range_source') != 'monocular_estimate' or
            not 2 <= obj['d'] <= 80 or not -20 <= obj['lat'] <= 20):
          return None
    return value
  except (KeyError, TypeError, ValueError, AttributeError):
    return None


def glyph_lines(cls):
  """Normalized line segments; same primitive source used by render tests."""
  if cls == 0:
    return [((0, -.65), (0, .3)), ((-.45, -.25), (.45, -.25)),
            ((0, .3), (-.35, .85)), ((0, .3), (.35, .85))]
  if cls in (1, 3):
    return [((-.6, .5), (-.1, -.2)), ((-.1, -.2), (.6, .5)),
            ((-.6, .5), (.6, .5)), ((-.1, -.2), (.25, -.2)),
            ((.25, -.2), (.4, -.55)), ((-.1, -.2), (-.2, -.7))]
  top = -.7 if cls in (5, 7) else -.35
  return [((-.65, .5), (.65, .5)), ((-.65, .5), (-.65, top)),
          ((-.65, top), (.65, top)), ((.65, top), (.65, .5)),
          ((-.45, top+.2), (.45, top+.2))]


class ObjectOverlay:
  def __init__(self, path=None):
    self.path = Path(path) if path else None
    self.next_read = 0.
    self.cached = None
    self.error = ''

  @classmethod
  def from_environment(cls):
    return cls(os.environ.get('CARROT_HUD_YOLO_FILE'))

  def read(self, now=None):
    now = time.monotonic() if now is None else now
    if self.path is None:
      return None
    if now >= self.next_read:
      self.next_read = now + .1
      self.cached = None
      try:
        with self.path.open('rb') as f:
          raw = f.read(32769)
        if len(raw) <= 32768:
          self.cached = json.loads(raw)
      except (OSError, ValueError):
        pass
    # Expiry is checked on every rendered frame, including cached JSON.
    return valid_result(self.cached, now) if self.cached is not None else None

  def draw_world(self, renderer, scene, state):
    if self.path is None or not state.onroad:
      return
    try:
      self._draw_world(renderer, scene, state)
    except Exception as error:
      self.error = type(error).__name__  # Isolate optional display errors.

  def _draw_world(self, renderer, scene, state):
    from cluster_config import cluster_camera_view_is_road_camera
    from cluster_renderer import rl, rl_color, vec3, world_to_screen_label_anchor
    from cluster_scene import render_scene_forward_m
    value = self.read()
    if value is None:
      return
    rect = renderer._camera_overlay_content_rect()
    camera_view = cluster_camera_view_is_road_camera(state.camera_view_mode)
    projection = None
    if camera_view:
      if renderer._camera_overlay_wide:
        return  # Narrow detections must never be painted on the wide stream.
      displayed = getattr(getattr(renderer, '_live_road_camera', None), 'display_frame', None)
      if (displayed is None or displayed[4] or displayed[2:4] != (value['source_width'], value['source_height']) or
          not 0 <= displayed[0] - value['frame_id'] <= 6 or
          abs(displayed[1] - value['captured_mono']) > .3):
        return
      projection = renderer._camera_overlay_projection(state)
      if projection is None:
        return
    else:
      camera = rl.Camera3D(vec3(scene.camera.position), vec3(scene.camera.target), rl.Vector3(0, 0, 1),
                           scene.camera.fovy_deg, rl.CameraProjection.CAMERA_PERSPECTIVE)
      shift = renderer._world_view_shift_x(state)
      panel_offset = renderer._driving_panel_offset_design_x() * renderer.width / 1920 if abs(shift) > .001 else 0.
    rl.begin_scissor_mode(int(rect.x), int(rect.y + 80 * renderer.height / 480),
                          int(rect.width), max(0, int(rect.height - 130 * renderer.height / 480)))
    try:
      for obj in sorted(value['objects'], key=lambda x: -x.get('d', 0)):
        color = COLORS[obj['cls']]
        if projection is not None:
          video = projection.video_dest
          x1, y1, x2, y2 = obj['box']
          x, y = video.x+x1*video.width, video.y+y1*video.height
          rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, (x2-x1)*video.width, (y2-y1)*video.height),
                                      2., rl_color(color))
          x += (x2-x1)*video.width/2
          y -= 16
        else:
          if 'd' not in obj:
            continue
          point = rl.Vector3(obj['lat'] + scene.scene_shift_x_m,
                             render_scene_forward_m(obj['d'], state), .7)
          anchor = world_to_screen_label_anchor(point, camera, renderer.width, renderer.height)
          if anchor is None:
            continue
          x, y = anchor.x+panel_offset-shift, anchor.y
          size = max(9., min(24., 100 / math.sqrt(obj['d']))) * renderer.height / 480
          self._glyph(rl, rl_color(color), obj['cls'], x, y, size)
          y += size + 12
        label = LABELS[obj['cls']] + (f" ~{obj['d']:.0f}m" if 'd' in obj else '')
        renderer._draw_text_with_stroke(label, x, y, max(12, 18*renderer.height/480), color,
                                        (0, 0, 0), 2, anchor='center')
    finally:
      rl.end_scissor_mode()

  @staticmethod
  def _glyph(rl, color, cls, x, y, size):
    for a, b in glyph_lines(cls):
      rl.draw_line_ex(rl.Vector2(x+a[0]*size, y+a[1]*size), rl.Vector2(x+b[0]*size, y+b[1]*size), 3., color)
    if cls == 0:
      rl.draw_circle_v(rl.Vector2(x, y-.9*size), .23*size, color)
    else:
      for dx in (-.6, .6):
        rl.draw_circle_lines(int(x+dx*size), int(y+.5*size), .25*size, color)

  def draw_status(self, renderer, state):
    if self.path is None or not state.onroad:
      return
    try:
      from cluster_renderer import rl, rl_color
      value = self.read()
      if isinstance(self.cached, dict) and self.cached.get('status') == 'stopped':
        return
      text = 'YOLO: waiting / stale' if value is None else 'YOLO ' + ' '.join(
        f"{label}:{sum(o['cls'] == cls for o in value['objects'])}" for cls, label in LABELS.items())
      if value and not any('d' in o for o in value['objects']):
        text += ' | range unavailable'
      if self.error:
        text = 'YOLO: display error'
      rect = renderer._camera_overlay_content_rect()
      y = rect.y + rect.height - 14 * renderer.height / 480
      rl.draw_rectangle(int(rect.x), int(y-13), int(rect.width), 26, rl_color((0, 0, 0), 190))
      renderer._draw_text(text, rect.x+rect.width/2, y, max(12, 17*renderer.height/480),
                          (175, 210, 190), anchor='center')
    except Exception:
      pass
