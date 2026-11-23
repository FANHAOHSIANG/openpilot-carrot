"""C4 presentation selector contracts. No vehicle-control or graphics imports."""
import unittest
from pathlib import Path
from openpilot.selfdrive.ui.layout_profile import c4_scene_style, device_layout

ROOT = Path(__file__).resolve().parents[4]


class _Params:
  def __init__(self, value=None, error=None):
    self.value = value
    self.error = error

  def get_int(self, key):
    assert key == "C4SceneStyle"
    if self.error is not None:
      raise self.error
    return self.value


class TestC4SceneStyle(unittest.TestCase):
  def test_stock_is_repository_default(self):
    self.assertEqual(device_layout("c4")["scene_style"], 0)

  def test_all_three_modes(self):
    for selection in (0, 1, 2):
      with self.subTest(selection=selection):
        self.assertEqual(c4_scene_style(_Params(selection)), selection)

  def test_invalid_or_unreadable_value_falls_back_to_stock(self):
    for selection in (-1, 3, 99):
      with self.subTest(selection=selection):
        self.assertEqual(c4_scene_style(_Params(selection)), 0)
    self.assertEqual(c4_scene_style(_Params(error=ValueError("unavailable"))), 0)

  def test_native_setting_and_runtime_are_wired(self):
    toggles = (ROOT / "openpilot/selfdrive/ui/mici/layouts/settings/toggles.py").read_text()
    renderer = (ROOT / "openpilot/selfdrive/ui/mici/onroad/augmented_road_view.py").read_text()
    hud = (ROOT / "openpilot/selfdrive/ui/mici/onroad/hud_renderer.py").read_text()
    keys = (ROOT / "openpilot/common/params_keys.h").read_text()
    self.assertIn('"C4SceneStyle", {PERSISTENT, INT, "0"}', keys)
    self.assertIn('"官方原生", "Tony 3D 夜間", "Tony 3D 日間"', toggles)
    self.assertIn('not ui_state.started and not ui_state.engaged', toggles)
    self.assertIn('self._refresh_scene_style(now)', renderer)
    self.assertIn('self._reality.style["scene_style"] = c4_scene_style(ui_state.params)', renderer)
    self.assertIn('HUD_LAYOUT["scene_style"])  # Invalidate cached HUD paint', hud)


if __name__ == "__main__":
  unittest.main()
