import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hud_link import DisplayPolicy, HudSample, HudReader
from ipixel_core import Controller, DemoBackend


def sample(stamp, accel=-0.8, speed=10.0, brake=False, left=False, right=False, gear="drive"):
    return HudSample(stamp, speed, accel, brake, left, right, gear)


class PolicyTests(unittest.TestCase):
    def test_sustained_deceleration_without_pedal_then_release(self):
        policy = DisplayPolicy()
        self.assertEqual(policy.choose(sample(1.0)), "blank")
        self.assertEqual(policy.choose(sample(1.2)), "blank")
        self.assertEqual(policy.choose(sample(1.31)), "decel")
        self.assertEqual(policy.choose(sample(1.4, accel=-0.35)), "decel")
        self.assertEqual(policy.choose(sample(1.5, accel=-0.1)), "blank")
        self.assertEqual(policy.choose(sample(1.6)), "blank")

    def test_old_sample_gap_and_low_speed_cannot_trigger_deceleration(self):
        policy = DisplayPolicy()
        for stamp in (1.0, 1.0, 1.6, 1.8):
            self.assertEqual(policy.choose(sample(stamp)), "blank")
        self.assertEqual(policy.choose(sample(1.95, speed=0.7)), "blank")
        self.assertEqual(policy.choose(None), "blank")
        self.assertEqual(policy.choose(sample(2.01)), "blank")

    def test_turn_and_brake_keep_priority_over_deceleration(self):
        policy = DisplayPolicy()
        policy.choose(sample(1.0))
        policy.choose(sample(1.2))
        self.assertEqual(policy.choose(sample(1.4, left=True)), "left")
        self.assertEqual(policy.choose(sample(1.5, right=True)), "right")
        self.assertEqual(policy.choose(sample(1.6, brake=True, left=True)), "left")
        self.assertEqual(policy.choose(sample(1.7, left=True, right=True)), "thanks")
        self.assertEqual(policy.choose(sample(1.8, speed=0.0)), "blank")

    def test_gear_hazard_and_hard_deceleration(self):
        policy = DisplayPolicy()
        self.assertEqual(policy.choose(sample(1.0, gear="park", brake=True)), "blank")
        self.assertEqual(policy.choose(sample(1.1, gear="park", left=True, right=True)), "pause_thanks")
        self.assertEqual(policy.choose(sample(1.2, brake=True)), "decel")
        self.assertEqual(policy.choose(sample(1.3, left=True, right=True, accel=-2.2)), "thanks")
        self.assertEqual(policy.choose(sample(1.5, left=True, right=True, accel=-2.2)), "thanks")
        self.assertEqual(policy.choose(sample(1.65, left=True, right=True, accel=-2.2)), "traffic")
        self.assertEqual(policy.choose(sample(1.75, left=True, right=True, accel=-1.7)), "traffic")
        self.assertEqual(policy.choose(sample(1.85, left=True, right=True, accel=-1.4)), "thanks")
        self.assertEqual(policy.choose(sample(1.95, left=True, right=True, gear="unknown")), "blank")


class ScreenFixture(DemoBackend):
    def __init__(self, fail=False):
        super().__init__()
        self.connected = True
        self.writes = []
        self.fail = fail

    async def send(self, kind, text="", color="ffffff"):
        self.writes.append(kind)
        return not self.fail or kind == "blank"


class ReaderFixture:
    path = "/fixture/carrot-jetlink-hud.packet"
    error = ""

    def __init__(self, controller):
        self.controller = controller
        self.updates = 0
        self.samples = iter([sample(1.0), sample(1.2), sample(1.4),
                             sample(1.5), None])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    def current(self):
        try:
            current = next(self.samples)
        except StopIteration:
            self.controller.stop_event.set()
            return None
        if current:
            self.updates += 1
        return current


class ControllerLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_hud_reader_uses_the_tools_python_environment(self):
        class EmptyStream:
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration

        class Process:
            stdout = EmptyStream()
            returncode = 0

        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "tools/jetlink/hud.py"
            script.parent.mkdir(parents=True)
            script.touch()
            with patch.dict(os.environ, {"CARROT_MAC_HUD_ROOT": folder}), patch(
                "asyncio.create_subprocess_exec", new=AsyncMock(return_value=Process())
            ) as launch:
                async with HudReader():
                    pass
            self.assertEqual(launch.await_args.args[0], sys.executable)

    async def run_link(self, mode, fail=False):
        with tempfile.TemporaryDirectory() as folder:
            backend = ScreenFixture(fail)
            controller = Controller(backend, Path(folder))
            controller.device_info = {"profile": "loy-fff", "dimensions_known": False}
            controller.override = [96, 16]
            reader = ReaderFixture(controller)
            with patch("ipixel_core.HudReader", return_value=reader):
                await controller.dispatch("hud_link", {"mode": mode})
                await asyncio.wait_for(controller.task, 2)
            return controller.snapshot(), backend.writes

    async def test_preview_detects_deceleration_without_ble_writes(self):
        state, writes = await self.run_link("preview")
        self.assertEqual(writes, [])
        self.assertEqual(state["hud_link"]["updates"], 4)
        self.assertIn("decel", [e.get("kind") for e in state["events"]])

    async def test_screen_updates_on_change_and_blanks_on_stale_input(self):
        state, writes = await self.run_link("screen")
        self.assertEqual(writes, ["blank", "decel", "blank"])
        self.assertFalse(state["hud_link"]["active"])
        self.assertEqual(state["error"], "")

    async def test_unacknowledged_frame_stops_output_and_attempts_clear(self):
        state, writes = await self.run_link("screen", fail=True)
        self.assertEqual(writes, ["blank", "decel", "blank"])
        self.assertFalse(state["hud_link"]["active"])
        self.assertIn("未完整確認", state["error"])


    async def test_custom_returns_after_alert_but_not_after_stale_data(self):
        with tempfile.TemporaryDirectory() as folder:
            backend = ScreenFixture()
            async def send_styled(style, tick):
                backend.writes.append('custom')
                return True
            backend.send_styled = send_styled
            controller = Controller(backend, Path(folder), settings_path=Path(folder)/'styles.json')
            controller.device_info = {'profile':'loy-fff', 'dimensions_known':False}
            controller.override = [96, 16]
            controller.custom_style = {'text':'謝謝你','color':'ff0000','effect':'static','speed':1}
            reader = ReaderFixture(controller)
            reader.samples = iter([sample(1.0, accel=0), sample(1.1, accel=0, left=True),
                                   sample(1.2, accel=0), None])
            with patch('ipixel_core.HudReader', return_value=reader):
                await controller.dispatch('hud_link', {'mode':'screen'})
                await asyncio.wait_for(controller.task, 2)
            self.assertEqual(backend.writes, ['custom', 'left', 'custom', 'blank'])
