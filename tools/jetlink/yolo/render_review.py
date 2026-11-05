#!/usr/bin/env python3
"""Render a labelled SYNTHETIC layout check with the actual Carrot HUD renderer.

Requires a GL display. No device connection or actual detector evidence is used.
"""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'openpilot/selfdrive/carrot/cluster')]
from cluster_models import SimulatorInput, ClusterAlert, ModelPathPoint, LaneMarking
from cluster_renderer import ClusterUiRenderer
from cluster_simulator import ClusterSimulator


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('output', type=Path)
  parser.add_argument('--legacy-renderer', type=Path, help='Render a patched existing Mac renderer fixture')
  args = parser.parse_args()
  args.output.mkdir(parents=True, exist_ok=True)
  from openpilot.selfdrive.carrot import signal_mode
  signal_mode._params = SimpleNamespace(get_int=lambda key: 0)  # Synthetic settings; no native vehicle Params.
  with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary)/'synthetic.json'
    os.environ['CARROT_HUD_YOLO_FILE'] = str(path)
    os.environ['CARROT_HUD_LAYOUT'] = 'henry-v2'
    renderer_class = ClusterUiRenderer
    if args.legacy_renderer:
      from install_mac_yolo import patch_renderer
      namespace = {'__file__':str(ROOT/'openpilot/selfdrive/carrot/cluster/cluster_renderer.py')}
      exec(compile(patch_renderer(args.legacy_renderer.read_text()), str(args.legacy_renderer), 'exec'),namespace)
      renderer_class = namespace['ClusterUiRenderer']
    renderer = renderer_class(width=1920, height=462, language='en', theme_mode='dark', screen_mode=7)
    def road(offset):
      return tuple(ModelPathPoint(d, offset + .00004*d*d) for d in range(2,101,2))
    state = replace(ClusterSimulator().update(SimulatorInput(), .05), onroad=True,
                    detected_vehicles=(), radar_points=(), speed_kph=44., cruise_kph=60,
                    display_speed_kph=44., cruise_display_state='engaged',speed_limit_kph=50,
                    planned_accel_mps2=-.4,steering_output_normalized=.05,
                    planned_curvature_m_inv=.000134,vision_yaw_rate_rps=.00164,
                    model_path=road(0), lanes=tuple(LaneMarking(offset, model_points=road(offset)) for offset in (-5.4,-1.8,1.8,5.4)),
                    left_road_edge_points=road(-7.2),right_road_edge_points=road(7.2),camera_view_mode=0)
    objects = [{'cls': cls, 'conf': .9, 'box': [.2, .3, .3, .6], 'd': d, 'lat': lat,
                'range_source': 'monocular_estimate'}
               for cls, d, lat in [(0, 19, 3.5), (3, 11, -2.2), (2, 32, 0), (5, 50, -4.2), (7, 42, 4.2)]]
    try:
      renderer.open(hidden=True)
      for name, value in [('normal', state), ('alert', replace(state, alert=ClusterAlert('TEST ALERT', 'SYNTHETIC', size=2, status=1))),
                          ('standby', replace(state, onroad=False)), ('stale',state), ('unlocated',state)]:
        now = time.monotonic()
        if name == 'stale': now -= 2
        scene_objects = [{k:v for k,v in o.items() if k not in ('d','lat','range_source')} for o in objects] if name == 'unlocated' else objects
        path.write_text(json.dumps({'version': 1, 'mode': 'live', 'status': 'ready', 'captured_mono': now,
                                    'written_mono': now, 'expires_mono': now+.8, 'frame_id': 1,
                                    'source_width': 1344, 'source_height': 760, 'objects': scene_objects}))
        renderer._yolo_overlay.next_read = 0
        image = renderer.render_to_png_bytes(value)
        if renderer._yolo_overlay.error:
          raise RuntimeError(renderer._yolo_overlay.error)
        if renderer._henry_layout.error:
          raise RuntimeError(renderer._henry_layout.error)
        (args.output/f'{name}.png').write_bytes(image)
        # Prevent these synthetic layout screenshots being mistaken for real detection evidence.
        from PIL import Image, ImageDraw
        preview = Image.open(args.output/f'{name}.png')
        draw = ImageDraw.Draw(preview)
        draw.rectangle((640,0,1280,27),fill=(30,36,42))
        draw.text((695,7),'SYNTHETIC LAYOUT PREVIEW / NOT A VEHICLE TEST', fill=(240,200,90))
        preview.save(args.output/f'{name}.png')
    finally:
      renderer.close()


if __name__ == '__main__':
  main()
