#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${ANDROID_SDK_ROOT:?Set ANDROID_SDK_ROOT to an Android SDK with platform 36 and build-tools 36.0.0}"
bt="$ANDROID_SDK_ROOT/build-tools/36.0.0"
platform="$ANDROID_SDK_ROOT/platforms/android-36/android.jar"
out="${CARROT_ANDROID_OUT:-$PWD/build-cli}"
mkdir -p "$out/classes"
"$bt/aapt2" compile --dir app/src/main/res -o "$out/resources.zip"
python3 - "$out/AndroidManifest.xml" <<'PYMANIFEST'
import pathlib,sys
text=pathlib.Path('app/src/main/AndroidManifest.xml').read_text()
pathlib.Path(sys.argv[1]).write_text(text.replace('<manifest ', '<manifest package="tw.carrot.led" ',1))
PYMANIFEST
"$bt/aapt2" link -o "$out/base.apk" -I "$platform" --manifest "$out/AndroidManifest.xml" --version-code 4 --version-name 0.1.3 "$out/resources.zip"
find app/src/main/java -name '*.java' -print > "$out/sources.txt"
javac -encoding UTF-8 -source 17 -target 17 -classpath "$platform" -d "$out/classes" @"$out/sources.txt"
jar cf "$out/classes.jar" -C "$out/classes" .
"$bt/d8" --lib "$platform" --min-api 26 --output "$out" "$out/classes.jar"
python3 - "$out" <<'PY'
import pathlib,sys,zipfile,shutil
p=pathlib.Path(sys.argv[1]); shutil.copyfile(p/'base.apk',p/'unsigned.apk')
with zipfile.ZipFile(p/'unsigned.apk','a',zipfile.ZIP_DEFLATED) as z:
    for dex in p.glob('classes*.dex'): z.write(dex,dex.name)
PY
"$bt/zipalign" -f 4 "$out/unsigned.apk" "$out/aligned.apk"
key="${CARROT_ANDROID_KEYSTORE:-$HOME/.android/debug.keystore}"
if [ ! -f "$key" ]; then
  mkdir -p "$(dirname "$key")"
  keytool -genkeypair -keystore "$key" -storepass android -keypass android -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=Android Debug,O=Android,C=US'
  chmod 600 "$key"
fi
"$bt/apksigner" sign --ks "$key" --ks-key-alias androiddebugkey --ks-pass pass:android --key-pass pass:android --out "$out/CarrotLED-0.1.3.apk" "$out/aligned.apk"
"$bt/apksigner" verify --verbose "$out/CarrotLED-0.1.3.apk"
echo "APK: $out/CarrotLED-0.1.3.apk"
