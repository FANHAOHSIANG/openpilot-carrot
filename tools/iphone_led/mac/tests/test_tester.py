import asyncio
import http.client
import io
import json
import sys
import tempfile
import threading
import time
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ipixel_core import (Controller, DemoBackend, PixelBackend, dimensions, draw_symbol,
                         packet_size, describe_gatt, identify_profile, ProtocolMismatchError)
from ipixel_test import Worker, diagnostic_zip, handler_class
from http.server import ThreadingHTTPServer


class FakeBackend(DemoBackend):
    def __init__(self):
        super().__init__()
        self.connected = True
        self.sends = 0
        self.failures = 0

    async def send(self, kind, text="", color="ffffff"):
        self.sends += 1
        if self.failures:
            self.failures -= 1
            raise TimeoutError("fixture: lost ACK")


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backend = FakeBackend()
        self.c = Controller(self.backend, Path(self.tmp.name))
        self.c.selected = {"id": "fixture", "name": "fixture LED"}
        self.c.device_info = {"dimensions_known": True, "width": 64, "height": 16}
        self.c._pause = AsyncMock(return_value=True)

    async def asyncTearDown(self):
        await self.c.shutdown()
        self.tmp.cleanup()

    async def wait_done(self):
        await self.c.task

    async def test_success_is_not_visual_confirmation(self):
        await self.c.dispatch("send", {"kind": "test"})
        await self.wait_done()
        s = self.c.snapshot()
        self.assertEqual(s["stats"]["completed"], 1)
        self.assertFalse(s["physical_display_verified"])
        await self.c.dispatch("visual", {"value": "目視正常"})
        self.assertTrue(self.c.snapshot()["physical_display_verified"])

    async def test_lost_ack_recovers_once_with_correct_counters(self):
        self.backend.failures = 1
        await self.c.dispatch("send", {"kind": "brake"})
        await self.wait_done()
        self.assertEqual(self.backend.sends, 2)
        self.assertEqual(self.c.stats, dict(requests=1, completed=1, failed=0, retries=1, reconnects=1))

    async def test_persistent_failure_is_never_counted_as_success(self):
        self.backend.failures = 20
        await self.c.dispatch("send", {"kind": "test"})
        await self.wait_done()
        self.assertEqual(self.backend.sends, 2)
        self.assertEqual(self.c.stats["failed"], 1)
        self.assertEqual(self.c.stats["completed"], 0)
        self.assertEqual(self.c.latencies, [])

    async def test_stop_during_failure_prevents_reconnect_and_retry(self):
        async def fail_and_stop(*args):
            self.backend.sends += 1
            self.c.stop_event.set()
            raise TimeoutError("fixture stop")
        self.backend.send = fail_and_stop
        await self.c.dispatch("send", {"kind": "test"})
        await self.wait_done()
        self.assertEqual(self.backend.sends, 1)
        self.assertEqual(self.c.stats["reconnects"], 0)

    async def test_stop_during_reconnect_does_not_resend_stale_content(self):
        self.backend.failures = 1
        original = self.backend.connect
        async def connect_and_stop(address):
            info = await original(address)
            self.c.stop_event.set()
            return info
        self.backend.connect = connect_and_stop
        await self.c.dispatch("send", {"kind": "test"})
        await self.wait_done()
        self.assertEqual(self.backend.sends, 1)
        self.assertEqual(self.c.stats["failed"], 1)

    async def test_stop_inside_planned_reconnect_does_not_send_new_frame(self):
        original = self.backend.connect
        async def connect_and_stop(address):
            info = await original(address)
            self.c.stop_event.set()
            return info
        self.backend.connect = connect_and_stop
        await self.c.dispatch("reconnect", {"count": 3})
        await self.wait_done()
        self.assertEqual(self.backend.sends, 0)
        self.assertEqual(self.c.stats["requests"], 0)

    async def test_three_failed_requests_stop_a_long_test(self):
        self.backend.failures = 100
        await self.c.dispatch("test", {"count": 10})
        await self.wait_done()
        self.assertEqual(self.c.stats["requests"], 3)
        self.assertEqual(self.backend.sends, 6)
        self.assertIn("連續 3", self.c.error)

    async def test_two_requests_cannot_overlap(self):
        gate = asyncio.Event()
        async def blocked(*args):
            self.backend.sends += 1
            await gate.wait()
        self.backend.send = blocked
        await self.c.dispatch("send", {"kind": "test"})
        with self.assertRaises(ValueError):
            await self.c.dispatch("send", {"kind": "right"})
        gate.set()
        await self.wait_done()
        self.assertEqual(self.backend.sends, 1)

    async def test_unknown_resolution_blocks_device_writes(self):
        self.c.device_info = {"dimensions_known": False, "width": None, "height": None}
        await self.c.dispatch("send", {"kind": "left"})
        await self.wait_done()
        self.assertEqual(self.backend.sends, 0)
        self.assertIn("解析度未知", self.c.error)

    async def test_loy_small_test_can_be_visually_checked_with_no_ack(self):
        self.c.device_info = {"dimensions_known": False, "profile": "loy-fff"}
        self.backend.send = AsyncMock(return_value=False)
        await self.c.dispatch("send", {"kind": "test"})
        await self.wait_done()
        state = self.c.snapshot()
        self.assertIn("16 × 8", state["expected"])
        self.assertIn("未收到確認", state["message"])
        self.assertTrue(state["can_confirm_visual"])
        self.assertFalse(state["physical_display_verified"])

    async def test_old_send_does_not_allow_visual_confirmation_after_rejection(self):
        from loy_protocol import LoyCommandRejected
        await self.c.dispatch("send", {"kind": "test"})
        await self.wait_done()
        self.backend.send = AsyncMock(side_effect=LoyCommandRejected("fixture"))
        await self.c.dispatch("send", {"kind": "right"})
        await self.wait_done()
        self.backend.send.assert_awaited_once()
        self.assertEqual(self.c.stats["failed"], 1)
        self.assertFalse(self.c.snapshot()["can_confirm_visual"])
        with self.assertRaises(ValueError):
            await self.c.dispatch("visual", {"value": "目視正常"})

    async def test_validation_rejects_unscanned_device_and_emoji(self):
        with self.assertRaises(ValueError):
            await self.c.dispatch("connect", {"id": "other device"})
        with self.assertRaises(ValueError):
            await self.c.dispatch("send", {"kind": "custom", "text": "hello😀"})

    async def test_disconnect_revokes_live_visual_confirmation(self):
        self.c.visual = "目視正常"
        self.backend.connected = False
        self.assertFalse(self.c.snapshot()["physical_display_verified"])

    async def test_p95_uses_nearest_rank_for_small_sample(self):
        self.c.latencies = list(range(100, 1100, 100))
        self.assertEqual(self.c.snapshot()["p95_ms"], 1000)


class BackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_library_failure_result_is_not_hidden(self):
        from pypixelcolor.lib.command_result import CommandResult
        raw = types.SimpleNamespace(is_connected=True, mtu_size=247)
        backend = PixelBackend()
        backend.session = types.SimpleNamespace(is_connected=True, _client=raw, _ack_mgr=object())
        with patch("pypixelcolor.lib.transport.send_plan.send_plan", AsyncMock(return_value=CommandResult(success=False, message="fixture nack"))):
            with self.assertRaisesRegex(RuntimeError, "fixture nack"):
                await backend.command("set_brightness", level=10)

    async def test_half_connected_session_is_cleaned_up(self):
        raw = types.SimpleNamespace(disconnect=AsyncMock())
        class BrokenSession:
            def __init__(self, address):
                self._client = raw
            async def connect(self):
                raise TimeoutError("fixture handshake")
        backend = PixelBackend()
        backend.gatt_report = {"identification": {"profile": "ipixel-fa"}}
        backend._open_gatt = AsyncMock(return_value=types.SimpleNamespace(disconnect=AsyncMock()))
        with patch("pypixelcolor.lib.device_session.DeviceSession", BrokenSession):
            with self.assertRaises(TimeoutError):
                await backend.connect("fixture")
        raw.disconnect.assert_awaited_once()
        self.assertIsNone(backend.session)

    async def test_non_ipixel_profile_blocks_original_session_and_writes(self):
        backend = PixelBackend()
        backend.gatt_report = {"identification": {
            "profile": "loy-fff-candidate", "label": "LOY 候選"}}
        raw = types.SimpleNamespace(disconnect=AsyncMock(), start_notify=AsyncMock(),
                                    write_gatt_char=AsyncMock())
        backend._open_gatt = AsyncMock(return_value=raw)
        with patch("pypixelcolor.lib.device_session.DeviceSession") as factory:
            with self.assertRaises(ProtocolMismatchError):
                await backend.connect("fixture")
            factory.assert_not_called()
        raw.start_notify.assert_not_awaited()
        raw.write_gatt_char.assert_not_awaited()

    async def test_inspection_enumerates_services_without_application_writes(self):
        char = lambda u,p: types.SimpleNamespace(uuid=u, properties=p, handle=3,
                                                 description="fixture")
        service = types.SimpleNamespace(uuid="fff0",handle=1,characteristics=[
            char("fff2",["write-without-response"]),char("fff1",["notify"])])
        raw = types.SimpleNamespace(connect=AsyncMock(),disconnect=AsyncMock(),
                                    services=[service],write_gatt_char=AsyncMock(),
                                    read_gatt_char=AsyncMock(),start_notify=AsyncMock())
        backend = PixelBackend()
        with patch("bleak.BleakClient",return_value=raw):
            report = await backend.inspect("fixture")
        self.assertEqual(report["identification"]["profile"],"loy-fff-candidate")
        self.assertTrue(report["read_only_gatt"])
        self.assertEqual(report["application_writes"],0)
        raw.write_gatt_char.assert_not_awaited()
        raw.read_gatt_char.assert_not_awaited()
        raw.start_notify.assert_not_awaited()
        raw.disconnect.assert_awaited_once()

    async def test_failed_inspection_preserves_error_report_and_closes_link(self):
        raw = types.SimpleNamespace(connect=AsyncMock(side_effect=TimeoutError("fixture")),
                                    disconnect=AsyncMock())
        backend = PixelBackend()
        with patch("bleak.BleakClient",return_value=raw):
            with self.assertRaises(TimeoutError):await backend.inspect("fixture")
        self.assertFalse(backend.gatt_report["completed"])
        self.assertIn("TimeoutError",backend.gatt_report["error"])
        raw.disconnect.assert_awaited_once()

    async def test_real_frame_builders_accept_chinese_and_preview_images(self):
        from pypixelcolor.commands import COMMANDS
        from pypixelcolor.lib.device_info import parse_device_info
        info = parse_device_info(bytes([0x0b, 0, 5, 0x80, 131, 0, 0, 0, 0, 0, 255]))
        self.assertEqual((info.width, info.height), (64, 16))
        plan = COMMANDS["send_text"](text="煞車", animation="static", save_slot=0,
                    char_height=16, device_info=info, color="ff3020")
        frames = list(plan.windows)
        self.assertGreater(len(frames[0].data), 30)
        self.assertEqual(frames[0].data[14], 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "arrow.png"
            draw_symbol("left", 64, 16).save(path)
            images = list(COMMANDS["send_image"](path=path, save_slot=0, device_info=info).windows)
            self.assertGreater(len(images[0].data), 20)


class UtilityTests(unittest.TestCase):
    def test_channel_signatures_require_properties_and_same_service(self):
        def service(chars):
            return {"uuid":"fixture","characteristics":[
                {"uuid":"0000"+u+"-0000-1000-8000-00805f9b34fb", "properties":p}
                for u,p in chars]}
        self.assertEqual(identify_profile([service([("fa02",["read"]),
                                                   ("fa03",["notify"])])])["profile"],"unknown")
        self.assertEqual(identify_profile([service([("fa02",["write"]) ]),
                                           service([("fa03",["notify"])])])["profile"],"unknown")
        self.assertEqual(identify_profile([service([("fa02",["write"]),
                                                   ("fa03",["notify"])])])["profile"],"ipixel-fa")

    def test_multiple_profiles_are_not_arbitrarily_selected(self):
        rows=[{"uuid":"service","characteristics":[
            {"uuid":"0000fa02-0000-1000-8000-00805f9b34fb","properties":["write"]},
            {"uuid":"0000fa03-0000-1000-8000-00805f9b34fb","properties":["notify"]}]}]
        self.assertEqual(identify_profile(rows+rows)["profile"],"ambiguous")

    def test_safe_packet_sizes_and_unknown_model(self):
        self.assertEqual(packet_size(23), 20)
        self.assertEqual(packet_size(247), 180)
        self.assertEqual(packet_size(512), 180)
        info = types.SimpleNamespace(device_type=255, width=64, height=64, mcu_version="unknown")
        result = dimensions(info, {})
        self.assertIsNone(result["width"])
        self.assertFalse(result["dimensions_known"])

    def test_arrow_images_have_correct_direction_and_black_frame(self):
        from PIL import ImageOps
        left, right = draw_symbol("left", 64, 16), draw_symbol("right", 64, 16)
        self.assertEqual(left.tobytes(), ImageOps.mirror(right).tobytes())
        self.assertIsNone(draw_symbol("blank", 64, 16).getbbox())


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.worker = Worker(Path(cls.tmp.name), demo=True)
        cls.token = "fixture-capability"
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class(cls.worker, cls.token))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.stop()
        cls.thread.join(2)
        cls.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        code, data = response.status, response.read()
        conn.close()
        return code, data

    def test_status_requires_token_and_demo_cannot_claim_real_hardware(self):
        self.assertEqual(self.request("GET", "/api/state")[0], 403)
        code, data = self.request("GET", "/api/state", headers={"X-iPixel-Token": self.token})
        self.assertEqual(code, 200)
        state = json.loads(data)
        self.assertTrue(state["demo"])
        self.assertFalse(state["physical_display_verified"])

    def test_cross_origin_mutation_is_rejected(self):
        code, _ = self.request("POST", "/api/action", json.dumps({"action": "scan"}),
             {"X-iPixel-Token": self.token, "Origin": "https://example.invalid"})
        self.assertEqual(code, 403)

    def test_report_contains_json_without_session_token(self):
        data = diagnostic_zip(self.worker)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            report = archive.read("summary.json").decode()
            self.assertNotIn(self.token, report)
            self.assertNotIn('"devices":', report)
            self.assertFalse(json.loads(report)["physical_display_verified"])

    def test_inspect_action_can_export_gatt_without_display_connection(self):
        headers={"X-iPixel-Token":self.token,"Content-Type":"application/json"}
        def action(name, **payload):
            self.assertEqual(self.request("POST","/api/action",json.dumps({"action":name,**payload}),headers)[0],200)
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                state=json.loads(self.request("GET","/api/state",headers=headers)[1])
                if not state["busy"]:
                    self.assertFalse(state["error"])
                    return state
                time.sleep(.02)
            self.fail("operation did not finish")
        state=action("scan")
        state=action("inspect",id=state["devices"][0]["id"])
        self.assertFalse(state["connected"])
        self.assertTrue(state["gatt_report"]["completed"])
        with zipfile.ZipFile(io.BytesIO(self.request("GET","/api/report",headers=headers)[1])) as archive:
            gatt=json.loads(archive.read("gatt.json"))
            self.assertEqual(gatt["application_writes"],0)


if __name__ == "__main__":
    unittest.main()
