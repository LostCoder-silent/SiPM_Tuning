#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для скачивания .raw файлов с сервера по временному диапазону,
заданному CSV-файлом с метками, с возможностью коррекции часового пояса.

Структура URL на сервере:
    base_url/год/YYMMDD-HH/_timestamp.13.raw

Пример:
    http://example.com/data/2026/260303-16/_1772545747.13.raw

Поддерживается:
- чтение временных меток из CSV (формат: 2026-03-03T14:29:18.842930)
- коррекция часового пояса (задаётся смещением в секундах)
- определение минимальной и максимальной метки (после коррекции)
- поиск всех файлов в этом диапазоне (по подпапкам YYMMDD-HH)
- скачивание с докачкой (resume)
- режим мониторинга новых файлов
"""

import requests
import re
import os
import time
import csv
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse
from typing import List, Optional, Union, Tuple, Set


# ==================== УТИЛИТЫ ДЛЯ ВРЕМЕНИ ====================

def parse_timestamp(ts_str: str) -> int:
    """
    Преобразует строку с временной меткой вида '2026-03-03T14:29:18.842930'
    в UNIX timestamp (целое число секунд в UTC).
    Поддерживает форматы с микросекундами и без.
    """
    ts_str = ts_str.replace('Z', '')  # удаляем возможный Z на конце
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(ts_str, fmt)
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    raise ValueError(f"Не удалось распарсить временную метку: {ts_str}")


def read_csv_timestamps(csv_path: str, timestamp_column: Union[int, str] = 0,
                        time_offset_seconds: float = 0.0) -> List[int]:
    """
    Читает CSV-файл и извлекает временные метки из указанной колонки.
    Применяет коррекцию часового пояса (прибавляет time_offset_seconds).
    Предполагается, что первая строка — заголовок.
    
    Args:
        csv_path: путь к CSV файлу
        timestamp_column: индекс колонки (0..) или название колонки
        time_offset_seconds: смещение, которое нужно добавить к прочитанным меткам,
                             чтобы получить UTC (например, +10800 для UTC+3).
    
    Returns:
        список скорректированных UNIX timestamp
    """
    timestamps = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)  # пропускаем заголовок
        if header and isinstance(timestamp_column, str):
            try:
                timestamp_column = header.index(timestamp_column)
            except ValueError:
                raise ValueError(f"Колонка '{timestamp_column}' не найдена в заголовке CSV")

        for row in reader:
            if not row:
                continue
            if isinstance(timestamp_column, int):
                if timestamp_column >= len(row):
                    continue
                ts_str = row[timestamp_column].strip()
            else:
                continue

            if not ts_str:
                continue
            try:
                local_ts = parse_timestamp(ts_str)
                # Применяем коррекцию
                utc_ts = local_ts + int(round(time_offset_seconds))
                timestamps.append(utc_ts)
            except ValueError as e:
                print(f"Предупреждение: {e} (строка {reader.line_num})")
    return timestamps


def get_timestamp_range(timestamps: List[int]) -> Tuple[int, int]:
    """Возвращает минимальный и максимальный timestamp из списка."""
    if not timestamps:
        raise ValueError("Список временных меток пуст")
    return min(timestamps), max(timestamps)


def timestamp_to_subfolder(ts: int) -> str:
    """
    Преобразует timestamp в имя подпапки формата YYMMDD-HH (UTC).
    """
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime('%y%m%d-%H')


def filename_to_timestamp(filename: str) -> Optional[int]:
    """
    Извлекает timestamp из имени файла вида '_1772545747.13.raw'.
    Возвращает int или None, если не удалось.
    """
    match = re.search(r'_(\d+)\.', filename)
    if match:
        return int(match.group(1))
    return None


# ==================== РАБОТА С СЕРВЕРОМ ====================

def check_file_exists(url: str, timeout: int = 5) -> bool:
    """Проверяет существование файла по HEAD-запросу."""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code == 200
    except requests.RequestException:
        return False


def resume_download(url: str, download_dir: str, chunk_size: int = 8192) -> Optional[str]:
    """
    Скачивает файл с поддержкой докачки (resume).
    Если файл уже существует, продолжает загрузку с места остановки.
    Возвращает путь к сохранённому файлу или None при ошибке.
    """
    filename = os.path.basename(urlparse(url).path)
    if not filename:
        filename = f"downloaded_{int(time.time())}.raw"

    os.makedirs(download_dir, exist_ok=True)
    filepath = os.path.join(download_dir, filename)

    downloaded_size = 0
    if os.path.exists(filepath):
        downloaded_size = os.path.getsize(filepath)
        print(f"Найден частично скачанный файл: {downloaded_size} байт")

    headers = {'Range': f'bytes={downloaded_size}-'} if downloaded_size > 0 else {}

    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        # Если сервер не поддерживает докачку, начинаем сначала
        if downloaded_size > 0 and response.status_code != 206:
            print("Сервер не поддерживает докачку. Начинаем сначала.")
            downloaded_size = 0
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

        mode = 'ab' if downloaded_size > 0 else 'wb'
        total_size = downloaded_size + int(response.headers.get('content-length', 0))

        print(f"Скачивание: {filename}")
        print(f"Размер: {total_size/1024:.1f} KB")

        downloaded = downloaded_size
        start_time = time.time()

        with open(filepath, mode) as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Прогресс
                    if total_size > 0:
                        percent = downloaded / total_size * 100
                        elapsed = time.time() - start_time
                        speed = (downloaded - downloaded_size) / elapsed / 1024 if elapsed > 0 else 0
                        print(f"\rПрогресс: {percent:.1f}% ({downloaded/1024:.1f}/{total_size/1024:.1f} KB) [{speed:.1f} KB/s]", end='')

        print("\n✓ Завершено")
        return filepath

    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        return None


# ==================== ПОИСК ФАЙЛОВ ПО ИНДЕКСАЦИИ ====================

def get_subfolders_in_year(base_url: str, year: str) -> List[str]:
    """
    Получает список подпапок в директории года (предполагается включённая индексация).
    Возвращает имена подпапок вида '260303-16'.
    """
    url = urljoin(base_url, f"{year}/")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # Ищем ссылки, оканчивающиеся на '/'
        pattern = r'href=["\']([^"\']+/?)["\']'
        links = re.findall(pattern, response.text)
        subfolders = []
        for link in links:
            link = link.rstrip('/')
            # Оставляем только те, что похожи на YYMMDD-HH
            if re.match(r'\d{6}-\d{2}', link):
                subfolders.append(link)
        return subfolders
    except Exception as e:
        print(f"Ошибка получения списка подпапок: {e}")
        return []


def is_subfolder_relevant(subfolder: str, min_ts: int, max_ts: int) -> bool:
    """
    Проверяет, может ли подпапка содержать файлы с timestamp в диапазоне.
    Анализирует дату и час из имени подпапки.
    """
    match = re.match(r'(\d{2})(\d{2})(\d{2})-(\d{2})', subfolder)
    if not match:
        return False
    yy, mm, dd, hh = match.groups()
    year_full = 2000 + int(yy)  # предполагаем 21 век
    try:
        start_dt = datetime(year_full, int(mm), int(dd), int(hh), 0, 0, tzinfo=timezone.utc)
        start_ts = int(start_dt.timestamp())
        end_ts = start_ts + 3600  # конец часа (не включая последнюю секунду)
        # Пересечение интервалов
        return not (end_ts < min_ts or start_ts > max_ts)
    except:
        return False


def find_raw_files_on_page(url: str, pattern: str = r'\.13\.raw$') -> List[str]:
    """
    Ищет на указанной странице все ссылки на файлы, соответствующие паттерну.
    Возвращает полные URL.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        file_pattern = r'href=["\']([^"\']*\.raw[^"\']*)["\']'
        all_raw = re.findall(file_pattern, response.text, re.IGNORECASE)
        matching = []
        for fname in all_raw:
            if re.search(pattern, fname, re.IGNORECASE):
                matching.append(urljoin(url, fname))
        return matching
    except Exception as e:
        print(f"Ошибка при загрузке {url}: {e}")
        return []


