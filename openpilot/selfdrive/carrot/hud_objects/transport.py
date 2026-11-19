"""Local, latest-frame handoff between the C4 detector and the USB renderer."""
import json
import os
from pathlib import Path
import tempfile
import time

HUD_PATH = Path("/dev/shm/carrot-hud-objects.json")
SHARED_TRAFFIC_PATH = Path("/dev/shm/carrot-hud-truck-observation.json")


def capture_monotonic(eof_ns: int) -> float:
  """Express camerad's boot-clock capture timestamp on the readers' monotonic clock."""
  age = (time.clock_gettime_ns(time.CLOCK_BOOTTIME) - eof_ns) / 1e9
  return time.monotonic() - age


def write_snapshot(path: Path, payload: dict) -> None:
  data = json.dumps(payload, allow_nan=False, separators=(",", ":"))
  with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=path.name + ".", delete=False) as tmp:
    try:
      tmp.write(data)
      tmp.close()
      os.replace(tmp.name, path)
    finally:
      Path(tmp.name).unlink(missing_ok=True)
