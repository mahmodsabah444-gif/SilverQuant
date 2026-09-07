[app]
title = SilverQuant
package.name = silverquant
package.domain = org.quant
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 8.8
requirements = python3==3.11.9,hostpython3==3.11.9,kivy,openssl,requests
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 24
android.ndk_api = 21
android.accept_sdk_license = True

p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 1
