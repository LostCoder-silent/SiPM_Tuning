#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Интегрированный модуль для поиска, скачивания и анализа .raw файлов
"""

import requests
import re
import os
import time
import struct
from pathlib import Path
from urllib.parse import urljoin, urlparse
from collections import defaultdict
from typing import List, Optional, Dict, Union, Tuple, Any

# ==================== ЧАСТЬ 1: БЫСТРЫЕ ФУНКЦИИ ДЛЯ СКАЧИВАНИЯ ====================

def quick_download(url: str, download_dir: str = "downloads", 
                  filename: Optional[str] = None, timeout: int = 30) -> Optional[str]:
    """
    Быстрое скачивание файла без визуализации и прогресс-баров.
    
    Args:
        url: URL файла для скачивания
        download_dir: директория для сохранения
        filename: имя файла (если None, берется из URL)
        timeout: таймаут соединения в секундах
    
    Returns:
        Optional[str]: путь к сохраненному файлу или None при ошибке
    """
    try:
        os.makedirs(download_dir, exist_ok=True)
        
        if filename is None:
            filename = os.path.basename(urlparse(url).path)
            if not filename or filename == '/':
                filename = f"downloaded_{int(time.time())}.raw"
        
        filepath = os.path.join(download_dir, filename)
        
        if os.path.exists(filepath):
            base, ext = os.path.splitext(filepath)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            filepath = f"{base}_{counter}{ext}"
        
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return filepath
        
    except Exception as e:
        print(f"Ошибка в quick_download: {e}")
        return None


def quick_batch_download(urls: List[str], download_dir: str = "downloads", 
                        max_files: Optional[int] = None) -> List[str]:
    """
    Быстрое скачивание нескольких файлов без визуализации.
    
    Args:
        urls: список URL для скачивания
        download_dir: директория для сохранения
        max_files: максимальное количество файлов для скачивания
    
    Returns:
        List[str]: список успешно скачанных файлов
    """
    if max_files:
        urls = urls[:max_files]
    
    downloaded = []
    
    for url in urls:
        result = quick_download(url, download_dir)
        if result:
            downloaded.append(result)
    
    return downloaded


def quick_find_and_download(url: str, pattern: str = r'\.13\.raw$', 
                           download_dir: str = "downloads",
                           max_files: Optional[int] = None) -> List[str]:
    """
    Быстрый поиск и скачивание файлов одной функцией.
    
    Args:
        url: URL страницы для поиска
        pattern: регулярное выражение для фильтрации
        download_dir: директория для сохранения
        max_files: максимальное количество файлов для скачивания
    
    Returns:
        List[str]: список скачанных файлов
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        file_pattern = r'href=["\']([^"\']*\.raw[^"\']*)["\']'
        all_files = re.findall(file_pattern, response.text, re.IGNORECASE)
        
        files_to_download = []
        for filename in all_files:
            if re.search(pattern, filename, re.IGNORECASE):
                full_url = urljoin(url, filename)
                files_to_download.append(full_url)
        
        if max_files:
            files_to_download = files_to_download[:max_files]
        
        return quick_batch_download(files_to_download, download_dir)
        
    except Exception as e:
        print(f"Ошибка в quick_find_and_download: {e}")
        return []


def quick_get(url: str, filename: Optional[str] = None) -> Optional[str]:
    """
    Максимально быстрая функция для скачивания одного файла.
    
    Args:
        url: URL файла
        filename: имя файла (если None, берется из URL)
    
    Returns:
        Optional[str]: путь к файлу или None
    """
    try:
        if filename is None:
            filename = os.path.basename(urlparse(url).path) or "file.raw"
        
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        
        with open(filename, 'wb') as f:
            f.write(r.content)
        
        return filename
    except Exception as e:
        print(f"Ошибка в quick_get: {e}")
        return None


# ==================== ЧАСТЬ 2: ФУНКЦИИ ДЛЯ ПОИСКА ФАЙЛОВ ====================

