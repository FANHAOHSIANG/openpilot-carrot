import asyncio
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.service import BleakGATTService, BleakGATTServiceCollection
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ipixel_core import PixelBackend, ProtocolMismatchError, describe_gatt, identify_profile, uuid_key
from loy_protocol import (LoyCommandRejected, bitmap_commands, clear_command, encode_frame,
                          text_mask)


def services_fixture(service_uuid="fff0", properties=("write-without-response",)):
    services = BleakGATTServiceCollection()
    service = BleakGATTService(None, 4, uuid_key(service_uuid))
    services.add_service(service)
    write = BleakGATTCharacteristic(None, 5, uuid_key("fff2"), list(properties), lambda: 20, service)
    notify = BleakGATTCharacteristic(None, 7, uuid_key("fff1"), ["notify"], lambda: 20, service)
    services.add_characteristic(write)
    services.add_characteristic(notify)
    return services, write, notify


class SimulatedSign:
    def __init__(self, ack=None, report_power=False):
        self.services, self.write, self.notify = services_fixture()
        self.is_connected = False
        self.connect_count = 0
        self.ack = ack
        self.report_power = report_power
        self.power_on = True
        self.callback = None
        self.buffer = bytearray()
        self.frames = []

    async def connect(self):
        self.is_connected = True
        self.connect_count += 1

    async def disconnect(self):
        self.is_connected = False

    async def start_notify(self, characteristic, callback):
        assert characteristic is self.notify
        self.callback = callback

    def reply(self, kind, sequence, payload):
        prefix = (bytes.fromhex("aa557e7c") + struct.pack("<H", len(payload) + 6)
                  + sequence + kind + payload)
        packet = prefix + struct.pack("<H", sum(prefix) & 0xffff)
        self.callback(self.notify, packet[:5])
        self.callback(self.notify, packet[5:])

    async def write_gatt_char(self, characteristic, data, *, response):
        assert self.is_connected and characteristic is self.write
        assert response is False
        assert 1 <= len(data) <= 20
        self.buffer.extend(data)
        frame_size = int.from_bytes(self.buffer[4:6], "little") + 6
        if len(self.buffer) < frame_size:
            return
        assert len(self.buffer) == frame_size
        frame = bytes(self.buffer)
        self.buffer.clear()
        assert frame[:4] == bytes.fromhex("aa55ffff")
        assert int.from_bytes(frame[-2:], "little") == sum(frame[:-2]) & 0xffff
        self.frames.append(frame)
        payload = frame[10:-2]
        status = self.ack(payload) if self.ack is not None else 0
        if status == 0 and len(payload) == 4 and payload[:3] == b"\x04\x02\x00":
            self.power_on = bool(payload[3])
        if self.ack is not None:
            self.reply(b"\x81\x82", frame[6:8], bytes([status]))
        if self.report_power and payload == b"\x04\x00":
            self.reply(b"\x81\x83", frame[6:8], bytes([4, 2, 0, self.power_on]))


