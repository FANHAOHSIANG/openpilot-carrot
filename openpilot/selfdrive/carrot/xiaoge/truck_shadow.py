"""Opt-in truck shadow inference on Xiaoge Vision's existing wide-camera frames."""
import json
import threading
import time

import cv2
import openpilot.cereal.messaging as messaging
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.carrot.xiaoge.nv12 import pack_nv12
from openpilot.tools.clearance_shadow.live_observer import (
  RUN_DIR, check_model, driving_model_headroom, external_model_block, healthy, requested, status_snapshot, write_status,
)
from openpilot.tools.clearance_shadow.onnx_observer import decode_output, letterbox_rgb


def side_result(boxes, config, width, height, eligible):
  import numpy as np

  result = []
  for box in boxes:
    x1, y1, x2, y2 = box['box']
    point = ((x1 + x2) * .5 * config['width'] / width, y2 * config['height'] / height)
    sides = [side for side in eligible if len(config.get(f'poly_{side}', [])) >= 3
             and cv2.pointPolygonTest(np.asarray(config[f'poly_{side}'], dtype=np.float32), point, False) >= 0]
    result.append(dict(box, side=sides[0] if len(sides) == 1 and not box.get('edge_clipped') else 'unknown'))
  detected = {box['side'] for box in result}
  candidate = {'left': 'right', 'right': 'left'}.get(next(iter(detected))) if len(detected) == 1 else None
  return result, candidate


def offset_review(candidate, enabled, driver_override, lane_change):
  request = {'left': -0.15, 'right': 0.15}.get(candidate, 0.0)
  if not enabled:
    reason = 'disabled'
  elif driver_override:
    reason = 'driver_override'
  elif lane_change:
    reason = 'lane_change_or_signal'
  elif not request:
    reason = 'no_unambiguous_adjacent_target'
  else:
    reason = 'lane_clearance_unverified'
  return {'requested_offset_m': request, 'applied_offset_m': 0.0, 'cancel_reason': reason}


class TruckShadow:
  def __init__(self, params):
    self.params = params
    self.sm = messaging.SubMaster(['deviceState', 'modelV2', 'carState'])
    self.next_check = 0.
    self.worker = None
    self.arm = None
    self.infer = None
    self.cpu_used = 0.
    self.failed = False

  def status(self):
    return status_snapshot(armed_override=True if self.params is not None and self.params.get_bool('OnnxTruckEnabled') else None)

  def ticket(self):
    if self.params is not None and self.params.get_bool('OnnxTruckEnabled'):
      return 0, True, True
    if not requested():
      return None
    try:
      value = json.loads((RUN_DIR / 'armed.json').read_text())
      continuous = value['version'] == 2
      timestamp = value['started_monotonic_ns'] if continuous else value['expires_monotonic_ns']
      return timestamp, value.get('with_jetlink') is True, continuous
    except (OSError, ValueError, KeyError, TypeError):
      return None

  def offer(self, buffer, frame_id, eof, config, now):
    if now < self.next_check or (self.worker and self.worker.is_alive()):
      return
    self.next_check = now + .25
    ticket = self.ticket()
    if not ticket or self.params is None:
      self.infer = None
      return
    if ticket != self.arm:
      self.arm = ticket
      self.infer = None
      self.cpu_used = 0.
      self.failed = False
    if self.failed:
      return
    if not ticket[2] and self.cpu_used >= 30:
      write_status(RUN_DIR, {'state': 'cpu_budget_exhausted'})
      self.failed = True
      self.infer = None
      return

    self.sm.update(0)
    if not healthy(self.params, self.sm):
      write_status(RUN_DIR, {'state': 'waiting_for_healthy_onroad'})
      return
    model = self.sm['modelV2']
    if ticket[1] and not driving_model_headroom(model, time.monotonic_ns()):
      write_status(RUN_DIR, {'state': 'waiting_for_driving_model_headroom'})
      return
    if not 0 <= time.monotonic_ns() - eof <= 300_000_000:
      return
    if external_model_block(self.params, ticket[1]):
      write_status(RUN_DIR, {'state': 'waiting_for_driving_model'})
      return
    width, height = buffer.width, buffer.height
    frame = pack_nv12(buffer.data, width, height, buffer.stride, buffer.uv_offset).copy()
    if int(buffer.frame_id) != frame_id:
      return
    meta = model.meta
    eligible = tuple(side for side, lane_width in (('left', meta.laneWidthLeft), ('right', meta.laneWidthRight)) if lane_width >= 2.)
    self.next_check = now + 2.
    self.worker = threading.Thread(target=self.evaluate, args=(frame, width, height, eof, config, eligible, ticket), daemon=True)
    self.worker.start()

  def evaluate(self, frame, width, height, eof, config, eligible, ticket):
    cpu_start = time.thread_time()
    started = time.monotonic()
    try:
      if self.infer is None:
        self.infer = cv2.dnn.readNetFromONNX(check_model())
        self.infer.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.infer.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
      if self.ticket() != ticket or external_model_block(self.params, ticket[1]):
        return
      image, transform = letterbox_rgb(cv2.cvtColor(frame, cv2.COLOR_YUV2RGB_NV12))
      self.infer.setInput(image)
      boxes, candidate = side_result(decode_output(self.infer.forward(), transform), config, width, height, eligible)
      if self.ticket() != ticket or external_model_block(self.params, ticket[1]):
        return
      self.sm.update(0)
      if not healthy(self.params, self.sm) or (ticket[1] and not driving_model_headroom(self.sm['modelV2'], time.monotonic_ns())):
        return
      if not 0 <= time.monotonic_ns() - eof <= 1_500_000_000:
        return
      model = self.sm['modelV2']
      car = self.sm['carState']
      car_valid = self.sm.all_alive(['carState']) and self.sm.all_valid(['carState'])
      review = offset_review(candidate, self.params.get_bool('TruckClearanceShadowEnabled'),
                             car_valid and car.steeringPressed,
                             model.meta.laneChangeState != 'off' or (car_valid and (car.leftBlinker or car.rightBlinker)))
      if car_valid is False and review['cancel_reason'] == 'lane_clearance_unverified':
        review['cancel_reason'] = 'car_state_unavailable'
      record = {**review, 'state': 'observing', 'detections': boxes, 'candidate_side': candidate,
                'with_jetlink': ticket[1], 'timestamp_eof_ns': eof,
                'work_ms': (time.monotonic() - started) * 1000}
      write_status(RUN_DIR, record)
      cloudlog.event('truckShadowObservation', **record)
    except (OSError, RuntimeError, ValueError, ImportError, cv2.error) as error:
      self.failed = True
      self.infer = None
      write_status(RUN_DIR, {'state': 'error', 'error': str(error)[:200]})
    finally:
      cpu = time.thread_time() - cpu_start
      self.cpu_used += cpu
      self.next_check = max(self.next_check, time.monotonic() + 19 * cpu)

