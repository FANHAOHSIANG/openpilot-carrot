import pytest
from openpilot.common.jetlink_peer import classify_auto_peer, may_provision

MAC = {'protocol': 3, 'backend': 'ort', 'device': 'ane-both-Apple_M4', 'carrot_host': 'mac'}


@pytest.mark.parametrize('device', ['ane-both-Apple_M4', 'ane-Apple_M4', 'ane-whole-Apple_M4', 'coreml-Apple_M4', 'ane-both-Apple_M5_Max'])
def test_supported_mac(device):
  peer = dict(MAC, device=device)
  assert classify_auto_peer(peer, 'usb') == 'usb'
  assert may_provision(peer, 'auto') and may_provision(peer, 'usb')
  assert classify_auto_peer(peer, 'tcp') is None


@pytest.mark.parametrize('change', [{'device': 'ane-other-Apple_M4'}, {'device': 'cpu-Apple_M4'}, {'device': 'ane-both-Apple_A17_Pro'}, {'protocol': True}, {'protocol': 4}, {'backend': 'trt'}, {'carrot_host': 'jetson'}])
def test_reject_invalid(change):
  peer = dict(MAC, **change)
  assert classify_auto_peer(peer, 'usb') is None
  assert not may_provision(peer, 'usb')
