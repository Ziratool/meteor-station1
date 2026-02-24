[app]
title = Метеостанция
package.name = meteorstation
package.domain = org.yourname

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt,json

version = 0.1
#version.regex = __version__ = ['"](.*)['"]
version.filename = %(source.dir)s/main.py

requirements = python3,kivy,pyjnius,android

orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.1.0

fullscreen = 0

[buildozer]
log_level = 2

warn_on_root = 1

[[android]]
api = 33
minapi = 21
ndk = 25b
gradle_dependencies = 'com.android.support:support-annotations:28.0.0'

android.permissions = BLUETOOTH_SCAN, BLUETOOTH_CONNECT, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION
android.extra_permissions = android.permission.BLUETOOTH_SCAN, android.permission.BLUETOOTH_CONNECT

android.gradle_dependencies = 'com.android.support:support-annotations:28.0.0'
android.add_src =

p4a.branch = develop
