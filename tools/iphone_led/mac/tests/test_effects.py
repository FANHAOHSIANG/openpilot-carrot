import tempfile
import unittest
from pathlib import Path
from PIL import Image
import effects
from ipixel_core import Controller, DemoBackend, PRESET_COLOR, PRESET_TEXT

class EffectsTests(unittest.TestCase):
    def setUp(self):
        self.styles = effects.defaults(PRESET_TEXT, PRESET_COLOR)
        self.style = self.styles['left']
        self.mask = Image.new('1', (8, 1))
        self.mask.putpixel((3, 0), 1)

    def test_scroll_directions(self):
        self.style.update(effect='scroll_left', speed=1)
        left, _ = effects.render(self.mask, self.style, 1)
        self.style['effect'] = 'scroll_right'
        right, _ = effects.render(self.mask, self.style, 1)
        self.assertEqual(left.getpixel((1, 0)), 1)
        self.assertEqual(right.getpixel((5, 0)), 1)

    def test_blink_and_breathe(self):
        self.style.update(effect='blink', speed=2, color='ff0000')
        self.assertIsNotNone(effects.render(self.mask, self.style, 0)[0])
        self.assertIsNone(effects.render(self.mask, self.style, 1)[0])
        self.style.update(effect='breathe', speed=1)
        self.assertLess(effects.render(self.mask, self.style, 0)[1][0], effects.render(self.mask, self.style, 4)[1][0])

    def test_invalid_values_are_rejected(self):
        self.styles['left']['effect'] = 'unknown'
        with self.assertRaises(ValueError): effects.validate(self.styles)
        self.styles['left']['effect'] = 'static'
        self.styles['left']['color'] = 'xxxxxx'
        with self.assertRaises(ValueError): effects.validate(self.styles)

class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_settings_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            c = Controller(DemoBackend(), root / 'logs', demo=True, settings_path=root / 'settings.json')
            styles = effects.defaults(PRESET_TEXT, PRESET_COLOR)
            styles['left'].update(text='左轉請注意', color='aabbcc', effect='blink', speed=2)
            await c.dispatch('styles', {'styles': styles})
            other = Controller(DemoBackend(), root / 'logs2', demo=True, settings_path=root / 'settings.json')
            self.assertEqual(other.styles, styles)

    async def test_custom_setting_can_change_while_hud_active(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            backend = DemoBackend()
            backend.connected = True
            c = Controller(backend, root / 'logs', demo=True, settings_path=root / 'settings.json')
            c.override = [96, 16]
            c.busy = 'hud_link'
            await c.dispatch('custom_standby', {'text':'謝謝你', 'color':'ff0000', 'effect':'static', 'speed':1})
            self.assertEqual(c.custom_style['text'], '謝謝你')
            await c.dispatch('clear_standby', {})
            self.assertIsNone(c.custom_style)

    async def test_five_slots_persist_and_activate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            backend = DemoBackend()
            backend.connected = True
            c = Controller(backend, root/'logs', demo=True, settings_path=root/'styles.json')
            c.override = [96,16]
            slots = [None, {'text':'謝謝','color':'ff0000','effect':'scroll_left','speed':2}, None, None, None]
            await c.dispatch('save_custom_slots', {'slots':slots})
            c.busy = 'hud_link'
            await c.dispatch('activate_custom_slot', {'index':1})
            self.assertEqual(c.custom_style, slots[1])
            restored = Controller(DemoBackend(), root/'logs2', demo=True, settings_path=root/'styles.json')
            self.assertEqual(restored.custom_slots, slots)

    async def test_auto_hud_starts_only_when_screen_on_and_ready(self):
        import asyncio
        from unittest.mock import AsyncMock
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            backend = DemoBackend()
            backend.connected = True
            backend.gatt_report = {'loy': {'power_status': {'on': False}}}
            c = Controller(backend, root/'logs', demo=True, settings_path=root/'styles.json')
            c.device_info = {'profile':'loy-fff'}
            c.override = [96,16]
            c.dispatch = AsyncMock()
            task = asyncio.create_task(c.auto_connect_loop())
            await asyncio.sleep(0.05)
            c.dispatch.assert_not_awaited()
            backend.gatt_report['loy']['power_status']['on'] = True
            await asyncio.sleep(1.1)
            c.dispatch.assert_awaited_once_with('hud_link', {'mode':'screen'})
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task

    async def test_custom_weight_survives_save_and_activation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            backend = DemoBackend(); backend.connected = True
            c = Controller(backend, root/'logs', demo=True, settings_path=root/'styles.json')
            c.override = [96, 16]; c.busy = 'hud_link'
            slots = [{'text':'謝謝', 'color':'ff0000', 'effect':'static', 'speed':1, 'weight':'bold'}] + [None]*4
            await c.dispatch('save_custom_slots', {'slots':slots})
            await c.dispatch('activate_custom_slot', {'index':0})
            self.assertEqual(c.custom_style['weight'], 'bold')
            reloaded = Controller(DemoBackend(), root/'logs2', demo=True, settings_path=root/'styles.json')
            self.assertEqual(reloaded.custom_slots[0]['weight'], 'bold')