class LoyWireTests(unittest.TestCase):
    def test_known_query_frame_and_rectangle(self):
        self.assertEqual(encode_frame(b"\x0a\x00", 1, 3).hex(),
                         "aa55ffff08000100c1030a00d403")
        self.assertEqual(encode_frame(bytes.fromhex("04020001"), 1, 2).hex(),
                         "aa55ffff0a000100c10204020001d203")
        self.assertEqual(encode_frame(bytes.fromhex("04020000"), 1, 2).hex(),
                         "aa55ffff0a000100c10204020000d103")
        self.assertEqual(clear_command(16, 8).hex(), "320d0100000000000000000f000700")

    def test_bitmap_rows_pack_msb_first_and_pad_independently(self):
        image = Image.new("1", (9, 2))
        for point in [(0, 0), (8, 0), (1, 1), (8, 1)]:
            image.putpixel(point, 255)
        self.assertEqual(list(bitmap_commands(image, b"\x11\x22\x33")),
                         [bytes.fromhex("321000112233000000000800010080804080")])

    def test_large_bitmap_uses_bands_with_contiguous_row_coordinates(self):
        image = Image.new("1", (512, 128), 255)
        commands = list(bitmap_commands(image, b"\xff\xff\xff"))
        next_row = 0
        for command in commands:
            self.assertLessEqual(len(command), 400)
            coordinates = {0x81: 7, 0x82: 8}[command[1]]
            pixels = coordinates + 8
            start_x, start_y, end_x, end_y = struct.unpack("<4H", command[coordinates:pixels])
            self.assertEqual((start_x, start_y, end_x), (0, next_row, 511))
            self.assertEqual(len(command) - pixels, (end_y - start_y + 1) * 64)
            next_row = end_y + 1
        self.assertEqual(next_row, 128)

    def test_fff2_without_response_and_fff0_are_required_for_ys(self):
        for service_uuid, props in [("a800", ["write-without-response"]), ("fff0", ["write"])]:
            with self.subTest(service_uuid=service_uuid, props=props):
                services, _, _ = services_fixture(service_uuid, props)
                result = identify_profile(describe_gatt(services), "YS5255140425")
                self.assertEqual(result["profile"], "loy-fff-candidate")


