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

[buildozer]
log_level = 2

[android]
api = 33
minapi = 21
ndk = 25b
android.build_tools_version = 34.0.0
android.accept_sdk_license = True
android.sdkmanager_accept_license = True

android.permissions = BLUETOOTH_SCAN, BLUETOOTH_CONNECT, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION
android.extra_permissions = android.permission.BLUETOOTH_SCAN, android.permission.BLUETOOTH_CONNECT

p4a.branch = develop
