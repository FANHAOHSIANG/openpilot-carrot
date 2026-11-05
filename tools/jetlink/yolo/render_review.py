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
from cluster_models import SimulatorInput, ClusterAlert
from cluster_renderer import ClusterUiRenderer
from cluster_simulator import ClusterSimulator


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('output', type=Path)
  args = parser.parse_args()
  args.output.mkdir(parents=True, exist_ok=True)
  from openpilot.selfdrive.carrot import signal_mode
  signal_mode._params = SimpleNamespace(get_int=lambda key: 0)  # Synthetic settings; no native vehicle Params.
  with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary)/'synthetic.json'
    os.environ['CARROT_HUD_YOLO_FILE'] = str(path)
    renderer = ClusterUiRenderer(width=1920, height=462, language='en', theme_mode='dark', screen_mode=7)
    state = replace(ClusterSimulator().update(SimulatorInput(), .05), onroad=True,
                    detected_vehicles=(), radar_points=(), speed_kph=44., cruise_kph=60,
                    camera_view_mode=0)
    objects = [{'cls': cls, 'conf': .9, 'box': [.2, .3, .3, .6], 'd': d, 'lat': lat,
                'range_source': 'monocular_estimate'}
               for cls, d, lat in [(0, 19, 3.5), (3, 11, -2.2), (2, 32, 0), (5, 50, -4.2), (7, 42, 4.2)]]
    try:
      renderer.open(hidden=True)
      for name, value in [('normal', state), ('alert', replace(state, alert=ClusterAlert('TEST ALERT', 'SYNTHETIC', size=2, status=1)))]:
        now = time.monotonic()
        path.write_text(json.dumps({'version': 1, 'mode': 'live', 'status': 'ready', 'captured_mono': now,
                                    'written_mono': now, 'expires_mono': now+.8, 'frame_id': 1,
                                    'source_width': 1344, 'source_height': 760, 'objects': objects}))
        renderer._yolo_overlay.next_read = 0
        image = renderer.render_to_png_bytes(value)
        if renderer._yolo_overlay.error:
          raise RuntimeError(renderer._yolo_overlay.error)
        (args.output/f'{name}.png').write_bytes(image)
    finally:
      renderer.close()


if __name__ == '__main__':
  main()
