"""Temporary drawing commands for YS displays with the FFF0 BLE service."""
from __future__ import annotations

import asyncio
import struct
from importlib.resources import as_file, files

READ_INFO = bytes.fromhex("0a00")
READ_POWER = bytes.fromhex("0400")
SET_POWER = bytes.fromhex("040200")
ENTER_DRAW = bytes.fromhex("300190")
EXIT_DRAW = bytes.fromhex("300165")
READ = 3
WRITE = 2
PROBE_SIZE = (16, 8)
MAX_PAYLOAD = 400


def checksum(data):
    return struct.pack("<H", sum(data) & 0xffff)


def encode_frame(payload, sequence, mode):
    header = struct.pack("<4sHHBB", b"\xaa\x55\xff\xff", len(payload) + 6,
                         sequence, 0xc1, mode)
    data = header + payload
    return data + checksum(data)


def draw_command(data):
    size = len(data)
    if size < 128:
        length = bytes([size])
    elif size < 256:
        length = bytes([0x81, size])
    else:
        length = struct.pack("<BH", 0x82, size)
    return b"\x32" + length + data


def clear_command(width, height):
    return draw_command(b"\x01\x00\x00\x00\x00" +
                        struct.pack("<4H", 0, 0, width - 1, height - 1))


def bitmap_commands(mask, rgb, full_frame=False):
    # Pillow mode 1 packs each row MSB-first and pads it to a whole byte.
    bounds = (0, 0, mask.width, mask.height) if full_frame else mask.getbbox()
    if bounds is None:
        return
    left, top, right, bottom = bounds
    bytes_per_row = (right - left + 7) // 8
    rows_per_command = (MAX_PAYLOAD - 16) // bytes_per_row
    for y in range(top, bottom, rows_per_command):
        end = min(y + rows_per_command, bottom)
        region = struct.pack("<4H", left, y, right - 1, end - 1)
        data = mask.crop((left, y, right, end)).tobytes()
        yield draw_command(b"\x00" + rgb + region + data)


