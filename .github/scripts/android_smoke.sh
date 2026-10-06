#!/usr/bin/env bash
# Install the APK on the running emulator, start it, tap through the menu and check Python didn't crash.
set -u
PKG=io.github.richardkenny1980.voidsiege
mkdir -p android-smoke
adb install -r void-siege.apk
adb logcat -c
adb shell am start -n "$PKG/org.kivy.android.PythonActivity"
sleep 30
adb exec-out screencap -p > android-smoke/menu.png
adb shell input tap 960 540
sleep 10
adb exec-out screencap -p > android-smoke/battle.png
adb logcat -d > android-smoke/logcat.txt
grep -E "python|Python" android-smoke/logcat.txt | tail -n 80
if grep -q "Traceback" android-smoke/logcat.txt; then
  echo "Python crashed on Android"; exit 1
fi
if ! adb shell pidof "$PKG" > /dev/null; then
  echo "The app is not running"; exit 1
fi
echo "App is running"
