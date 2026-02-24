[app]
# Основные настройки приложения
title = Метеостанция
package.name = meteorstation
package.domain = org.yourname

# Где искать код
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt,json

# Версия и зависимости
version = 0.1
requirements = python3,kivy,pyjnius,android

# Настройки экрана
orientation = portrait
fullscreen = 0

[buildozer]
# Настройки сборщика
log_level = 2

[android]
# Android SDK версии
api = 33
minapi = 21
ndk = 25b
android.build_tools_version = 34.0.0

# Автоматическое принятие лицензий
android.accept_sdk_license = True

# Разрешения для Bluetooth
android.permissions = BLUETOOTH_SCAN, BLUETOOTH_CONNECT, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION
android.extra_permissions = android.permission.BLUETOOTH_SCAN, android.permission.BLUETOOTH_CONNECT

# Ветка python-for-android
p4a.branch = develop
