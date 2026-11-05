#!/usr/bin/env python3
"""Install the optional YOLO trial into an existing CarrotMacHUD, without git checkout.

Downloads only a hash-checked manifest from an explicitly pinned GitHub commit.
Preserves local Mac/navigation patches and provides hash-guarded restoration.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.request

REPO = 'https://raw.githubusercontent.com/FANHAOHSIANG/openpilot-carrot'
CLUSTER = Path('openpilot/selfdrive/carrot/cluster')
REQUIRED_METHODS = {'__init__', 'render', '_render_world', '_camera_overlay_content_rect',
                    '_world_view_shift_x', '_driving_panel_offset_design_x', '_camera_overlay_projection',
                    '_draw_text_with_stroke'}


def digest(data):
  return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
  path = Path(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
    temporary = Path(f.name)
    f.write(data)
  try:
    if path.exists():
      temporary.chmod(path.stat().st_mode & 0o777)
    temporary.replace(path)
  finally:
    temporary.unlink(missing_ok=True)


def patch_renderer(source):
  tree = ast.parse(source)
  cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ClusterUiRenderer'), None)
  if cls is None:
    raise ValueError('找不到 Carrot HUD renderer')
  methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
  if not REQUIRED_METHODS <= methods.keys() or 'def world_to_screen_label_anchor(' not in source:
    raise ValueError('目前 Mac HUD 介面與此測試不相容；保留原檔，請回報訊息')
  if '_yolo_overlay' in source:
    if all(s in source for s in ('ObjectOverlay.from_environment()', 'self._yolo_overlay.draw_world(self, scene, state)',
                                 'self._yolo_overlay.draw_status(self, state)')):
      has_overlay = True
    else:
      raise ValueError('發現不同或不完整的 YOLO 修改，保留原檔')
  else:
    has_overlay = False
  if '_henry_layout' in source:
    if has_overlay and all(s in source for s in ('self._henry_layout = HenryLayout()',
        'self._henry_layout.draw(self, state', 'self._henry_layout.draw_error(self)')):
      return source
    raise ValueError('發現不完整的 Henry 版面修改，保留原檔')
  alerts = [n for n in ast.walk(methods['render']) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == '_draw_alert_overlay']
  if len(alerts) != 1 or alerts[0] not in methods['render'].body:
    raise ValueError('HUD 警告繪製位置不同，保留原檔')
  if not any(isinstance(n, ast.Name) and n.id == 'scene' and isinstance(n.ctx, ast.Store)
             for n in ast.walk(methods['_render_world'])):
    raise ValueError('HUD 場景介面不同，保留原檔')
  lines = source.splitlines(keepends=True)
  additions = [] if has_overlay else [(methods['__init__'].end_lineno,
                '        from cluster_yolo_overlay import ObjectOverlay\n        self._yolo_overlay = ObjectOverlay.from_environment()\n'),
               (methods['_render_world'].end_lineno,
                "        if getattr(self, '_yolo_overlay', None) is not None:\n            self._yolo_overlay.draw_world(self, scene, state)\n"),
               (alerts[0].lineno-1,
                "        if getattr(self, '_yolo_overlay', None) is not None:\n            self._yolo_overlay.draw_status(self, state)\n")]
  # Upgrade an already installed v1 overlay as well as a clean original renderer.
  first = methods['render'].body[0]
  if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
    render_index = first.end_lineno
  else:
    render_index = first.lineno - 1
  additions.extend([(methods['__init__'].end_lineno,
                     '        from cluster_henry_layout import HenryLayout\n        self._henry_layout = HenryLayout()\n'),
                    (render_index, '        if self._henry_layout.draw(self, state, locals().get("signal_lights")):\n'
                     '            self._draw_alert_overlay(getattr(state, "alert", None))\n            return\n'),
                    (alerts[0].lineno-1, '        self._henry_layout.draw_error(self)\n')])
  for index, text in sorted(additions, reverse=True):
    lines.insert(index, text)
  result = ''.join(lines)
  compile(result, 'cluster_renderer.py', 'exec')
  return result


def assert_stopped(root, runtime):
  rows = subprocess.check_output(['ps', '-ax', '-o', 'command='], text=True).splitlines()
  active = [row for row in rows if
            ('Jetlink.app/Contents/MacOS/Jetlink' in row or
             any(str(root/'tools/jetlink'/name) in row for name in ('hud.py', 'mac_hud_supervisor.py')) or
             (str(runtime) in row and 'hud_yolo.py live' in row))]
  if active:
    raise RuntimeError('請先退出 Jetlink App 並停止舊 YOLO 測試，再執行安裝或還原。')


def fetch(revision, path):
  with urllib.request.urlopen(f'{REPO}/{revision}/{path}', timeout=60) as response:
    data = response.read(100001)
  if len(data) > 100000:
    raise ValueError(f'檔案超過上限：{path}')
  return data


def restore(config_path):
  config = json.loads(config_path.read_text())
  root, runtime = Path(config['root']), config_path.parent
  assert_stopped(root, runtime)
  for item in config['changes']:
    target = Path(item['target'])
    if not target.is_file() or digest(target.read_bytes()) != item['installed_sha256']:
      raise ValueError(f'安裝後檔案又被修改，為保留修改未還原：{target}')
  for item in config['changes']:
    target = Path(item['target'])
    if item['backup'] is None:
      target.unlink()
    else:
      atomic_write(target, Path(item['backup']).read_bytes())
  config['installed'] = False
  atomic_write(config_path, json.dumps(config, indent=2).encode())
  print('已還原安裝前的 Mac HUD 檔案；可以照原本方式開啟 Jetlink。')


def install(args):
  root, runtime = args.root.expanduser().resolve(), args.runtime.expanduser().resolve()
  assert_stopped(root, runtime)
  renderer_path = root/CLUSTER/'cluster_renderer.py'
  overlay_path = root/CLUSTER/'cluster_yolo_overlay.py'
  initial = {renderer_path: renderer_path.read_bytes(),
             overlay_path: overlay_path.read_bytes() if overlay_path.exists() else None}
  for name in ('cluster_henry_layout.py', 'henry_font.ttf', 'henry_font.codepoints', 'henry_font.OFL.txt'):
    target = root/CLUSTER/name
    initial[target] = target.read_bytes() if target.exists() else None
  patched = patch_renderer(initial[renderer_path].decode())
  if not (root/'tools/jetlink/hud_runtime.py').is_file():
    raise ValueError('找不到已安裝的 Mac HUD 時鐘／路徑轉接器 hud_runtime.py')
  app = root.parent/'jetlink/macos/build/Jetlink.app/Contents/MacOS/Jetlink'
  if not app.is_file():
    raise ValueError(f'找不到既有 Jetlink App：{app}')
  config_path = runtime/'config.json'
  previous = json.loads(config_path.read_text()) if config_path.exists() else None
  if previous and previous.get('installed'):
    for item in previous['changes']:
      if digest(Path(item['target']).read_bytes()) != item['installed_sha256']:
        raise ValueError('Mac HUD 已有後續修改；保留檔案，請先確認修改內容')
  source = runtime/f"source-{args.revision[:12]}"
  manifest = json.loads(fetch(args.revision, 'tools/jetlink/yolo/mac_manifest.json'))
  if manifest.get('version') != 1 or not 5 <= len(manifest['files']) <= 20:
    raise ValueError('套件清單格式錯誤')
  for name, expected in manifest['files'].items():
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or not name.startswith(('tools/jetlink/', str(CLUSTER)+'/')):
      raise ValueError('套件路徑不合法')
    data = fetch(args.revision, name)
    if digest(data) != expected:
      raise ValueError(f'檔案雜湊不符：{name}')
    atomic_write(source/path, data)
  python = runtime/'venv/bin/python'
  if not python.exists():
    subprocess.run([sys.executable, '-m', 'venv', str(runtime/'venv')], check=True)
  print('準備獨立 YOLO 環境與模型，首次下載需要幾分鐘。', flush=True)
  subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(source/'tools/jetlink/yolo/requirements.txt'),
                  'torch==2.5.1', 'torchvision==0.20.1', 'ultralytics==8.3.40', 'onnx==1.19.1', 'ml-dtypes==0.5.3'], check=True)
  subprocess.run([str(python), str(source/'tools/jetlink/yolo/prepare_model.py'), str(runtime/'model')], check=True)
  changes = {renderer_path: patched.encode(), overlay_path: (source/CLUSTER/'cluster_yolo_overlay.py').read_bytes()}
  for target in initial:
    if target not in changes:
      changes[target] = (source/CLUSTER/target.name).read_bytes()
  for target, original in initial.items():
    if (target.read_bytes() if target.exists() else None) != original:
      raise ValueError('準備期間 HUD 檔案已改變，未套用補丁')
  backup = runtime/'backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
  backup.mkdir(parents=True)
  records, rollback = [], {}
  prior = {item['target']: item for item in previous['changes']} if previous and previous.get('installed') else {}
  for target, data in changes.items():
    rollback[target] = target.read_bytes() if target.exists() else None
    saved = None
    if str(target) in prior:
      saved = prior[str(target)]['backup']
    elif rollback[target] is not None:
      saved = str(backup/target.name)
      Path(saved).write_bytes(rollback[target])
    records.append({'target': str(target), 'backup': saved, 'installed_sha256': digest(data)})
  # Recheck after slow model preparation, in case the user reopened the App.
  assert_stopped(root, runtime)
  for target in changes:
    current = target.read_bytes() if target.exists() else None
    if current != rollback[target]:
      raise ValueError('準備期間 HUD 檔案已改變，未套用補丁')
  try:
    for target, data in changes.items():
      atomic_write(target, data)
    config = {'installed': True, 'revision': args.revision, 'root': str(root), 'source': str(source),
              'app': str(app), 'changes': records}
    atomic_write(config_path, json.dumps(config, indent=2).encode())
    for name, command in [('Start-YOLO.command', [str(python), str(source/'tools/jetlink/yolo/mac_launcher.py'), str(config_path)]),
                          ('Restore-HUD.command', [str(python), str(source/'tools/jetlink/yolo/install_mac_yolo.py'), '--restore', '--runtime', str(runtime)])]:
      script = '#!/bin/bash\nset -euo pipefail\n' + shlex.join(command) + '\n'
      atomic_write(runtime/name, script.encode())
      (runtime/name).chmod(0o700)
  except BaseException:
    for target, data in rollback.items():
      if data is None: target.unlink(missing_ok=True)
      else: atomic_write(target, data)
    if previous is not None: atomic_write(config_path, json.dumps(previous, indent=2).encode())
    else: config_path.unlink(missing_ok=True)
    raise
  print(f'安裝完成。停車測試請執行：bash {shlex.quote(str(runtime/"Start-YOLO.command"))}')
  print('沒有切換任何 Git 分支；原有 Jetlink App、大模型及 C4 未被更新。')


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--revision')
  parser.add_argument('--root', type=Path, default=Path.home()/'CarrotMacHUD/carrot')
  parser.add_argument('--runtime', type=Path, default=Path.home()/'CarrotHUD-YOLO')
  parser.add_argument('--restore', action='store_true')
  args = parser.parse_args()
  if sys.platform != 'darwin' or sys.version_info[:2] != (3, 12):
    parser.error('請在 Mac 使用 python3.12 執行')
  if args.restore:
    restore(args.runtime.expanduser()/'config.json')
  elif not args.revision or not re.fullmatch('[0-9a-f]{40}', args.revision):
    parser.error('--revision 必須指定完整、固定的 GitHub commit SHA')
  else:
    install(args)


if __name__ == '__main__':
  main()
