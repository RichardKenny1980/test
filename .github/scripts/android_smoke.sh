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
sleep 5
adb exec-out screencap -p > android-smoke/levels.png
# the first level card sits at about 20% across and 42% down the level select screen
read -r W H < <(adb shell wm size | grep -oE '[0-9]+x[0-9]+' | tail -n 1 | tr 'x' ' ')
[ "$W" -lt "$H" ] && { T=$W; W=$H; H=$T; }
adb shell input tap $((W * 20 / 100)) $((H * 42 / 100))
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
