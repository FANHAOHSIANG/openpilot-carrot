"""Wide HUD presentation for the opt-in Mac trial; no control or CAN writes.

Coordinates are a schematic top-down perspective, not a camera calibration.
Only measured/model geometry is drawn. YOLO ranges remain labelled estimates.
"""
import math
import os
from pathlib import Path
import time

BLUE = (79, 163, 255)
GREEN = (53, 217, 119)
RED = (255, 91, 99)
GRAY = (143, 165, 183)
WHITE = (237, 244, 250)
LABELS = {0: '行人', 1: '自行車', 2: '汽車', 3: '機車', 5: '公車', 7: '卡車'}


def number(value):
  return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def formatted(value, precision=0):
  return f'{value:.{precision}f}' if number(value) else '—'


def project(forward, lateral):
  if not number(forward) or not number(lateral) or not 2 <= forward <= 100 or abs(lateral) > 30:
    return None
  return 960 + lateral * 2000 / (forward + 8), 70 + 3300 / (forward + 8)


def metric_values(state):
  lead = next((v for v in state.detected_vehicles if v.primary and v.longitudinal_m > 0), None)
  relative = getattr(lead, 'relative_speed_mps', None)
  relative = relative * 3.6 if number(relative) else None
  curvature, yaw = getattr(state, 'planned_curvature_m_inv', None), getattr(state, 'vision_yaw_rate_rps', None)
  speed = state.speed_kph / 3.6 if number(state.speed_kph) else None
  target = speed * speed * curvature if speed is not None and number(curvature) else None
  actual = speed * yaw if speed is not None and number(yaw) else None
  return relative, getattr(state, 'planned_accel_mps2', None), getattr(state, 'steering_output_normalized', None), target, actual