def find_files_in_range(base_url: str, year: str, min_ts: int, max_ts: int) -> List[str]:
    """
    Основной метод поиска: определяет все подпапки, которые могут содержать
    файлы из диапазона, заходит в каждую и собирает файлы, фильтруя по timestamp.
    Возвращает список URL файлов, попадающих в диапазон.
    """
    print("Получение списка подпапок...")
    subfolders = get_subfolders_in_year(base_url, year)
    if not subfolders:
        print("Не удалось получить подпапки. Возможно, отключена индексация.")
        return []

    print(f"Найдено подпапок: {len(subfolders)}. Отбор релевантных...")
    relevant = [sf for sf in subfolders if is_subfolder_relevant(sf, min_ts, max_ts)]
    print(f"Релевантных подпапок: {len(relevant)}")

    all_files = []
    for sf in relevant:
        folder_url = urljoin(base_url, f"{year}/{sf}/")
        files = find_raw_files_on_page(folder_url)
        all_files.extend(files)

    # Финальная фильтрация по timestamp в имени файла
    filtered = []
    for url in all_files:
        fname = os.path.basename(urlparse(url).path)
        ts = filename_to_timestamp(fname)
        if ts is not None and min_ts <= ts <= max_ts:
            filtered.append(url)

    return filtered


# ==================== ОСНОВНЫЕ ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЯ ====================