class LoyBackendTests(unittest.IsolatedAsyncioTestCase):
    async def open_sign(self, sign, name="YS5255140425"):
        backend = PixelBackend()
        device = object()
        backend.scan_cache["fixture"] = (device, name)
        with patch("bleak.BleakClient", return_value=sign) as factory:
            info = await backend.connect("fixture")
        factory.assert_called_once_with(device)
        self.addAsyncCleanup(backend.disconnect)
        return backend, info

    async def test_probes_then_sends_draw_commands_without_ack_and_reuses_link(self):
        sign = SimulatedSign()
        backend, info = await self.open_sign(sign)
        self.assertFalse(info["dimensions_known"])
        self.assertEqual([frame[8:-2].hex() for frame in sign.frames],
                         ["c1030a00", "c1030400"])
        with self.assertRaisesRegex(RuntimeError, "解析度"):
            await backend.send("brake")
        self.assertFalse(await backend.send("test"))
        self.assertEqual(len(sign.frames), 5)
        enter, clear, bitmap = sign.frames[-3:]
        self.assertEqual(enter[10:-2], bytes.fromhex("300190"))
        self.assertEqual(clear[10:-2], clear_command(16, 8))
        self.assertEqual(bitmap[10], 0x32)
        self.assertEqual(bitmap[12], 0)
        self.assertTrue(any(bitmap[24:-2]))
        backend.set_resolution(96, 16)
        for kind in ("brake", "left", "right", "blank"):
            await backend.send(kind)
        self.assertEqual(sign.connect_count, 1)
        self.assertEqual(sum(frame[10:-2] == bytes.fromhex("300190") for frame in sign.frames), 1)
        await backend.disconnect()
        self.assertEqual(sign.frames[-1][10:-2], bytes.fromhex("300165"))
        self.assertFalse(sign.is_connected)

    async def test_fragmented_ack_and_explicit_rejection(self):
        sign = SimulatedSign(ack=lambda _: 0)
        backend, _ = await self.open_sign(sign)
        self.assertTrue(backend.gatt_report["loy"]["probe_reply"])
        self.assertTrue(await backend.send("test"))
        sign.ack = lambda payload: 3 if payload[0] == 0x32 else 0
        with self.assertRaisesRegex(LoyCommandRejected, "0x03"):
            await backend.send("test")
        self.assertEqual(backend.gatt_report["loy"]["commands"][-1]["ack_status"], 3)
        self.assertEqual(sign.frames[-1][10:-2], clear_command(16, 8))

    async def test_delayed_ack_is_accepted_for_live_screen(self):
        sign = SimulatedSign()
        original = sign.write_gatt_char
        async def delayed(characteristic, data, *, response):
            previous = len(sign.frames)
            await original(characteristic, data, response=response)
            if len(sign.frames) > previous:
                frame = sign.frames[-1]
                asyncio.get_running_loop().call_later(
                    0.25, sign.reply, b"\x81\x82", frame[6:8], b"\x00")
        sign.write_gatt_char = delayed
        backend, _ = await self.open_sign(sign)
        backend.set_resolution(96, 16)
        self.assertTrue(await backend.send("decel"))

    async def test_power_switch_queries_both_states_on_the_same_connection(self):
        sign = SimulatedSign(ack=lambda _: 0, report_power=True)
        backend, _ = await self.open_sign(sign)
        status = backend.gatt_report["loy"]
        self.assertTrue(status["power_status"]["on"])
        self.assertTrue(await backend.send("test"))

        result = await backend.screen_power(False)
        self.assertEqual(result, {"requested_on": False, "acknowledged": True, "reported_on": False})
        self.assertEqual([frame[8:-2].hex() for frame in sign.frames[-3:]],
                         ["c102300165", "c10204020000", "c1030400"])
        self.assertFalse(status["power_status"]["on"])
        self.assertTrue(backend.connected)

        result = await backend.screen_power(True)
        self.assertEqual(result, {"requested_on": True, "acknowledged": True, "reported_on": True})
        self.assertEqual([frame[8:-2].hex() for frame in sign.frames[-2:]],
                         ["c10204020001", "c1030400"])
        self.assertTrue(status["power_status"]["on"])
        self.assertEqual(status["power_status"]["source"], "device")
        self.assertEqual(sign.connect_count, 1)
        self.assertTrue(await backend.send("test"))
        self.assertEqual(sign.frames[-3][10:-2], bytes.fromhex("300190"))

    async def test_power_switch_falls_back_to_last_command_when_query_is_unsupported(self):
        sign = SimulatedSign(ack=lambda payload: 3 if payload == b"\x04\x00" else 0)
        backend, _ = await self.open_sign(sign)
        sign.callback(sign.notify, bytes.fromhex("aa55ffff0a000200c10604020000d603"))
        status = backend.gatt_report["loy"]
        self.assertFalse(status["power_status"]["on"])
        for on in (True, False):
            result = await backend.screen_power(on)
            self.assertEqual(result, {"requested_on": on, "acknowledged": True, "reported_on": None})
            self.assertEqual(status["power_status"], {"on": on, "source": "ack"})
            self.assertEqual(status["commands"][-1]["ack_status"], 3)

    async def test_rejects_unrelated_name_with_same_characteristics(self):
        sign = SimulatedSign()
        with self.assertRaises(ProtocolMismatchError):
            await self.open_sign(sign, name="Unrelated")
        self.assertEqual(sign.frames, [])
        self.assertIsNone(sign.callback)
        self.assertFalse(sign.is_connected)

    def test_chinese_render_uses_bundled_font(self):
        image = text_mask("煞車", 96, 20)
        other = text_mask("測試", 96, 20)
        self.assertEqual(image.size, (96, 20))
        self.assertIsNotNone(image.getbbox())
        self.assertNotEqual(image.tobytes(), other.tobytes())


if __name__ == "__main__":
    unittest.main()

class FullFrameTests(unittest.TestCase):
    def test_full_frame_keeps_zeros_and_full_width(self):
        img = Image.new('1', (16, 8))
        img.putpixel((5, 3), 255)
        packet = list(bitmap_commands(img, b'\xff\x00\x00', full_frame=True))
        self.assertEqual(len(packet), 1)
        self.assertEqual(packet[0][6:14], struct.pack('<4H', 0, 0, 15, 7))
        self.assertEqual(len(packet[0][-16:]), 16)

    def test_bold_text_adds_pixels_without_changing_size(self):
        normal = text_mask('謝謝', 96, 16)
        bold = text_mask('謝謝', 96, 16, bold=True)
        self.assertEqual(normal.size, bold.size)
        self.assertGreater(sum(bool(p) for p in bold.getdata()), sum(bool(p) for p in normal.getdata()))
        for a, b in zip(normal.getdata(), bold.getdata()):
            if a: self.assertTrue(b)
