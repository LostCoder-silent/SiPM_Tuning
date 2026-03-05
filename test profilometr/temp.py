import minimalmodbus

def write_modbus_register(port, slave_address, register_address, value,
                          baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=1):
    """
    Записывает значение в один регистр Modbus RTU.

    Параметры:
        port (str): имя последовательного порта (например, 'COM3' для Windows или '/dev/ttyUSB0' для Linux).
        slave_address (int): адрес ведомого устройства Modbus (1–247).
        register_address (int): адрес регистра для записи. Можно указывать в формате документации,
                                 например, 40001 – функция автоматически преобразует его в Modbus-адрес.
        value (int): записываемое значение (0–65535 для 16-битного регистра).
        baudrate (int): скорость обмена (по умолчанию 9600).
        bytesize (int): количество бит данных (по умолчанию 8).
        parity (str): проверка чётности: 'N' – нет, 'E' – чёт, 'O' – нечёт (по умолчанию 'N').
        stopbits (int): количество стоповых бит (по умолчанию 1).
        timeout (float): таймаут в секундах (по умолчанию 1).

    Возвращает:
        None

    Исключения:
        minimalmodbus.ModbusException: если возникает ошибка связи или устройство не отвечает.
        ValueError: если параметры недопустимы.
    """
    # Создаём объект инструмента
    instrument = minimalmodbus.Instrument(port, slave_address)
    
    # Настраиваем параметры последовательного порта
    instrument.serial.baudrate = baudrate
    instrument.serial.bytesize = bytesize
    instrument.serial.parity = parity
    instrument.serial.stopbits = stopbits
    instrument.serial.timeout = timeout

    # Запись одного регистра (функция 06)
    # Параметр functioncode=6 явно указывает на запись одного регистра
    instrument.write_register(register_address, value, functioncode=6)

# Пример использования
if __name__ == "__main__":
    try:
        # Запись значения 1234 в регистр с адресом 40001 устройства с адресом 1 на порту COM3
        write_modbus_register('dev/ttyUSB0', 1, 1, 34)
        print("Запись выполнена успешно")
    except Exception as e:
        print(f"Ошибка при записи: {e}")
