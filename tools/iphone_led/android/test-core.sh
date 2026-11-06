#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
out="${CARROT_TEST_OUT:-$PWD/build-cli/tests}"
mkdir -p "$out"
javac -encoding UTF-8 -d "$out" app/src/main/java/tw/carrot/led/VehicleRules.java app/src/main/java/tw/carrot/led/LoyProtocol.java app/src/main/java/tw/carrot/led/DisplaySelection.java tests/CoreTests.java
java -cp "$out" tw.carrot.led.CoreTests