def download_files_by_range(csv_path: str, base_url: str, year: str,
                            timestamp_column: Union[int, str] = 0,
                            time_offset_seconds: float = 0.0,
                            download_dir: str = "downloads",
                            resume: bool = True,
                            max_files: Optional[int] = None,
                            monitor: bool = False,
                            interval: int = 60) -> List[str]:
    """
    Главная функция: читает CSV, применяет коррекцию часового пояса,
    определяет диапазон UTC-меток, скачивает все подходящие файлы.

    Args:
        csv_path: путь к CSV-файлу с временными метками
        base_url: базовый URL (например, http://example.com/data/)
        year: год (например, '2026')
        timestamp_column: колонка с метками (индекс или название)
        time_offset_seconds: смещение, которое нужно прибавить к локальным меткам,
                             чтобы получить UTC (например, +10800 для UTC+3)
        download_dir: папка для сохранения
        resume: использовать докачку
        max_files: максимальное количество файлов для скачивания (если None, все)
        monitor: если True, запускает режим мониторинга новых файлов
        interval: интервал проверки в секундах (для monitor=True)

    Returns:
        список путей к скачанным файлам (если monitor=False)
    """
    print("=" * 70)
    print("ЗАГРУЗКА ФАЙЛОВ ПО ДИАПАЗОНУ ИЗ CSV")
    print("=" * 70)

    # 1. Чтение меток с коррекцией
    print(f"\n[1/4] Чтение временных меток из {csv_path}...")
    timestamps = read_csv_timestamps(csv_path, timestamp_column, time_offset_seconds)
    print(f"Прочитано {len(timestamps)} меток (после коррекции).")
    if not timestamps:
        print("Нет корректных меток. Завершение.")
        return []

    # 2. Диапазон (уже в UTC)
    min_ts, max_ts = get_timestamp_range(timestamps)
    min_dt = datetime.fromtimestamp(min_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    max_dt = datetime.fromtimestamp(max_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[2/4] Диапазон UTC: {min_ts} - {max_ts} ({min_dt} – {max_dt})")

    if monitor:
        # Режим мониторинга
        print("[3/4] Запуск режима мониторинга...")
        _monitor_loop(base_url, year, min_ts, max_ts, download_dir, resume, interval)
        return []  # мониторинг бесконечный, возвращаем пустой список

    # 3. Поиск файлов
    print("[3/4] Поиск файлов на сервере...")
    files_to_download = find_files_in_range(base_url, year, min_ts, max_ts)
    if not files_to_download:
        print("Файлы в указанном диапазоне не найдены.")
        return []

    print(f"Найдено {len(files_to_download)} файлов.")
    if max_files:
        files_to_download = files_to_download[:max_files]
        print(f"Скачивание первых {max_files} файлов...")

    # 4. Скачивание
    print("[4/4] Скачивание...")
    downloaded = []
    for i, url in enumerate(files_to_download, 1):
        print(f"\n[{i}/{len(files_to_download)}] {os.path.basename(urlparse(url).path)}")
        if resume:
            result = resume_download(url, download_dir)
        else:
            # упрощённое скачивание без докачки
            result = _simple_download(url, download_dir)
        if result:
            downloaded.append(result)

    print(f"\nСкачано {len(downloaded)} файлов в '{download_dir}'")
    return downloaded


def _simple_download(url: str, download_dir: str) -> Optional[str]:
    """Простое скачивание файла без прогресса и докачки (запасной вариант)."""
    filename = os.path.basename(urlparse(url).path)
    if not filename:
        filename = f"downloaded_{int(time.time())}.raw"
    os.makedirs(download_dir, exist_ok=True)
    filepath = os.path.join(download_dir, filename)
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return filepath
    except Exception as e:
        print(f"Ошибка скачивания: {e}")
        return None


def _monitor_loop(base_url: str, year: str, min_ts: int, max_ts: int,
                  download_dir: str, resume: bool, interval: int) -> None:
    """
    Бесконечный цикл мониторинга: каждые interval секунд проверяет наличие новых
    файлов в диапазоне и скачивает их.
    """
    downloaded_files: Set[str] = set()
    if os.path.exists(download_dir):
        for f in os.listdir(download_dir):
            if f.endswith('.raw'):
                downloaded_files.add(f)
        print(f"Найдено {len(downloaded_files)} уже скачанных файлов в '{download_dir}'")

    print(f"Мониторинг новых файлов в диапазоне {min_ts} - {max_ts} (интервал {interval}с)")
    try:
        while True:
            current = find_files_in_range(base_url, year, min_ts, max_ts)
            new = [url for url in current if os.path.basename(urlparse(url).path) not in downloaded_files]

            if new:
                print(f"Найдено {len(new)} новых файлов. Скачивание...")
                for url in new:
                    fname = os.path.basename(urlparse(url).path)
                    if resume:
                        result = resume_download(url, download_dir)
                    else:
                        result = _simple_download(url, download_dir)
                    if result:
                        downloaded_files.add(fname)
                        print(f"Скачан: {fname}")
            else:
                print(f"Новых файлов нет. Следующая проверка через {interval}с.")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nМониторинг остановлен пользователем.")


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================
if __name__ == "__main__":
    # Пример с коррекцией для часового пояса UTC+3 (10800 секунд)
    downloaded = download_files_by_range(
        csv_path="log.csv",
    base_url="http://10.163.1.148/runs/raw/",
        year="2026",
        timestamp_column="timestamp",
        time_offset_seconds=10800,  # +3 часа
        download_dir="raw_data",
        resume=True,
        max_files=10,          # ограничение для теста
        monitor=False
    )
    print("Готово.")
