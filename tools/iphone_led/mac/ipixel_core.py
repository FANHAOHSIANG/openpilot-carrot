"""LED test controller with an optional read-only Mac HUD input.

The pypixelcolor 0.5.0 adapter uses DeviceSession/SendPlan directly so that a
failed CommandResult is never hidden by AsyncClient's data-only return value.
"""
from __future__ import annotations

import asyncio
import copy
import dataclasses
import datetime as dt
import json
import math
import os
import platform
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path

import effects
from hud_link import DisplayPolicy, HudReader
from loy_protocol import LoyCommandRejected, LoySession, PROBE_SIZE, text_mask

VERSION = "0.4.1"
PRESETS = ("test", "brake", "left", "right", "chinese", "decel", "pause_thanks", "thanks", "traffic")
PRESET_TEXT = {"test": "TEST", "brake": "煞車", "chinese": "測試", "decel": "減速中",
               "left": "左轉彎", "right": "右轉彎", "pause_thanks": "暫停一下謝謝",
               "thanks": "謝謝", "traffic": "前方塞車"}
PRESET_COLOR = {"test": "ffffff", "brake": "ff3020", "chinese": "00c6b0",
                "decel": "ff3020", "left": "ffb000", "right": "ffb000",
                "pause_thanks": "ffb000", "thanks": "ffb000", "traffic": "ff3020"}
FRAME_LABELS = {**PRESET_TEXT, "blank": "清屏"}


def uuid_key(value):
    value = str(value).lower()
    if re.fullmatch(r"[0-9a-f]{4}", value):
        return f"0000{value}-0000-1000-8000-00805f9b34fb"
    if re.fullmatch(r"[0-9a-f]{8}", value):
        return f"{value}-0000-1000-8000-00805f9b34fb"
    return value


def describe_gatt(services):
    """Enumerate metadata only. No reads, writes or notify subscriptions."""
    rows = []
    for service in services:
        chars = []
        for char in service.characteristics:
            chars.append({"uuid": uuid_key(char.uuid), "handle": char.handle,
                          "properties": list(char.properties),
                          "description": getattr(char, "description", "")})
        rows.append({"uuid": uuid_key(service.uuid), "handle": service.handle,
                     "characteristics": chars})
    return rows


def identify_profile(services, device_name=""):
    # FFF UUIDs are reused by unrelated hardware. Match the YS advertising
    # name and the specific service/properties before allowing a LOY trial.
    definitions = [
        ("ipixel-fa", "fa02", "fa03", "iPixel FA02/FA03 通道"),
        ("loy-fff-candidate", "fff2", "fff1", "LOY 系列 FFF 通道候選，需確認協定"),
        ("a800-candidate", "a802", "a801", "A800 通道候選，需確認協定"),
    ]
    matches = []
    for service in services:
        chars = service["characteristics"]
        for name, write, notify, label in definitions:
            tx = [c for c in chars if c["uuid"] == uuid_key(write)
                  and set(c["properties"]) & {"write", "write-without-response"}]
            rx = [c for c in chars if c["uuid"] == uuid_key(notify)
                  and set(c["properties"]) & {"notify", "indicate"}]
            if len(tx) == len(rx) == 1:
                if (name == "loy-fff-candidate" and service["uuid"] == uuid_key("fff0")
                        and re.fullmatch(r"YS[0-9]+", device_name, re.IGNORECASE)
                        and "write-without-response" in tx[0]["properties"]
                        and "notify" in rx[0]["properties"]):
                    name, label = "loy-fff", "YS 系列 FFF0／FFF2／FFF1"
                matches.append({"profile": name, "label": label,
                                "service": service["uuid"], "write": tx[0]["uuid"],
                                "notify": rx[0]["uuid"]})
    if len(matches) == 1:
        return matches[0]
    return {"profile": "ambiguous" if matches else "unknown",
            "label": "多組候選通道，需確認" if matches else "未知通道，需讀取診斷紀錄",
            "matches": matches}


class ProtocolMismatchError(RuntimeError):
    pass


def packet_size(mtu: int) -> int:
    # Conservative size, also valid before a larger ATT MTU has been negotiated.
    return min(180, max(20, int(mtu) - 3))


def dimensions(info, known_types: dict) -> dict:
    known = info.device_type in known_types
    return {"device_type": info.device_type,
            "width": info.width if known else None,
            "height": info.height if known else None,
            "dimensions_known": known,
            "mcu_version": info.mcu_version,
            "note": "裝置回報型號對照" if known else "未知型號，請手動選擇解析度"}


