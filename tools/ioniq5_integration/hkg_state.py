"""HKG Enhanced state machines and nominal gain table for desktop simulations.

Copyright (c) 2021-, Haibin Wen, sunnypilot, and other contributors.
Source FANHAOHSIANG/sunnypilot at 872cfd28. See LICENSE-HKG.md.
This software is licensed under a custom license requiring permission for use.
Offline inputs are explicitly supplied events, not events derived from live CAN.
"""
from types import SimpleNamespace


def names(words):
  return SimpleNamespace(**{word: word for word in words.split()})


ET = names("PERMANENT USER_DISABLE IMMEDIATE_DISABLE SOFT_DISABLE OVERRIDE_LATERAL OVERRIDE_LONGITUDINAL ENABLE NO_ENTRY PRE_ENABLE WARNING")
MadsState = names("disabled enabled paused overriding softDisabling")
AccState = names("disabled enabled preEnabled overriding softDisabling")
EventNameSP = names("silentLkasDisable")
GEARS_ALLOW_PAUSED = ("wrongGear", "reverseGear", "brakeHold", "doorOpen", "seatbeltNotLatched", "parkBrake")
GEARS_ALLOW_PAUSED_SILENT = tuple("silent" + event[0].upper() + event[1:] for event in GEARS_ALLOW_PAUSED)
MADS_ACTIVE = (MadsState.enabled, MadsState.softDisabling, MadsState.overriding)
MADS_ENABLED = (MadsState.paused, *MADS_ACTIVE)
ACC_ACTIVE = (AccState.enabled, AccState.softDisabling, AccState.overriding)
ACC_ENABLED = (AccState.preEnabled, *ACC_ACTIVE)
DT_CTRL = 0.01
SOFT_DISABLE_TIME = 3

KP = 0.8
INTERP_SPEEDS = [1, 1.5, 2.0, 3.0, 5, 7.5, 10, 15, 30]
KP_INTERP = [250, 120, 65, 30, 11.5, 5.5, 3.5, 2.0, KP]


class AccStateMachine:
  def __init__(self):
    self.current_alert_types = [ET.PERMANENT]
    self.state = AccState.disabled
    self.soft_disable_timer = 0

  def update(self, events):
    # decrement the soft disable timer at every step, as it's reset on
    # entrance in SOFT_DISABLING state
    self.soft_disable_timer = max(0, self.soft_disable_timer - 1)

    self.current_alert_types = [ET.PERMANENT]

    # ENABLED, SOFT DISABLING, PRE ENABLING, OVERRIDING
    if self.state != AccState.disabled:
      # user and immediate disable always have priority in a non-disabled state
      if events.contains(ET.IMMEDIATE_DISABLE):
        self.state = AccState.disabled
        self.current_alert_types.append(ET.IMMEDIATE_DISABLE)

      elif events.contains(ET.USER_DISABLE):
        self.state = AccState.disabled
        self.current_alert_types.append(ET.USER_DISABLE)

      else:
        # ENABLED
        if self.state == AccState.enabled:
          if events.contains(ET.SOFT_DISABLE):
            self.state = AccState.softDisabling
            self.soft_disable_timer = int(SOFT_DISABLE_TIME / DT_CTRL)
            self.current_alert_types.append(ET.SOFT_DISABLE)

          elif events.contains(ET.OVERRIDE_LATERAL) or events.contains(ET.OVERRIDE_LONGITUDINAL):
            self.state = AccState.overriding
            self.current_alert_types += [ET.OVERRIDE_LATERAL, ET.OVERRIDE_LONGITUDINAL]

        # SOFT DISABLING
        elif self.state == AccState.softDisabling:
          if not events.contains(ET.SOFT_DISABLE):
            # no more soft disabling condition, so go back to ENABLED
            self.state = AccState.enabled

          elif self.soft_disable_timer > 0:
            self.current_alert_types.append(ET.SOFT_DISABLE)

          elif self.soft_disable_timer <= 0:
            self.state = AccState.disabled

        # PRE ENABLING
        elif self.state == AccState.preEnabled:
          if not events.contains(ET.PRE_ENABLE):
            self.state = AccState.enabled
          else:
            self.current_alert_types.append(ET.PRE_ENABLE)

        # OVERRIDING
        elif self.state == AccState.overriding:
          if events.contains(ET.SOFT_DISABLE):
            self.state = AccState.softDisabling
            self.soft_disable_timer = int(SOFT_DISABLE_TIME / DT_CTRL)
            self.current_alert_types.append(ET.SOFT_DISABLE)
          elif not (events.contains(ET.OVERRIDE_LATERAL) or events.contains(ET.OVERRIDE_LONGITUDINAL)):
            self.state = AccState.enabled
          else:
            self.current_alert_types += [ET.OVERRIDE_LATERAL, ET.OVERRIDE_LONGITUDINAL]

    # DISABLED
    elif self.state == AccState.disabled:
      if events.contains(ET.ENABLE):
        if events.contains(ET.NO_ENTRY):
          self.current_alert_types.append(ET.NO_ENTRY)

        else:
          if events.contains(ET.PRE_ENABLE):
            self.state = AccState.preEnabled
          elif events.contains(ET.OVERRIDE_LATERAL) or events.contains(ET.OVERRIDE_LONGITUDINAL):
            self.state = AccState.overriding
          else:
            self.state = AccState.enabled
          self.current_alert_types.append(ET.ENABLE)

    # Check if openpilot is engaged and actuators are enabled
    enabled = self.state in ACC_ENABLED
    active = self.state in ACC_ACTIVE
    if active:
      self.current_alert_types.append(ET.WARNING)
    return enabled, active


