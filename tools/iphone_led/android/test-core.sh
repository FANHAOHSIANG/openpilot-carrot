#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
out="${CARROT_TEST_OUT:-$PWD/build-cli/tests}"
mkdir -p "$out"
javac -encoding UTF-8 -d "$out" app/src/main/java/tw/carrot/led/VehicleRules.java app/src/main/java/tw/carrot/led/LoyProtocol.java app/src/main/java/tw/carrot/led/DisplaySelection.java tests/CoreTests.java
java -cp "$out" tw.carrot.led.CoreTests

javac -encoding UTF-8 -d "$out" app/src/main/java/tw/carrot/led/IPixelProtocol.java tests/IPixelTests.java
java -cp "$out" tw.carrot.led.IPixelTests

javac -encoding UTF-8 -d "$out" app/src/main/java/tw/carrot/led/EyesBitmap.java tests/EyesTests.java
java -cp "$out" tw.carrot.led.EyesTests

javac -encoding UTF-8 -d "$out" app/src/main/java/tw/carrot/led/VehicleRules.java tests/VehicleRulesTests.java
java -cp "$out" tw.carrot.led.VehicleRulesTests

javac -encoding UTF-8 -d "$out" app/src/main/java/tw/carrot/led/StartupPlayback.java app/src/main/java/tw/carrot/led/IPixelProtocol.java app/src/main/java/tw/carrot/led/LoyProtocol.java tests/StartupTests.java
java -cp "$out" tw.carrot.led.StartupTests

javac -encoding UTF-8 -d "$out" app/src/main/java/tw/carrot/led/LoyProtocol.java tests/LoyAnimationTests.java
java -cp "$out" tw.carrot.led.LoyAnimationTests

javac -encoding UTF-8 -d "$out" app/src/main/java/tw/carrot/led/VehicleNotificationPolicy.java tests/VehicleNotificationTests.java
java -cp "$out" tw.carrot.led.VehicleNotificationTests

javac -encoding UTF-8 -d "$out" app/src/main/java/tw/carrot/led/LanRoute.java tests/LanRouteTests.java
java -cp "$out" tw.carrot.led.LanRouteTests
