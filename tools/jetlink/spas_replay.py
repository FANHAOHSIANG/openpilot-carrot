"""Read local SPAS evidence. No vehicle interfaces or messaging are used."""
import argparse
from collections import Counter
import json
from pathlib import Path


NRC_NAMES = {0x11: 'service_not_supported', 0x12: 'subfunction_not_supported',
             0x22: 'conditions_not_correct', 0x31: 'request_out_of_range',
             0x33: 'security_access_denied', 0x78: 'response_pending'}


def decode_reply(payload):
  """Decode one complete UDS response, with ISO-TP framing already removed."""
  if len(payload) == 3 and payload[0] == 0x7F:
    service, nrc = payload[1:]
    return {'kind': 'negative', 'service': service, 'nrc': nrc,
            'name': NRC_NAMES.get(nrc, 'unknown')}
  if len(payload) == 6 and payload[0] == 0x50:
    return {'kind': 'session', 'session': payload[1]}
  if len(payload) == 2 and payload[0] == 0x68:
    return {'kind': 'communication_control', 'mode': payload[1]}
  if len(payload) >= 4 and payload[0] == 0x62:
    return {'kind': 'read_data', 'did': payload[1:3].hex(), 'data_hex': payload[3:].hex()}
  if len(payload) >= 3 and payload[:2] == b'\x59\x02' and (len(payload) - 3) % 4 == 0:
    records = [{'code_hex': payload[i:i+3].hex(), 'status': payload[i+3]}
               for i in range(3, len(payload), 4)]
    return {'kind': 'dtc_status', 'availability_mask': payload[2], 'records': records}
  return {'kind': 'unclassified'}


def summarize_rlog(events, bus):
  from opendbc.car.hyundai.spas import APRK, RESPONSE, checksum
  from tools.jetlink.spas_check import Monitor

  monitor = Monitor(bus, checksum)
  counts = Counter()
  fingerprints = set()
  firmware = {}
  replies = Counter()
  for event in events:
    if not event.valid:
      continue
    kind = event.which()
    if kind == 'carParams':
      fingerprints.add(str(event.carParams.carFingerprint))
      for record in event.carParams.carFw:
        if (str(record.ecu) == 'parkingAdas' and record.address == APRK and record.bus == bus
            and record.subAddress == 0 and record.responseAddress in (0, RESPONSE) and record.fwVersion):
          version = bytes(record.fwVersion).hex()
          requests = tuple(bytes(request).hex() for request in record.request)
          key = (record.responseAddress, requests, version)
          firmware[key] = {'response_address': record.responseAddress or None,
                           'request_hex': list(requests), 'version_hex': version}
    elif kind == 'carState':
      cs = event.carState
      if str(cs.gearShifter) == 'park' and cs.standstill and abs(cs.vEgo) < .01:
        counts['parked_car_state'] += 1
    elif kind == 'can':
      counts['can_events'] += 1
      stamp = event.logMonoTime * 1e-9
      for msg in event.can:
        if msg.src != bus:
          continue
        monitor.observe(msg.address, msg.dat, msg.src, stamp, stamp)
        if msg.address == RESPONSE:
          data = bytes(msg.dat)
          if len(data) == 8 and 2 <= data[0] <= 7:
            result = decode_reply(data[1:1+data[0]])
            label = result['kind']
            if label == 'negative':
              label = f"negative:{result['service']:02x}:{result['nrc']:02x}"
            replies[label] += 1
          else:
            replies['other_isotp_frame'] += 1
      counts['stock_ready_samples'] += monitor.ready(stamp)
      counts['neutral_samples'] += bool(monitor.neutral(stamp))
  return {'bus': bus, 'fingerprints': sorted(fingerprints),
          'counts': dict(counts), 'stock_counts': dict(monitor.counts),
          'diagnostic_frame_counts': dict(replies),
          'recorded_firmware': [firmware[key] for key in sorted(firmware)]}


def read_events(path):
  from openpilot.cereal import log
  import zstandard

  with path.open('rb') as stream:
    magic = stream.read(4)
    stream.seek(0)
    if magic == b'\x28\xb5\x2f\xfd':
      with zstandard.ZstdDecompressor().stream_reader(stream) as reader:
        data = reader.read()
    else:
      data = stream.read()
  yield from log.Event.read_multiple_bytes(data)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  source = parser.add_mutually_exclusive_group(required=True)
  source.add_argument('--rlog', type=Path, help='Local full-schema rlog, raw or Zstandard')
  source.add_argument('--reply', action='append', help='Complete hexadecimal UDS reply, repeatable')
  parser.add_argument('--bus', type=int, default=0, help='Logical bus to inspect in a recording')
  args = parser.parse_args()
  try:
    if args.rlog is not None:
      if not args.rlog.is_file():
        parser.error('--rlog requires a local file')
      result = summarize_rlog(read_events(args.rlog), args.bus)
    else:
      result = [decode_reply(bytes.fromhex(value)) for value in args.reply]
  except (OSError, ValueError) as exc:
    parser.error(str(exc))
  print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
  main()
