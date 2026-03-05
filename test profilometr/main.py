#!/usr/bin/env python3
"""
Точка входа в приложение для автоматического перебора параметров профилометра через Modbus.
Загружает конфигурацию, инициализирует графический интерфейс и запускает главный цикл.
"""

import sys
import argparse
import json
import os
from gui import ModbusExperimentGUI
import tkinter as tk

def parse_arguments():
    """Разбор аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Управление экспериментом Modbus')
    parser.add_argument('-c', '--config', default='config.json',
                        help='Путь к файлу конфигурации (по умолчанию config.json)')
    return parser.parse_args()

def load_config(config_path):
    """Загрузка и проверка конфигурационного файла"""
    if not os.path.exists(config_path):
        print(f"Ошибка: файл конфигурации {config_path} не найден.")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON: {e}")
        sys.exit(1)
    
    # Проверка наличия обязательных полей
    required_sections = ['port', 'baudrate', 'device_address', 'register_1', 'register_2',
                         'range_1', 'range_2']
    missing = [sec for sec in required_sections if sec not in config]
    if missing:
        print(f"В конфигурации отсутствуют обязательные поля: {missing}")
        sys.exit(1)
    
    # Проверка наличия полей в диапазонах
    for r in ['range_1', 'range_2']:
        for field in ['min', 'max', 'step']:
            if field not in config[r]:
                print(f"В разделе {r} отсутствует поле {field}")
                sys.exit(1)
    
    return config

def main():
    args = parse_arguments()
    config = load_config(args.config)
    
    # Создаём корневое окно Tkinter
    root = tk.Tk()
    
    # Передаём путь к конфигу в GUI, чтобы он мог его загрузить и при необходимости сохранять
    app = ModbusExperimentGUI(root, config_path=args.config)
    
    # Устанавливаем обработчик закрытия окна
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Запускаем главный цикл
    root.mainloop()

if __name__ == "__main__":
    main()