class MadsStateMachine:
  def __init__(self, mads):
    self.selfdrive = mads.selfdrive
    self.ss_state_machine = mads.selfdrive.state_machine
    self._events = mads.selfdrive.events
    self._events_sp = mads.selfdrive.events_sp

    self.state = MadsState.disabled

  def add_current_alert_types(self, alert_type):
    if not self.selfdrive.enabled:
      self.ss_state_machine.current_alert_types.append(alert_type)

  def check_contains(self, event_type: str) -> bool:
    return bool(self._events.contains(event_type) or self._events_sp.contains(event_type))

  def check_contains_in_list(self) -> bool:
    return bool(self._events.contains_in_list(GEARS_ALLOW_PAUSED) or self._events_sp.contains_in_list(GEARS_ALLOW_PAUSED_SILENT))

  def update(self):
    # soft disable timer and current alert types are from the state machine of openpilot
    # decrement the soft disable timer at every step, as it's reset on
    # entrance in SOFT_DISABLING state

    # ENABLED, SOFT DISABLING, PAUSED, OVERRIDING
    if self.state != MadsState.disabled:
      # user and immediate disable always have priority in a non-disabled state
      if self.check_contains(ET.USER_DISABLE):
        if self._events_sp.has(EventNameSP.silentLkasDisable):
          self.state = MadsState.paused
        else:
          self.state = MadsState.disabled
        self.ss_state_machine.current_alert_types.append(ET.USER_DISABLE)

      elif self.check_contains(ET.IMMEDIATE_DISABLE):
        self.state = MadsState.disabled
        self.add_current_alert_types(ET.IMMEDIATE_DISABLE)

      else:
        # ENABLED
        if self.state == MadsState.enabled:
          if self.check_contains(ET.SOFT_DISABLE):
            self.state = MadsState.softDisabling
            if not self.selfdrive.enabled:
              self.ss_state_machine.soft_disable_timer = int(SOFT_DISABLE_TIME / DT_CTRL)
              self.ss_state_machine.current_alert_types.append(ET.SOFT_DISABLE)

          elif self.check_contains(ET.OVERRIDE_LATERAL):
            self.state = MadsState.overriding
            self.add_current_alert_types(ET.OVERRIDE_LATERAL)

        # SOFT DISABLING
        elif self.state == MadsState.softDisabling:
          if not self.check_contains(ET.SOFT_DISABLE):
            # no more soft disabling condition, so go back to ENABLED
            self.state = MadsState.enabled

          elif self.ss_state_machine.soft_disable_timer > 0:
            self.add_current_alert_types(ET.SOFT_DISABLE)

          elif self.ss_state_machine.soft_disable_timer <= 0:
            self.state = MadsState.disabled

        # PAUSED
        elif self.state == MadsState.paused:
          if self.check_contains(ET.ENABLE):
            if self.check_contains(ET.NO_ENTRY):
              self.add_current_alert_types(ET.NO_ENTRY)

            else:
              if self.check_contains(ET.OVERRIDE_LATERAL):
                self.state = MadsState.overriding
              else:
                self.state = MadsState.enabled
              self.add_current_alert_types(ET.ENABLE)

        # OVERRIDING
        elif self.state == MadsState.overriding:
          if self.check_contains(ET.SOFT_DISABLE):
            self.state = MadsState.softDisabling
            if not self.selfdrive.enabled:
              self.ss_state_machine.soft_disable_timer = int(SOFT_DISABLE_TIME / DT_CTRL)
              self.ss_state_machine.current_alert_types.append(ET.SOFT_DISABLE)
          elif not self.check_contains(ET.OVERRIDE_LATERAL):
            self.state = MadsState.enabled
          else:
            self.ss_state_machine.current_alert_types += [ET.OVERRIDE_LATERAL]

    # DISABLED
    elif self.state == MadsState.disabled:
      if self.check_contains(ET.ENABLE):
        if self.check_contains(ET.NO_ENTRY):
          if self.check_contains_in_list():
            self.state = MadsState.paused
          self.add_current_alert_types(ET.NO_ENTRY)

        else:
          if self.check_contains(ET.OVERRIDE_LATERAL):
            self.state = MadsState.overriding
          else:
            self.state = MadsState.enabled
          self.add_current_alert_types(ET.ENABLE)

    # check if MADS is engaged and actuators are enabled
    enabled = self.state in MADS_ENABLED
    active = self.state in MADS_ACTIVE
    if active:
      self.add_current_alert_types(ET.WARNING)

    return enabled, active
