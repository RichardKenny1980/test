[app]
title = Void Siege
package.name = voidsiege
package.domain = io.github.richardkenny1980
source.dir = .
source.include_exts = py,json
version = 0.1.0
requirements = python3,pygame
orientation = landscape
fullscreen = 1
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #0c0a12
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, x86_64
android.accept_sdk_license = True
p4a.bootstrap = sdl2
# p4a's pygame recipe is 2.1.0, whose C sources only compile against Python <= 3.10;
# newer p4a releases build Python 3.11+, so pin the last release that ships 3.10.
p4a.branch = v2023.09.16
android.ndk = 25b

[buildozer]
log_level = 2
warn_on_root = 0
