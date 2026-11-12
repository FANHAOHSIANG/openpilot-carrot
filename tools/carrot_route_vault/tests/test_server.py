import asyncio
from pathlib import Path

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

from ..server import UPLOAD_SERVICE_KEY, Config, create_app


DEVICE = "0123456789abcdef"
CLIENT_IP = "203.0.113.10"


def config(tmp_path: Path, *, quota: int = 1024 * 1024) -> Config:
  return Config(
    storage_root=tmp_path / "uploads",
    db_path=tmp_path / "state" / "uploads.sqlite3",
    daily_device_quota=quota,
    daily_ip_quota=quota * 4,
    max_file_bytes=1024 * 1024,
    max_tmux_bytes=1024 * 1024,
    min_free_bytes=0,
    session_ttl_seconds=600,
    concurrent_per_device=3,
    concurrent_global=16,
  )


async def session(
  client: TestClient,
  *,
  purpose: str = "dashcam",
  ip: str = CLIENT_IP,
  metadata: dict[str, str] | None = None,
) -> str:
  response = await client.post(
    "/api/v1/session",
    json={"deviceId": DEVICE, "purpose": purpose, "carName": "TEST", **(metadata or {})},
    headers={"X-Forwarded-For": ip},
  )
  assert response.status == 200, await response.text()
  return (await response.json())["token"]


def test_health_session_stream_upload_and_completion(tmp_path: Path):
  async def run():
    async with TestClient(TestServer(create_app(config(tmp_path), start_cleanup=False))) as client:
      health = await client.get("/api/v1/health")
      assert health.status == 200
      health_body = await health.json()
      assert health_body["ok"] is True
      assert health_body["bandwidthLimit"] is None

      token = await session(client)
      content = b"camera-data"
      headers = {
        "Authorization": f"Bearer {token}",
        "X-Forwarded-For": CLIENT_IP,
        "X-File-Size": str(len(content)),
      }
      upload = await client.put(
        f"/api/v1/upload/{DEVICE}/2026-07-20--00-00-00--0/qlog.zst",
        data=content,
        headers=headers,
      )
      assert upload.status == 200, await upload.text()
      assert await upload.json() == {"ok": True, "size": len(content)}
      assert (
        tmp_path / "uploads" / "routes" / f"TEST {DEVICE}" / "2026-07-20--00-00-00--0" / "qlog.zst"
      ).read_bytes() == content

      complete = await client.post(
        "/api/v1/complete",
        json={"deviceId": DEVICE, "ok": True, "meta": {"dongleId": DEVICE}},
        headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": CLIENT_IP},
      )
      assert complete.status == 200
      manifests = list((tmp_path / "state" / "manifests" / DEVICE).glob("*.json"))
      assert len(manifests) == 1

  asyncio.run(run())


def test_session_is_bound_to_ip_and_device(tmp_path: Path):
  async def run():
    async with TestClient(TestServer(create_app(config(tmp_path), start_cleanup=False))) as client:
      token = await session(client)
      headers = {
        "Authorization": f"Bearer {token}",
        "X-Forwarded-For": "203.0.113.99",
        "X-File-Size": "1",
      }
      wrong_ip = await client.put(
        f"/api/v1/upload/{DEVICE}/route--0/qlog", data=b"x", headers=headers,
      )
      assert wrong_ip.status == 403

      headers["X-Forwarded-For"] = CLIENT_IP
      wrong_device = await client.put(
        "/api/v1/upload/fedcba9876543210/route--0/qlog", data=b"x", headers=headers,
      )
      assert wrong_device.status == 403

      test_token = await session(client, purpose="test")
      test_session_upload = await client.put(
        f"/api/v1/upload/{DEVICE}/route--0/qlog",
        data=b"x",
        headers={
          "Authorization": f"Bearer {test_token}",
          "X-Forwarded-For": CLIENT_IP,
          "X-File-Size": "1",
        },
      )
      assert test_session_upload.status == 403

      spoofed_session = await session(client, ip=f"198.51.100.77, {CLIENT_IP}")
      real_ip_upload = await client.put(
        f"/api/v1/upload/{DEVICE}/route--0/qlog",
        data=b"x",
        headers={
          "Authorization": f"Bearer {spoofed_session}",
          "X-Forwarded-For": CLIENT_IP,
          "X-File-Size": "1",
        },
      )
      assert real_ip_upload.status == 200

  asyncio.run(run())


def test_quota_and_file_validation(tmp_path: Path):
  async def run():
    async with TestClient(TestServer(create_app(config(tmp_path, quota=8), start_cleanup=False))) as client:
      token = await session(client)

      async def upload(filename: str, content: bytes):
        return await client.put(
          f"/api/v1/upload/{DEVICE}/route--0/{filename}",
          data=content,
          headers={
            "Authorization": f"Bearer {token}",
            "X-Forwarded-For": CLIENT_IP,
            "X-File-Size": str(len(content)),
          },
        )

      first = await upload("qlog", b"123456")
      assert first.status == 200
      # Replacing an existing remote path still consumes daily transfer quota.
      # Otherwise a client could evade the limit by overwriting one filename.
      over_quota = await upload("qlog", b"7890")
      assert over_quota.status == 413
      blocked = await upload("run.py", b"x")
      assert blocked.status == 400
      assert not list((tmp_path / "uploads").rglob("*.part"))

  asyncio.run(run())


