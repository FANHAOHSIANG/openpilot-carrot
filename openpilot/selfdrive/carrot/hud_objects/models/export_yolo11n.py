"""Off-device exporter. Usage: python export_yolo11n.py yolo11n.pt yolo11n-road.onnx"""
import argparse
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
import torch
from ultralytics import YOLO
from ultralytics.nn.modules.head import Detect

SOURCE_SHA256 = '0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1'


def export(source, target):
  if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
    raise ValueError('Expected the Ultralytics v8.3.0 release yolo11n.pt')
  model = YOLO(str(source)).model.float().eval().fuse(verbose=False)
  for layer in model.modules():
    if isinstance(layer, Detect):
      layer.dynamic, layer.export, layer.format = False, True, 'onnx'
  image = torch.zeros((1, 3, 384, 576))
  with torch.no_grad():
    model(image)  # Initialize the static output grids before tracing.
  with TemporaryDirectory() as folder:
    original = Path(folder) / 'fp32.onnx'
    torch.onnx.export(model, image, original, opset_version=17, input_names=['images'], output_names=['output0'],
                      export_params=True, dynamic_axes=None, dynamo=False)
    graph = onnx.load(original)
  # Keep CPU activations in FP32. Only packed constant weights use FP16 storage.
  casts = []
  for index, tensor in enumerate(graph.graph.initializer):
    if tensor.data_type == TensorProto.FLOAT and len(tensor.dims):
      name = tensor.name
      tensor.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(tensor).astype(np.float16), name=name + '_fp16'))
      casts.append(helper.make_node('Cast', [tensor.name], [name], name=f'unpack_{index}', to=TensorProto.FLOAT))
  nodes = list(graph.graph.node)
  del graph.graph.node[:]
  graph.graph.node.extend([*casts, *nodes])
  onnx.checker.check_model(graph)
  onnx.save(graph, target)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('source', type=Path)
  parser.add_argument('target', type=Path)
  args = parser.parse_args()
  export(args.source, args.target)
