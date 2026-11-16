"""Read local CarrotMacHUD data and select a frame for the LOY display."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

MAX_AGE = 0.55
MAX_SAMPLE_GAP = 0.30
DECEL_START = -0.50  # m/s²
DECEL_END = -0.25
DECEL_DWELL = 0.30
HARD_DECEL_START = -2.0
HARD_DECEL_END = -1.5
START_SPEED = 5 / 3.6  # m/s
END_SPEED = 3 / 3.6


@dataclass(frozen=True)
class HudSample:
    stamp: float
    speed: float
    accel: float
    brake: bool
    left: bool
    right: bool
    gear: str = "unknown"


class DisplayPolicy:
    def __init__(self):
        self.last_stamp = None
        self.since = None
        self.slowing = False
        self.hard_since = None
        self.hard = False

    def choose(self, sample):
        if sample is None:
            self.last_stamp = self.since = None
            self.slowing = False
            self.hard_since = None
            self.hard = False
            return "blank"

        if self.last_stamp is not None and not 0 <= sample.stamp - self.last_stamp <= MAX_SAMPLE_GAP:
            self.since = None
            self.slowing = False
            self.hard_since = None
            self.hard = False
        self.last_stamp = sample.stamp

        if self.slowing:
            if sample.speed < END_SPEED or sample.accel >= DECEL_END:
                self.slowing = False
                self.since = None
        elif sample.speed >= START_SPEED and sample.accel <= DECEL_START:
            if self.since is None:
                self.since = sample.stamp
            self.slowing = sample.stamp - self.since >= DECEL_DWELL
        else:
            self.since = None

        if self.hard:
            if sample.speed < END_SPEED or sample.accel >= HARD_DECEL_END:
                self.hard = False
                self.hard_since = None
        elif sample.speed >= START_SPEED and sample.accel <= HARD_DECEL_START:
            if self.hard_since is None:
                self.hard_since = sample.stamp
            self.hard = sample.stamp - self.hard_since >= DECEL_DWELL
        else:
            self.hard_since = None

        if sample.left and sample.right:
            if sample.gear == "drive" and self.hard:
                return "traffic"
            if sample.gear == "park":
                return "pause_thanks"
            if sample.gear == "drive":
                return "thanks"
            return "blank"
        if sample.left != sample.right:
            return "left" if sample.left else "right"
        return "decel" if sample.gear == "drive" and (sample.brake or self.slowing) else "blank"


class HudReader:
    """Use the installed HUD reader with this tool's Python environment."""

    def __init__(self):
        self.path = None
        self.updates = 0
        self.error = ""
        self.latest = None

    async def __aenter__(self):
        default_root = Path.home() / "CarrotMacHUD" / "carrot"
        root = Path(os.environ.get("CARROT_MAC_HUD_ROOT", default_root)).expanduser()
        hud_script = root / "tools" / "jetlink" / "hud.py"
        if not hud_script.is_file():
            raise FileNotFoundError(f"找不到已安裝的 Mac HUD 讀取器（{hud_script}）")
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": os.pathsep.join((str(hud_script.parent), str(root)))}
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", str(Path(__file__).resolve()), "--read-hud",
            cwd=root, env=env, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
        self.task = asyncio.create_task(self._collect())
        return self

    async def _collect(self):
        try:
            async for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(message, dict):
                    continue
                if "sample" in message:
                    self.latest = HudSample(**message["sample"])
                    self.updates += 1
                elif "path" in message:
                    self.path = message["path"]
                elif "error" in message:
                    self.error = message["error"]
            if not self.error:
                self.error = "Mac HUD 讀取器已停止"
        except Exception as exc:
            self.error = f"Mac HUD 資料讀取失敗（{type(exc).__name__}）"
        finally:
            self.latest = None

    def current(self):
        if self.latest is not None and 0 <= time.monotonic() - self.latest.stamp <= MAX_AGE:
            return self.latest
        return None

    async def __aexit__(self, *_):
        if self.process.returncode is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self.process.wait(), 1)
            except asyncio.TimeoutError:
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
                await self.process.wait()
        await self.task


def _emit(**payload):
    print(json.dumps(payload, ensure_ascii=False, allow_nan=False), flush=True)


def _read_local_hud():
    import hud_protocol
    from hud import RemoteSubMaster

    packet = Path(hud_protocol.HUD_PACKET)
    if sys.platform == "darwin" and not packet.is_file():
        for folder in ("/tmp", tempfile.gettempdir()):
            candidate = Path(folder) / packet.name
            if candidate.is_file():
                hud_protocol.HUD_PACKET = candidate
                break
    _emit(path=str(hud_protocol.HUD_PACKET))
    service = "carState"
    sm = RemoteSubMaster([service])
    while True:
        sm.update()
        if sm.updated[service] and sm.valid[service] and sm.alive[service]:
            cs = sm[service]
            stamp = sm.recv_time[service]
            speed, accel = float(cs.vEgo), float(cs.aEgo)
            if all(math.isfinite(v) for v in (stamp, speed, accel)):
                _emit(sample=dict(stamp=stamp, speed=speed, accel=accel,
                                  brake=bool(cs.brakePressed), left=bool(cs.leftBlinker),
                                  right=bool(cs.rightBlinker), gear=str(cs.gearShifter)))
        time.sleep(0.05)


if __name__ == "__main__" and sys.argv[1:] == ["--read-hud"]:
    try:
        _read_local_hud()
    except Exception as exc:
        _emit(error=f"無法使用 Mac HUD 讀取器（{type(exc).__name__}：{exc}）")
