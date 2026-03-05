import threading
import time
from modbus import write_modbus_register  # импорт функции записи из предоставленной библиотеки

class ExperimentRunner(threading.Thread):
    """
    Поток, выполняющий перебор комбинаций значений двух параметров.
    Управляется через флаги паузы и остановки.
    """
    def __init__(self, config, logger, gui_callback=None):
        """
        :param config: dict с настройками (порт, адреса регистров, диапазоны и т.д.)
        :param logger: объект логгера (должен иметь метод log(param1, param2, success1, success2))
        :param gui_callback: функция для обновления GUI, вызывается после каждой итерации
        """
        super().__init__()
        self.config = config
        self.logger = logger
        self.gui_callback = gui_callback

        # Извлекаем параметры подключения
        self.port = config.get('port', '/dev/ttyUSB0')
        self.baudrate = config.get('baudrate', 9600)
        self.device_address = config.get('device_address', 1)
        self.register_1 = config.get('register_1', 100)
        self.register_2 = config.get('register_2', 101)

        # Диапазоны для двух параметров
        self.range1_min = config['range_1']['min']
        self.range1_max = config['range_1']['max']
        self.range1_step = config['range_1']['step']
        self.range2_min = config['range_2']['min']
        self.range2_max = config['range_2']['max']
        self.range2_step = config['range_2']['step']

        # Задержка между итерациями (в секундах)
        self.delay = config.get('delay_between_writes', 1.0)

        # События для управления потоком
        self._pause = threading.Event()
        self._pause.set()      # изначально не на паузе
        self._stop = threading.Event()
        self._is_running = False

    def pause(self):
        """Приостановить выполнение после текущей итерации"""
        self._pause.clear()

    def resume(self):
        """Возобновить выполнение"""
        self._pause.set()

    def stop(self):
        """Остановить выполнение (поток завершится после текущей итерации)"""
        self._stop.set()
        self.resume()  # чтобы выйти из ожидания паузы

    def is_paused(self):
        """Возвращает True, если эксперимент на паузе"""
        return not self._pause.is_set()

    def run(self):
        """Основной цикл перебора комбинаций"""
        self._is_running = True

        # Генерация списков значений с заданными шагами
        values1 = list(range(self.range1_min, self.range1_max + 1, self.range1_step))
        values2 = list(range(self.range2_min, self.range2_max + 1, self.range2_step))

        total_steps = len(values1) * len(values2)
        current_step = 0

        for v2 in values2:
            if self._stop.is_set():
                break
            for v1 in values1:
                if self._stop.is_set():
                    break
                # Ожидание снятия паузы
                self._pause.wait()

                # Запись первого параметра
                success1, _, err1, msg1 = write_modbus_register(
                    device_address=self.device_address,
                    register_address=self.register_1,
                    value=v1,
                    port=self.port,
                    baudrate=self.baudrate
                )
                # Небольшая задержка между записями (можно убрать или вынести в конфиг)
                time.sleep(0.1)

                # Запись второго параметра
                success2, _, err2, msg2 = write_modbus_register(
                    device_address=self.device_address,
                    register_address=self.register_2,
                    value=v2,
                    port=self.port,
                    baudrate=self.baudrate
                )

                # Логирование результата
                self.logger.log(v1, v2, success1, success2)

                current_step += 1
                # Уведомление GUI о прогрессе
                if self.gui_callback:
                    self.gui_callback(current_step, total_steps, v1, v2, success1, success2)

                # Задержка перед следующей итерацией
                time.sleep(self.delay)

        self._is_running = False
