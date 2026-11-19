# HUD traffic detector

The bundled `yolo11n-road.onnx` is an off-device export of Ultralytics YOLO11n trained on COCO. It uses one 576 × 384 RGB letterbox input and returns the 80 COCO class scores with box coordinates in a `[1,84,4536]` tensor. The HUD selects pedestrians, bicycles, cars, motorcycles, buses and trucks. Cones have their own model and class map.

| Artifact | SHA-256 |
| --- | --- |
| Source `yolo11n.pt` (5,613,764 bytes) | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |
| Bundled `yolo11n-road.onnx` (5,417,439 bytes) | `5cc88f7b3208aae79af52f99da1a478a57b6c4a3294044cf39f3ed8352c65c72` |

[Official Ultralytics v8.3.0 model weights](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt) · [Ultralytics source at v8.3.2](https://github.com/ultralytics/ultralytics/tree/v8.3.2) · [AGPL-3.0 license](../../web/vendor/road-detector/ULTRALYTICS-AGPL-3.0.txt)

The export uses Ultralytics 8.3.2, PyTorch's legacy ONNX exporter at opset 17 and ONNX. Run `python export_yolo11n.py yolo11n.pt yolo11n-road.onnx` on a development computer. The graph stores constant weights in FP16 and converts them to FP32 for CPU inference. The device loads the bundled artifact with OpenCV.
