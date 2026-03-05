import struct
from collections import defaultdict
from typing import List, Tuple, Dict, Optional
import time

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

def parse_data_file(filename: str) -> List[Tuple[int, List[int]]]:
    """
    Парсит файл с данными срабатываний.
    
    Формат записи:
    - timestamp_end (2 байта)
    - marker 0x00BE (2 байта)
    - channel1 (2 байта)
    - channel2 (2 байта)
    - channel3 (2 байта)
    - channel4 (2 байта)
    - timestamp_end (2 байта)
    - marker 0x00FE (2 байта)
    
    Returns:
        List[Tuple[int, List[int]]] - список кортежей (временная_метка, [канал1, канал2, канал3, канал4])
    """
    events = []
    
    with open(filename, 'rb') as f:
        data = f.read()
    
    # Размер одной записи: 2 + 2 + 8 + 2 + 2 = 16 байт
    record_size = 16
    pos = 0
    
    while pos + record_size <= len(data):
        # Читаем конец временной метки (2 байта)
        timestamp_end1 = struct.unpack('>H', data[pos:pos+2])[0]
        pos += 2
        
        # Проверяем маркер 0x00BE
        marker1 = struct.unpack('>H', data[pos:pos+2])[0]
        pos += 2
        
        if marker1 != 0x00BE:
            # Если маркер не совпадает, пропускаем байт и пробуем снова
            pos -= 3  # Откатываемся на 1 байт назад от текущей позиции
            continue
        
        # Читаем данные 4 каналов (каждый по 2 байта)
        channels = []
        for _ in range(4):
            channel_data = struct.unpack('>H', data[pos:pos+2])[0]
            channels.append(channel_data)
            pos += 2
        
        # Читаем конец временной метки
        timestamp_end2 = struct.unpack('>H', data[pos:pos+2])[0]
        pos += 2
        
        # Проверяем маркер 0x00FE
        marker2 = struct.unpack('>H', data[pos:pos+2])[0]
        pos += 2
        
        if marker2 != 0x00FE:
            # Если маркер не совпадает, пропускаем запись
            continue
        
        # Используем вторую временную метку как основную
        events.append((timestamp_end2, channels))
    
    return events


# ==================== БЫСТРЫЕ ФУНКЦИИ ДЛЯ ПОДСЧЕТА ====================

def count_channel_activations_fast(filename: str, channel_num: int) -> int:
    """
    БЫСТРЫЙ ПОДСЧЕТ: Общее количество срабатываний в указанном канале.
    Не создает промежуточных структур данных, минимальное использование памяти.
    
    Args:
        filename: путь к файлу
        channel_num: номер канала (0-3)
    
    Returns:
        int: общее количество срабатываний в канале
    """
    if channel_num < 0 or channel_num > 3:
        raise ValueError("Channel number must be between 0 and 3")
    
    count = 0
    record_size = 16
    
    with open(filename, 'rb') as f:
        data = f.read()
    
    pos = 0
    data_len = len(data)
    
    while pos + record_size <= data_len:
        # Пропускаем первую метку и маркер 0x00BE (4 байта)
        pos += 4
        
        # Читаем данные каналов
        for ch in range(4):
            # Быстрое преобразование без struct (быстрее)
            channel_data = (data[pos] << 8) | data[pos + 1]
            
            if ch == channel_num and channel_data != 0:
                count += 1
            pos += 2
        
        # Пропускаем вторую метку и маркер 0x00FE (4 байта)
        pos += 4
    
    return count


def get_channel_stats_fast(filename: str, channel_num: int) -> Tuple[int, Dict[int, int]]:
    """
    БЫСТРЫЙ ПОДСЧЕТ: Детальная статистика по каналу с разбивкой по ячейкам.
    
    Args:
        filename: путь к файлу
        channel_num: номер канала (0-3)
    
    Returns:
        Tuple[int, Dict[int, int]]: (общее_количество, словарь{ячейка: количество})
    """
    if channel_num < 0 or channel_num > 3:
        raise ValueError("Channel number must be between 0 and 3")
    
    cell_counts = [0] * 16
    total = 0
    record_size = 16
    
    with open(filename, 'rb') as f:
        data = f.read()
    
    pos = 0
    data_len = len(data)
    
    while pos + record_size <= data_len:
        # Пропускаем первую метку и маркер 0x00BE (4 байта)
        pos += 4
        
        # Читаем данные каналов
        for ch in range(4):
            # Быстрое преобразование без struct
            channel_data = (data[pos] << 8) | data[pos + 1]
            
            if ch == channel_num:
                if channel_data != 0:
                    total += 1
                    # Подсчет по ячейкам (проверяем каждый бит)
                    for cell in range(16):
                        if channel_data & (1 << cell):
                            cell_counts[cell] += 1
            pos += 2
        
        # Пропускаем вторую метку и маркер 0x00FE (4 байта)
        pos += 4
    
    # Создаем словарь только для ненулевых ячеек
    stats = {i: cell_counts[i] for i in range(16) if cell_counts[i] > 0}
    return total, stats