def text_mask(text, width, height, bold=False):
    from PIL import Image, ImageDraw, ImageFont

    resource = files("pypixelcolor").joinpath("fonts", "unifont.otf")
    with as_file(resource) as path:
        font = ImageFont.truetype(str(path), max(16, height))
    left, top, right, bottom = font.getbbox(text)
    glyphs = Image.new("L", (max(1, right - left), max(1, bottom - top)))
    ImageDraw.Draw(glyphs).text((-left, -top), text, font=font, fill=255)
    glyphs.thumbnail((width - 2, height - 2), Image.Resampling.LANCZOS)
    pixels = glyphs.point(lambda v: 255 if v >= 100 else 0, mode="1")
    mask = Image.new("1", (width, height))
    mask.paste(pixels, ((width - pixels.width) // 2, (height - pixels.height) // 2))
    if bold:
        from PIL import ImageChops
        shifted = Image.new("1", (width, height))
        shifted.paste(mask.crop((0, 0, width - 1, height)), (1, 0))
        mask = ImageChops.lighter(mask, shifted)
    return mask


class LoyCommandRejected(RuntimeError):
    pass


class LoySession:
    """Use the discovered FFF2 and FFF1 characteristics on one BLE connection."""

    def __init__(self, client, write_char, notify_char, report):
        self.client = client
        self.write_char = write_char
        self.notify_char = notify_char
        self.report = report
        self.log = report["loy"] = {"commands": [], "notifications": [], "probe_reply": False}
        self.sequence = 1
        self.receive_buffer = bytearray()
        self.size = None
        self.drawing_active = False
        self.pending_ack = {}

    async def probe(self):
        self.report["read_only_gatt"] = False
        await self.client.start_notify(self.notify_char, self._on_notify)
        await asyncio.sleep(0.8)
        query = await self._transmit("device_info", READ_INFO, mode=READ, settle=0.35)
        self.log["probe_reply"] = query.get("reply", False)
        await self._read_power()
        return self.log["probe_reply"]

    def _on_notify(self, _sender, data):
        notifications = self.log["notifications"]
        notifications.append(bytes(data[:512]).hex())
        del notifications[:-24]
        self.receive_buffer.extend(data)
        buffer = self.receive_buffer
        # The prefix and length can span notifications. Skip unrelated bytes
        # and cap incomplete packets so stray data cannot grow the log buffer.
        while len(buffer) >= 6:
            if buffer[:2] != b"\xaa\x55":
                del buffer[0]
                continue
            size = int.from_bytes(buffer[4:6], "little") + 6
            if not 12 <= size <= 1024:
                del buffer[0]
                continue
            if len(buffer) < size:
                break
            packet = bytes(buffer[:size])
            if checksum(packet[:-2]) != packet[-2:]:
                del buffer[0]
                continue
            del buffer[:size]
            sequence = int.from_bytes(packet[6:8], "little")
            kind = packet[8:10]
            if (kind in (b"\x81\x83", b"\xc1\x06") and size == 16
                    and packet[10:13] == b"\x04\x02\x00" and packet[13] in (0, 1)):
                self.log["power_status"] = {
                    "on": bool(packet[13]), "source": "device", "frame": packet.hex(),
                }
            if kind == b"\xc1\x06":
                continue  # Unsolicited event, with its own sequence counter.
            for command in reversed(self.log["commands"]):
                if command["sequence"] == sequence:
                    command["reply"] = True
                    if size == 13 and kind == b"\x81\x82":
                        command["ack_status"] = packet[10]
                        event = self.pending_ack.get(sequence)
                        if event:
                            event.set()
                    break

    async def _transmit(self, name, payload, *, mode=WRITE, settle=0.1):
        if not self.client.is_connected:
            raise ConnectionError("藍牙連線已中斷")
        sequence = self.sequence
        self.sequence = (sequence + 1) & 0xffff
        frame = encode_frame(payload, sequence, mode)
        chunk_size = min(180, self.write_char.max_write_without_response_size)
        entry = {"name": name, "sequence": sequence, "bytes": len(frame),
                 "chunk_size": chunk_size, "chunks_sent": 0}
        commands = self.log["commands"]
        commands.append(entry)
        del commands[:-24]
        # Count an attempted frame even if the BLE link fails partway through.
        self.report["application_writes"] += 1
        event = self.pending_ack[sequence] = asyncio.Event()
        try:
            for offset in range(0, len(frame), chunk_size):
                if offset:
                    await asyncio.sleep(0.01)
                await self.client.write_gatt_char(
                    self.write_char, frame[offset:offset + chunk_size], response=False)
                entry["chunks_sent"] += 1
            await asyncio.sleep(settle)
            if mode == WRITE and "ack_status" not in entry:
                try:
                    await asyncio.wait_for(event.wait(), 0.5)
                except asyncio.TimeoutError:
                    pass
        finally:
            self.pending_ack.pop(sequence, None)
        if not self.client.is_connected:
            raise ConnectionError("傳送期間藍牙連線中斷")
        status = entry.get("ack_status")
        if status is not None and status != 0:
            raise LoyCommandRejected(f"屏幕拒絕 {name} 指令（0x{status:02X}）")
        return entry

    async def draw(self, size, mask=None, rgb=b"\x00\x00\x00", full_frame=False):
        replies = []
        if not self.drawing_active:
            self.drawing_active = True
            try:
                replies.append(await self._transmit("enter_draw", ENTER_DRAW, settle=0.15))
            except LoyCommandRejected:
                self.drawing_active = False
                raise
        if mask is None or not full_frame:
            replies.append(await self._transmit("clear", clear_command(*size)))
        if mask is not None:
            for payload in bitmap_commands(mask, rgb, full_frame=full_frame):
                replies.append(await self._transmit("bitmap", payload))
        for reply in replies:
            # A reply can arrive during a later command in the same drawing.
            status = reply.get("ack_status")
            if status is not None and status != 0:
                raise LoyCommandRejected(f"屏幕拒絕 {reply['name']} 指令（0x{status:02X}）")
        return all(reply.get("ack_status") == 0 for reply in replies)

    async def brightness(self, percent):
        level = max(1, round(percent * 15 / 100))
        await self._transmit("brightness", bytes([0x06, 0x02, 0x00, level]))

    async def _read_power(self):
        try:
            await self._transmit("read_power", READ_POWER, mode=READ, settle=0.35)
        except LoyCommandRejected:
            return  # Some firmware accepts power control without readback.

    async def screen_power(self, on):
        # The next drawing starts with a fresh canvas after a power change.
        await self.exit_drawing()
        previous = self.log.get("power_status")
        name = "power_on" if on else "power_off"
        command = await self._transmit(name, SET_POWER + bytes([on]), settle=0.25)
        await self._read_power()
        current = self.log.get("power_status")
        acknowledged = command.get("ack_status") == 0
        reported_on = current["on"] if current is not previous else None
        if reported_on is None:
            # Keep the reverse action available when only the write is known.
            self.log["power_status"] = {"on": on, "source": "ack" if acknowledged else "sent"}
        return {"requested_on": on, "acknowledged": acknowledged, "reported_on": reported_on}

    async def exit_drawing(self):
        if self.drawing_active and self.client.is_connected:
            self.drawing_active = False
            try:
                await asyncio.wait_for(self._transmit("exit_draw", EXIT_DRAW), 1)
            except Exception as exc:
                self.log["exit_error"] = f"{type(exc).__name__}: {exc}"
