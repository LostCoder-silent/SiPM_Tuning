import time
from modbus import write_modbus_register, diagnose_connection

class ModbusController:
    """
    Контроллер для управления Modbus-устройством с двумя параметрами.
    Предоставляет методы записи с повторными попытками и диагностикой.
    """
    
    def __init__(self, config):
        """
        :param config: словарь с конфигурацией, должен содержать:
            - port: str
            - baudrate: int
            - device_address: int
            - register_1: int
            - register_2: int
            - retries: int (опционально, по умолчанию 3)
            - retry_delay: float (опционально, по умолчанию 0.5)
            - timeout: float (опционально, по умолчанию 2)
        """
        self.port = config['port']
        self.baudrate = config['baudrate']
        self.device_address = config['device_address']
        self.register_1 = config['register_1']
        self.register_2 = config['register_2']
        self.retries = config.get('retries', 3)
        self.retry_delay = config.get('retry_delay', 0.5)
        self.timeout = config.get('timeout', 2)
        
    def _write_with_retry(self, register, value):
        """
        Внутренний метод для записи значения в регистр с повторными попытками.
        Возвращает (success, data, error_code, message)
        """
        last_result = (False, None, 5, "No attempts made")  # fallback
        
        for attempt in range(1, self.retries + 1):
            success, data, error_code, message = write_modbus_register(
                device_address=self.device_address,
                register_address=register,
                value=value,
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            last_result = (success, data, error_code, message)
            
            if success:
                return last_result
            
            # Если ошибка подключения или таймаут, возможно, стоит подождать дольше
            if error_code in (1, 2, 5):  # ошибка подключения, таймаут, общая ошибка
                time.sleep(self.retry_delay)
            else:
                # Другие ошибки (например, неверный адрес) вряд ли исправятся повтором
                # Но можно всё равно сделать паузу и попробовать ещё раз
                time.sleep(self.retry_delay)
        
        return last_result
    
    def write_param1(self, value):
        """Запись значения в регистр параметра 1"""
        return self._write_with_retry(self.register_1, value)
    
    def write_param2(self, value):
        """Запись значения в регистр параметра 2"""
        return self._write_with_retry(self.register_2, value)
    
    def diagnose(self):
        """Проверка соединения с устройством"""
        return diagnose_connection(port=self.port, baudrate=self.baudrate)
    
    def set_param1_register(self, new_register):
        """Изменение адреса регистра параметра 1 (на случай, если нужно динамически)"""
        self.register_1 = new_register
        
    def set_param2_register(self, new_register):
        self.register_2 = new_register
