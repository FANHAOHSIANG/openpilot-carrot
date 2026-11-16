"""Protocol-3 Mac transport: explicit negotiation and lossless N16 data only."""
from dataclasses import replace
import json

import numpy as np
import pytest

from test_output_projection import Loopback
from test_nav_rl import SPEC
from jetlink import output_projection as C, packed_codec as M, protocol as P
from jetlink.client import JetlinkClient
from jetlink.transport.base import LinkError


def pair(capability=True, host='mac', model=SPEC):
  transport = Loopback()
  transport.protocol_version = 3
  seen = []
  def handle(message):
    if message.msg_type == P.Msg.HELLO_REQ:
      hello = {'protocol': 3, 'carrot_host': host}
      if capability: hello[C.MAC_CAPABILITY] = C.descriptor()
      transport.send(P.Msg.HELLO_RESP, message.seq, [json.dumps(hello).encode()])
      return
    frame, flags = P.unpack_infer_req(message.payload)
    context = message.payload[P.INFER_REQ_SIZE + model.warped_nbytes:]
    restored = M.decode(context, model) if flags & M.FLAG else bytes(context)
    seen.append((bytes(message.payload[P.INFER_REQ_SIZE:P.INFER_REQ_SIZE + model.warped_nbytes]), restored, flags))
    count = C.COUNT if flags & C.FLAG else model.output_nelem
    output = np.arange(count, dtype=np.float32) / 8
    body = P.pack_infer_resp(frame, P.Status.OK, 35000, 50, 35100) + output.tobytes()
    if flags & P.Flag.WANT_STATE: body += b'{"temperature":42}'
    transport.send(P.Msg.INFER_RESP, message.seq, [body], flags=C.FLAG if flags & C.FLAG else 0)
  transport.handler = handle
  client = JetlinkClient(transport, allow_output_projection=True)
  client.hello()
  client.spec = model
  return client, seen


def test_mac_v3_full_compact_full_preserves_exact_inputs_and_driving_outputs():
  client, seen = pair()
  assert client.output_projection_available
  images = np.arange(SPEC.warped_nbytes, dtype=np.uint8).reshape(SPEC.warped_shape)
  packed = np.arange(SPEC.packed_nelem, dtype=np.float32) / 8
  offset = sum(SPEC.packed_sizes[:list(SPEC.packed_shapes).index('nav_map')])
  packed[offset:offset + M.MAP_PIXELS] = np.arange(M.MAP_PIXELS, dtype=np.uint8)
  # Non-map scalars retain their exact float bits, including signed zero.
  packed[0] = -0.
  replies = []
  for frame, compact in enumerate([False, True, False, True]):
    client.project_output = compact
    replies.append(client.infer(images, packed, frame, reset=frame == 0, want_state=True))
    assert seen[-1][0] == images.tobytes() and seen[-1][1] == packed.tobytes()
    assert bool(seen[-1][2] & P.Flag.WANT_HIDDEN) == (not compact)
    assert client.last_state == {'temperature': 42}
    request = client.t.requests[-1]
    assert len(request.payload) == P.INFER_REQ_SIZE + SPEC.warped_nbytes + SPEC.packed_nbytes - 3*M.MAP_PIXELS
  assert replies[0][:C.COUNT].tobytes() == replies[1].tobytes() == replies[2][:C.COUNT].tobytes() == replies[3].tobytes()


@pytest.mark.parametrize('pixel', [.25, -0., -1., 256.])
def test_mac_noncanonical_map_keeps_full_float32_without_quantization(pixel):
  client, seen = pair()
  packed = np.zeros(SPEC.packed_nelem, np.float32)
  packed[12] = pixel
  client.project_output = True
  client.infer(np.zeros(SPEC.warped_shape, np.uint8), packed, 4)
  assert not seen[-1][2] & M.FLAG
  assert seen[-1][1] == packed.tobytes()


@pytest.mark.parametrize('capability,host', [(False, 'mac'), (True, 'jetson'), (True, None)])
def test_v3_old_or_other_host_keeps_original_full_protocol(capability, host):
  client, seen = pair(capability, host)
  assert not client.output_projection_available
  result = client.infer(np.zeros(SPEC.warped_shape, np.uint8), np.zeros(SPEC.packed_nelem, np.float32), 1)
  assert result.size == C.FULL_COUNT
  assert not seen[-1][2] & (C.FLAG | M.FLAG)
  assert seen[-1][2] & P.Flag.WANT_HIDDEN


@pytest.mark.parametrize('change', ['sha', 'slices', 'skip'])
def test_v3_different_model_contract_never_uses_extension(change):
  model = (replace(SPEC, sha256='0'*64) if change == 'sha' else
           replace(SPEC, frame_skip=2) if change == 'skip' else
           replace(SPEC, output_slices={**SPEC.output_slices, 'action': slice(2061, 2065)}))
  client, seen = pair(model=model)
  assert not client.output_projection_available
  client.infer(np.zeros(model.warped_shape, np.uint8), np.zeros(model.packed_nelem, np.float32), 1)
  assert not seen[-1][2] & (C.FLAG | M.FLAG)
  client.project_output = True
  with pytest.raises(LinkError, match='not negotiated'):
    client.infer_begin(np.zeros(model.warped_shape, np.uint8), np.zeros(model.packed_nelem, np.float32))


def test_v3_rehello_revokes_compaction():
  client, _ = pair()
  assert client.output_projection_available
  client.project_output = True
  client.t.handler = lambda msg: client.t.send(P.Msg.HELLO_RESP, msg.seq, [b'{"protocol":3,"carrot_host":"mac"}'])
  client.hello()
  assert not client.project_output and not client.output_projection_available and not client._mac_n16_transport
