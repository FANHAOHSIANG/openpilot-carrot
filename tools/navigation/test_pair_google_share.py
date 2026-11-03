"""The device shell may have no aiohttp or native openpilot modules."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


class PairCLITest(unittest.TestCase):
  def test_without_site_packages_and_with_existing_pairing(self):
    script = Path(__file__).with_name('pair_google_share.py')
    with tempfile.TemporaryDirectory() as directory:
      target = Path(directory) / 'state/google-share-pair.json'
      target.parent.mkdir()
      target.write_text('{"token_sha256":"old"}')
      target.chmod(0o644)
      for _ in range(2):
        result = subprocess.run([sys.executable, '-I', '-S', str(script)],
                                env=dict(os.environ, CARROT_DATA_DIR=directory),
                                capture_output=True, text=True, check=True)
        code = re.search(r'：(\d{6})', result.stdout)[1]
        saved = json.loads(target.read_text())
        self.assertEqual(saved['code_sha256'], hashlib.sha256(code.encode()).hexdigest())
        self.assertNotIn('token_sha256', saved)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertFalse(target.with_name(target.name + '.tmp').exists())


if __name__ == '__main__':
  unittest.main()
