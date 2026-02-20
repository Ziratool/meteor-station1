"""
NRF52820 Метеостанция - Приложение для работы с метеостанцией на nRF52820
Протокол: Версия 1 от 12.11.2023
Сервис UUID: 01e10001-6d6f-43e6-9ea1-c1516874a6a8
Характеристика записи: 01e10002-6d6f-43e6-9ea1-c1516874a6a8
Характеристика чтения: 01e10003-6d6f-43e6-9ea1-c1516874a6a8
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelHeader
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import StringProperty, ListProperty
from kivy.utils import platform
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
import time
from datetime import datetime
import struct

# ==================== КОНСТАНТЫ ПРОТОКОЛА ====================

# UUID сервиса и характеристик
SERVICE_UUID = "01e10001-6d6f-43e6-9ea1-c1516874a6a8"
WRITE_CHAR_UUID = "01e10002-6d6f-43e6-9ea1-c1516874a6a8"
READ_CHAR_UUID = "01e10003-6d6f-43e6-9ea1-c1516874a6a8"


# Коды функций (ЗАПРОСЫ/КОМАНДЫ)
class CMD:
    # Запросы на чтение (0x80+)
    GET_VALUE_P_T = 0x87
    GET_VALUE_H_T = 0x88
    GET_COEFF_P = 0x84
    GET_COEFF_T = 0x89
    GET_COEFF_H = 0x8A
    GET_COEFF_T1 = 0x8B
    GET_TIME_T = 0x15  # специально для периода
    GET_DATETIME = 0x90
    GET_DEVICE_ID1 = 0x91
    GET_DEVICE_ID2 = 0x92
    GET_DEVICE_INFO = 0x93
    GET_DEVICE_VERSION = 0x94
    GET_DEVICE_STATUS = 0x95
    GET_LOG_SIZE = 0xA0
    GET_LOG_PARAMS = 0xA6

    # Команды установки (0x50+)
    SET_COEFF_P = 0x54
    SET_COEFF_T = 0x57
    SET_COEFF_H = 0x58
    SET_COEFF_T1 = 0x59
    SET_TIME_T = 0x55
    SET_DATETIME = 0x60
    SET_DEVICE_INFO = 0x63
    SET_LOG_PARAMS = 0xA7

    # Команды журнала
    START_READ_LOG = 0xA1
    PAUSE_READ_LOG = 0xA2
    RESUME_READ_LOG = 0xA3
    STOP_READ_LOG = 0xA4
    RESET_LOG = 0xA5


# Коды функций (ОТВЕТЫ/УВЕДОМЛЕНИЯ)
class RSP:
    # Данные и параметры
    VALUE_P_T = 0x17
    VALUE_H_T = 0x18
    COEFF_P = 0x14
    COEFF_T = 0x19
    COEFF_H = 0x1A
    COEFF_T1 = 0x1B
    TIME_T = 0x15
    DATETIME = 0x20
    DEVICE_ID1 = 0x21
    DEVICE_ID2 = 0x22
    DEVICE_INFO = 0x23
    DEVICE_VERSION = 0x24
    DEVICE_STATUS = 0x25

    # Журнал
    LOG_SIZE = 0xB0
    LOG_RECORD1 = 0xB1
    LOG_RECORD2 = 0xB2
    LOG_RECORD3 = 0xB3
    LOG_READ_COMPLETE = 0xB5
    LOG_PARAMS = 0xB6


# ==================== ПАРСЕР ПРОТОКОЛА ====================

class MeteorStationProtocol:
    """Парсер протокола метеостанции"""

    @staticmethod
    def encode_float(value):
        """Упаковка float в 4 байта (little-endian)"""
        return struct.pack('<f', float(value))

    @staticmethod
    def decode_float(data):
        """Распаковка 4 байт в float"""
        return struct.unpack('<f', data)[0]

    @staticmethod
    def encode_uint32(value):
        """Упаковка uint32 в 4 байта"""
        return struct.pack('<I', int(value))

    @staticmethod
    def decode_uint32(data):
        """Распаковка 4 байт в uint32"""
        return struct.unpack('<I', data)[0]

    @staticmethod
    def encode_uint16(value):
        """Упаковка uint16 в 2 байта"""
        return struct.pack('<H', int(value))

    @staticmethod
    def decode_uint16(data):
        """Распаковка 2 байт в uint16"""
        return struct.unpack('<H', data)[0]

    @staticmethod
    def encode_request(cmd):
        """Формирование запроса (1 байт команды + длина 0)"""
        return bytes([cmd, 0])

    @staticmethod
    def encode_set_coeff(cmd, a, b):
        """Формирование команды установки коэффициентов"""
        data = bytes([cmd, 8])  # команда + длина 8 байт
        data += MeteorStationProtocol.encode_float(a)
        data += MeteorStationProtocol.encode_float(b)
        return data

    @staticmethod
    def encode_set_time_t(period_ms):
        """Установка периода измерений"""
        data = bytes([CMD.SET_TIME_T, 4])  # команда + длина 4 байта
        data += MeteorStationProtocol.encode_uint32(period_ms)
        return data

    @staticmethod
    def encode_set_datetime(timestamp):
        """Установка даты и времени"""
        data = bytes([CMD.SET_DATETIME, 4])
        data += MeteorStationProtocol.encode_uint32(timestamp)
        return data

    @staticmethod
    def encode_set_device_info(creation_timestamp, sn):
        """Установка серийного номера и даты производства"""
        data = bytes([CMD.SET_DEVICE_INFO, 8])
        data += MeteorStationProtocol.encode_uint32(creation_timestamp)
        data += MeteorStationProtocol.encode_uint32(sn)
        return data

    @staticmethod
    def parse_response(data):
        """Парсинг ответа от устройства"""
        if len(data) < 2:
            return None

        cmd = data[0]  # команда
        length = data[1]  # длина данных

        if len(data) < 2 + length:
            return None

        payload = data[2:2 + length]
        result = {'cmd': cmd, 'length': length}

        try:
            if cmd == RSP.VALUE_P_T and length >= 8:
                result['type'] = 'pressure_temperature'
                result['pressure'] = MeteorStationProtocol.decode_float(payload[0:4])
                result['temperature'] = MeteorStationProtocol.decode_float(payload[4:8])

            elif cmd == RSP.VALUE_H_T and length >= 8:
                result['type'] = 'humidity_temperature'
                result['humidity'] = MeteorStationProtocol.decode_float(payload[0:4])
                result['temperature'] = MeteorStationProtocol.decode_float(payload[4:8])

            elif cmd in [RSP.COEFF_P, RSP.COEFF_T, RSP.COEFF_H, RSP.COEFF_T1] and length >= 8:
                channel = {RSP.COEFF_P: 'P', RSP.COEFF_T: 'T',
                           RSP.COEFF_H: 'H', RSP.COEFF_T1: 'T1'}[cmd]
                result['type'] = f'coeff_{channel}'
                result['A'] = MeteorStationProtocol.decode_float(payload[0:4])
                result['B'] = MeteorStationProtocol.decode_float(payload[4:8])

            elif cmd == RSP.TIME_T and length >= 4:
                result['type'] = 'measurement_period'
                result['period_ms'] = MeteorStationProtocol.decode_uint32(payload[0:4])

            elif cmd == RSP.DATETIME and length >= 4:
                timestamp = MeteorStationProtocol.decode_uint32(payload[0:4])
                result['type'] = 'datetime'
                result['timestamp'] = timestamp
                result['datetime'] = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M:%S')

            elif cmd == RSP.DEVICE_ID1 and length >= 8:
                result['type'] = 'device_id1'
                result['id_bytes'] = payload[0:8].hex()
                result['id'] = int.from_bytes(payload[0:8], 'little')

            elif cmd == RSP.DEVICE_ID2 and length >= 8:
                result['type'] = 'device_id2'
                result['id_bytes'] = payload[0:8].hex()
                result['id'] = int.from_bytes(payload[0:8], 'little')

            elif cmd == RSP.DEVICE_INFO and length >= 8:
                creation = MeteorStationProtocol.decode_uint32(payload[0:4])
                sn = MeteorStationProtocol.decode_uint32(payload[4:8])
                result['type'] = 'device_info'
                result['creation_date'] = datetime.fromtimestamp(creation).strftime('%d.%m.%Y')
                result['serial_number'] = sn

            elif cmd == RSP.DEVICE_VERSION and length >= 4:
                version = MeteorStationProtocol.decode_uint32(payload[0:4])
                result['type'] = 'firmware_version'
                result[
                    'version'] = f"v{(version >> 24) & 0xFF}.{(version >> 16) & 0xFF}.{(version >> 8) & 0xFF}.{version & 0xFF}"
                result['version_raw'] = version

            elif cmd == RSP.LOG_SIZE and length >= 4:
                result['type'] = 'log_size'
                result['log_size'] = MeteorStationProtocol.decode_uint32(payload[0:4])

            elif cmd == RSP.LOG_RECORD1 and length >= 10:
                result['type'] = 'log_record1'
                result['record_number'] = MeteorStationProtocol.decode_uint16(payload[0:2])
                result['timestamp'] = MeteorStationProtocol.decode_uint32(payload[2:6])
                result['datetime'] = datetime.fromtimestamp(result['timestamp']).strftime('%d.%m.%Y %H:%M:%S')
                result['pressure'] = MeteorStationProtocol.decode_float(payload[6:10])

            elif cmd == RSP.LOG_RECORD2 and length >= 10:
                result['type'] = 'log_record2'
                result['record_number'] = MeteorStationProtocol.decode_uint16(payload[0:2])
                result['temperature'] = MeteorStationProtocol.decode_float(payload[2:6])
                result['humidity'] = MeteorStationProtocol.decode_float(payload[6:10])

            elif cmd == RSP.LOG_RECORD3 and length >= 6:
                result['type'] = 'log_record3'
                result['record_number'] = MeteorStationProtocol.decode_uint16(payload[0:2])
                result['temperature_ext'] = MeteorStationProtocol.decode_float(payload[2:6])

            elif cmd == RSP.LOG_READ_COMPLETE:
                result['type'] = 'log_complete'

        except Exception as e:
            print(f"Parse error: {e}")
            result['error'] = str(e)

        return result


# ==================== BLE МЕНЕДЖЕР ДЛЯ МЕТЕОСТАНЦИИ ====================

class MeteorStationBLE:
    """Специализированный BLE менеджер для метеостанции"""

    def __init__(self):
        self.device = None
        self.connected = False
        self.write_char = None
        self.read_char = None
        self.data_callback = None
        self.connection_callback = None
        self.notification_callback = None

        if platform == 'android':
            self._init_android_ble()

    def _init_android_ble(self):
        """Инициализация BLE на Android"""
        try:
            from jnius import autoclass, cast, PythonJavaClass, java_method

            self.BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            self.BluetoothManager = autoclass('android.bluetooth.BluetoothManager')
            self.BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
            self.BluetoothGatt = autoclass('android.bluetooth.BluetoothGatt')
            self.BluetoothGattCharacteristic = autoclass('android.bluetooth.BluetoothGattCharacteristic')
            self.BluetoothGattDescriptor = autoclass('android.bluetooth.BluetoothGattDescriptor')
            self.BluetoothProfile = autoclass('android.bluetooth.BluetoothProfile')
            self.BluetoothGattService = autoclass('android.bluetooth.BluetoothGattService')

            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            self.bluetooth_manager = activity.getSystemService(
                autoclass('android.content.Context').BLUETOOTH_SERVICE
            )
            self.bluetooth_manager = cast('android.bluetooth.BluetoothManager',
                                          self.bluetooth_manager)
            self.bluetooth_adapter = self.bluetooth_manager.getAdapter()

        except Exception as e:
            print(f"BLE init error: {e}")

    def scan(self, duration=5, callback=None):
        """Сканирование устройств метеостанции"""
        self.scan_callback = callback

        if platform == 'android':
            try:
                from jnius import PythonJavaClass, java_method

                class ScanCallback(PythonJavaClass):
                    __javainterfaces__ = ['android/bluetooth/le/ScanCallback']

                    def __init__(self, ble):
                        super().__init__()
                        self.ble = ble
                        self.devices = {}

                    @java_method('(ILandroid/bluetooth/le/ScanResult;)V')
                    def onScanResult(self, callbackType, result):
                        device = result.getDevice()
                        name = device.getName()
                        address = device.getAddress()

                        # Проверяем, есть ли наш сервис
                        scan_record = result.getScanRecord()
                        if scan_record:
                            uuids = scan_record.getServiceUuids()
                            if uuids:
                                for uuid in uuids.toArray():
                                    if str(uuid).upper() == SERVICE_UUID.upper():
                                        device_info = {
                                            'name': name if name else 'Метеостанция',
                                            'address': address,
                                            'rssi': result.getRssi(),
                                            'device': device
                                        }
                                        self.devices[address] = device_info

                                        if self.ble.scan_callback:
                                            Clock.schedule_once(
                                                lambda dt, d=list(self.devices.values()):
                                                self.ble.scan_callback(d), 0
                                            )
                                        break

                scanner = self.bluetooth_adapter.getBluetoothLeScanner()
                self.scan_callback_obj = ScanCallback(self)
                scanner.startScan(self.scan_callback_obj)

                def stop_scan(dt):
                    try:
                        scanner.stopScan(self.scan_callback_obj)
                    except:
                        pass

                Clock.schedule_once(stop_scan, duration)

            except Exception as e:
                print(f"Scan error: {e}")

    def connect(self, device_info, callback=None):
        """Подключение к метеостанции"""
        self.connection_callback = callback

        try:
            device = device_info['device']

            if platform == 'android':
                from jnius import PythonJavaClass, java_method

                class GattCallback(PythonJavaClass):
                    __javainterfaces__ = ['android/bluetooth/BluetoothGattCallback']

                    def __init__(self, ble):
                        super().__init__()
                        self.ble = ble

                    @java_method('(Landroid/bluetooth/BluetoothGatt;II)V')
                    def onConnectionStateChange(self, gatt, status, newState):
                        if newState == self.ble.BluetoothProfile.STATE_CONNECTED:
                            self.ble.connected = True
                            self.ble.device = gatt
                            gatt.discoverServices()
                        elif newState == self.ble.BluetoothProfile.STATE_DISCONNECTED:
                            self.ble.connected = False
                            self.ble.device = None
                            self.ble.write_char = None
                            self.ble.read_char = None
                            if self.ble.connection_callback:
                                Clock.schedule_once(
                                    lambda dt: self.ble.connection_callback(False), 0
                                )

                    @java_method('(Landroid/bluetooth/BluetoothGatt;I)V')
                    def onServicesDiscovered(self, gatt, status):
                        if status == self.ble.BluetoothGatt.GATT_SUCCESS:
                            # Ищем наш сервис и характеристики
                            service = gatt.getService(
                                autoclass('java.util.UUID').fromString(SERVICE_UUID)
                            )
                            if service:
                                self.ble.write_char = service.getCharacteristic(
                                    autoclass('java.util.UUID').fromString(WRITE_CHAR_UUID)
                                )
                                self.ble.read_char = service.getCharacteristic(
                                    autoclass('java.util.UUID').fromString(READ_CHAR_UUID)
                                )

                                if self.ble.read_char:
                                    # Включаем нотификации
                                    gatt.setCharacteristicNotification(self.ble.read_char, True)

                                    # Настраиваем CCCD
                                    descriptor = self.ble.read_char.getDescriptor(
                                        autoclass('java.util.UUID')
                                        .fromString("00002902-0000-1000-8000-00805F9B34FB")
                                    )
                                    if descriptor:
                                        descriptor.setValue(
                                            self.ble.BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                                        )
                                        gatt.writeDescriptor(descriptor)

                            if self.ble.connection_callback:
                                Clock.schedule_once(
                                    lambda dt: self.ble.connection_callback(True), 0
                                )

                    @java_method(
                        '(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;[B)V')
                    def onCharacteristicChanged(self, gatt, characteristic, value):
                        if self.ble.data_callback:
                            data = bytes(value)
                            parsed = MeteorStationProtocol.parse_response(data)
                            if parsed:
                                Clock.schedule_once(
                                    lambda dt, p=parsed: self.ble.data_callback(p), 0
                                )

                self.gatt_callback = GattCallback(self)
                device.connectGatt(
                    autoclass('org.kivy.android.PythonActivity').mActivity,
                    False,
                    self.gatt_callback,
                    self.BluetoothDevice.TRANSPORT_LE
                )
                return True

        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def send_command(self, data):
        """Отправка команды на устройство"""
        if not self.connected or not self.device or not self.write_char:
            return False

        try:
            if isinstance(data, bytes):
                payload = data
            else:
                payload = bytes(data)

            self.write_char.setValue(payload)
            self.device.writeCharacteristic(self.write_char)
            return True
        except Exception as e:
            print(f"Send error: {e}")
            return False

    def disconnect(self):
        """Отключение"""
        if self.device:
            try:
                self.device.disconnect()
                self.device.close()
            except:
                pass
            self.device = None
            self.connected = False
            self.write_char = None
            self.read_char = None
            return True
        return False


# ==================== ГЛАВНОЕ ПРИЛОЖЕНИЕ ====================

class MeteorStationApp(App):
    """Приложение для работы с метеостанцией на nRF52820"""

    # Состояние подключения
    connection_status = StringProperty("Отключено")
    device_name = StringProperty("Метеостанция")
    device_address = StringProperty("")

    # Данные с устройства
    pressure = StringProperty("---")
    temperature = StringProperty("---")
    humidity = StringProperty("---")
    temperature_ext = StringProperty("---")

    # Параметры
    measurement_period = StringProperty("---")
    device_time = StringProperty("---")
    firmware_version = StringProperty("---")
    serial_number = StringProperty("---")

    # Коэффициенты
    coeff_p_a = StringProperty("---")
    coeff_p_b = StringProperty("---")
    coeff_t_a = StringProperty("---")
    coeff_t_b = StringProperty("---")
    coeff_h_a = StringProperty("---")
    coeff_h_b = StringProperty("---")
    coeff_t1_a = StringProperty("---")
    coeff_t1_b = StringProperty("---")

    # Журнал
    log_records = ListProperty([])
    log_size = StringProperty("0")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ble = MeteorStationBLE()
        self.ble.data_callback = self.on_data_received
        self.auto_update = False
        self.log_reading = False

    def build(self):
        """Создание интерфейса"""
        Window.clearcolor = (0.95, 0.9, 0.98, 1)

        main_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        # Верхняя панель с подключением
        main_layout.add_widget(self.create_connection_panel())

        # Tab панель
        tabs = TabbedPanel(
            do_default_tab=False,
            tab_width=dp(120),
            background_color=(0.9, 0.8, 0.98, 1)
        )

        # Вкладка "Текущие данные"
        data_tab = TabbedPanelHeader(text='📊 Текущие данные')
        data_tab.content = self.create_data_tab()
        tabs.add_widget(data_tab)

        # Вкладка "Калибровка"
        coeff_tab = TabbedPanelHeader(text='⚙️ Калибровка')
        coeff_tab.content = self.create_coeff_tab()
        tabs.add_widget(coeff_tab)

        # Вкладка "Настройки"
        settings_tab = TabbedPanelHeader(text='🔧 Настройки')
        settings_tab.content = self.create_settings_tab()
        tabs.add_widget(settings_tab)

        # Вкладка "Журнал"
        log_tab = TabbedPanelHeader(text='📋 Журнал')
        log_tab.content = self.create_log_tab()
        tabs.add_widget(log_tab)

        # Вкладка "Информация"
        info_tab = TabbedPanelHeader(text='ℹ️ Информация')
        info_tab.content = self.create_info_tab()
        tabs.add_widget(info_tab)

        main_layout.add_widget(tabs)

        return main_layout

    def create_connection_panel(self):
        """Панель подключения"""
        panel = BoxLayout(size_hint=(1, 0.1), spacing=dp(10))

        with panel.canvas.before:
            from kivy.graphics import Color, Rectangle
            panel.rect = Rectangle(pos=panel.pos, size=panel.size)
            panel.bind(pos=self._update_rect, size=self._update_rect)

        # Статус
        status_layout = BoxLayout(orientation='vertical', size_hint=(0.5, 1))
        status_layout.add_widget(Label(
            text=f'Статус: {self.connection_status}',
            font_size='14sp',
            halign='left',
            color=(0.2, 0.6, 0.9, 1) if 'Подключено' in self.connection_status else (1, 0.3, 0.3, 1)
        ))
        status_layout.add_widget(Label(
            text=f'Устройство: {self.device_name}',
            font_size='12sp',
            halign='left'
        ))

        # Кнопки
        btn_layout = BoxLayout(size_hint=(0.5, 1), spacing=dp(5))

        self.scan_btn = Button(
            text='🔍 Сканировать',
            background_color=(0.2, 0.6, 0.9, 1),
            on_press=self.scan_devices
        )

        self.connect_btn = Button(
            text='🔗 Подключиться',
            background_color=(0.3, 0.8, 0.3, 1),
            disabled=True,
            on_press=self.toggle_connection
        )

        btn_layout.add_widget(self.scan_btn)
        btn_layout.add_widget(self.connect_btn)

        panel.add_widget(status_layout)
        panel.add_widget(btn_layout)

        return panel

    def _update_rect(self, instance, value):
        instance.rect.pos = instance.pos
        instance.rect.size = instance.size

    def create_data_tab(self):
        """Вкладка с текущими данными"""
        layout = GridLayout(cols=2, spacing=dp(20), padding=dp(20), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        # Давление
        layout.add_widget(Label(text='📊 Давление:', font_size='15sp', bold=True))
        pressure_box = BoxLayout(orientation='vertical')
        pressure_box.add_widget(Label(
            text=self.pressure,
            font_size='24sp',
            color=(0, 0.5, 0.8, 1)
        ))
        pressure_box.add_widget(Label(text='кПа', font_size='12sp'))
        layout.add_widget(pressure_box)

        # Температура основная
        layout.add_widget(Label(text='🌡️ Температура:', font_size='15sp', bold=True))
        temp_box = BoxLayout(orientation='vertical')
        temp_box.add_widget(Label(
            text=self.temperature,
            font_size='20sp',
            color=(0.8, 0.4, 0, 1)
        ))
        temp_box.add_widget(Label(text='°C', font_size='12sp'))
        layout.add_widget(temp_box)

        # Влажность
        layout.add_widget(Label(text='💧 Влажность:', font_size='16sp', bold=True))
        hum_box = BoxLayout(orientation='vertical')
        hum_box.add_widget(Label(
            text=self.humidity,
            font_size='24sp',
            color=(0, 0.6, 0.3, 1)
        ))
        hum_box.add_widget(Label(text='%', font_size='12sp'))
        layout.add_widget(hum_box)

        # Внешняя температура
        layout.add_widget(Label(text='🌡️ Внешняя T:', font_size='16sp', bold=True))
        t1_box = BoxLayout(orientation='vertical')
        t1_box.add_widget(Label(
            text=self.temperature_ext,
            font_size='24sp',
            color=(0.8, 0.2, 0.2, 1)
        ))
        t1_box.add_widget(Label(text='°C', font_size='12sp'))
        layout.add_widget(t1_box)

        # Кнопки обновления
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(30))
        btn_layout.add_widget(Button(
            text='🔄 Обновить\n давление/температуру',
            halign='center',
            valign='middle',
            font_size='15sp',
            on_press=lambda x: self.send_command(CMD.GET_VALUE_P_T)
        ))
        btn_layout.add_widget(Button(
            text='🔄 Обновить влажность',
            on_press=lambda x: self.send_command(CMD.GET_VALUE_H_T)
        ))
        layout.add_widget(btn_layout)

        scroll = ScrollView()
        scroll.add_widget(layout)
        return scroll

    def create_coeff_tab(self):
        """Вкладка калибровочных коэффициентов"""
        layout = GridLayout(cols=2, spacing=dp(15), padding=dp(20), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        # Канал давления
        layout.add_widget(Label(text='Канал P (давление):', font_size='14sp', bold=True))
        layout.add_widget(Label(text=''))  # пустой

        layout.add_widget(Label(text='Коэф. A:'))
        coeff_p_layout1 = BoxLayout()
        self.coeff_p_a_input = TextInput(text=self.coeff_p_a, multiline=False, size_hint=(0.6, 1))
        coeff_p_layout1.add_widget(self.coeff_p_a_input)
        coeff_p_layout1.add_widget(Label(text=self.coeff_p_a, size_hint=(0.4, 1)))
        layout.add_widget(coeff_p_layout1)

        layout.add_widget(Label(text='Коэф. B:'))
        coeff_p_layout2 = BoxLayout()
        self.coeff_p_b_input = TextInput(text=self.coeff_p_b, multiline=False, size_hint=(0.6, 1))
        coeff_p_layout2.add_widget(self.coeff_p_b_input)
        coeff_p_layout2.add_widget(Label(text=self.coeff_p_b, size_hint=(0.4, 1)))
        layout.add_widget(coeff_p_layout2)

        # Кнопки для P
        btn_p_layout = BoxLayout()
        btn_p_layout.add_widget(Button(
            text='📥 Прочитать',
            on_press=lambda x: self.send_command(CMD.GET_COEFF_P)
        ))
        btn_p_layout.add_widget(Button(
            text='📤 Записать',
            on_press=self.set_coeff_p
        ))
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_p_layout)

        # Канал температуры
        layout.add_widget(Label(text='Канал T (температура):', font_size='14sp', bold=True))
        layout.add_widget(Label(text=''))

        layout.add_widget(Label(text='Коэф. A:'))
        coeff_t_layout1 = BoxLayout()
        self.coeff_t_a_input = TextInput(text=self.coeff_t_a, multiline=False, size_hint=(0.6, 1))
        coeff_t_layout1.add_widget(self.coeff_t_a_input)
        coeff_t_layout1.add_widget(Label(text=self.coeff_t_a, size_hint=(0.4, 1)))
        layout.add_widget(coeff_t_layout1)

        layout.add_widget(Label(text='Коэф. B:'))
        coeff_t_layout2 = BoxLayout()
        self.coeff_t_b_input = TextInput(text=self.coeff_t_b, multiline=False, size_hint=(0.6, 1))
        coeff_t_layout2.add_widget(self.coeff_t_b_input)
        coeff_t_layout2.add_widget(Label(text=self.coeff_t_b, size_hint=(0.4, 1)))
        layout.add_widget(coeff_t_layout2)

        btn_t_layout = BoxLayout()
        btn_t_layout.add_widget(Button(
            text='📥 Прочитать',
            on_press=lambda x: self.send_command(CMD.GET_COEFF_T)
        ))
        btn_t_layout.add_widget(Button(
            text='📤 Записать',
            on_press=self.set_coeff_t
        ))
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_t_layout)

        # Канал влажности
        layout.add_widget(Label(text='Канал H (влажность):', font_size='14sp', bold=True))
        layout.add_widget(Label(text=''))

        layout.add_widget(Label(text='Коэф. A:'))
        coeff_h_layout1 = BoxLayout()
        self.coeff_h_a_input = TextInput(text=self.coeff_h_a, multiline=False, size_hint=(0.6, 1))
        coeff_h_layout1.add_widget(self.coeff_h_a_input)
        coeff_h_layout1.add_widget(Label(text=self.coeff_h_a, size_hint=(0.4, 1)))
        layout.add_widget(coeff_h_layout1)

        layout.add_widget(Label(text='Коэф. B:'))
        coeff_h_layout2 = BoxLayout()
        self.coeff_h_b_input = TextInput(text=self.coeff_h_b, multiline=False, size_hint=(0.6, 1))
        coeff_h_layout2.add_widget(self.coeff_h_b_input)
        coeff_h_layout2.add_widget(Label(text=self.coeff_h_b, size_hint=(0.4, 1)))
        layout.add_widget(coeff_h_layout2)

        btn_h_layout = BoxLayout()
        btn_h_layout.add_widget(Button(
            text='📥 Прочитать',
            on_press=lambda x: self.send_command(CMD.GET_COEFF_H)
        ))
        btn_h_layout.add_widget(Button(
            text='📤 Записать',
            on_press=self.set_coeff_h
        ))
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_h_layout)

        scroll = ScrollView()
        scroll.add_widget(layout)
        return scroll

    def create_settings_tab(self):
        """Вкладка настроек"""
        layout = GridLayout(cols=2, spacing=dp(15), padding=dp(20), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        # Период измерений
        layout.add_widget(Label(text='⏱️ Период измерений:', font_size='14sp', bold=True))
        layout.add_widget(Label(text=''))

        layout.add_widget(Label(text='Текущий:'))
        layout.add_widget(Label(text=self.measurement_period))

        layout.add_widget(Label(text='Установить (мс):'))
        period_layout = BoxLayout()
        self.period_input = TextInput(text='1000', multiline=False, size_hint=(0.6, 1))
        period_layout.add_widget(self.period_input)
        period_layout.add_widget(Button(
            text='Установить',
            on_press=self.set_measurement_period
        ))
        layout.add_widget(period_layout)

        layout.add_widget(Button(
            text='📥 Прочитать период',
            on_press=lambda x: self.send_command(CMD.GET_TIME_T)
        ))
        layout.add_widget(Label(text=''))

        # Дата и время
        layout.add_widget(Label(text='📅 Дата и время:', font_size='14sp', bold=True))
        layout.add_widget(Label(text=''))

        layout.add_widget(Label(text='На устройстве:'))
        layout.add_widget(Label(text=self.device_time))

        layout.add_widget(Label(text='Синхронизация:'))
        sync_layout = BoxLayout()
        sync_layout.add_widget(Button(
            text='📥 Прочитать',
            on_press=lambda x: self.send_command(CMD.GET_DATETIME)
        ))
        sync_layout.add_widget(Button(
            text='🔄 Установить текущее',
            on_press=self.sync_datetime
        ))
        layout.add_widget(sync_layout)

        scroll = ScrollView()
        scroll.add_widget(layout)
        return scroll

    def create_log_tab(self):
        """Вкладка журнала измерений"""
        layout = BoxLayout(orientation='vertical', spacing=dp(10))

        # Панель управления журналом
        control_panel = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        control_panel.add_widget(Button(
            text='📊 Размер журнала',
            on_press=lambda x: self.send_command(CMD.GET_LOG_SIZE)
        ))
        control_panel.add_widget(Button(
            text='▶️ Читать журнал',
            on_press=self.start_read_log
        ))
        control_panel.add_widget(Button(
            text='⏸️ Пауза',
            on_press=lambda x: self.send_command(CMD.PAUSE_READ_LOG)
        ))
        control_panel.add_widget(Button(
            text='⏹️ Стоп',
            on_press=lambda x: self.send_command(CMD.STOP_READ_LOG)
        ))
        layout.add_widget(control_panel)

        # Информация о журнале
        info_panel = BoxLayout(size_hint_y=None, height=dp(30))
        info_panel.add_widget(Label(text=f'Записей: {self.log_size}'))
        layout.add_widget(info_panel)

        # Список записей
        self.log_list = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.log_list.bind(minimum_height=self.log_list.setter('height'))

        scroll = ScrollView()
        scroll.add_widget(self.log_list)
        layout.add_widget(scroll)

        return layout

    def create_info_tab(self):
        """Вкладка информации об устройстве"""
        layout = GridLayout(cols=2, spacing=dp(15), padding=dp(20), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        layout.add_widget(Label(text='🆔 Версия прошивки:', font_size='14sp', bold=True))
        layout.add_widget(Label(text=self.firmware_version))

        layout.add_widget(Label(text='🔢 Серийный номер:', font_size='14sp', bold=True))
        layout.add_widget(Label(text=self.serial_number))

        layout.add_widget(Label(text='📅 Дата производства:'))
        layout.add_widget(Label(text='---'))

        layout.add_widget(Button(
            text='📥 Прочитать информацию',
            on_press=lambda x: self.send_command(CMD.GET_DEVICE_INFO)
        ))
        layout.add_widget(Button(
            text='📥 Версия',
            on_press=lambda x: self.send_command(CMD.GET_DEVICE_VERSION)
        ))

        scroll = ScrollView()
        scroll.add_widget(layout)
        return scroll

    def scan_devices(self, instance):
        """Сканирование устройств"""
        self.scan_btn.text = '🔍 Сканирование...'
        self.scan_btn.disabled = True

        self.ble.scan(duration=5, callback=self.on_devices_found)

    def on_devices_found(self, devices):
        """Обработка найденных устройств"""
        self.scan_btn.text = '🔍 Сканировать'
        self.scan_btn.disabled = False

        if not devices:
            self.show_popup('Устройства не найдены',
                            'Метеостанция не обнаружена.\n'
                            'Проверьте:\n'
                            '• Bluetooth включен\n'
                            '• Устройство включено\n'
                            '• Рядом с телефоном')
            return

        # Показываем список устройств
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))

        for device in devices:
            btn = Button(
                text=f"{device['name']}\n{device['address']} (RSSI: {device['rssi']}dBm)",
                size_hint_y=None,
                height=dp(60),
                background_normal='',
                background_color=(0.2, 0.6, 0.9, 0.8)
            )
            btn.bind(on_press=lambda x, d=device: self.select_device(d))
            content.add_widget(btn)

        scroll = ScrollView(size_hint=(1, 0.8))
        scroll.add_widget(content)

        popup = Popup(
            title='Выберите метеостанцию',
            content=scroll,
            size_hint=(0.9, 0.8)
        )
        popup.open()
        self.device_popup = popup

    def select_device(self, device):
        """Выбор устройства"""
        self.selected_device = device
        self.device_name = device['name']
        self.device_address = device['address']
        self.connect_btn.disabled = False

        if hasattr(self, 'device_popup'):
            self.device_popup.dismiss()

        self.show_message(f'Выбрано: {device["name"]}')

    def toggle_connection(self, instance):
        """Подключение/отключение"""
        if not self.ble.connected:
            self.connect_btn.text = '⏳ Подключение...'
            self.connect_btn.disabled = True

            def connected(success):
                if success:
                    self.connection_status = "Подключено"
                    self.connect_btn.text = '❌ Отключиться'
                    self.connect_btn.disabled = False
                    self.scan_btn.disabled = True

                    # Автоматически запрашиваем данные
                    self.send_command(CMD.GET_DEVICE_VERSION)
                    self.send_command(CMD.GET_DEVICE_INFO)
                    self.send_command(CMD.GET_TIME_T)
                    self.send_command(CMD.GET_VALUE_P_T)
                    self.send_command(CMD.GET_VALUE_H_T)
                else:
                    self.connection_status = "Ошибка подключения"
                    self.connect_btn.text = '🔗 Подключиться'
                    self.connect_btn.disabled = False
                    self.show_popup('Ошибка', 'Не удалось подключиться к устройству')

            self.ble.connect(self.selected_device, callback=connected)
        else:
            self.ble.disconnect()
            self.connection_status = "Отключено"
            self.connect_btn.text = '🔗 Подключиться'
            self.scan_btn.disabled = False

    def send_command(self, cmd):
        """Отправка команды на устройство"""
        if self.ble.connected:
            data = MeteorStationProtocol.encode_request(cmd)
            return self.ble.send_command(data)
        return False

    def set_coeff_p(self, instance):
        """Установка коэффициентов канала P"""
        try:
            a = float(self.coeff_p_a_input.text)
            b = float(self.coeff_p_b_input.text)
            data = MeteorStationProtocol.encode_set_coeff(CMD.SET_COEFF_P, a, b)
            self.ble.send_command(data)
            self.show_message('Коэффициенты P отправлены')
        except ValueError:
            self.show_popup('Ошибка', 'Введите корректные числа')

    def set_coeff_t(self, instance):
        """Установка коэффициентов канала T"""
        try:
            a = float(self.coeff_t_a_input.text)
            b = float(self.coeff_t_b_input.text)
            data = MeteorStationProtocol.encode_set_coeff(CMD.SET_COEFF_T, a, b)
            self.ble.send_command(data)
            self.show_message('Коэффициенты T отправлены')
        except ValueError:
            self.show_popup('Ошибка', 'Введите корректные числа')

    def set_coeff_h(self, instance):
        """Установка коэффициентов канала H"""
        try:
            a = float(self.coeff_h_a_input.text)
            b = float(self.coeff_h_b_input.text)
            data = MeteorStationProtocol.encode_set_coeff(CMD.SET_COEFF_H, a, b)
            self.ble.send_command(data)
            self.show_message('Коэффициенты H отправлены')
        except ValueError:
            self.show_popup('Ошибка', 'Введите корректные числа')

    def set_measurement_period(self, instance):
        """Установка периода измерений"""
        try:
            period = int(self.period_input.text)
            data = MeteorStationProtocol.encode_set_time_t(period)
            self.ble.send_command(data)
            self.show_message(f'Период установлен: {period} мс')
        except ValueError:
            self.show_popup('Ошибка', 'Введите целое число')

    def sync_datetime(self, instance):
        """Синхронизация времени"""
        timestamp = int(time.time())
        data = MeteorStationProtocol.encode_set_datetime(timestamp)
        self.ble.send_command(data)
        self.show_message('Время синхронизировано')

    def start_read_log(self, instance):
        """Начать чтение журнала"""
        self.log_records = []
        self.log_list.clear_widgets()
        self.send_command(CMD.START_READ_LOG)
        self.log_reading = True
        self.show_message('Чтение журнала...')

    def on_data_received(self, data):
        """Обработка полученных данных"""
        if 'type' not in data:
            return

        # Обновляем интерфейс в зависимости от типа данных
        if data['type'] == 'pressure_temperature':
            self.pressure = f"{data['pressure']:.2f}"
            self.temperature = f"{data['temperature']:.1f}"

        elif data['type'] == 'humidity_temperature':
            self.humidity = f"{data['humidity']:.1f}"
            self.temperature_ext = f"{data['temperature']:.1f}"

        elif data['type'] == 'coeff_P':
            self.coeff_p_a = f"{data['A']:.6f}"
            self.coeff_p_b = f"{data['B']:.6f}"

        elif data['type'] == 'coeff_T':
            self.coeff_t_a = f"{data['A']:.6f}"
            self.coeff_t_b = f"{data['B']:.6f}"

        elif data['type'] == 'coeff_H':
            self.coeff_h_a = f"{data['A']:.6f}"
            self.coeff_h_b = f"{data['B']:.6f}"

        elif data['type'] == 'measurement_period':
            self.measurement_period = f"{data['period_ms']} мс"

        elif data['type'] == 'datetime':
            self.device_time = data['datetime']

        elif data['type'] == 'firmware_version':
            self.firmware_version = data['version']

        elif data['type'] == 'device_info':
            self.serial_number = str(data['serial_number'])

        elif data['type'] == 'log_size':
            self.log_size = str(data['log_size'])

        elif data['type'] in ['log_record1', 'log_record2', 'log_record3']:
            self.add_log_record(data)

        elif data['type'] == 'log_complete':
            self.show_message('Чтение журнала завершено')
            self.log_reading = False

    def add_log_record(self, data):
        """Добавление записи в журнал"""
        record_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            spacing=dp(10),
            padding=dp(5)
        )

        if 'datetime' in data:
            record_layout.add_widget(Label(
                text=data['datetime'],
                size_hint=(0.3, 1),
                halign='left'
            ))

        if 'pressure' in data:
            record_layout.add_widget(Label(
                text=f"P: {data['pressure']:.2f}",
                size_hint=(0.2, 1)
            ))

        if 'temperature' in data:
            record_layout.add_widget(Label(
                text=f"T: {data['temperature']:.1f}",
                size_hint=(0.2, 1)
            ))

        if 'humidity' in data:
            record_layout.add_widget(Label(
                text=f"H: {data['humidity']:.1f}",
                size_hint=(0.2, 1)
            ))

        self.log_list.add_widget(record_layout)

    def show_popup(self, title, message):
        """Показать всплывающее окно"""
        content = BoxLayout(orientation='vertical', padding=dp(10))
        content.add_widget(Label(text=message))

        btn = Button(text='OK', size_hint_y=None, height=dp(40))
        content.add_widget(btn)

        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        btn.bind(on_press=popup.dismiss)
        popup.open()

    def show_message(self, message):
        """Показать временное сообщение"""
        # Здесь можно добавить Snackbar или Toast
        print(f"Message: {message}")


if __name__ == '__main__':
    MeteorStationApp().run()