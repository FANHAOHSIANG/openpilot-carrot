"""Compare pinned HCOP and HKG parameter derivation with a Carrot parked CAN summary.

Desktop only. Runs the donor's parameter derivation, not its vehicle initialization.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

SOURCES = {
  "hcop": "40181738da3f695e679eff3feef028074153e759",
  "hkg": "1c51731784729da5ebaf24b3c34106bd27aaf94b",
}
CAR = "HYUNDAI_IONIQ_5"


def checked_checkout(checkout, source):
  checkout = checkout.resolve()
  git = ["git", "-C", str(checkout)]
  revision = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
  if revision != SOURCES[source]:
    raise ValueError(f"{source} requires opendbc {SOURCES[source]}, found {revision}")
  if subprocess.check_output([*git, "status", "--porcelain"], text=True).strip():
    raise ValueError("Donor checkout must be clean")
  if not (checkout / "opendbc/car/hyundai/interface.py").is_file():
    raise ValueError("Pass the root of the donor opendbc checkout")
  return checkout


def evaluate(sample, source, checkout):
  recorded = sample["car"]
  if recorded["name"] != CAR or sample["samples"]["can_events"] <= 0:
    raise ValueError("A populated IONIQ 5 parked CAN summary is required")

  sys.path.insert(0, str(checkout))
  import opendbc
  from opendbc.car import gen_empty_fingerprint, structs
  from opendbc.car.hyundai.hyundaicanfd import CanBus
  from opendbc.car.hyundai.interface import CarInterface
  from opendbc.car.hyundai.values import HyundaiFlags

  if not Path(opendbc.__file__).resolve().is_relative_to(checkout):
    raise ValueError("opendbc was imported from outside the donor checkout")

  fingerprint = gen_empty_fingerprint()
  for bus, frames in sample["observed_ids"].items():
    index = int(bus)
    if index not in fingerprint:
      raise ValueError(f"Invalid CAN bus {index}")
    for address, length in frames:
      address = int(address, 16)
      if not 0 <= address <= 0x1fffffff or length not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64):
        raise ValueError("Invalid CAN address or length")
      fingerprint[index][address] = length

  # The observer supplies ECU types, not firmware payloads. Never invent missing entries.
  firmware = [structs.CarParams.CarFw(ecu=ecu) for ecu in recorded["ecu_types"]]
  rows = []
  for alpha in (False, True):
    cp = CarInterface.get_params(CAR, fingerprint, firmware, alpha, False, False)
    base_radar_unavailable = cp.radarUnavailable
    row = {"requested_alpha": alpha}
    if source == "hkg":
      cp_sp = CarInterface.get_params_sp(cp, CAR, fingerprint, firmware, alpha, False, False)
      row["sunnypilot"] = {"flags": int(cp_sp.flags), "safety_param": int(cp_sp.safetyParam)}
    bus = CanBus(cp)
    row.update(
      flags=[flag.name for flag in HyundaiFlags if cp.flags & flag],
      longitudinal=cp.openpilotLongitudinalControl,
      safety=[(str(config.safetyModel), config.safetyParam) for config in cp.safetyConfigs],
      buses={"acan": bus.ACAN, "ecan": bus.ECAN, "camera": bus.CAM},
      base_radar_unavailable=base_radar_unavailable,
      radar_unavailable=cp.radarUnavailable,
    )
    rows.append(row)
  return {
    "car": CAR,
    "observed_firmware_count": recorded["firmware_count"],
    "carrot_recorded": {key: recorded[key] for key in ("flags", "ext_flags", "longitudinal", "safety")},
    "donor": source,
    "opendbc_commit": SOURCES[source],
    "offline_candidates": rows,
  }


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("sample", type=Path, help="JSON from the parked observer")
  parser.add_argument("--source", required=True, choices=SOURCES)
  parser.add_argument("--opendbc", required=True, type=Path)
  args = parser.parse_args()
  if Path("/AGNOS").exists() or Path("/TICI").exists():
    parser.error("Run this comparison on a computer, not on a comma device.")
  try:
    checkout = checked_checkout(args.opendbc, args.source)
    result = evaluate(json.loads(args.sample.read_text()), args.source, checkout)
  except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
    parser.error(str(error))
  print(json.dumps(result, indent=2))


if __name__ == "__main__":
  main()