def count_multiple_channels_fast(filename: str, channels: List[int]) -> Dict[int, int]:
    """
    БЫСТРЫЙ ПОДСЧЕТ: Подсчет срабатываний для нескольких каналов одновременно.
    
    Args:
        filename: путь к файлу
        channels: список номеров каналов для подсчета
    
    Returns:
        Dict[int, int]: словарь {канал: количество_срабатываний}
    """
    for ch in channels:
        if ch < 0 or ch > 3:
            raise ValueError(f"Channel {ch} must be between 0 and 3")
    
    counts = {ch: 0 for ch in channels}
    record_size = 16
    
    with open(filename, 'rb') as f:
        data = f.read()
    
    pos = 0
    data_len = len(data)
    
    while pos + record_size <= data_len:
        pos += 4  # пропускаем первую метку и 0x00BE
        
        for ch in range(4):
            channel_data = (data[pos] << 8) | data[pos + 1]
            
            if ch in channels and channel_data != 0:
                counts[ch] += 1
            pos += 2
        
        pos += 4  # пропускаем вторую метку и 0x00FE
    
    return counts


def get_channel_activation_timeline_fast(filename: str, channel_num: int, 
                                        cell_num: Optional[int] = None) -> List[int]:
    """
    БЫСТРЫЙ ПОДСЧЕТ: Получение временных меток срабатываний.
    
    Args:
        filename: путь к файлу
        channel_num: номер канала (0-3)
        cell_num: если указан, только срабатывания конкретной ячейки
    
    Returns:
        List[int]: список временных меток
    """
    if channel_num < 0 or channel_num > 3:
        raise ValueError("Channel number must be between 0 and 3")
    if cell_num is not None and (cell_num < 0 or cell_num > 15):
        raise ValueError("Cell number must be between 0 and 15")
    
    timestamps = []
    record_size = 16
    
    with open(filename, 'rb') as f:
        data = f.read()
    
    pos = 0
    data_len = len(data)
    
    while pos + record_size <= data_len:
        pos += 2  # пропускаем первую метку
        marker = (data[pos] << 8) | data[pos + 1]
        pos += 2
        
        if marker != 0x00BE:
            pos -= 2
            continue
        
        # Сохраняем позицию перед чтением каналов
        channels_pos = pos
        
        # Пропускаем каналы до нужного
        for ch in range(4):
            if ch == channel_num:
                channel_data = (data[pos] << 8) | data[pos + 1]
                
                if cell_num is None:
                    if channel_data != 0:
                        # Читаем временную метку из конца записи
                        timestamp_pos = channels_pos + 8 + 2  # после каналов + метка
                        timestamp = (data[timestamp_pos] << 8) | data[timestamp_pos + 1]
                        timestamps.append(timestamp)
                else:
                    if channel_data & (1 << cell_num):
                        timestamp_pos = channels_pos + 8 + 2
                        timestamp = (data[timestamp_pos] << 8) | data[timestamp_pos + 1]
                        timestamps.append(timestamp)
            pos += 2
        
        pos += 4  # пропускаем вторую метку и 0x00FE
    
    return timestamps


# ==================== ОСНОВНЫЕ ФУНКЦИИ (из предыдущей версии) ====================

def get_events_by_timestamp(events: List[Tuple[int, List[int]]], 
                           timestamp: int) -> List[List[int]]:
    """
    Возвращает все события для указанной временной метки.
    """
    return [channels for ts, channels in events if ts == timestamp]


def get_channel_statistics(events: List[Tuple[int, List[int]]], 
                          channel_num: int) -> Dict[int, int]:
    """
    Возвращает статистику срабатываний для указанного канала по ячейкам.
    """
    if channel_num < 0 or channel_num > 3:
        raise ValueError("Channel number must be between 0 and 3")
    
    statistics = defaultdict(int)
    
    for _, channels in events:
        channel_data = channels[channel_num]
        
        for cell in range(16):
            if channel_data & (1 << cell):
                statistics[cell] += 1
    
    return dict(statistics)


def get_total_events_by_cell(events: List[Tuple[int, List[int]]], 
                            channel_num: int) -> Dict[int, int]:
    """
    То же что и get_channel_statistics.
    """
    return get_channel_statistics(events, channel_num)


def print_channel_statistics(stats: Dict[int, int], channel_num: int):
    """
    Красиво выводит статистику по каналу.
    """
    print(f"\nСтатистика для канала {channel_num}:")
    print("-" * 40)
    total_events = sum(stats.values())
    print(f"Всего событий: {total_events}")
    print("\nСрабатывания по ячейкам:")
    for cell in range(16):
        count = stats.get(cell, 0)
        percentage = (count / total_events * 100) if total_events > 0 else 0
        print(f"Ячейка {cell:2d}: {count:6d} раз ({percentage:5.2f}%)")


