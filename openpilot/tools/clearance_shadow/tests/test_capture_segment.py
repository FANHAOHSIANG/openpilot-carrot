import json
import zipfile

import pytest

from openpilot.tools.clearance_shadow import capture_segment as capture


@pytest.fixture
def segment(tmp_path):
  root = tmp_path / 'realdata'
  root.mkdir()
  path = root / '00000384--8d2511ca94--1'
  path.mkdir()
  (path / 'rlog.zst').write_bytes(b'rlog content')
  (path / 'fcamera.hevc').write_bytes(b'camera content')
  return path


def test_pack_and_verify_keep_originals(segment, tmp_path):
  output = tmp_path / 'evidence.zip'
  manifest = capture.pack_segment(segment.parent, segment.name, output, lambda: True)
  assert manifest['control_eligible'] is False
  assert capture.verify_archive(output) == manifest
  with zipfile.ZipFile(output) as archive:
    assert archive.read('rlog.zst') == b'rlog content'
    assert archive.read('fcamera.hevc') == b'camera content'
  assert (segment / 'rlog.zst').read_bytes() == b'rlog content'
  assert (segment / 'fcamera.hevc').read_bytes() == b'camera content'


def test_offroad_unknown_or_onroad_fails_without_writing(segment, tmp_path):
  output = tmp_path / 'evidence.zip'
  with pytest.raises(RuntimeError, match='IsOffroad'):
    capture.pack_segment(segment.parent, segment.name, output, lambda: False)
  assert not output.exists()


def test_logger_lock_fails_without_writing(segment, tmp_path):
  (segment / 'rlog.lock').touch()
  output = tmp_path / 'evidence.zip'
  assert capture.list_segments(segment.parent)[0]['locked'] is True
  with pytest.raises(RuntimeError, match='logger lock'):
    capture.pack_segment(segment.parent, segment.name, output, lambda: True)
  assert not output.exists()


def test_onroad_during_copy_deletes_only_partial_archive(segment, tmp_path):
  output = tmp_path / 'evidence.zip'
  checks = iter([True, True, True, False])
  with pytest.raises(RuntimeError, match='IsOffroad'):
    capture.pack_segment(segment.parent, segment.name, output, lambda: next(checks))
  assert not output.exists()
  assert (segment / 'rlog.zst').read_bytes() == b'rlog content'


def test_existing_output_is_never_overwritten(segment, tmp_path):
  output = tmp_path / 'evidence.zip'
  output.write_bytes(b'previous result')
  with pytest.raises(FileExistsError):
    capture.pack_segment(segment.parent, segment.name, output, lambda: True)
  assert output.read_bytes() == b'previous result'


def test_source_replacement_during_copy_is_rejected(segment, tmp_path):
  output = tmp_path / 'evidence.zip'
  calls = 0

  def offroad():
    nonlocal calls
    calls += 1
    if calls == 4:
      (segment / 'rlog.zst').write_bytes(b'changed during copy')
    return True

  with pytest.raises(RuntimeError, match='changed'):
    capture.pack_segment(segment.parent, segment.name, output, offroad)
  assert not output.exists()


@pytest.mark.parametrize('name', ['../outside--1', 'a/b--1', 'not-a-segment'])
def test_invalid_segment_names_rejected(segment, tmp_path, name):
  with pytest.raises(ValueError, match='segment name'):
    capture.pack_segment(segment.parent, name, tmp_path / 'x.zip', lambda: True)


def test_source_symlink_rejected(segment, tmp_path):
  source = segment / 'rlog.zst'
  source.unlink()
  source.symlink_to(tmp_path / 'elsewhere')
  with pytest.raises(ValueError, match='regular file'):
    capture.pack_segment(segment.parent, segment.name, tmp_path / 'x.zip', lambda: True)


def test_output_inside_segment_rejected(segment):
  with pytest.raises(ValueError, match='inside'):
    capture.pack_segment(segment.parent, segment.name, segment / 'evidence.zip', lambda: True)


def test_insufficient_space_fails_without_writing(segment, tmp_path, monkeypatch):
  monkeypatch.setattr(capture.shutil, 'disk_usage', lambda _: type('Space', (), {'free': capture.FREE_RESERVE})())
  output = tmp_path / 'evidence.zip'
  with pytest.raises(OSError, match='free space'):
    capture.pack_segment(segment.parent, segment.name, output, lambda: True)
  assert not output.exists()


def test_verify_detects_changed_contents(segment, tmp_path):
  good, bad = tmp_path / 'good.zip', tmp_path / 'bad.zip'
  capture.pack_segment(segment.parent, segment.name, good, lambda: True)
  with zipfile.ZipFile(good) as src, zipfile.ZipFile(bad, 'w') as dst:
    for name in src.namelist():
      data = src.read(name)
      if name == 'fcamera.hevc':
        data = b'X' * len(data)
      dst.writestr(name, data)
  with pytest.raises(ValueError, match='SHA-256 mismatch'):
    capture.verify_archive(bad)


def test_verify_rejects_unexpected_archive_members(tmp_path):
  path = tmp_path / 'bad.zip'
  with zipfile.ZipFile(path, 'w') as archive:
    archive.writestr('manifest.json', json.dumps({'schema': 1}))
    archive.writestr('../unexpected', 'x')
  with pytest.raises(ValueError, match='archive entries'):
    capture.verify_archive(path)


def test_missing_file_is_not_listed_or_packed(segment, tmp_path):
  (segment / 'fcamera.hevc').unlink()
  assert capture.list_segments(segment.parent) == []
  with pytest.raises(FileNotFoundError):
    capture.pack_segment(segment.parent, segment.name, tmp_path / 'x.zip', lambda: True)
