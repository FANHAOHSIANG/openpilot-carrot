#!/usr/bin/env python3
"""Run offline navigation tests with real schemas; omit native Params/socket imports.

This does not run manager, actuators, or native messaging. CarrotServ methods are
loaded unchanged from their AST, and publication uses real Cap'n Proto messages.
"""
import ast
import collections
import datetime
import json
import math
from pathlib import Path
import sys
import time
import types

import capnp
import numpy as np
import psutil
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openpilot.common.constants import CV
from openpilot.selfdrive.carrot.gps_sources import GPSSources
from openpilot.selfdrive.carrot.carrot_navi_control import CarrotNaviControl, parse_carrot_navi_control
from openpilot.selfdrive.carrot.carrot_pre_adjust import pre_adjust_candidate, shared_pre_adjust_candidate


def main():
  log = capnp.load(str(ROOT / 'openpilot/cereal/log.capnp'), imports=[
    str(ROOT / 'openpilot/cereal'), str(ROOT / 'opendbc_repo/opendbc/car'),
  ])

  def new_message(name, valid=True):
    message = log.Event.new_message()
    message.init(name)
    message.valid = valid
    return message

  def unavailable_params(*args):
    raise RuntimeError('Tests must explicitly supply their isolated Params implementation')

  path = ROOT / 'openpilot/selfdrive/carrot/carrot_serv.py'
  tree = ast.parse(path.read_text())
  tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom, ast.If))]
  module = types.ModuleType('openpilot.selfdrive.carrot.carrot_serv')
  module.__dict__.update(dict(collections=collections, json=json, math=math, time=time, np=np, datetime=datetime.datetime,
                             CV=CV, GPSSources=GPSSources, log=log, Params=unavailable_params,
                             messaging=types.SimpleNamespace(new_message=new_message),
                             CarrotNaviControl=CarrotNaviControl,
                             parse_carrot_navi_control=parse_carrot_navi_control,
                             pre_adjust_candidate=pre_adjust_candidate,
                             shared_pre_adjust_candidate=shared_pre_adjust_candidate))
  exec(compile(tree, str(path), 'exec'), module.__dict__)
  sys.modules[module.__name__] = module
  # The sandbox may prohibit NIC enumeration. Discovery tests still exercise
  # their explicit-interface mocks and real no-interface fallback.
  psutil.net_if_addrs = lambda: {}
  tests = ROOT / 'openpilot/selfdrive/carrot/tests'
  return pytest.main(['-q', *(str(tests / name) for name in (
    'test_carrot_pre_adjust.py', 'test_carrot_shared_pre_adjust.py', 'test_carrot_navi.py',
    'test_carrot_navi_control.py', 'test_carrot_navi_serv.py',
  ))])


if __name__ == '__main__':
  raise SystemExit(main())
