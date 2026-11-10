"""Prepare the optional camera adapter without sharing modeld's tinygrad state."""
from concurrent.futures import Future, InvalidStateError
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

PREPARE_TIMEOUT = 60


def preparation_output_tail(output):
  return os.pread(output.fileno(), 2000, max(0, os.fstat(output.fileno()).st_size - 2000)).decode(errors='replace').strip()


class WarpPreparation:
  def __init__(self, width, height):
    self.future = Future()
    self.cancelled = threading.Event()
    self.thread = threading.Thread(target=self._prepare, args=(width, height), name='jetlink-prepare', daemon=True)
    self.thread.start()

  def _prepare(self, width, height):
    try:
      # Do not inherit modeld's realtime policy/core for the supervisor or compiler.
      if hasattr(os, 'sched_setscheduler'):
        os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))
        os.sched_setaffinity(0, {0, 1, 2})
      started = time.monotonic()
      with tempfile.TemporaryDirectory(prefix='jetlink-warp-', dir='/dev/shm' if sys.platform == 'linux' else None) as directory:
        target = Path(directory) / 'warp.pkl'
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(Path(p or '.').resolve()) for p in sys.path))
        # This adapter always targets the local QCOM GPU, regardless of any
        # unrelated default-device discovery or optional external model backend.
        env.update(DEV='QCOM', WARP_DEV='QCOM')
        process = None
        try:
          with (Path(directory) / 'prepare.log').open('w+b') as output:
            process = subprocess.Popen([sys.executable, '-m', __name__, str(width), str(height), str(os.getpid()), str(target)],
                                       cwd=directory, env=env, stdout=output, stderr=subprocess.STDOUT)
            while process.poll() is None:
              if self.cancelled.wait(.05):
                raise InterruptedError('Jetlink adapter preparation cancelled')
              if time.monotonic() - started > PREPARE_TIMEOUT:
                raise TimeoutError('Jetlink adapter preparation timed out: ' + (preparation_output_tail(output) or 'no worker output'))
            if process.returncode:
              raise RuntimeError('Jetlink adapter preparation failed: ' + preparation_output_tail(output))
            self.future.set_result((target.read_bytes(), time.monotonic() - started))
        finally:
          if process is not None and process.poll() is None:
            process.kill()
            process.wait()
    except InvalidStateError:
      pass  # Disconnected after preparation finished, before delivery.
    except Exception as exc:
      try:
        self.future.set_exception(exc)
      except InvalidStateError:
        pass
  def close(self):
    self.cancelled.set()
    self.future.cancel()


def main():
  import ctypes
  import signal
  width, height, parent = map(int, sys.argv[1:4])
  # A manager/modeld restart must not leave an orphan GPU compiler running.
  if ctypes.CDLL(None).prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent:
    raise RuntimeError('Jetlink preparation parent unavailable')
  os.nice(19)
  print('Jetlink warp worker: importing adapter', flush=True)
  from openpilot.selfdrive.modeld.jetlink.model import Warp

  print('Jetlink warp worker: building and validating camera warp', flush=True)
  warp = Warp(width, height)
  print('Jetlink warp worker: serializing and verifying restored warp', flush=True)
  warp.save_prepared(Path(sys.argv[4]), width, height)


if __name__ == '__main__':
  main()
