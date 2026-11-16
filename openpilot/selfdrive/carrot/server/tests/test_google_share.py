import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from types import SimpleNamespace as NS
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from openpilot.selfdrive.carrot.server.features import google_share as g

@pytest.mark.parametrize('url', [
 'https://www.google.com/maps/search/?api=1&query=24.8%2C121',
 'https://maps.google.com/maps?q=24.8,121',
 'https://maps.google.com/?q=24.8,121',
 'https://www.google.com.tw/maps/dir/?destination=24.8,121',
 '台元二街\nhttps://www.google.com/maps/place/Test/@0,0,3z/data=!3d24.8!4d121',
])
def test_explicit_place(url):
  p=g.parse_place(url)['destination'];assert (p['latitude'],p['longitude'])==(24.8,121.)

@pytest.mark.parametrize('url', [
 'https://www.google.com/maps/@24,121,15z',
 'https://www.google.com/maps/dir/24,121/25,122/',
 'https://www.google.com/maps/?q=91,121',
 'https://www.google.com/maps/?q=NaN,121',
])
def test_no_camera_center_or_invalid_coordinates(url):
  with pytest.raises(ValueError):g.parse_place(url)

def test_names_and_ambiguous_places_require_search():
  assert g.parse_place('https://www.google.com/maps/place/My+Place/@0,0,3z')['query']=='My Place'
  assert g.parse_place('https://www.google.com/maps/place/Test/data=!3d24!4d121!3d25!4d122')['query']=='Test'

@pytest.mark.parametrize('url', ['http://maps.app.goo.gl/test','https://127.0.0.1/maps',
 'https://www.google.com.evil.test/maps','https://google.com@127.0.0.1/maps',
 'https://user:password@google.com/maps','https://google.com:8080/maps',
 'https://google.com:bad/maps','https://goo.gl/notmaps/foo','https://www.google.com/url?q=x',
 'https://www.google.com/maps\nhttps://www.google.com/maps','',None,'x'*4097])
def test_url_boundary(url):
  with pytest.raises(ValueError):g.validate_url(url)

class HTTP:
  def __init__(self, targets):self.targets=list(targets);self.calls=[]
  @asynccontextmanager
  async def get(self,url,**kwargs):
    self.calls.append(url);assert kwargs['allow_redirects'] is False
    status,location=self.targets.pop(0)
    yield NS(status=status,headers={'Location':location})

def test_redirect_hops():
  async def run():
    http=HTTP([(302,'https://www.google.com/maps/?q=24,121')])
    assert (await g.resolve_url(http,'https://maps.app.goo.gl/test'))['destination']['latitude']==24
    for location in ['https://127.0.0.1/maps','http://www.google.com/maps?q=24,121','https://evil.test/']:
      http=HTTP([(302,location)])
      with pytest.raises(ValueError):await g.resolve_url(http,'https://maps.app.goo.gl/test')
      assert len(http.calls)==1
    http=HTTP([(302,'https://maps.app.goo.gl/next')]*6)
    with pytest.raises(ValueError):await g.resolve_url(http,'https://maps.app.goo.gl/test')
    assert len(http.calls)==6
    with pytest.raises(ValueError):await g.resolve_url(HTTP([(200,'')]),'https://maps.app.goo.gl/test')
  asyncio.run(run())

def test_pair_confirm_revoke(monkeypatch,tmp_path):
  path=tmp_path/'pair.json';monkeypatch.setattr(g,'PAIR_PATH',path)
  values={};monkeypatch.setattr(g,'set_param_value',lambda k,v:values.__setitem__(k,v))
  g.write_pair({'code_sha256':hashlib.sha256(b'123456').hexdigest(),'expires':10**12})
  assert path.stat().st_mode & 0o777 == 0o600
  async def run():
    app=web.Application();app['http']=HTTP([]);g.register(app)
    async with TestClient(TestServer(app)) as c:
      assert (await c.get('/navigation/share')).status==200
      assert (await c.post('/api/navigation/share/confirm',json={})).status==401
      assert (await c.post('/api/navigation/share/pair',json={'code':'wrong'})).status==403
      r=await c.post('/api/navigation/share/pair',json={'code':'123456'})
      token=(await r.json())['token'];headers={'Authorization':'Bearer '+token}
      assert 'code_sha256' not in g.read_pair()
      assert (await c.post('/api/navigation/share/pair',json={'code':'123456'})).status==403
      r=await c.post('/api/navigation/share/resolve',headers=headers,json={'url':'https://www.google.com/maps/?q=24,121'})
      assert r.status==200;place=(await r.json())['destination'];assert not values
      r=await c.post('/api/navigation/share/confirm',headers=headers,json=place)
      assert r.status==200 and json.loads(values['NavDestination'])==place
      assert values['NavDestinationWaypoints']==''
      assert (await c.post('/api/navigation/share/confirm',headers=headers,json={'latitude':None,'longitude':121})).status==400
      g.write_pair({'code_sha256':'new','expires':10**12})
      assert (await c.post('/api/navigation/share/confirm',headers=headers,json=place)).status==401
  asyncio.run(run())

def test_expiry_rate_limit(monkeypatch,tmp_path):
  monkeypatch.setattr(g,'PAIR_PATH',tmp_path/'pair.json')
  g.write_pair({'code_sha256':hashlib.sha256(b'123456').hexdigest(),'expires':1})
  async def run():
    app=web.Application();app['http']=HTTP([]);g.register(app)
    async with TestClient(TestServer(app)) as c:
      for _ in range(5):assert (await c.post('/api/navigation/share/pair',json={'code':'123456'})).status==403
      assert (await c.post('/api/navigation/share/pair',json={'code':'123456'})).status==429
  asyncio.run(run())
