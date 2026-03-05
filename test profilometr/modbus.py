import minimalmodbus
import serial
import os
import time
from datetime import datetime

# Заглушки для имитации ответов pymodbus
class ModbusWriteResponse:
    """Имитация ответа на запрос записи одного регистра (функция 06)"""
    def __init__(self, address, value):
        self.address = address
        self.value = value

    def isError(self):
        return False

class ModbusMultipleWriteResponse:
    """Имитация ответа на запрос записи нескольких регистров (функция 16)"""
    def __init__(self, address, count):
        self.address = address
        self.count = count

    def isError(self):
        return False


class ModbusResponseFormatter:
    """Класс для форматирования ответов Modbus в стиле qmodbus"""
    
    @staticmethod
    def format_write_response(success, data, error_code, device_address, register_address, value):
        """
        Форматирует ответ на запись в стиле qmodbus
        
        Параметры:
        - success: Успешность операции
        - data: Данные ответа
        - error_code: Код ошибки
        - device_address: Адрес устройства
        - register_address: Адрес регистра
        - value: Записываемое значение
        """
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        if success:
            return (
                f"[{timestamp}] "
                f"Запись успешна - Устройство: {device_address}, "
                f"Регистр: {register_address}, Значение: {value}\n"
                f"Ответ: [Функция 06] Адрес: {data.address}, Значение: {data.value}"
            )
        else:
            error_msg = ModbusResponseFormatter.get_detailed_error(error_code, data)
            return (
                f"[{timestamp}] "
                f"ОШИБКА - Устройство: {device_address}, "
                f"Регистр: {register_address}, Значение: {value}\n"
                f"Код ошибки: {error_code} - {error_msg}"
            )
    
    @staticmethod
    def format_multiple_write_response(success, data, error_code, device_address, start_register, values):
        """Форматирует ответ на множественную запись"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        if success:
            return (
                f"[{timestamp}] "
                f"Множественная запись успешна - Устройство: {device_address}, "
                f"Начальный регистр: {start_register}, Значения: {values}\n"
                f"Ответ: [Функция 16] Адрес: {start_register}, Количество: {len(values)}"
            )
        else:
            error_msg = ModbusResponseFormatter.get_detailed_error(error_code, data)
            return (
                f"[{timestamp}] "
                f"ОШИБКА множественной записи - Устройство: {device_address}, "
                f"Начальный регистр: {start_register}, Значения: {values}\n"
                f"Код ошибки: {error_code} - {error_msg}"
            )
    
    @staticmethod
    def get_detailed_error(error_code, data=None):
        """
        Возвращает детальное описание ошибки в стиле qmodbus
        """
        error_descriptions = {
            0: "Успех",
            1: "Ошибка подключения - проверьте порт и права доступа",
            2: "Таймаут - устройство не отвечает",
            3: "Ошибка Modbus устройства",
            4: "Несоответствие данных",
            5: "Общая ошибка выполнения"
        }
        
        base_msg = error_descriptions.get(error_code, "Неизвестная ошибка")
        
        # Детализация ошибки Modbus
        if error_code == 3 and data is not None:
            if hasattr(data, 'message'):
                base_msg += f" | {data.message}"
            if hasattr(data, 'exception_code'):
                exception_codes = {
                    1: "Неверная функция",
                    2: "Неверный адрес данных", 
                    3: "Неверное значение данных",
                    4: "Ошибка устройства",
                    5: "Подтверждение",
                    6: "Устройство занято"
                }
                exc_msg = exception_codes.get(data.exception_code, "Неизвестная ошибка устройства")
                base_msg += f" | Код исключения: {data.exception_code} ({exc_msg})"
        
        return base_msg
    
    @staticmethod
    def format_diagnostic_info(port, baudrate, device_count=1):
        """Форматирует диагностическую информацию"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        return (
            f"[{timestamp}] "
            f"Диагностика - Порт: {port}, Скорость: {baudrate}, "
            f"Устройств: {device_count}"
        )


def write_modbus_register(device_address, register_address, value, port='/dev/ttyUSB0', baudrate=9600, timeout=2):
    """
    Записывает значение в регистр хранения Modbus RTU устройства.

    Параметры:
    - device_address (int): Адрес устройства в сети Modbus (1-247)
    - register_address (int): Адрес регистра для записи
    - value (int): Значение для записи в регистр
    - port (str): Последовательный порт (по умолчанию '/dev/ttyUSB0')
    - baudrate (int): Скорость передачи (по умолчанию 9600)
    - timeout (float): Таймаут в секундах (по умолчанию 2)

    Возвращает:
    - tuple: (success, data, error_code, formatted_message)
    """
    instrument = None
    try:
        # Создаем инструмент minimalmodbus
        instrument = minimalmodbus.Instrument(port, device_address)
        instrument.serial.baudrate = baudrate
        instrument.serial.bytesize = 8
        instrument.serial.parity = 'N'
        instrument.serial.stopbits = 1
        instrument.serial.timeout = timeout

        # Запись одного регистра (функция 06)
        instrument.write_register(register_address, value, functioncode=6)

        # Если дошли до сюда - успех. Создаем объект-ответ, совместимый с форматтером
        response = ModbusWriteResponse(register_address, value)
        msg = ModbusResponseFormatter.format_write_response(
            True, response, 0, device_address, register_address, value
        )
        return True, response, 0, msg

    except minimalmodbus.NoResponseError:
        # Таймаут
        msg = ModbusResponseFormatter.format_write_response(
            False, None, 2, device_address, register_address, value
        )
        return False, None, 2, msg
    except minimalmodbus.ModbusException as e:
        # Ошибка Modbus (например, исключение от устройства)
        # Создаем псевдо-ответ с атрибутами, которые ожидает форматтер
        class ModbusError:
            def __init__(self, msg):
                self.message = msg
                self.exception_code = None  # можно попытаться извлечь, но minimalmodbus не даёт детали
        error_data = ModbusError(str(e))
        msg = ModbusResponseFormatter.format_write_response(
            False, error_data, 3, device_address, register_address, value
        )
        return False, error_data, 3, msg
    except serial.SerialException as e:
        # Ошибка подключения к порту
        msg = ModbusResponseFormatter.format_write_response(
            False, None, 1, device_address, register_address, value
        )
        return False, None, 1, msg
    except Exception as e:
        # Общая ошибка
        print(f"Исключение в write_modbus_register: {e}")
        msg = ModbusResponseFormatter.format_write_response(
            False, None, 5, device_address, register_address, value
        )
        return False, None, 5, msg
    finally:
        if instrument:
            instrument.serial.close()


