#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
on_error() {
  echo
  echo '啟動失敗。請保留這個視窗的訊息及資料夾中的 setup.log。'
  read -r -p '按 Enter 關閉。' _reply || true
}
trap on_error ERR
PYTHON_BIN=''
for candidate in /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3 || true)"; do
  if [ -n "$candidate" ] && [ -x "$candidate" ] && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' 2>/dev/null; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  echo '找不到 Python 3.10 以上版本。請先安裝 Python，再重新雙擊 START.command。'
  on_error
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo '第一次啟動：建立此工具專用的 Python 環境。'
  "$PYTHON_BIN" -m venv .venv
fi
if ! .venv/bin/python -c 'from importlib.metadata import version; import PIL, bleak, pypixelcolor, capnp; assert version("pypixelcolor")=="0.5.0"; assert version("bleak")=="3.0.1"; assert version("pycapnp")=="2.1.0"' 2>/dev/null; then
  echo '下載藍牙及文字顯示套件，第一次啟動需要連上網路。'
  .venv/bin/python -m pip install --disable-pip-version-check --timeout 20 --retries 1 -r requirements.txt 2>&1 | tee setup.log
fi
echo '啟動 LED 藍牙測試工具。若系統詢問藍牙權限，請允許終端機／Python 使用藍牙。'
echo '測試期間請保留此視窗；結束請按網頁上的「結束工具」，或在此按 Control-C。'
.venv/bin/python ipixel_test.py