def draw_symbol(kind: str, width: int, height: int):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (width, height), "black")
    if kind == "blank":
        return image
    draw = ImageDraw.Draw(image)
    cy = height // 2
    half = max(3, min(height // 2 - 1, 12))
    start, end = max(1, width // 5), min(width - 2, width * 4 // 5)
    thickness = max(2, height // 5)
    draw.line((start, cy, end, cy), fill="#ffb000", width=thickness)
    head = min(half + 1, (end - start) // 2)
    if kind == "left":
        draw.polygon([(start, cy), (start + head, cy - half),
                      (start + head, cy + half)], fill="#ffb000")
    elif kind == "right":
        draw.polygon([(end, cy), (end - head, cy - half),
                      (end - head, cy + half)], fill="#ffb000")
    else:
        raise ValueError("未知圖示")
    return image


class PixelBackend:
    """All methods must run on the same asyncio loop, one operation at a time."""
    def __init__(self):
        self.session = None
        self.loy = None
        self.info = None
        self.render_info = None
        self.gatt_report = None
        self.scan_cache = {}

    @property
    def connected(self):
        if self.loy:
            return self.loy.client.is_connected
        session = self.session
        return bool(session and session.is_connected and session._client
                    and session._client.is_connected)

    async def scan(self, show_all=False):
        from bleak import BleakScanner
        found = await BleakScanner.discover(timeout=7.0, return_adv=True)
        self.scan_cache = {}
        rows = []
        for device, adv in found.values():
            name = adv.local_name or device.name or "未命名設備"
            services = [s.lower() for s in (adv.service_uuids or [])]
            candidate = (name.upper().startswith(("LED_BLE", "YS", "LOY")) or "ipixel" in name.lower()
                         or "000000fa-0000-1000-8000-00805f9b34fb" in services
                         or "0000fa01-0000-1000-8000-00805f9b34fb" in services
                         or uuid_key("fff0") in services or uuid_key("a800") in services)
            if candidate or show_all:
                self.scan_cache[device.address] = (device, name)
                rows.append({"id": device.address, "name": name, "rssi": adv.rssi,
                             "candidate": candidate})
        return sorted(rows, key=lambda row: (not row["candidate"], -row["rssi"]))

    async def _open_gatt(self, address):
        from bleak import BleakClient
        device, name = self.scan_cache.get(address, (address, ""))
        report = {"device_id": address, "device_name": name,
                  "time": dt.datetime.now().astimezone().isoformat(),
                  "services": [], "completed": False, "read_only_gatt": True, "application_writes": 0,
                  "identification": {"profile": "unknown", "label": "尚未辨識"}}
        self.gatt_report = report
        # Reuse the device object returned by this Mac's scan. Do not substitute
        # a phone MAC address or infer a different peer from the display name.
        raw = BleakClient(device)
        try:
            await asyncio.wait_for(raw.connect(), 25)
            report["services"] = describe_gatt(raw.services)
            report["identification"] = identify_profile(report["services"], name)
            report["completed"] = True
            return raw
        except BaseException as exc:
            report["completed"] = False
            report["error"] = f"{type(exc).__name__}: {exc}"
            await self._close_gatt(raw)
            raise

    @staticmethod
    async def _close_gatt(raw):
        try:
            await asyncio.wait_for(raw.disconnect(), 5)
        except Exception:
            pass

    async def inspect(self, address):
        if self.connected:
            raise ValueError("請先斷線再檢查通道")
        raw = await self._open_gatt(address)
        await self._close_gatt(raw)
        return self.gatt_report

    async def connect(self, address):
        await self.disconnect()
        raw = await self._open_gatt(address)
        report = self.gatt_report
        profile = report["identification"]
        if profile["profile"] == "loy-fff":
            try:
                service = raw.services.get_service(profile["service"])
                self.loy = LoySession(raw, service.get_characteristic(profile["write"]),
                                      service.get_characteristic(profile["notify"]), report)
                replied = await self.loy.probe()
            except BaseException as exc:
                self.loy = None
                report["error"] = f"{type(exc).__name__}: {exc}"
                await self._close_gatt(raw)
                raise
            return {"profile": "loy-fff", "width": None, "height": None,
                    "dimensions_known": False,
                    "note": ("FFF1 收到裝置查詢回覆" if replied else "裝置查詢尚無可辨識回覆")
                    + "。可先試小範圍 TEST。"}
        await self._close_gatt(raw)
        if profile["profile"] != "ipixel-fa":
            raise ProtocolMismatchError(
                f"{profile['label']}。請下載診斷紀錄以確認這台屏幕的協定。")
        from pypixelcolor.lib.device_session import DeviceSession
        from pypixelcolor.lib.device_info import DEVICE_TYPE_MAP

        self.session = DeviceSession(address)
        try:
            info = await asyncio.wait_for(self.session.connect(), 25)
            self.info = info
            self.render_info = info if info.device_type in DEVICE_TYPE_MAP else None
            return dimensions(info, DEVICE_TYPE_MAP)
        except BaseException:
            await self.disconnect()
            raise

    async def disconnect(self):
        loy, self.loy = self.loy, None
        if loy:
            try:
                await loy.exit_drawing()
            finally:
                await self._close_gatt(loy.client)
        # Close the raw client as well: upstream's connected flag can be false
        # after a dropped link or a partially completed connection handshake.
        session, self.session = self.session, None
        self.info = self.render_info = None
        if session:
            raw = getattr(session, "_client", None)
            if raw:
                await self._close_gatt(raw)

    def set_resolution(self, width, height):
        if self.loy:
            self.loy.size = (width, height)
            return
        if not self.info:
            raise RuntimeError("請先連線")
        self.render_info = dataclasses.replace(self.info, width=width, height=height)

    async def command(self, name, **kwargs):
        from pypixelcolor.commands import COMMANDS
        from pypixelcolor.lib.transport.send_plan import send_plan
        if not self.connected:
            raise RuntimeError("藍牙連線已中斷")
        session = self.session
        raw = session._client
        plan = COMMANDS[name](**kwargs)
        try:
            mtu = raw.mtu_size
        except Exception:
            mtu = 23
        plan.chunk_size = packet_size(mtu)
        result = await send_plan(raw, plan, session._ack_mgr, ack_timeout=6.0)
        if not result.success:
            raise RuntimeError(result.message or "裝置未確認傳送結果")

    async def send(self, kind, text="", color="ffffff"):
        if self.loy:
            size = self.loy.size
            if not size:
                if kind != "test":
                    raise RuntimeError("解析度未知，請先輸入屏幕的實際像素")
                size = PROBE_SIZE
            if kind == "blank":
                return await self.loy.draw(size)
            if kind in PRESET_TEXT or kind == "custom":
                mask = text_mask(PRESET_TEXT.get(kind, text), *size)
                rgb = bytes.fromhex(PRESET_COLOR.get(kind, color))
            else:
                mask = draw_symbol(kind, *size).convert("L").point(
                    lambda v: 255 if v else 0, mode="1")
                rgb = bytes.fromhex("ffb000")
            return await self.loy.draw(size, mask, rgb)
        if not self.render_info:
            raise RuntimeError("解析度未知：請先手動選擇解析度")
        if kind in PRESET_TEXT or kind == "custom":
            value = PRESET_TEXT.get(kind, text)
            await self.command("send_text", text=value,
                               color=PRESET_COLOR.get(kind, color), animation="static",
                               save_slot=0, char_height=min(16, self.render_info.height),
                               device_info=self.render_info)
        else:
            image = draw_symbol(kind, self.render_info.width, self.render_info.height)
            with tempfile.TemporaryDirectory(prefix="ipixel-frame-") as folder:
                path = Path(folder) / "frame.png"
                image.save(path)
                await self.command("send_image", path=path, save_slot=0,
                                   device_info=self.render_info)

    async def brightness(self, value):
        if self.loy:
            await self.loy.brightness(value)
            return
        await self.command("set_brightness", level=value)

    async def send_styled(self, style, tick):
        if not self.loy or not self.loy.size:
            raise RuntimeError("請先連接 LOY 屏幕並套用解析度")
        mask = text_mask(style["text"], *self.loy.size, bold=style.get("weight") == "bold")
        image, color = effects.render(mask, style, tick)
        if style["effect"] in ("scroll_left", "scroll_right"):
            return await self.loy.draw(self.loy.size, image, color, full_frame=True)
        return await self.loy.draw(self.loy.size, image, color)

    async def screen_power(self, on):
        if not self.loy:
            raise ValueError("請先連接相容的 LOY 屏幕")
        return await self.loy.screen_power(on)


class DemoBackend:
    """Explicit UI/offline demonstration, never represents a real LED test."""
    def __init__(self):
        self.connected = False
        self.gatt_report = None

    async def inspect(self, address):
        self.gatt_report = {"device_id": address, "services": [], "completed": True,
                            "read_only_gatt": True, "application_writes": 0,
                            "identification": {"profile": "demo", "label": "模擬通道資料"}}
        return self.gatt_report

    async def scan(self, show_all=False):
        await asyncio.sleep(.1)
        return [{"id": "DEMO-ONLY", "name": "模擬 LED（非實體設備）", "rssi": -50,
                 "candidate": True}]

    async def connect(self, address):
        self.connected = True
        return {"device_type": 131, "width": 64, "height": 16,
                "dimensions_known": True, "note": "模擬資料", "mcu_version": "demo"}

    async def disconnect(self):
        self.connected = False

    def set_resolution(self, width, height):
        pass

    async def send(self, kind, text="", color="ffffff"):
        await asyncio.sleep(.05)

    async def brightness(self, value):
        await asyncio.sleep(.01)


class Controller:
    def __init__(self, backend, result_dir: Path, demo=False, settings_path=None):
        self.backend = backend
        self.result_dir = result_dir
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = result_dir / "events.jsonl"
        self.demo = demo
        self.devices = []
        self.selected = None
        self.device_info = None
        self.override = None
        self.task = None
        self.stop_event = asyncio.Event()
        self.busy = ""
        self.message = "先讓手機上的 LOY PLAY／CP 搭子斷線，再掃描並檢查通道。"
        self.error = ""
        self.expected = "尚未傳送"
        self.events = []
        self.test_progress = None
        self.hud_link = None
        self.settings_path = settings_path or Path.home() / "Library/Application Support/CarrotLED/styles.json"
        self.styles = effects.defaults(PRESET_TEXT, PRESET_COLOR)
        self.style_revision = 0
        self.custom_style = None
        self.custom_slots = [None] * 5
        self.custom_path = self.settings_path.with_name("custom_presets.json")
        try:
            slots = json.loads(self.custom_path.read_text(encoding="utf-8"))
            if isinstance(slots, list) and len(slots) == 5:
                for index, slot in enumerate(slots):
                    if slot is not None:
                        test = effects.defaults(PRESET_TEXT, PRESET_COLOR)
                        test["left"] = slot
                        self.custom_slots[index] = effects.validate(test)["left"]
        except (OSError, ValueError, TypeError):
            pass
        self.auto_hud = True
        self.auto_hud_next = 0.0
        self.auto_allowed = True
        self.auto_task = None
        self.connection_path = self.settings_path.with_name("connection.json")
        self.remembered = None
        try:
            remembered = json.loads(self.connection_path.read_text(encoding="utf-8"))
            if isinstance(remembered.get("id"), str) and isinstance(remembered.get("name"), str):
                self.remembered = remembered
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        try:
            self.styles = effects.validate(json.loads(self.settings_path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            pass
        self.visual = "尚未確認"
        self.last_send_complete = False
        self.stats = dict(requests=0, completed=0, failed=0, retries=0, reconnects=0)
        self.latencies = []
        self._record("session", version=VERSION, demo=demo,
                     python=platform.python_version(), platform=sys.platform)

    def _record(self, event, **fields):
        row = {"time": dt.datetime.now().astimezone().isoformat(timespec="milliseconds"),
               "event": event, **fields}
        self.events.append(row)
        self.events = self.events[-45:]
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def snapshot(self):
        connected = bool(self.backend.connected)
        values = sorted(self.latencies)
        p95 = values[min(len(values) - 1, max(0, math.ceil(len(values) * .95) - 1))] if values else None
        return copy.deepcopy({"version": VERSION, "demo": self.demo,
            "devices": self.devices, "selected": self.selected,
            "connected": connected, "device_info": self.device_info,
            "override": self.override, "busy": self.busy, "message": self.message,
            "error": self.error, "expected": self.expected, "visual": self.visual,
            "stats": self.stats, "test_progress": self.test_progress, "hud_link": self.hud_link,
            "styles": self.styles, "custom_style": self.custom_style, "custom_slots": self.custom_slots, "auto_hud": self.auto_hud, "auto_enabled": self.auto_allowed,
            "average_ms": round(statistics.mean(values)) if values else None,
            "p95_ms": round(p95) if p95 is not None else None,
            "events": self.events, "log_folder": str(self.result_dir),
            "gatt_report": getattr(self.backend, "gatt_report", None),
            "can_confirm_visual": self.last_send_complete and connected and not self.busy,
            "physical_display_verified": self.last_send_complete and self.visual == "目視正常"
            and connected and not self.demo})

    async def dispatch(self, action, payload):
        if action == "styles":
            styles = effects.validate(payload.get("styles"))
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.settings_path.parent, delete=False) as out:
                name = out.name
                try:
                    json.dump(styles, out, ensure_ascii=False)
                except BaseException:
                    os.unlink(name)
                    raise
            try:
                os.replace(name, self.settings_path)
            except BaseException:
                os.unlink(name)
                raise
            self.styles = styles
            self.style_revision += 1
            self.message = "文字與特效已儲存。"
            self._record("styles_saved")
            return
        if action == "save_custom_slots":
            slots = payload.get("slots")
            if not isinstance(slots, list) or len(slots) != 5:
                raise ValueError("需要五組自訂文字")
            checked = []
            for slot in slots:
                if slot is None or (isinstance(slot, dict) and not str(slot.get("text", "")).strip()):
                    checked.append(None)
                else:
                    test = effects.defaults(PRESET_TEXT, PRESET_COLOR)
                    test["left"] = slot
                    checked.append(effects.validate(test)["left"])
            self.custom_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.custom_path.parent, delete=False) as f:
                name = f.name
                json.dump(checked, f, ensure_ascii=False)
            try:
                os.replace(name, self.custom_path)
            except BaseException:
                os.unlink(name)
                raise
            self.custom_slots = checked
            self.message = "五組自訂文字已儲存。"
            self._record("custom_slots_saved")
            return
        if action == "activate_custom_slot":
            index = payload.get("index")
            if type(index) is not int or not 0 <= index < 5 or self.custom_slots[index] is None:
                raise ValueError("請先填寫並儲存該組文字")
            await self.dispatch("custom_standby", self.custom_slots[index])
            return
        if action in ("custom_standby", "clear_standby"):
            if self.busy and self.busy != "hud_link":
                raise ValueError("目前正在執行操作，請先停止或等候完成")
            if not self.backend.connected or not self.override:
                raise ValueError("請先連接屏幕並套用解析度")
            if action == "custom_standby":
                values = copy.deepcopy(self.styles)
                values["left"] = {"text": payload.get("text"), "color": payload.get("color"),
                                  "effect": payload.get("effect", "static"), "speed": payload.get("speed", 1)}
                if "weight" in payload:
                    values["left"]["weight"] = payload["weight"]
                self.custom_style = effects.validate(values)["left"]
            else:
                self.custom_style = None
            self.style_revision += 1
            self.message = "待機文字已設定，車況提示結束後會顯示。" if self.custom_style else "已取消待機文字。"
            if self.busy == "hud_link":
                return
            if self.busy:
                raise ValueError("目前正在執行操作，請先停止或等候完成")
            if not self.backend.connected or not self.override:
                raise ValueError("請先連接屏幕並套用解析度")
            self.busy = "standby_once"
            self.stop_event.clear()
            self.task = asyncio.create_task(self._run("standby_once", {}))
            return
        if action == "stop":
            if self.busy == "hud_link":
                self.auto_hud = False
            self.stop_event.set()
            self.message = "停止中：完成或逾時結束目前這一筆後，不再送下一筆。"
            return
        if action == "visual":
            if self.busy or not self.backend.connected:
                raise ValueError("請等傳送完成並保持連線，再目視確認")
            value = payload.get("value")
            if value not in ("目視正常", "畫面異常"):
                raise ValueError("未知確認結果")
            if not self.last_send_complete:
                raise ValueError("請先完成一次傳送，再目視確認")
            self.visual = value
            self._record("visual_confirmation", value=value, expected=self.expected)
            return
        if action == "screen_power" and self.busy == "hud_link":
            if not isinstance(payload.get("on"), bool):
                raise ValueError("請指定開啟或關閉屏幕")
            self.auto_hud = False
            self.stop_event.set()
            if self.task:
                await asyncio.wait_for(asyncio.shield(self.task), 2.7)
        if self.busy:
            raise ValueError("目前正在執行操作，請先停止或等候完成")
        if action not in ("scan", "inspect", "connect", "disconnect", "send", "brightness",
                          "test", "reconnect", "resolution", "screen_power", "hud_link", "effect_preview"):
            raise ValueError("未知操作")
        # Validate before scheduling so malformed requests receive an HTTP error.
        if action in ("connect", "inspect") and not any(d["id"] == payload.get("id") for d in self.devices):
            raise ValueError("請先掃描並選擇清單中的屏幕")
        if action == "inspect" and self.backend.connected:
            raise ValueError("請先斷線再檢查通道")
        if action in ("send", "test", "reconnect", "brightness", "resolution", "screen_power") and not self.backend.connected:
            raise ValueError("請先連接屏幕")
        if action == "screen_power":
            if (self.device_info or {}).get("profile") != "loy-fff":
                raise ValueError("電源開關適用於 YS 系列 LOY 屏幕")
            if not isinstance(payload.get("on"), bool):
                raise ValueError("請指定開啟或關閉屏幕")
        if action == "hud_link":
            mode = payload.get("mode")
            if self.demo or mode not in ("preview", "screen"):
                raise ValueError("請使用實體 HUD 讀取模式")
            if mode == "screen":
                if not self.backend.connected or (self.device_info or {}).get("profile") != "loy-fff":
                    raise ValueError("請先連接 LOY 屏幕")
                if not self.override:
                    raise ValueError("請先套用屏幕解析度，例如 96x16")
                report = getattr(self.backend, "gatt_report", None) or {}
                power = report.get("loy", {}).get("power_status") or {}
                if power.get("on") is False:
                    raise ValueError("請先開啟屏幕")
        if action == "effect_preview":
            if payload.get("kind") not in effects.KINDS:
                raise ValueError("請選擇要預覽的車況")
            if not self.backend.connected or (self.device_info or {}).get("profile") != "loy-fff" or not self.override:
                raise ValueError("請先連接 LOY 屏幕並套用解析度")
        if action == "send":
            kind = payload.get("kind")
            if kind not in (*PRESETS, "blank", "custom"):
                raise ValueError("未知測試畫面")
            if kind == "custom":
                text = payload.get("text", "")
                if not isinstance(text, str) or not 1 <= len(text.strip()) <= 16:
                    raise ValueError("請輸入 1–16 個字")
                if any(ord(c) < 32 for c in text) or "[" in text or "]" in text:
                    raise ValueError("測試文字不接受控制字元或方括號")
                # Keep the tester offline: upstream may download Twemoji for emoji.
                if any(not (32 <= ord(c) <= 126 or 0x3400 <= ord(c) <= 0x9fff
                            or 0xff01 <= ord(c) <= 0xff60
                            or c in "，。！？、：；「」『』（）《》…—") for c in text):
                    raise ValueError("這版先支援中英文、數字及常用標點；箭頭請使用圖示按鈕")
            if not re.fullmatch(r"[0-9a-fA-F]{6}", str(payload.get("color", "ffffff"))):
                raise ValueError("顏色格式錯誤")
        if action == "brightness" and not 1 <= int(payload.get("value", 0)) <= 30:
            raise ValueError("測試亮度請使用 1–30%")
        if action in ("test", "reconnect"):
            count = int(payload.get("count", 30 if action == "test" else 3))
            maximum = 120 if action == "test" else 10
            if not 1 <= count <= maximum:
                raise ValueError("測試次數超出範圍")
            payload = {**payload, "count": count}
        if action == "resolution":
            w, h = int(payload.get("width", 0)), int(payload.get("height", 0))
            if not 16 <= w <= 512 or not 8 <= h <= 128:
                raise ValueError("解析度超出測試範圍")
        if action == "hud_link" and payload.get("mode") == "screen":
            self.auto_hud = True
        self.busy = action
        self.error = ""
        self.stop_event.clear()
        self.task = asyncio.create_task(self._run(action, dict(payload)))

    async def _run(self, action, payload):
        try:
            if action == "scan":
                if self.backend.connected:
                    raise ValueError("請先斷開目前屏幕，再掃描")
                self.message = "掃描中，約需 7 秒…"
                self.devices = await asyncio.wait_for(self.backend.scan(bool(payload.get("all"))), 15)
                self.message = f"找到 {len(self.devices)} 台設備，請選擇你的屏幕。" if self.devices else "沒有找到：確認屏幕通電、手機 App 已斷線，或勾選顯示其他設備再掃描。"
                self._record("scan", count=len(self.devices))
            elif action == "inspect":
                self.selected = next(d for d in self.devices if d["id"] == payload["id"])
                self.message = "讀取藍牙通道清單中…"
                report = await self.backend.inspect(payload["id"])
                self.message = f"通道檢查完成。{report['identification']['label']}。"
                self._record("gatt_inspection", report=report)
            elif action == "connect":
                self.selected = next(d for d in self.devices if d["id"] == payload["id"])
                self.auto_allowed = True
                self.override = [96, 16]
                await self._connect()
                self.remembered = {"id": self.selected["id"], "name": self.selected["name"], "size": self.override}
                self._save_connection()
            elif action == "disconnect":
                self.auto_allowed = False
                await self.backend.disconnect()
                self.last_send_complete = False
                self.visual = "尚未確認"
                self.message = "已斷線。屏幕可能回到原本節目或保留最後畫面。"
                self._record("disconnect")
            elif action == "resolution":
                size = [int(payload["width"]), int(payload["height"])]
                self.backend.set_resolution(*size)
                self.override = size
                if self.remembered:
                    self.remembered["size"] = size
                    self._save_connection()
                self.message = "已套用手動解析度，僅供本次測試。"
                self._record("resolution_override", width=self.override[0], height=self.override[1])
            elif action == "brightness":
                await asyncio.wait_for(self.backend.brightness(int(payload["value"])), 15)
                self.message = "亮度命令已完成，請目視確認。"
                self._record("brightness", value=int(payload["value"]))
            elif action == "screen_power":
                self.auto_hud = payload["on"]
                self.auto_hud_next = 0.0
                self.last_send_complete = False
                self.visual = "尚未確認"
                on = payload["on"]
                verb = "開啟" if on else "關閉"
                self.message = f"正在{verb}屏幕並查詢電源狀態…"
                result = await asyncio.wait_for(self.backend.screen_power(on), 10)
                reported_on = result["reported_on"]
                if reported_on is not None:
                    status = "開啟" if reported_on else "關閉"
                    state = "已" if reported_on == on else "仍"
                    self.message = f"屏幕回報{state}{status}。"
                elif result["acknowledged"]:
                    self.message = f"屏幕已收到{verb}指令，請目視確認。"
                else:
                    self.message = f"已送出{verb}指令，尚未收到屏幕確認。"
                self._record("screen_power", **result)
            elif action == "send":
                await self._send(payload["kind"], payload.get("text", "").strip(), payload.get("color", "ffffff"))
            elif action == "hud_link":
                await self._link_hud(payload["mode"])
            elif action == "effect_preview":
                await self._preview_effect(payload["kind"])
            elif action == "standby_once":
                if self.custom_style:
                    ack = await self.backend.send_styled(self.custom_style, 0)
                    self.expected = self.custom_style["text"]
                else:
                    ack = await self.backend.send("blank")
                    self.expected = "清屏"
                if ack is not True:
                    raise RuntimeError("屏幕未完整確認畫面")
            else:
                await self._test(action, payload["count"])
        except asyncio.CancelledError:
            self._record("cancelled", action=action)
            raise
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, (ProtocolMismatchError, LoyCommandRejected)):
                self.message = "已保存通道及回覆，請下載診斷紀錄。"
            else:
                self.message = "操作未完成，詳情已記錄。"
            self._record("operation_error", action=action, error=self.error)
        finally:
            self.busy = ""

    async def _connect(self):
        self.message = "連線並讀取屏幕資料中…"
        self.device_info = None
        self.last_send_complete = False
        self.visual = "尚未確認"
        info = await asyncio.wait_for(self.backend.connect(self.selected["id"]), 30)
        self.device_info = info
        if self.override:
            self.backend.set_resolution(*self.override)
        if info["dimensions_known"] or self.override:
            self.message = "已連線，可以先試 TEST。"
        elif info.get("profile") == "loy-fff":
            self.message = "已連線，可以先按 TEST 試小畫面。其他圖示請先套用實際解析度。"
        else:
            self.message = "已連線，請先手動套用實際解析度。"
        if info.get("profile") == "loy-fff":
            result = await asyncio.wait_for(self.backend.screen_power(False), 10)
            self._record("connect_power_off", **result)
            self.message = "藍牙已連接，已送出關閉屏幕指令；請按開啟屏幕。"
        self._record("connect", name=self.selected["name"], info=info)

    async def _send(self, kind, text="", color="ffffff"):
        if self.stop_event.is_set():
            return False
        info = self.device_info or {}
        needs_size = not info.get("dimensions_known") and not self.override
        small_test = needs_size and kind == "test" and info.get("profile") == "loy-fff"
        if needs_size and not small_test:
            raise ValueError("解析度未知，請先輸入屏幕的實際像素")
        self.stats["requests"] += 1
        started = time.monotonic()
        self.expected = FRAME_LABELS.get(kind, text)
        if small_test:
            self.expected = "TEST（16 × 8 小區域）"
        self.last_send_complete = False
        self.visual = "尚未確認"
        self.message = "傳送中…"
        for attempt in range(2):
            if attempt and self.stop_event.is_set():
                break
            try:
                if not self.backend.connected:
                    raise ConnectionError("藍牙連線已中斷")
                acknowledged = await asyncio.wait_for(self.backend.send(kind, text, color), 20)
                if not self.backend.connected:
                    raise ConnectionError("傳送期間連線中斷")
                elapsed = round((time.monotonic() - started) * 1000)
                self.stats["completed"] += 1
                self.last_send_complete = True
                self.latencies.append(elapsed)
                self.latencies = self.latencies[-240:]
                if acknowledged is False:
                    self.message = "Mac 已送出資料，部分封包未收到確認，請目視檢查屏幕。"
                else:
                    self.message = "通訊完成，請目視確認屏幕。"
                self._record("send_complete", kind=kind, text=text if kind == "custom" else self.expected,
                             elapsed_ms=elapsed, retried=bool(attempt), loy_acknowledged=acknowledged)
                return True
            except Exception as exc:
                report = getattr(self.backend, "gatt_report", None) or {}
                self._record("send_error", kind=kind, attempt=attempt + 1,
                             error=f"{type(exc).__name__}: {exc}", loy=copy.deepcopy(report.get("loy")))
                if attempt == 0 and not self.stop_event.is_set() and not isinstance(exc, LoyCommandRejected):
                    self.stats["retries"] += 1
                    await self.backend.disconnect()
                    if not await self._pause(2):
                        break
                    try:
                        await self._connect()
                        self.stats["reconnects"] += 1
                        continue
                    except Exception as reconnect_error:
                        self._record("reconnect_error", error=str(reconnect_error))
                self.error = f"{type(exc).__name__}: {exc}"
                break
        self.stats["failed"] += 1
        self.message = "這次傳送失敗，未計為完成；屏幕可能仍留著上一個畫面。"
        return False

    async def _link_hud(self, mode):
        publish = mode == "screen"
        status = self.hud_link = {"mode": mode, "active": True, "updates": 0,
                                  "path": None, "sample": None, "pattern": "黑屏"}
        policy = DisplayPolicy()
        previous = None
        sent = None
        effect_start = time.monotonic()
        active_style = None
        self.message = "等候 Mac HUD 車況…"
        if publish:
            self.last_send_complete = False
            self.visual = "尚未確認"
        self._record("hud_link_start", mode=mode)
        cleanup_error = ""
        try:
            async with HudReader() as reader:
                while not self.stop_event.is_set():
                    if reader.error:
                        raise RuntimeError(reader.error)
                    if publish and not self.backend.connected:
                        raise ConnectionError("屏幕藍牙連線中斷")
                    sample = reader.current()
                    kind = policy.choose(sample)
                    label = FRAME_LABELS[kind]
                    if kind == "blank" and sample is not None and self.custom_style:
                        kind = "custom_standby"
                        label = self.custom_style["text"]
                    status.update(updates=reader.updates, path=reader.path,
                                  sample=dataclasses.asdict(sample) if sample else None,
                                  pattern=label)
                    decision = (sample is not None, kind)
                    if decision != previous:
                        self._record("hud_link_state", mode=mode, kind=kind, sample=status["sample"])
                        self.message = ("正在連動屏幕。" if publish else "正在預覽 HUD 車況。") if sample else (
                            "HUD 資料暫停，等候有效車況。" if reader.updates else "等候 Mac HUD 車況…")
                        previous = decision
                    style = self.custom_style if kind == "custom_standby" else self.styles.get(kind)
                    style_key = (kind, self.style_revision)
                    if style_key != active_style:
                        effect_start = time.monotonic()
                        active_style = style_key
                    tick = int((time.monotonic() - effect_start) * 3)
                    frame = (style_key, effects.signature(style, tick)) if style else (kind, None)
                    if publish and frame != sent:
                        # Use only the current sample. A failed frame is never retried.
                        sent = None
                        default = effects.defaults(PRESET_TEXT, PRESET_COLOR).get(kind)
                        operation = (self.backend.send(kind) if style is None or style == default
                                     else self.backend.send_styled(style, tick))
                        ack = await asyncio.wait_for(operation, 2.5)
                        self._record("hud_link_send", kind=kind, acknowledged=ack)
                        if ack is not True:
                            raise RuntimeError("屏幕未完整確認連動畫面")
                        sent = frame
                        self.expected = style["text"] if style else label
                    await self._pause(0.05)
        finally:
            if publish and sent != ("blank", None):
                try:
                    if not self.backend.connected:
                        raise ConnectionError("屏幕藍牙已斷線")
                    ack = await asyncio.wait_for(self.backend.send("blank"), 2.5)
                    if ack is not True:
                        raise RuntimeError("屏幕未完整確認清屏")
                    self.expected = "清屏"
                except Exception as exc:
                    cleanup_error = f"{type(exc).__name__}: {exc}"
                    status["clear_error"] = cleanup_error
                    self._record("hud_link_clear_error", error=cleanup_error)
            status["active"] = False
            self._record("hud_link_stop", mode=mode, updates=status["updates"])
        self.message = ("連動已停止。請目視確認屏幕是否清除。" if cleanup_error else "HUD 測試已停止。")

    async def _preview_effect(self, kind):
        style = self.styles[kind]
        self.last_send_complete = False
        self.visual = "尚未確認"
        self.expected = style["text"]
        self.message = "特效預覽中，按停止結束。"
        start = time.monotonic()
        previous = None
        try:
            while not self.stop_event.is_set():
                tick = int((time.monotonic() - start) * 3)
                frame = effects.signature(style, tick)
                if frame != previous:
                    ack = await asyncio.wait_for(self.backend.send_styled(style, tick), 2.5)
                    if ack is not True:
                        raise RuntimeError("屏幕未完整確認預覽畫面")
                    previous = frame
                await self._pause(0.05)
        finally:
            if self.backend.connected:
                await asyncio.wait_for(self.backend.send("blank"), 2.5)
        self.message = "特效預覽已停止。"

    async def _pause(self, seconds):
        try:
            await asyncio.wait_for(self.stop_event.wait(), seconds)
            return False
        except asyncio.TimeoutError:
            return True

    async def _test(self, action, count):
        if action == "test" and not (self.override or (self.device_info or {}).get("dimensions_known")):
            raise ValueError("解析度未知，請先套用實際像素再做連續測試")
        self.test_progress = {"mode": action, "done": 0, "total": count, "stopped": False}
        consecutive_failures = 0
        for index in range(count):
            if self.stop_event.is_set():
                break
            if action == "reconnect":
                await self.backend.disconnect()
                if not await self._pause(1):
                    break
                await self._connect()
                self.stats["reconnects"] += 1
                if self.stop_event.is_set():
                    break
            ok = await self._send("test" if action == "reconnect" else PRESETS[index % len(PRESETS)])
            self.test_progress["done"] = index + 1
            consecutive_failures = 0 if ok else consecutive_failures + 1
            if consecutive_failures >= 3:
                self.error = "連續 3 次傳送失敗，已停止測試。"
                break
            if index + 1 < count and not await self._pause(3):
                break
        self.test_progress["stopped"] = self.stop_event.is_set()
        self.message = "測試已停止。" if self.stop_event.is_set() else "測試流程結束，可下載紀錄；仍請確認實際畫面。"
        self._record("test_end", progress=self.test_progress, stats=self.stats)

    def _save_connection(self):
        self.connection_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection_path.write_text(json.dumps(self.remembered, ensure_ascii=False), encoding="utf-8")

    async def auto_connect_loop(self):
        next_scan = 0.0
        while True:
            now = time.monotonic()
            if self.remembered and self.auto_allowed and not self.backend.connected and not self.busy and now >= next_scan:
                next_scan = now + 15
                self.busy = "auto_connect"
                try:
                    devices = await asyncio.wait_for(self.backend.scan(False), 15)
                    match = next((d for d in devices if d["id"] == self.remembered["id"]), None)
                    if match:
                        self.devices = devices
                        self.selected = match
                        size = self.remembered.get("size")
                        self.override = size if isinstance(size, list) and len(size) == 2 and all(type(v) is int for v in size) and 16 <= size[0] <= 512 and 8 <= size[1] <= 128 else None
                        await self._connect()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._record("auto_connect_error", error=f"{type(exc).__name__}: {exc}")
                    await self.backend.disconnect()
                finally:
                    self.busy = ""
            report = getattr(self.backend, "gatt_report", None) or {}
            power = report.get("loy", {}).get("power_status") or {}
            if (self.auto_hud and self.backend.connected and not self.busy and self.override
                and (self.device_info or {}).get("profile") == "loy-fff"
                and power.get("on") is True and time.monotonic() >= self.auto_hud_next):
                self.auto_hud_next = time.monotonic() + 15
                try:
                    await self.dispatch("hud_link", {"mode": "screen"})
                    self._record("hud_auto_start")
                except Exception as exc:
                    self._record("hud_auto_error", error=f"{type(exc).__name__}: {exc}")
            await asyncio.sleep(1)

    async def shutdown(self):
        if self.auto_task:
            self.auto_task.cancel()
            try:
                await self.auto_task
            except asyncio.CancelledError:
                pass
        self.stop_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await self.backend.disconnect()
        self._record("shutdown")