def find_raw_files_on_page(url: str, pattern: str = r'\.13\.raw$') -> List[str]:
    """
    Ищет файлы на указанной веб-странице, соответствующие заданному паттерну.
    
    Args:
        url: URL страницы для поиска
        pattern: регулярное выражение для фильтрации файлов
    
    Returns:
        List[str]: список найденных URL файлов
    """
    try:
        print(f"Загрузка страницы: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        file_pattern = r'href=["\']([^"\']*\.raw[^"\']*)["\']'
        all_raw_files = re.findall(file_pattern, response.text, re.IGNORECASE)
        
        matching_files = []
        for filename in all_raw_files:
            if re.search(pattern, filename, re.IGNORECASE):
                full_url = urljoin(url, filename)
                matching_files.append(full_url)
        
        return matching_files
        
    except requests.RequestException as e:
        print(f"Ошибка при загрузке страницы {url}: {e}")
        return []


def get_file_info(file_url: str) -> Optional[Dict[str, Any]]:
    """
    Получает информацию о файле без скачивания.
    
    Args:
        file_url: URL файла
    
    Returns:
        Optional[Dict]: информация о файле или None
    """
    try:
        response = requests.head(file_url, timeout=5)
        response.raise_for_status()
        
        size = int(response.headers.get('content-length', 0))
        
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024**2:
            size_str = f"{size/1024:.1f} KB"
        elif size < 1024**3:
            size_str = f"{size/(1024**2):.1f} MB"
        else:
            size_str = f"{size/(1024**3):.1f} GB"
        
        info = {
            'url': file_url,
            'filename': os.path.basename(urlparse(file_url).path),
            'size': size,
            'size_str': size_str,
            'type': response.headers.get('content-type', 'unknown'),
            'last_modified': response.headers.get('last-modified', 'unknown')
        }
        
        return info
        
    except requests.RequestException as e:
        print(f"Ошибка получения информации о файле: {e}")
        return None


def print_files_info(files: Union[List[str], List[Dict]], title: str = "Найденные файлы") -> None:
    """
    Красиво выводит информацию о файлах.
    """
    if not files:
        print("Файлы не найдены")
        return
    
    if isinstance(files[0], str):
        files_info = []
        for f in files:
            info = get_file_info(f)
            if info:
                files_info.append(info)
    else:
        files_info = files
    
    if not files_info:
        print("Не удалось получить информацию о файлах")
        return
    
    print(f"\n{title}:")
    print("-" * 100)
    print(f"{'#':<3} {'Имя файла':<40} {'Размер':<12} {'Дата модификации':<25} {'Тип':<15}")
    print("-" * 100)
    
    for i, info in enumerate(files_info, 1):
        name = info['filename'][:38] + '..' if len(info['filename']) > 40 else info['filename']
        last_mod = info['last_modified'][:25] if info['last_modified'] != 'unknown' else 'unknown'
        print(f"{i:<3} {name:<40} {info['size_str']:<12} {last_mod:<25} {info['type'][:15]}")


# ==================== ЧАСТЬ 3: ФУНКЦИИ С ВИЗУАЛИЗАЦИЕЙ ====================

def download_file(url: str, download_dir: str = "downloads", filename: Optional[str] = None,
                 chunk_size: int = 8192, timeout: int = 30, verify: bool = True) -> Optional[str]:
    """
    Скачивает файл по URL с отображением прогресса.
    """
    try:
        os.makedirs(download_dir, exist_ok=True)
        
        if filename is None:
            filename = os.path.basename(urlparse(url).path)
            if not filename or filename == '/':
                filename = f"downloaded_file_{int(time.time())}.raw"
        
        filepath = os.path.join(download_dir, filename)
        
        if os.path.exists(filepath):
            base, ext = os.path.splitext(filepath)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            filepath = f"{base}_{counter}{ext}"
        
        print(f"Скачивание: {filename}")
        print(f"Из: {url}")
        print(f"В: {filepath}")
        
        head_response = requests.head(url, timeout=timeout, verify=verify)
        total_size = int(head_response.headers.get('content-length', 0))
        
        response = requests.get(url, stream=True, timeout=timeout, verify=verify)
        response.raise_for_status()
        
        downloaded = 0
        start_time = time.time()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = downloaded / total_size * 100
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed / 1024 if elapsed > 0 else 0
                        
                        bar_length = 30
                        filled = int(bar_length * downloaded // total_size)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        
                        print(f"\rПрогресс: |{bar}| {percent:.1f}% "
                              f"({downloaded/1024:.1f}/{total_size/1024:.1f} KB) "
                              f"[{speed:.1f} KB/s]", end='')
        
        elapsed = time.time() - start_time
        print(f"\n✓ Скачивание завершено за {elapsed:.1f}с")
        print(f"  Размер: {downloaded/1024:.1f} KB")
        
        return filepath
        
    except requests.exceptions.Timeout:
        print(f"\n✗ Ошибка: Таймаут при скачивании {url}")
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Ошибка: Не удалось подключиться к {url}")
    except requests.exceptions.HTTPError as e:
        print(f"\n✗ Ошибка HTTP: {e}")
    except Exception as e:
        print(f"\n✗ Неожиданная ошибка: {e}")
    
    return None


def download_files_batch(urls: List[str], download_dir: str = "downloads", 
                        max_files: Optional[int] = None, delay: float = 0.5) -> List[str]:
    """
    Скачивает несколько файлов последовательно с визуализацией.
    """
    if max_files:
        urls = urls[:max_files]
    
    downloaded = []
    total = len(urls)
    
    print(f"\nНачинаю скачивание {total} файлов...")
    print("=" * 60)
    
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{total}] Обработка файла...")
        
        result = download_file(url, download_dir)
        
        if result:
            downloaded.append(result)
        
        if i < total and delay > 0:
            print(f"Ожидание {delay}с перед следующим файлом...")
            time.sleep(delay)
    
    print("\n" + "=" * 60)
    print(f"Скачано {len(downloaded)} из {total} файлов")
    
    return downloaded


def resume_download(url: str, download_dir: str = "downloads", chunk_size: int = 8192) -> Optional[str]:
    """
    Скачивает файл с поддержкой докачки.
    """
    filename = os.path.basename(urlparse(url).path)
    if not filename:
        filename = f"resume_{int(time.time())}.raw"
    
    filepath = os.path.join(download_dir, filename)
    
    downloaded_size = 0
    if os.path.exists(filepath):
        downloaded_size = os.path.getsize(filepath)
        print(f"Найден частично скачанный файл: {downloaded_size} байт")
    
    headers = {'Range': f'bytes={downloaded_size}-'} if downloaded_size > 0 else {}
    
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        if downloaded_size > 0 and response.status_code != 206:
            print("Сервер не поддерживает докачку. Начинаем сначала.")
            downloaded_size = 0
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
        
        mode = 'ab' if downloaded_size > 0 else 'wb'
        total_size = downloaded_size + int(response.headers.get('content-length', 0))
        
        print(f"Скачивание: {filename}")
        print(f"Всего размер: {total_size/1024:.1f} KB")
        
        downloaded = downloaded_size
        start_time = time.time()
        
        with open(filepath, mode) as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    percent = downloaded / total_size * 100 if total_size > 0 else 0
                    elapsed = time.time() - start_time
                    speed = (downloaded - downloaded_size) / elapsed / 1024 if elapsed > 0 else 0
                    
                    print(f"\rПрогресс: {percent:.1f}% ({downloaded/1024:.1f}/{total_size/1024:.1f} KB) [{speed:.1f} KB/s]", end='')
        
        print(f"\n✓ Скачивание завершено")
        return filepath
        
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        return None


def interactive_file_selector(url: str, pattern: str = r'\.13\.raw$') -> None:
    """
    Интерактивный выбор файлов для скачивания.
    """
    files = find_raw_files_on_page(url, pattern)
    
    if not files:
        print("Файлы не найдены")
        return
    
    files_info = []
    for f in files:
        info = get_file_info(f)
        if info:
            files_info.append(info)
    
    print_files_info(files_info)
    
    print("\nВыберите файлы для скачивания:")
    print("  - Введите номера через запятую (например: 1,3,5)")
    print("  - Введите диапазон (например: 1-10)")
    print("  - Введите 'all' для скачивания всех")
    print("  - Введите 'q' для выхода")
    
    while True:
        choice = input("\nВаш выбор: ").strip().lower()
        
        if choice == 'q':
            print("Выход")
            return
        
        if choice == 'all':
            selected = files
            break
        
        try:
            if '-' in choice:
                start, end = map(int, choice.split('-'))
                indices = list(range(start - 1, min(end, len(files))))
            else:
                indices = [int(x.strip()) - 1 for x in choice.split(',')]
            
            selected = [files[i] for i in indices if 0 <= i < len(files)]
            break
            
        except (ValueError, IndexError):
            print("Некорректный ввод. Попробуйте снова.")
    
    if selected:
        print(f"\nВыбрано {len(selected)} файлов")
        download_files_batch(selected)


def find_and_download_13_raw(url: str, download: bool = True, max_files: Optional[int] = None) -> List[str]:
    """
    Комбинированная функция для поиска и скачивания файлов .13.raw.
    """
    print("\n" + "=" * 60)
    print(f"ПОИСК ФАЙЛОВ *.13.raw")
    print("=" * 60)
    
    files = find_raw_files_on_page(url, pattern=r'\.13\.raw$')
    
    if not files:
        print("Файлы не найдены")
        return []
    
    print(f"\nНайдено {len(files)} файлов:")
    
    files_info = []
    for f in files:
        info = get_file_info(f)
        if info:
            files_info.append(info)
    
    print_files_info(files_info)
    
    if download and files:
        print("\n" + "=" * 60)
        print("СКАЧИВАНИЕ ФАЙЛОВ")
        print("=" * 60)
        
        if max_files:
            files_to_download = files[:max_files]
            print(f"Скачивание первых {max_files} файлов...")
        else:
            files_to_download = files
            print(f"Скачивание всех {len(files)} файлов...")
        
        downloaded = download_files_batch(files_to_download, download_dir="raw_data_13")
        print(f"\nСкачано {len(downloaded)} файлов в директорию 'raw_data_13'")
    
    return files


# ==================== ЧАСТЬ 4: ФУНКЦИИ ДЛЯ ПАРСИНГА RAW ФАЙЛОВ ====================

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
    """
    events = []
    
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        record_size = 16
        pos = 0
        
        while pos + record_size <= len(data):
            timestamp_end1 = struct.unpack('>H', data[pos:pos+2])[0]
            pos += 2
            
            marker1 = struct.unpack('>H', data[pos:pos+2])[0]
            pos += 2
            
            if marker1 != 0x00BE:
                pos -= 3
                continue
            
            channels = []
            for _ in range(4):
                channel_data = struct.unpack('>H', data[pos:pos+2])[0]
                channels.append(channel_data)
                pos += 2
            
            timestamp_end2 = struct.unpack('>H', data[pos:pos+2])[0]
            pos += 2
            
            marker2 = struct.unpack('>H', data[pos:pos+2])[0]
            pos += 2
            
            if marker2 != 0x00FE:
                continue
            
            events.append((timestamp_end2, channels))
        
        return events
        
    except Exception as e:
        print(f"Ошибка при парсинге файла {filename}: {e}")
        return []


def get_channel_statistics(events: List[Tuple[int, List[int]]], channel_num: int) -> Dict[int, int]:
    """
    Возвращает статистику срабатываний для указанного канала по ячейкам.
    """
    if channel_num < 0 or channel_num > 3:
        raise ValueError("Channel number must be between 0 and 3")
    
    statistics = defaultdict(int)
    
    for _, channels in events:
        if channel_num < len(channels):
            channel_data = channels[channel_num]
            
            for cell in range(16):
                if channel_data & (1 << cell):
                    statistics[cell] += 1
    
    return dict(statistics)


def print_channel_statistics(stats: Dict[int, int], channel_num: int) -> None:
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


def count_channel_activations_fast(filename: str, channel_num: int) -> int:
    """
    БЫСТРЫЙ ПОДСЧЕТ: Общее количество срабатываний в указанном канале.
    """
    if channel_num < 0 or channel_num > 3:
        raise ValueError("Channel number must be between 0 and 3")
    
    count = 0
    record_size = 16
    
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        pos = 0
        data_len = len(data)
        
        while pos + record_size <= data_len:
            pos += 4
            
            for ch in range(4):
                channel_data = (data[pos] << 8) | data[pos + 1]
                
                if ch == channel_num and channel_data != 0:
                    count += 1
                pos += 2
            
            pos += 4
        
        return count
        
    except Exception as e:
        print(f"Ошибка при быстром подсчете {filename}: {e}")
        return 0


def get_channel_stats_fast(filename: str, channel_num: int) -> Tuple[int, Dict[int, int]]:
    """
    БЫСТРЫЙ ПОДСЧЕТ: Детальная статистика по каналу с разбивкой по ячейкам.
    """
    if channel_num < 0 or channel_num > 3:
        raise ValueError("Channel number must be between 0 and 3")
    
    cell_counts = [0] * 16
    total = 0
    record_size = 16
    
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        pos = 0
        data_len = len(data)
        
        while pos + record_size <= data_len:
            pos += 4
            
            for ch in range(4):
                channel_data = (data[pos] << 8) | data[pos + 1]
                
                if ch == channel_num:
                    if channel_data != 0:
                        total += 1
                        for cell in range(16):
                            if channel_data & (1 << cell):
                                cell_counts[cell] += 1
                pos += 2
            
            pos += 4
        
        stats = {i: cell_counts[i] for i in range(16) if cell_counts[i] > 0}
        return total, stats
        
    except Exception as e:
        print(f"Ошибка при быстром подсчете статистики {filename}: {e}")
        return 0, {}


# ==================== ЧАСТЬ 5: УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ====================

def download_and_analyze(url: str, pattern: str = r'\.13\.raw$', 
                        download_dir: str = "downloads",
                        channel: int = 0, max_files: Optional[int] = None,
                        quick_mode: bool = False) -> Dict[str, Any]:
    """
    УНИВЕРСАЛЬНАЯ ФУНКЦИЯ: Поиск + скачивание + анализ за один вызов.
    """
    results = {
        'found_files': [],
        'downloaded_files': [],
        'analysis': {},
        'errors': []
    }
    
    print("\n" + "=" * 70)
    print("УНИВЕРСАЛЬНЫЙ АНАЛИЗ ДАННЫХ")
    print("=" * 70)
    
    # ШАГ 1: Поиск файлов
    print(f"\n[1/4] Поиск файлов по паттерну: {pattern}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        file_pattern = r'href=["\']([^"\']*\.raw[^"\']*)["\']'
        all_files = re.findall(file_pattern, response.text, re.IGNORECASE)
        
        for filename in all_files:
            if re.search(pattern, filename, re.IGNORECASE):
                full_url = urljoin(url, filename)
                results['found_files'].append(full_url)
        
        print(f"Найдено {len(results['found_files'])} файлов")
        
        if not results['found_files']:
            print("Файлы не найдены. Завершение.")
            return results
            
    except Exception as e:
        error = f"Ошибка поиска: {e}"
        print(error)
        results['errors'].append(error)
        return results
    
    # ШАГ 2: Получение информации о файлах
    print(f"\n[2/4] Получение информации о файлах")
    files_info = []
    for file_url in results['found_files'][:5]:
        info = get_file_info(file_url)
        if info:
            files_info.append(info)
            print(f"  {info['filename']} - {info['size_str']}")
    
    if len(results['found_files']) > 5:
        print(f"  ... и еще {len(results['found_files']) - 5} файлов")
    
    # ШАГ 3: Скачивание файлов
    print(f"\n[3/4] Скачивание файлов")
    
    files_to_download = results['found_files']
    if max_files:
        files_to_download = files_to_download[:max_files]
        print(f"Скачивание первых {max_files} файлов...")
    
    if quick_mode:
        results['downloaded_files'] = quick_batch_download(
            files_to_download, 
            download_dir
        )
    else:
        results['downloaded_files'] = download_files_batch(
            files_to_download,
            download_dir,
            max_files=None,
            delay=0.5
        )
    
    print(f"Скачано {len(results['downloaded_files'])} файлов")
    
    # ШАГ 4: Анализ файлов
    print(f"\n[4/4] Анализ файлов (канал {channel})")
    
    for filepath in results['downloaded_files']:
        try:
            print(f"\nАнализ: {os.path.basename(filepath)}")
            
            if quick_mode:
                total, stats = get_channel_stats_fast(filepath, channel)
                print(f"  Всего срабатываний: {total}")
                if stats:
                    top_cells = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:3]
                    print(f"  Топ ячеек: {top_cells}")
            else:
                events = parse_data_file(filepath)
                stats = get_channel_statistics(events, channel)
                total = sum(stats.values())
                print(f"  Всего срабатываний: {total}")
                print(f"  Всего записей: {len(events)}")
                
                if stats:
                    print("  Активные ячейки (>10%):")
                    for cell in range(16):
                        count = stats.get(cell, 0)
                        if count > total * 0.1:
                            print(f"    Ячейка {cell}: {count} раз")
            
            results['analysis'][filepath] = {
                'total': total,
                'stats': stats
            }
            
        except Exception as e:
            error = f"Ошибка анализа {filepath}: {e}"
            print(f"  {error}")
            results['errors'].append(error)
    
    print("\n" + "=" * 70)
    print("АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 70)
    print(f"Найдено файлов: {len(results['found_files'])}")
    print(f"Скачано файлов: {len(results['downloaded_files'])}")
    print(f"Проанализировано: {len(results['analysis'])}")
    print(f"Ошибок: {len(results['errors'])}")
    
    return results


# ==================== ТЕСТОВАЯ ФУНКЦИЯ ====================

def test_module():
    """
    Тестирование основных функций модуля.
    """
    print("\n" + "=" * 70)
    print("ТЕСТИРОВАНИЕ МОДУЛЯ")
    print("=" * 70)
    
    # Проверка импортов
    print("\n✓ Все необходимые модули импортированы")
    print(f"✓ requests версия: {requests.__version__}")
    
    # Проверка основных функций
    test_functions = [
        quick_download,
        quick_batch_download,
        quick_find_and_download,
        find_raw_files_on_page,
        get_file_info,
        download_file,
        parse_data_file,
        count_channel_activations_fast,
        download_and_analyze
    ]
    
    for func in test_functions:
        print(f"✓ Функция {func.__name__} доступна")
    
    print("\n✓ Модуль готов к использованию")
    print("\n" + "=" * 70)


# ==================== ОСНОВНАЯ ЧАСТЬ ====================

if __name__ == "__main__":
    # Тестирование модуля
    test_module()
    
    # Пример использования (замените URL на реальный)
    TEST_URL = "http://example.com/data/"  # ЗАМЕНИТЕ НА РЕАЛЬНЫЙ URL
    
    print("\n" + "=" * 70)
    print("ПРИМЕР ИСПОЛЬЗОВАНИЯ")
    print("=" * 70)
    print("\nДля реального использования:")
    print('  results = download_and_analyze("http://ваш-сайт.com/data/", max_files=5)')
    print("\nИли для быстрого скачивания:")
    print('  files = quick_find_and_download("http://ваш-сайт.com/data/", max_files=10)')
