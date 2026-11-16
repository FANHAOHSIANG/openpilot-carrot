#!/usr/bin/env python3
"""Loopback-only control panel for the standalone LED tester."""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hmac
import io
import json
import logging
import secrets
import signal
import threading
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from ipixel_core import Controller, DemoBackend, PixelBackend, VERSION

ROOT = Path(__file__).resolve().parent


class Worker:
    def __init__(self, result_dir, demo=False):
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.controller = None

        def run():
            asyncio.set_event_loop(self.loop)
            self.controller = Controller(DemoBackend() if demo else PixelBackend(), result_dir, demo)
            if not demo:
                self.controller.auto_task = self.loop.create_task(self.controller.auto_connect_loop())
            self.ready.set()
            self.loop.run_forever()
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()

        self.thread = threading.Thread(target=run, daemon=True, name="ipixel-ble")
        self.thread.start()
        if not self.ready.wait(5):
            raise RuntimeError("無法啟動測試工作程序")

    def submit(self, coroutine, timeout=3):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout)

    def snapshot(self):
        async def read():
            return self.controller.snapshot()
        return self.submit(read())

    def action(self, action, payload):
        return self.submit(self.controller.dispatch(action, payload))

    def stop(self):
        try:
            self.submit(self.controller.shutdown(), timeout=12)
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(3)


def diagnostic_zip(worker):
    state = worker.snapshot()
    state.pop("devices", None)  # Do not include unrelated nearby devices in a shared log.
    package_versions = {}
    for name in ("pypixelcolor", "bleak", "Pillow", "pycapnp"):
        try:
            package_versions[name] = version(name)
        except PackageNotFoundError:
            package_versions[name] = "not installed (demo)"
    state["packages"] = package_versions
    state["verification_note"] = "送出表示 Mac 完成寫入。LOY 封包回覆與使用者目視結果分開記錄。"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("summary.json", json.dumps(state, ensure_ascii=False, indent=2))
        if state.get("gatt_report"):
            archive.writestr("gatt.json", json.dumps(state["gatt_report"], ensure_ascii=False, indent=2))
        for name in ("events.jsonl", "bluetooth.log"):
            path = worker.controller.result_dir / name
            if path.is_file():
                archive.writestr(name, path.read_bytes()[-2_000_000:])
    return buffer.getvalue()


def handler_class(worker, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "iPixelTest/" + VERSION

        def log_message(self, fmt, *args):
            pass

        def _authorized(self):
            host = self.headers.get("Host", "")
            expected = f"127.0.0.1:{self.server.server_port}"
            if host != expected:
                return False
            supplied = self.headers.get("X-iPixel-Token", "")
            return hmac.compare_digest(supplied, token)

        def _reply(self, code, data, content_type="application/json; charset=utf-8", extra=None):
            if isinstance(data, dict):
                data = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                    self._reply(403, {"error": "只允許本機連線"})
                else:
                    self._reply(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
                return
            if not self._authorized():
                self._reply(403, {"error": "請使用啟動視窗顯示的完整網址重新開啟"})
                return
            try:
                if self.path == "/api/state":
                    self._reply(200, worker.snapshot())
                elif self.path == "/api/report":
                    self._reply(200, diagnostic_zip(worker), "application/zip",
                                {"Content-Disposition": 'attachment; filename="LED_diagnostics.zip"'})
                else:
                    self._reply(404, {"error": "找不到頁面"})
            except Exception as exc:
                self._reply(500, {"error": f"{type(exc).__name__}: {exc}"})

        def do_POST(self):
            expected_origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self._authorized() or self.headers.get("Origin", expected_origin) != expected_origin:
                self._reply(403, {"error": "拒絕跨網站或未授權要求"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4096:
                    self._reply(413, {"error": "要求大小不正確"})
                    return
                if self.path != "/api/action":
                    self._reply(404, {"error": "找不到操作"})
                    return
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("操作格式不正確")
                action = payload.pop("action", "")
                if action == "quit":
                    self._reply(200, {"ok": True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                worker.action(action, payload)
                self._reply(200, {"ok": True})
            except (ValueError, TypeError, KeyError) as exc:
                self._reply(400, {"error": str(exc)})
            except Exception as exc:
                self._reply(500, {"error": f"{type(exc).__name__}: {exc}"})
    return Handler


def main():
    parser = argparse.ArgumentParser(description="LED Mac 藍牙測試工具")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--demo", action="store_true", help="僅模擬介面，不接觸藍牙")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    if not args.demo:
        for name, required in (("pypixelcolor", "0.5.0"), ("bleak", "3.0.1")):
            try:
                installed = version(name)
            except PackageNotFoundError:
                installed = None
            if installed != required:
                parser.exit(1, f"需要 {name}=={required}，請使用 START.command 啟動。\n")
    result_dir = ROOT / "results" / dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    result_dir.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    log_handler = RotatingFileHandler(result_dir / "bluetooth.log", maxBytes=1_000_000,
                                     backupCount=1, encoding="utf-8")
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(log_handler)
    logging.getLogger().setLevel(logging.INFO)
    worker = Worker(result_dir, args.demo)
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_class(worker, token))
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}/#{token}"
    print(f"LED Mac Test {VERSION}" + ("  [模擬模式，非實體測試]" if args.demo else ""), flush=True)
    print("請停車測試；先讓手機上的 LED App 斷線。", flush=True)
    print("操作網址：" + url, flush=True)
    print("紀錄資料夾：" + str(result_dir), flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    def stop_handler(signum, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    try:
        server.serve_forever(poll_interval=.2)
    finally:
        server.server_close()
        worker.stop()
        print("工具已結束。屏幕可能保留最後畫面；需要時請關閉屏幕電源。", flush=True)


if __name__ == "__main__":
    main()
