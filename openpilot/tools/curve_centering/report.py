"""Self-contained Traditional Chinese review UI; all telemetry stays local."""

import json
from pathlib import Path


def render_report(report, live=False):
  data = json.dumps(report, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
  template = Path(__file__).with_name('viewer.html').read_text(encoding='utf-8')
  return template.replace('__LIVE_MODE__', 'true' if live else 'false').replace('__REPORT_DATA__', data)


def write_report(path, report):
  Path(path).write_text(render_report(report), encoding='utf-8')
