import csv
import sqlite3
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict, Optional
import struct

# Предполагается, что parse_file.py находится в той же директории
# и содержит функции для работы с raw-файлами.
# Мы будем использовать некоторые из них, но добавим свою для подсчёта записей.

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def parse_log(csv_path: str) -> List[dict]:
    """
    Читает CSV-файл лога и возвращает список записей.
    Каждая запись — словарь с полями:
        timestamp (datetime), param1 (int), param2 (int),
        success1 (bool), success2 (bool)
    """
    records = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Парсим временную метку (ISO формат)
            dt = datetime.fromisoformat(row['timestamp'])
            # Приводим к UTC (если метка наивная, считаем что это UTC)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            records.append({
                'timestamp': dt,
                'param1': int(row['param1']),
                'param2': int(row['param2']),
                'success1': row['success1'].strip().lower() == 'true',
                'success2': row['success2'].strip().lower() == 'true'
            })
    return records


def get_raw_files(folder: str) -> List[Tuple[datetime, str]]:
    """
    Сканирует папку на предмет файлов с расширением .raw,
    извлекает из имени временную метку Unix (float).
    Возвращает список кортежей (datetime, полный_путь).
    Ожидаемый формат имени: _<timestamp>.raw или _<timestamp>.<anything>.raw
    """
    files = []
    pattern = re.compile(r'_(\d+(?:\.\d+)?)\.raw$')
    for fname in os.listdir(folder):
        if not fname.endswith('.raw'):
            continue
        match = pattern.search(fname)
        if not match:
            print(f"Предупреждение: не удалось извлечь timestamp из {fname}")
            continue
        ts_str = match.group(1)
        try:
            ts = float(ts_str)
        except ValueError:
            print(f"Предупреждение: некорректный timestamp {ts_str} в {fname}")
            continue
        # Создаем datetime в UTC
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        files.append((dt, os.path.join(folder, fname)))
    # Сортируем по времени для удобства
    files.sort(key=lambda x: x[0])
    return files


def count_events_in_file(filepath: str) -> int:
    """
    Быстро подсчитывает количество корректных записей в одном raw-файле.
    Использует минимальную проверку маркеров 0x00BE и 0x00FE.
    Возвращает число записей.
    """
    RECORD_SIZE = 16
    count = 0
    with open(filepath, 'rb') as f:
        data = f.read()
    pos = 0
    data_len = len(data)
    while pos + RECORD_SIZE <= data_len:
        # Проверяем маркер 0x00BE (big-endian) через 2 байта от начала записи
        # Запись: [timestamp_end(2)] [0x00BE(2)] [chan1(2)] [chan2(2)] [chan3(2)] [chan4(2)] [timestamp_end(2)] [0x00FE(2)]
        if (data[pos+2] == 0x00 and data[pos+3] == 0xBE and
            data[pos+14] == 0x00 and data[pos+15] == 0xFE):
            count += 1
        # В случае несовпадения маркеров просто пропускаем запись (не пытаемся ресинхронизироваться)
        pos += RECORD_SIZE
    return count


# ==================== ОСНОВНАЯ ЛОГИКА ====================

def create_db(db_path: str):
    """Создаёт таблицу для хранения результатов, если её нет."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            param1 INTEGER,
            param2 INTEGER,
            events INTEGER,
            interval_start TEXT  -- для отладки, можно сохранять начало интервала
        )
    ''')
    conn.commit()
    return conn


def process_data(log_path: str, raw_folder: str, db_path: str, t1: float, t2: float):
    """
    Основная функция обработки.
    t1 — время набора данных (сек)
    t2 — время передачи (сек) — используется только для проверки интервалов.
    """
    # Читаем лог
    log_records = parse_log(log_path)
    if len(log_records) < 2:
        print("Лог должен содержать минимум 2 записи для интервалов.")
        return

    # Получаем все raw-файлы с временами
    raw_files = get_raw_files(raw_folder)
    if not raw_files:
        print("Нет raw-файлов для обработки.")
        return

    # Создаём БД
    conn = create_db(db_path)
    cursor = conn.cursor()

    total_intervals = 0
    for i in range(len(log_records) - 1):
        start_dt = log_records[i]['timestamp']          # начало набора (конец предыдущей передачи)
        end_dt = start_dt + timedelta(seconds=t1)       # конец набора
        next_dt = log_records[i+1]['timestamp']         # следующая метка (конец передачи)

        # Проверяем, что интервал между метками согласуется с t1+t2 (необязательно)
        expected_next = start_dt + timedelta(seconds=t1 + t2)
        delta = abs((next_dt - expected_next).total_seconds())
        if delta > 0.1:  # допуск 0.1 сек
            print(f"Предупреждение: интервал {i}-{i+1} отличается от t1+t2 на {delta:.2f} сек")

        # Параметры для этого цикла берём из следующей записи
        param1 = log_records[i+1]['param1']
        param2 = log_records[i+1]['param2']

        # Выбираем файлы, попадающие в интервал [start_dt, end_dt]
        # raw_files уже отсортированы, можно использовать бинарный поиск для ускорения,
        # но для простоты сделаем линейный просмотр, так как файлов обычно не очень много.
        files_in_interval = []
        for ft, fpath in raw_files:
            if start_dt <= ft <= end_dt:
                files_in_interval.append(fpath)
            elif ft > end_dt:
                break  # так как файлы отсортированы, дальше можно не смотреть

        # Суммируем события
        total_events = 0
        for fpath in files_in_interval:
            total_events += count_events_in_file(fpath)

        # Сохраняем в БД
        cursor.execute(
            "INSERT INTO measurements (param1, param2, events, interval_start) VALUES (?, ?, ?, ?)",
            (param1, param2, total_events, start_dt.isoformat())
        )
        total_intervals += 1
        print(f"Интервал {i}: param1={param1}, param2={param2}, событий={total_events}, файлов={len(files_in_interval)}")

    conn.commit()
    conn.close()
    print(f"\nОбработано интервалов: {total_intervals}. Результаты сохранены в {db_path}")


# ==================== ТОЧКА ВХОДА ====================

if __name__ == "__main__":
    # Параметры, которые можно настроить
    LOG_FILE = "log.csv"               # путь к CSV-логу
    RAW_FOLDER = "./raw_data"           # папка с raw-файлами
    DB_FILE = "results.db"              # файл базы данных SQLite
    T1 = 25.0                           # время набора данных (сек)
    T2 = 5.0                            # время передачи (сек)

    process_data(LOG_FILE, RAW_FOLDER, DB_FILE, T1, T2)
