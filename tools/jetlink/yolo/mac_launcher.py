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
import time

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
  env['CARROT_HUD_LAYOUT'] = 'henry-v2'
  status_file = runtime/'layout-status.txt'
  status_file.unlink(missing_ok=True)
  env['CARROT_HUD_LAYOUT_STATUS'] = str(status_file)
  worker = subprocess.Popen([sys.executable, '-u', str(source/'tools/jetlink/hud_yolo.py'), 'live',
                             '--model', str(runtime/'model/yolo11n.onnx'), '--sha256', manifest['onnx_sha256'],
                             '--snapshot', snapshot, '--packet-clock', 'epoch', '--output', str(output)], env=env,
                            start_new_session=True)
  try:
    with (runtime/'jetlink-yolo.log').open('a') as log:
      app = subprocess.Popen([config['app']], env=env, stdout=log, stderr=log, start_new_session=True)
      print('正在啟動 Henry V2 寬幅版面與 YOLO，畫面左下應出現 HENRY V2。', flush=True)
      print('按 Ctrl+C 只停止 YOLO 測試；Jetlink App 仍會繼續運作。', flush=True)
      print(f'影像資料：{snapshot}', flush=True)
      started, acknowledged, warned = time.monotonic(), False, False
      while app.poll() is None:
        if not acknowledged and status_file.exists():
          acknowledged = True
          print('HUD 已確認載入 HENRY V2 版面。', flush=True)
        if not acknowledged and not warned and time.monotonic() - started > 30:
          warned = True
          print('尚未收到新版面回報；請確認 App 的 HUD 已啟用。記錄：'+str(runtime/'jetlink-yolo.log'), flush=True)
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