def write_multiple_registers(device_address, start_register, values, port='/dev/ttyUSB0', baudrate=9600):
    """
    Записывает несколько значений в регистры Modbus RTU устройства.

    Параметры:
    - device_address (int): Адрес устройства в сети Modbus (1-247)
    - start_register (int): Начальный адрес регистра для записи
    - values (list): Список значений для записи
    - port (str): Последовательный порт
    - baudrate (int): Скорость передачи

    Возвращает:
    - tuple: (success, data, error_code, formatted_message)
    """
    instrument = None
    try:
        instrument = minimalmodbus.Instrument(port, device_address)
        instrument.serial.baudrate = baudrate
        instrument.serial.bytesize = 8
        instrument.serial.parity = 'N'
        instrument.serial.stopbits = 1
        instrument.serial.timeout = 1  # фиксированный таймаут, можно сделать параметром

        # Запись нескольких регистров (функция 16)
        instrument.write_registers(start_register, values)

        # Успех. Создаем объект-ответ, совместимый с форматтером
        response = ModbusMultipleWriteResponse(start_register, len(values))
        msg = ModbusResponseFormatter.format_multiple_write_response(
            True, response, 0, device_address, start_register, values
        )
        return True, response, 0, msg

    except minimalmodbus.NoResponseError:
        msg = ModbusResponseFormatter.format_multiple_write_response(
            False, None, 2, device_address, start_register, values
        )
        return False, None, 2, msg
    except minimalmodbus.ModbusException as e:
        class ModbusError:
            def __init__(self, msg):
                self.message = msg
                self.exception_code = None
        error_data = ModbusError(str(e))
        msg = ModbusResponseFormatter.format_multiple_write_response(
            False, error_data, 3, device_address, start_register, values
        )
        return False, error_data, 3, msg
    except serial.SerialException as e:
        msg = ModbusResponseFormatter.format_multiple_write_response(
            False, None, 1, device_address, start_register, values
        )
        return False, None, 1, msg
    except Exception as e:
        print(f"Исключение в write_multiple_registers: {e}")
        msg = ModbusResponseFormatter.format_multiple_write_response(
            False, None, 5, device_address, start_register, values
        )
        return False, None, 5, msg
    finally:
        if instrument:
            instrument.serial.close()


def diagnose_connection(port='/dev/ttyUSB0', baudrate=9600):
    """
    Диагностика подключения к Modbus устройству
    
    Возвращает:
    - tuple: (success, error_code, formatted_message)
    """
    diagnostic_msg = ModbusResponseFormatter.format_diagnostic_info(port, baudrate)
    print(diagnostic_msg)
    
    # Проверка существования порта
    if not os.path.exists(port):
        error_msg = f"❌ Порт {port} не существует"
        print(error_msg)
        return False, 1, error_msg
    
    print(f"✅ Порт {port} существует")
    
    # Проверка прав доступа
    if not os.access(port, os.R_OK | os.W_OK):
        error_msg = f"❌ Нет прав доступа к порту {port}"
        print(error_msg)
        return False, 1, error_msg
    
    print(f"✅ Есть права доступа к порту {port}")
    
    # Попытка открыть порт
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )
        ser.close()
        success_msg = f"✅ Порт {port} успешно открывается"
        print(success_msg)
        return True, 0, success_msg
    except Exception as e:
        error_msg = f"❌ Ошибка открытия порта: {e}"
        print(error_msg)
        return False, 5, error_msg


def modbus_write(device_address, register_address, value, port='/dev/ttyUSB0', baudrate=9600):
    """
    Упрощенная функция записи с автоматическим выводом результата
    """
    success, data, error_code, message = write_modbus_register(
        device_address, register_address, value, port, baudrate
    )
    print(message)
    return success, data, error_code


# ----------------------------------------------------------------------
# Пример использования
if __name__ == "__main__":
    # Пример 1: запись одного регистра
    print("=== Пример записи одного регистра ===")
    success, data, err_code, msg = write_modbus_register(
        device_address=1,
        register_address=0,      # Modbus-адрес регистра (0 для holding register 40001)
        value=1234,
        port='COM3'               # для Windows; для Linux /dev/ttyUSB0
    )
    print(msg)

    # Пример 2: множественная запись
    print("\n=== Пример множественной записи ===")
    success, data, err_code, msg = write_multiple_registers(
        device_address=1,
        start_register=10,
        values=[100, 200, 300],
        port='COM3'
    )
    print(msg)

    # Пример 3: диагностика порта
    print("\n=== Диагностика порта ===")
    diagnose_connection(port='COM3')