class HenryLayout:
  def __init__(self):
    self.enabled = os.environ.get('CARROT_HUD_LAYOUT') == 'henry-v2'
    self.font = None
    self.error = ''
    self.last_heartbeat = 0.
    self.heartbeat = os.environ.get('CARROT_HUD_LAYOUT_STATUS')

  def _font(self, rl):
    if self.font is None:
      # A small OFL subset covers all fixed labels. No network or system-font dependency.
      codes = [int(c) for c in Path(__file__).with_name('henry_font.codepoints').read_text().split()]
      glyphs = rl.ffi.new('int[]', codes)
      font = rl.load_font_ex(str(Path(__file__).with_name('henry_font.ttf')), 144, rl.ffi.cast('int *',glyphs), len(codes))
      if font.texture.id == 0:
        raise RuntimeError('HUD font failed to load')
      rl.set_texture_filter(font.texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
      self.font = font
    return self.font

  def draw(self, renderer, state, signal_lights=None):
    if not self.enabled:
      return False
    import pyray as rl
    rl.clear_background(rl.Color(5, 9, 12, 255))
    rl.rl_push_matrix()
    rl.rl_scalef(renderer.width / 1920, renderer.height / 480, 1.)
    try:
      if signal_lights is None:
        signal_lights = renderer._turn_signal_lights(state)
      self._draw(rl, renderer, state, signal_lights)
      self.error = ''
      if self.heartbeat and time.monotonic() - self.last_heartbeat > 2:
        self.last_heartbeat = time.monotonic()
        # A tiny acknowledgement lets the launcher distinguish a running App from a loaded HUD.
        try:
          path = Path(self.heartbeat)
          temporary = path.with_suffix('.tmp')
          temporary.write_text('henry-v2\n')
          temporary.replace(path)
        except OSError:
          pass
    except Exception as error:
      if self.error != repr(error):
        print(f'Henry HUD layout error: {error!r}', flush=True)
      self.error = repr(error)
    finally:
      rl.rl_pop_matrix()
    if self.error:
      # Fail back to the existing renderer, with an explicit error instead of a silent old screen.
      return False
    return True

  def draw_error(self, renderer):
    if self.enabled and self.error:
      renderer._draw_text('HENRY V2 LOAD ERROR - see jetlink-yolo.log', renderer.width/2, 20, 18, RED, 'center')

  def _draw(self, rl, renderer, state, signal_lights):
    font = self._font(rl)
    def color(rgb, alpha=255):
      return rl.Color(*rgb[:3], alpha)
    def text(value, x, y, size=22, rgb=WHITE, anchor='left'):
      size *= 1.4  # Noto's em includes generous CJK ascender space; use the HUD's visible text height.
      width = rl.measure_text_ex(font, value, size, 0).x
      if anchor == 'right': x -= width
      if anchor == 'center': x -= width/2
      rl.draw_text_ex(font, value, rl.Vector2(x, y-size*.53), size, 0, color(rgb))
    def line(a, b, rgb, width=2):
      rl.draw_line_ex(rl.Vector2(*a), rl.Vector2(*b), width, color(rgb))
    def polygon(points, rgb, alpha=255):
      # Explicit winding avoids backend-dependent culling.
      for i in range(1, len(points)-1):
        a, b, c = points[0], points[i], points[i+1]
        if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]) > 0:
          b, c = c, b
        rl.draw_triangle(rl.Vector2(*a), rl.Vector2(*b), rl.Vector2(*c), color(rgb, alpha))
    def geometry(points, shift=0):
      return [p for point in points if (p := project(point.forward_m, point.lateral_m+shift)) is not None]
    def curve(points, rgb, width=3):
      for a, b in zip(points, points[1:]): line(a, b, rgb, width)
    # Background is decorative; road/lane/path lines below all come from the received state.
    polygon([(0, 400), (640, 70), (1280, 70), (1920, 400)], (16, 26, 33))
    live = bool(state.onroad)
    if live:
      for points, shift in [(getattr(state, 'left_road_edge_points', ()), getattr(state, 'left_road_edge_lateral_shift_m', 0)),
                            (getattr(state, 'right_road_edge_points', ()), getattr(state, 'right_road_edge_lateral_shift_m', 0))]:
        curve(geometry(points, shift), (151, 52, 57), 4)
      path = getattr(state, 'model_path', ())
      left, right = geometry(path, -.45), geometry(path, .45)
      if len(left) >= 2:
        for i in range(len(left)-1):
          polygon([left[i], right[i], right[i+1], left[i+1]], (24, 132, 72), 175)
      for lane in state.lanes:
        if lane.visible and lane.model_points:
          points = geometry(lane.model_points, lane.model_lateral_shift_m)
          for i, (a, b) in enumerate(zip(points, points[1:])):
            if lane.style != 'dashed' or i % 4 < 2: line(a, b, lane.color, 3)
      # Radar/vision targets retain their own identity and are not falsely classified by proximity to YOLO.
      for vehicle in sorted(state.detected_vehicles, key=lambda v: -v.longitudinal_m):
        point = project(vehicle.longitudinal_m, vehicle.lateral_m)
        if point is None: continue
        x, y = point
        size = max(8, min(23, 110/math.sqrt(vehicle.longitudinal_m)))
        polygon([(x-size, y-size*.7), (x, y-size*1.4), (x+size, y-size*.7), (x, y-size)], BLUE)
        if vehicle.primary:
          text(f'{vehicle.longitudinal_m:.0f} m', x, y+12, 24, BLUE, 'center')
      value = renderer._yolo_overlay.read() if renderer._yolo_overlay.path else None
    else:
      value = None
    counts = {cls: 0 for cls in LABELS}
    unplaced = 0
    if value:
      from cluster_yolo_overlay import COLORS
      for obj in sorted(value['objects'], key=lambda item: -item.get('d', 0)):
        cls = obj['cls']; counts[cls] += 1
        point = project(obj.get('d'), obj.get('lat'))
        if point is None:
          unplaced += 1
          continue
        x, y = point
        size = max(9, min(30, 120/math.sqrt(obj['d'])))
        rgb = COLORS[cls]
        if cls == 0:
          rl.draw_circle_v(rl.Vector2(x, y-size*1.7), size*.24, color(rgb))
          polygon([(x-size*.2,y-size*1.3),(x+size*.2,y-size*1.3),(x+size*.28,y-size*.3),(x-size*.28,y-size*.3)],rgb)
          line((x, y-size*.4),(x-size*.2,y),rgb,4)
          line((x, y-size*.4),(x+size*.2,y),rgb,4)
        elif cls in (1,3):
          rl.draw_circle_v(rl.Vector2(x, y-size*1.5), size*.25, color(rgb))
          polygon([(x-size*.23,y-size*1.17),(x+size*.23,y-size*1.17),(x+size*.33,y-size*.3),(x-size*.33,y-size*.3)],rgb)
          line((x-size*.63,y-size*.85),(x+size*.63,y-size*.85),rgb,5)
          line((x,y-size*.3),(x,y),rgb,5)
        else:
          w, h = size*1.3, size*(1.25 if cls in (5,7) else .85)
          rl.draw_rectangle_rounded(rl.Rectangle(x-w/2,y-h,w,h),.22,4,color((134,156,173)))
          rl.draw_rectangle_rounded(rl.Rectangle(x-w*.33,y-h*.85,w*.66,h*.32),.2,4,color((32,49,61)))
          for dx in (-.36,.26):
            rl.draw_rectangle_rec(rl.Rectangle(x+w*dx,y-h*.32,w*.15,h*.14),color(RED))
        text(f'{LABELS[cls]} ~{obj["d"]:.0f} m',x,y+16,19 if cls in (2,5,7) else 26,rgb,'center')
    # Side instruments deliberately sit over the road so speed and state stay legible.
    rl.draw_rectangle(0,0,255,400,color((5,9,12),245))
    rl.draw_rectangle(1625,0,295,400,color((5,9,12),245))
    text('設定速度',34,28,18,GRAY)
    text(formatted(state.cruise_kph) if live else '—',30,96,108,BLUE)
    text('車速  km/h',1884,28,18,GRAY,'right')
    speed = getattr(state, 'display_speed_kph', None)
    text(formatted(speed if number(speed) else state.speed_kph) if live else '—',1885,96,108,WHITE,'right')
    engaged = live and state.cruise_display_state == 'engaged'
    def badge(label,y,rgb):
      rl.draw_rectangle_rounded(rl.Rectangle(32,y,192,43),.12,4,color(rgb,25))
      rl.draw_rectangle_lines_ex(rl.Rectangle(32,y,192,43),1,color(rgb,110))
      text(label,128,y+22,24,rgb,'center')
    badge('ENGAGED' if engaged else ('PAUSED' if live else '待機'),173,GREEN if engaged else GRAY)
    radar_count = sum(v.source.startswith(('radar','corner')) for v in state.detected_vehicles) if live else 0
    badge(f'雷達目標 {radar_count}' if radar_count else '視覺疊圖',227,(61,195,223))
    lead = any(v.primary for v in state.detected_vehicles) if live else False
    badge('前方目標' if lead else 'YOLO 辨識',281,GREEN)
    lights = signal_lights if signal_lights is not None else (state.left_signal,state.right_signal)
    if live and lights[0]: text('◀',320,32,32,GREEN)
    if live and lights[1]: text('▶',1590,32,32,GREEN,'right')
    if live and state.left_blindspot: text('左側盲點',315,65,24,RED)
    if live and state.right_blindspot: text('右側盲點',1595,65,24,RED,'right')
    limit = state.speed_limit_kph if live else None
    if number(limit) and 0 < limit < 200:
      rl.draw_circle(1831,247,49,color((220,35,48)))
      rl.draw_circle(1831,247,39,color(WHITE))
      text(formatted(limit),1831,248,43,(15,20,25),'center')
      text('資料速限',1831,312,17,GRAY,'center')
    if not live:
      text('等待車輛即時資料',960,215,34,GRAY,'center')
    elif not getattr(state,'model_path',()):
      text('等待道路模型',960,88,20,GRAY,'center')
    if live and getattr(state,'longitudinal_plan_should_stop',False):
      text('規劃停車',960,30,28,(255,177,72),'center')
    status = 'YOLO 等待影像' if value is None else 'YOLO  ' + '  '.join(f'{LABELS[c]} {n}' for c,n in counts.items() if n)
    if value and not any(counts.values()): status = 'YOLO 未偵測到目標'
    if unplaced: status += f'  未定位 {unplaced}'
    text(status,1596,378,18,GREEN if value else GRAY,'right')
    text('HENRY V2',34,375,18,BLUE)
    text('~ 單鏡頭估距',1884,375,17,GRAY,'right')
    rl.draw_rectangle(0,400,1920,80,color((4,8,11)))
    line((0,400),(1920,400),(34,49,59),1)
    values = metric_values(state) if live else (None,)*5
    relative,accel,steer,target,actual = values
    titles = ['相對速度  km/h','縱向目標加速度  m/s²','轉向輸出  正規化','橫向加速度  目標 / 視覺估計  m/s²']
    contents = [formatted(relative,1),formatted(accel,2),formatted(steer,2),f'{formatted(target,2)} / {formatted(actual,2)}']
    for i,(title,content) in enumerate(zip(titles,contents)):
      x = i*480+32
      if i: line((i*480,418),(i*480,467),(35,52,63),1)
      text(title,x,417,16,GRAY)
      text(content,x,452,42,RED if i==0 and number(relative) and relative < 0 else WHITE)
