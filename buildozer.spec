[app]
title = Метеостанция
package.name = meteorstation
package.domain = org.yourname

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt,json

version = 0.1
requirements = python3,kivy,pyjnius,android

orientation = portrait
fullscreen = 0

# Android settings
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.build_tools_version = 34.0.0

android.permissions = BLUETOOTH_SCAN, BLUETOOTH_CONNECT, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION

[buildozer]
log_level = 2
