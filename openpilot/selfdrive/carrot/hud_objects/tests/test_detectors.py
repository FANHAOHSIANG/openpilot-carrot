import unittest

import numpy as np

from openpilot.selfdrive.carrot.hud_objects.detectors import build_detector, decode_cone_output, decode_traffic_output, separate_riders


class HudDetectorTest(unittest.TestCase):
  def setUp(self):
    self.output = np.zeros((1, 14, 8400), dtype=np.float32)
    self.transform = (1., 0, 140, 640, 360)

  def add(self, index, cls, score, box):
    self.output[0, :4, index] = box
    self.output[0, 4 + cls, index] = score

  def test_traffic_classes_from_pinned_head(self):
    for i in range(10):
      self.add(i, i, .8, [40 + i * 60, 320, 35, 60])
    detections = decode_traffic_output(self.output, self.transform)
    self.assertEqual([d[0] for d in detections], ['person', 'car', 'truck', 'bus', 'motorcycle', 'bicycle'])
    np.testing.assert_allclose(detections[0][1:], [40 / 640, 210 / 360, 35 / 640, 60 / 360, .8], rtol=1e-6)

  def test_same_channel_has_different_meaning_on_the_two_models(self):
    self.add(0, 6, .9, [320, 320, 64, 64])
    self.add(1, 7, .9, [500, 220, 30, 66])
    self.assertEqual([d[0] for d in decode_traffic_output(self.output, self.transform)], ['motorcycle', 'bicycle'])
    cone, = decode_cone_output(self.output)
    np.testing.assert_allclose(cone[1:], [.5, .55, .1, .1, .9], rtol=1e-6)
    self.assertEqual(cone[0], 'cone')
    self.output[0, 4 + 2, 0] = .95
    self.assertEqual(decode_cone_output(self.output), [cone])
    self.assertEqual(decode_traffic_output(self.output, self.transform)[0][0], 'car')

  def test_clipping_padding_and_low_score(self):
    self.add(0, 2, .9, [0, 145, 64, 40])   # intersects image left and top
    self.add(1, 3, .9, [320, 60, 100, 40])  # wholly inside letterbox padding
    self.add(2, 0, .49, [300, 250, 33, 100])
    box, = decode_traffic_output(self.output, self.transform)
    self.assertEqual(box[0], 'car')
    np.testing.assert_allclose(box[1:5], [.025, 25 / 360, .05, 25 / 360], rtol=1e-6)

  def test_one_truck_from_replay_and_independent_neighbours(self):
    # Real narrow-camera clip: at 49 s the same box truck activated the bus and
    # truck heads at IoU > .97. A nearby partially occluded car can still exist.
    for i, (cls, score, u, bottom, w, h) in enumerate([
      (4,.8098,.7592,.6575,.3085,.5074), (3,.6042,.7602,.6566,.3079,.4997),
      (2,.69,.64,.6,.15,.2), (6,.78,.77,.64,.19,.23), (0,.7,.77,.64,.18,.23),
    ]):
      self.add(i, cls, score, (640 * u, 140 + 360 * (bottom - h/2), 640*w, 360*h))
    self.assertEqual([d[0] for d in decode_traffic_output(self.output, self.transform)],
                     ['bus', 'motorcycle', 'person', 'car'])

  def test_nms_geometry_and_empty_result(self):
    self.add(0, 3, .9, [300, 300, 100, 80])
    self.add(1, 3, .8, [302, 301, 98, 80])
    self.add(2, 3, .7, [460, 300, 100, 80])
    self.add(3, 3, .9, [300, np.nan, 100, 80])
    boxes = decode_traffic_output(self.output, self.transform)
    self.assertEqual(len(boxes), 2)
    self.assertLess(boxes[0][1], boxes[1][1])
    self.assertEqual(decode_cone_output(self.output), [])

  def test_rider_uses_bike_ground_point_and_standing_pedestrian_is_preserved(self):
    bike = ['motorcycle', .50, .80, .14, .21, .82]
    rider = ['person', .50, .73, .07, .25, .93]
    walker = ['person', .625, .81, .07, .25, .91]
    self.assertEqual(separate_riders([rider, walker, bike]), [walker, bike])
    self.assertEqual(separate_riders([rider, walker]), [rider, walker])
    # Two plausible people or two plausible bikes: neither match is unique.
    second_rider = ['person', .51, .74, .05, .26, .87]
    second_bike = ['motorcycle', .515, .80, .14, .21, .76]
    for group in ([rider, second_rider, bike], [rider, bike, second_bike]):
      self.assertEqual(separate_riders(group), group)

  def test_rejects_wrong_model_contract_and_invalid_scores(self):
    with self.assertRaises(ValueError):
      decode_cone_output(self.output[:, :12])
    self.output[0, 8, 0] = 1.01
    with self.assertRaises(ValueError):
      decode_traffic_output(self.output, self.transform)
    with self.assertRaises(ValueError):
      build_detector('unconfigured')

  def test_both_bundled_models_run_single_image_cpu_inference(self):
    try:
      import cv2
    except ImportError:
      self.skipTest('OpenCV required for the bundled model smoke test')
    image = np.full((330, 526, 3), 114, dtype=np.uint8)
    for name in ('traffic', 'cone'):
      with self.subTest(name=name):
        detect = build_detector(name)
        self.assertEqual(cv2.getNumThreads(), 1)
        self.assertEqual(detect(image), [])
        with self.assertRaises(ValueError):
          detect(image[:, :, 0])
