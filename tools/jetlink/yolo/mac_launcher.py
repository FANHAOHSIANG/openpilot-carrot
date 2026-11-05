"""Launch the existing Jetlink App and independent YOLO worker with a shared file.

No branch changes, no second HUD renderer, no global launchctl environment.
"""
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys

from install_mac_yolo import assert_stopped, digest


def main():
  config_path = Path(sys.argv[1]).resolve()
  config = json.loads(config_path.read_text())
  if not config.get('installed'):
    raise SystemExit('YOLO overlay 已還原，請重新安裝後再啟動。')
  root, source, runtime = Path(config['root']), Path(config['source']), config_path.parent
  assert_stopped(root, runtime)
  for item in config['changes']:
    if digest(Path(item['target']).read_bytes()) != item['installed_sha256']:
      raise SystemExit('HUD 檔案已更新，請重新檢查／安裝 YOLO 相容補丁。')
  adapter = runpy.run_path(str(root/'tools/jetlink/hud_runtime.py'))
  snapshot = str(adapter['PACKET'])
  manifest = json.loads((runtime/'model/manifest.json').read_text())
  output = runtime/'objects.json'
  env = dict(os.environ)
  env['PYTHONPATH'] = str(root) + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
  env['CARROT_HUD_YOLO_FILE'] = str(output)
  worker = subprocess.Popen([sys.executable, '-u', str(source/'tools/jetlink/hud_yolo.py'), 'live',
                             '--model', str(runtime/'model/yolo11n.onnx'), '--sha256', manifest['onnx_sha256'],
                             '--snapshot', snapshot, '--packet-clock', 'epoch', '--output', str(output)], env=env,
                            start_new_session=True)
  try:
    with (runtime/'jetlink-yolo.log').open('a') as log:
      app = subprocess.Popen([config['app']], env=env, stdout=log, stderr=log, start_new_session=True)
      print('YOLO 與原本 Jetlink App 已啟動。請保持此終端機開啟。', flush=True)
      print('按 Ctrl+C 只停止 YOLO 測試；Jetlink App 仍會繼續運作。', flush=True)
      print(f'影像資料：{snapshot}', flush=True)
      while app.poll() is None:
        if worker.poll() is not None:
          print(f'YOLO 已停止（代碼 {worker.returncode}）；Jetlink App 保持運作。', flush=True)
          return worker.returncode
        try:
          app.wait(timeout=.5)
        except subprocess.TimeoutExpired:
          pass
  except KeyboardInterrupt:
    print('\n正在停止 YOLO；Jetlink App 保持運作。', flush=True)
  finally:
    if worker.poll() is None:
      worker.send_signal(signal.SIGINT)
      try:
        worker.wait(timeout=5)
      except subprocess.TimeoutExpired:
        worker.terminate()
        worker.wait(timeout=5)
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