def test_tmux_multipart_upload(tmp_path: Path):
  async def run():
    async with TestClient(TestServer(create_app(config(tmp_path), start_cleanup=False))) as client:
      token = await session(
        client,
        purpose="tmux",
        metadata={"git_branch": "carrot/wip", "tmux_why": "can_error"},
      )
      form = FormData()
      form.add_field("tmux_why", "can_error")
      form.add_field("files[0]", b"tmux output", filename="tmux.log", content_type="text/plain")
      form.add_field("files[1]", b'{"enabled":true}', filename="toggle_values.json", content_type="application/json")
      response = await client.post(
        "/api/v1/tmux/upload",
        data=form,
        headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": CLIENT_IP},
      )
      assert response.status == 200, await response.text()
      body = await response.json()
      assert body["ok"] is True
      assert body["files"] == 2
      tmux_logs = list(
        (tmp_path / "uploads" / "carrot__wip" / f"TEST {DEVICE}").glob(
          "can_error-*-carrot__wip.txt",
        ),
      )
      assert len(tmux_logs) == 1
      assert tmux_logs[0].read_bytes() == b"tmux output"
      assert not (tmp_path / "uploads" / "tmux" / "carrot__wip").exists()

  asyncio.run(run())


def test_cleanup_never_deletes_existing_openpilot_files(tmp_path: Path):
  async def run():
    existing = tmp_path / "uploads" / "carrot-wip" / "README.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("keep", encoding="utf-8")
    service_app = create_app(config(tmp_path), start_cleanup=False)
    await service_app[UPLOAD_SERVICE_KEY].cleanup()
    assert existing.read_text(encoding="utf-8") == "keep"

  asyncio.run(run())


def test_verified_duplicates_skip_upload_even_when_daily_quota_is_full(tmp_path):
  import hashlib
  from aiohttp import web
  from openpilot.selfdrive.carrot.web_upload import upload_folder_to_web, UploadQuotaExceeded
  import pytest

  async def run():
    calls = []
    @web.middleware
    async def count(request, handler):
      if request.method == 'PUT':
        calls.append(request.path)
      return await handler(request)
    app = create_app(config(tmp_path, quota=11), start_cleanup=False)
    app.middlewares.append(count)
    async with TestClient(TestServer(app)) as client:
      token = await session(client, ip='127.0.0.1')
      local = tmp_path / 'local'
      local.mkdir()
      video = local / 'qcamera.ts'
      video.write_bytes(b'camera-data')
      base = str(client.make_url('')).rstrip('/')
      args = (str(local), DEVICE, 'route--0', base, token)
      assert await upload_folder_to_web(*args)
      assert len(calls) == 1
      updates = []
      assert await upload_folder_to_web(*args, on_progress=lambda *a: updates.append(a))
      assert len(calls) == 1  # GET verified it; no duplicate transfer or reservation.
      assert updates == [('qcamera.ts', 11, 11, 0)]
      url = f'/api/v1/upload/{DEVICE}/route--0/qcamera.ts'
      headers = {'Authorization': f'Bearer {token}', 'X-File-Size': '11',
                 'X-File-SHA256': hashlib.sha256(b'camera-data').hexdigest()}
      duplicate = await client.put(url, data=b'camera-data', headers=headers)
      assert duplicate.status == 200 and (await duplicate.json())['skipped']
      video.write_bytes(b'changed-abc')  # Same size is insufficient to skip.
      with pytest.raises(UploadQuotaExceeded):
        await upload_folder_to_web(*args)
      assert len(calls) == 3  # One rejection, not two attempts.
      response = await client.put(url, data=b'x', headers={'Authorization': f'Bearer {token}', 'X-File-Size': '1'})
      assert response.status == 413
      assert (await response.json())['code'] == 'daily_quota_exceeded'
  asyncio.run(run())


def test_upload_checksum_mismatch_never_installs_file(tmp_path):
  async def run():
    async with TestClient(TestServer(create_app(config(tmp_path), start_cleanup=False))) as client:
      token = await session(client)
      url = f'/api/v1/upload/{DEVICE}/route--0/qcamera.ts'
      headers = {'Authorization': f'Bearer {token}', 'X-Forwarded-For': CLIENT_IP,
                 'X-File-Size': '3', 'X-File-SHA256': '0' * 64}
      response = await client.put(url, data=b'abc', headers=headers)
      assert response.status == 400
      status = await client.get(url, headers=headers)
      assert (await status.json())['exists'] is False
  asyncio.run(run())


def test_old_receiver_existing_original_is_hash_verified_before_put(tmp_path):
  from aiohttp import web
  from openpilot.selfdrive.carrot.web_upload import upload_folder_to_web

  async def run():
    puts, downloads = [], []
    @web.middleware
    async def old_receiver(request, handler):
      if request.method == 'GET' and request.path.startswith('/api/v1/upload/'):
        return web.Response(status=405)
      if request.method == 'PUT':
        puts.append(request.path)
      if '/files/' in request.path:
        downloads.append(request.path)
      return await handler(request)
    app = create_app(config(tmp_path, quota=11), start_cleanup=False)
    app.middlewares.append(old_receiver)
    async with TestClient(TestServer(app)) as client:
      token = await session(client, ip='127.0.0.1')
      local = tmp_path / 'local'
      local.mkdir()
      (local / 'qcamera.ts').write_bytes(b'camera-data')
      base = str(client.make_url('')).rstrip('/')
      args = (str(local), DEVICE, '000003cc--8d19bf55d5--15', base, token)
      assert await upload_folder_to_web(*args)
      existing = f'{base}/routes/TEST%20{DEVICE}/'
      assert await upload_folder_to_web(*args, existing_base_url=existing)
      assert len(puts) == 1 and len(downloads) == 1
  asyncio.run(run())
