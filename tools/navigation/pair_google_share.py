#!/usr/bin/env python3
"""Generate a Google-share pairing code using only the Python standard library."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import time


def main():
  path = Path(os.environ.get('CARROT_DATA_DIR', '/data/carrot')) / 'state/google-share-pair.json'
  code = f'{secrets.randbelow(1000000):06d}'
  record = {'code_sha256': hashlib.sha256(code.encode()).hexdigest(), 'expires': time.time() + 600}
  path.parent.mkdir(parents=True, exist_ok=True)
  pending = path.with_name(path.name + '.tmp')
  fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
  try:
    with os.fdopen(fd, 'w') as out:
      os.fchmod(out.fileno(), 0o600)
      json.dump(record, out)
    pending.replace(path)
  finally:
    pending.unlink(missing_ok=True)
  print('Google Maps 分享配對碼（10 分鐘內有效、限用一次）：' + code)
  print('在手機以原本 Carrot 網頁的主機與連接埠開啟 /navigation/share，輸入配對碼。')
  print('新配對碼會撤銷舊配對。請勿分享配對碼。')


if __name__ == '__main__':
  main()
