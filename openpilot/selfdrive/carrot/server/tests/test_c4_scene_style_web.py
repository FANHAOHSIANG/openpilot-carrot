"""C4 Web scene-style writes must agree with the C4 on-device selector."""
import asyncio
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

# Loading server.features/__init__.py pulls in live IPC and msgq, which the
# portable Web settings CI intentionally does not build. Import the actual
# param endpoint against a lightweight package and isolated system stub.
FEATURES = "openpilot.selfdrive.carrot.server.features"
if FEATURES not in sys.modules:
  package = ModuleType(FEATURES)
  package.__path__ = [str(Path(__file__).resolve().parents[1] / "features")]
  sys.modules[FEATURES] = package
system_stub = ModuleType(f"{FEATURES}.system")
system_stub.is_drive_engaged = lambda request: False
sys.modules.setdefault(f"{FEATURES}.system", system_stub)

from openpilot.selfdrive.carrot.server.features import params as endpoint
from openpilot.selfdrive.carrot.server.services.settings import build_menu_categories, group_index
from openpilot.selfdrive.carrot.server.config import DEFAULT_SETTINGS_PATH


class FakeParams:
  def __init__(self, onroad=False, engaged=False, unreadable=False):
    self.onroad = onroad
    self.engaged = engaged
    self.unreadable = unreadable

  def get_bool(self, key):
    if self.unreadable:
      raise RuntimeError("no device state")
    return {"IsOnroad": self.onroad, "IsEngaged": self.engaged}[key]


class FakeRequest:
  def __init__(self, choice):
    self.choice = choice

  async def json(self):
    return {"name": "C4SceneStyle", "value": self.choice, "source": "web"}


def test_c4_scene_web_catalog_is_localized_and_in_display():
  with open(DEFAULT_SETTINGS_PATH, encoding="utf-8") as f:
    catalog = json.load(f)
  _, by_name, _ = group_index(catalog)
  setting = by_name["C4SceneStyle"]
  assert (setting["min"], setting["max"], setting["default"], setting["control"]) == (0, 2, 0, "select")
  assert setting["options"]["zh-tw"] == ["官方原生", "Tony 3D 夜間", "Tony 3D 日間"]
  assert all(len(setting["options"][key]) == 3 for key in ("ko", "en", "zh", "zh-tw"))
  categories = build_menu_categories(catalog, by_name)
  display = next(category for category in categories if category["id"] == "DISPLAY")
  group = next(section for section in display["groups"] if section["id"] == "DISP_BRIGHT")
  assert "C4SceneStyle" in group["sections"][0]["items"]


@pytest.mark.parametrize("onroad,engaged,unreadable,allowed", [
  (False, False, False, True), (True, False, False, False),
  (False, True, False, False), (False, False, True, False),
])
def test_offroad_gate_fails_closed(monkeypatch, onroad, engaged, unreadable, allowed):
  monkeypatch.setattr(endpoint, "HAS_PARAMS", True)
  monkeypatch.setattr(endpoint, "Params", lambda: FakeParams(onroad, engaged, unreadable))
  assert endpoint._c4_scene_style_offroad() is allowed


@pytest.mark.parametrize("choice,status", [
  (0, 200), (1, 200), (2, 200), (3, 400), (-1, 400), (1.5, 400), (True, 400), ("2", 400),
])
def test_web_scene_write_validation(monkeypatch, choice, status):
  writes = []
  monkeypatch.setattr(endpoint, "HAS_PARAMS", True)
  monkeypatch.setattr(endpoint, "Params", lambda: FakeParams())
  monkeypatch.setattr(endpoint, "get_settings_cached",
                      lambda: (None, None, {"C4SceneStyle": {"default": 0, "min": 0, "max": 2}}, None))
  monkeypatch.setattr(endpoint, "get_param_values", lambda *args, **kwargs: {"C4SceneStyle": 0})
  monkeypatch.setattr(endpoint, "set_param_value", lambda name, value, _: writes.append((name, value)))
  monkeypatch.setattr(endpoint, "append_param_change", lambda *args, **kwargs: None)
  monkeypatch.setattr(endpoint, "is_drive_engaged", lambda _: False)
  result = asyncio.run(endpoint.api_param_set(FakeRequest(choice)))
  assert result.status == status
  payload = json.loads(result.body)
  assert payload["ok"] is (status == 200)
  assert writes == ([("C4SceneStyle", choice)] if status == 200 else [])


def test_web_rejects_in_motion_and_never_writes(monkeypatch):
  writes = []
  monkeypatch.setattr(endpoint, "HAS_PARAMS", True)
  monkeypatch.setattr(endpoint, "Params", lambda: FakeParams(onroad=True))
  monkeypatch.setattr(endpoint, "set_param_value", lambda *args: writes.append(args))
  monkeypatch.setattr(endpoint, "get_settings_cached",
                      lambda: (None, None, {"C4SceneStyle": {"default": 0, "min": 0, "max": 2}}, None))
  monkeypatch.setattr(endpoint, "get_param_values", lambda *args, **kwargs: {"C4SceneStyle": 0})
  result = asyncio.run(endpoint.api_param_set(FakeRequest(2)))
  assert result.status == 409
  assert writes == []
