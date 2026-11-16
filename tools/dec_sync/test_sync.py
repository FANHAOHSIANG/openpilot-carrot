"""Real local git histories: failed merges/checks must never publish."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('dec_sync', Path(__file__).with_name('sync.py'))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.upstream = self.root / 'official'
    self.downstream = self.root / 'downstream'
    self.published = self.root / 'published.git'
    self.upstream.mkdir()
    sync.git(self.upstream, 'init', '-b', 'carrot-wip')
    self.configure(self.upstream)
    self.commit(self.upstream, 'shared', 'base')
    self.protected = 'openpilot/selfdrive/controls/tests/test_carrot_dec.py'
    self.commit(self.upstream, self.protected, 'test gate')
    self.required = sync.git(self.upstream, 'rev-parse', 'HEAD')
    subprocess.run(['git', 'clone', str(self.upstream), str(self.downstream)], check=True, capture_output=True)
    self.configure(self.downstream)
    sync.git(self.downstream, 'checkout', '-b', 'carrotpilot-dec')
    self.commit(self.downstream, 'dec-feature', 'DEC enabled by setting')
    sync.git(self.root, 'init', '--bare', str(self.published))
    sync.git(self.downstream, 'remote', 'set-url', 'origin', str(self.published))
    sync.git(self.downstream, 'push', 'origin', 'carrotpilot-dec')
    self.base = sync.git(self.downstream, 'rev-parse', 'HEAD')

  def configure(self, repo):
    sync.git(repo, 'config', 'user.name', 'Test')
    sync.git(repo, 'config', 'user.email', 'test@example.invalid')

  def commit(self, repo, name, value):
    file = repo / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(value)
    sync.git(repo, 'add', name)
    sync.git(repo, 'commit', '-m', name)

  def prepare(self, validator=lambda _: None):
    return sync.prepare(self.downstream, str(self.upstream), self.required, validator)

  def assert_unpublished(self):
    self.assertEqual(sync.git(self.published, 'rev-parse', 'carrotpilot-dec'), self.base)

  def test_clean_merge_preserves_feature_and_validates_before_ready(self):
    self.commit(self.upstream, 'official-fix', 'fix')
    seen = []
    result = self.prepare(lambda p: seen.append((p / 'official-fix').read_text()))
    self.assertTrue(result['ready'])
    self.assertEqual(seen, ['fix'])
    self.assertTrue((self.downstream / 'dec-feature').exists())
    sync.git(self.downstream, 'merge-base', '--is-ancestor', self.required, result['candidate'])
    self.assert_unpublished()

  def test_already_current_does_not_merge_or_validate(self):
    result = self.prepare(lambda _: self.fail('No new commits'))
    self.assertFalse(result['ready'])
    self.assertEqual(result['candidate'], self.base)
    self.assert_unpublished()

  def test_conflict_aborts_without_publishing(self):
    self.commit(self.downstream, 'shared', 'downstream')
    self.commit(self.upstream, 'shared', 'upstream')
    before = sync.git(self.downstream, 'rev-parse', 'HEAD')
    with self.assertRaises(subprocess.CalledProcessError): self.prepare()
    self.assertEqual(sync.git(self.downstream, 'rev-parse', 'HEAD'), before)
    self.assertEqual(sync.git(self.downstream, 'status', '--porcelain'), '')
    self.assert_unpublished()

  def test_failed_checks_never_publish(self):
    self.commit(self.upstream, 'official-fix', 'fix')
    def failed(_): raise RuntimeError('Model API incompatible')
    with self.assertRaises(RuntimeError): self.prepare(failed)
    self.assert_unpublished()

  def test_upstream_cannot_replace_downstream_test_gate(self):
    self.commit(self.upstream, self.protected, 'weakened test')
    with self.assertRaisesRegex(RuntimeError, 'tests changed'): self.prepare()
    self.assert_unpublished()

  def test_dirty_checkout_is_rejected(self):
    (self.downstream / 'shared').write_text('local edit')
    with self.assertRaisesRegex(RuntimeError, 'dirty'): self.prepare()
    self.assert_unpublished()

  def test_missing_feature_history_is_rejected(self):
    self.commit(self.upstream, 'future', 'not in downstream')
    required = sync.git(self.upstream, 'rev-parse', 'HEAD')
    with self.assertRaises(subprocess.CalledProcessError):
      sync.prepare(self.downstream, str(self.upstream), required, lambda _: None)
    self.assert_unpublished()

  def test_checks_that_modify_source_are_rejected(self):
    self.commit(self.upstream, 'official-fix', 'fix')
    def modifies(root): (root / 'shared').write_text('unreviewed')
    with self.assertRaisesRegex(RuntimeError, 'modified tracked'): self.prepare(modifies)
    self.assert_unpublished()


if __name__ == '__main__': unittest.main()