def filter_events_by_time_range(events: List[Tuple[int, List[int]]], 
                               start_time: int, end_time: int) -> List[Tuple[int, List[int]]]:
    """Фильтрует события по диапазону временных меток."""
    return [(ts, ch) for ts, ch in events if start_time <= ts <= end_time]


def get_cell_activation_timeline(events: List[Tuple[int, List[int]]], 
                                channel_num: int, cell_num: int) -> List[int]:
    """
    Возвращает список временных меток, когда конкретная ячейка сработала.
    """
    timestamps = []
    for ts, channels in events:
        if channels[channel_num] & (1 << cell_num):
            timestamps.append(ts)
    return timestamps


def get_channel_heatmap(events: List[Tuple[int, List[int]]], 
                       channel_num: int) -> List[List[int]]:
    """
    Создает "тепловую карту" активности для канала по временным меткам.
    """
    return [(ts, channels[channel_num]) for ts, channels in events]


# ==================== ФУНКЦИИ ДЛЯ СРАВНЕНИЯ ПРОИЗВОДИТЕЛЬНОСТИ ====================

def compare_performance(filename: str, channel_num: int = 0):
    """
    Сравнивает производительность разных методов подсчета.
    """
    print(f"\n{'='*60}")
    print(f"СРАВНЕНИЕ ПРОИЗВОДИТЕЛЬНОСТИ (канал {channel_num})")
    print(f"{'='*60}")
    
    # Метод 1: Полный парсинг + статистика
    start = time.time()
    events = parse_data_file(filename)
    parse_time = time.time() - start
    
    start = time.time()
    stats = get_channel_statistics(events, channel_num)
    total_standard = sum(stats.values())
    standard_time = time.time() - start
    
    print(f"\n1. Стандартный метод (полный парсинг):")
    print(f"   - Время парсинга: {parse_time:.3f}с")
    print(f"   - Время анализа: {standard_time:.3f}с")
    print(f"   - Всего: {total_standard} событий")
    print(f"   - Память: ~{len(events) * 100} байт")
    
    # Метод 2: Быстрый подсчет общего количества
    start = time.time()
    total_fast = count_channel_activations_fast(filename, channel_num)
    fast_time = time.time() - start
    
    print(f"\n2. Быстрый метод (только количество):")
    print(f"   - Время: {fast_time:.3f}с")
    print(f"   - Всего: {total_fast} событий")
    print(f"   - Память: минимально")
    print(f"   - Ускорение: {parse_time+standard_time:.1f}x")
    
    # Метод 3: Быстрый метод с детализацией
    start = time.time()
    total_detailed, detailed_stats = get_channel_stats_fast(filename, channel_num)
    detailed_time = time.time() - start
    
    print(f"\n3. Быстрый метод (с детализацией):")
    print(f"   - Время: {detailed_time:.3f}с")
    print(f"   - Всего: {total_detailed} событий")
    print(f"   - Ячеек активно: {len(detailed_stats)}")


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    filename = "test.raw"  # замените на имя вашего файла
    
    try:
        # ПРИМЕР 1: Быстрый подсчет общего количества
        print("\n" + "="*60)
        print("ПРИМЕР 1: Быстрый подсчет общего количества")
        print("="*60)
        
        for channel in range(4):
            total = count_channel_activations_fast(filename, channel)
            print(f"Канал {channel}: {total} срабатываний")
        
        # ПРИМЕР 2: Детальная статистика по каналу
        print("\n" + "="*60)
        print("ПРИМЕР 2: Детальная статистика по каналу 0")
        print("="*60)
        
        total, stats = get_channel_stats_fast(filename, 0)
        print(f"Всего срабатываний: {total}")
        print("По ячейкам:")
        for cell in range(16):
            count = stats.get(cell, 0)
            if count > 0:
                print(f"  Ячейка {cell}: {count} раз")
        
        # ПРИМЕР 3: Подсчет для нескольких каналов
        print("\n" + "="*60)
        print("ПРИМЕР 3: Подсчет для нескольких каналов")
        print("="*60)
        
        multi_stats = count_multiple_channels_fast(filename, [0, 1, 2])
        for channel, count in multi_stats.items():
            print(f"Канал {channel}: {count} срабатываний")
        
        # ПРИМЕР 4: Получение временных меток для ячейки
        print("\n" + "="*60)
        print("ПРИМЕР 4: Временные метки для ячейки 5 канала 0")
        print("="*60)
        
        timeline = get_channel_activation_timeline_fast(filename, 0, cell_num=5)
        print(f"Найдено {len(timeline)} срабатываний")
        if timeline:
            print(f"Первые 5 меток: {[f'{t:04X}' for t in timeline[:5]]}")
        
        # ПРИМЕР 5: Сравнение производительности
        compare_performance(filename)
        
    except FileNotFoundError:
        print(f"Файл {filename} не найден")
        print("Создайте тестовый файл или укажите правильное имя файла")
    except Exception as e:
        print(f"Ошибка при обработке файла: {e}")
