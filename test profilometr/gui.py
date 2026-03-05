import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import threading
from experiment_runner import ExperimentRunner
from logger import CSVLogger
import os

class ModbusExperimentGUI:
    def __init__(self, root, config_path='config.json'):
        self.root = root
        self.config_path = config_path
        self.config = self.load_config()
        self.root.title("Modbus Experiment Controller")
        self.root.geometry("800x600")
        
        self.config_path = config_path
        self.config = self.load_config()
        self.runner = None
        self.logger = None
        
        self.create_widgets()
        self.protocol = None  # для after callback
        
    def load_config(self):
        """Загрузка конфигурации из JSON"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Ошибка", f"Файл конфигурации {self.config_path} не найден")
            return {}
        except json.JSONDecodeError:
            messagebox.showerror("Ошибка", f"Файл конфигурации {self.config_path} содержит ошибки")
            return {}
    
    def save_config(self):
        """Сохранение текущих настроек в конфиг (опционально)"""
        # Обновляем self.config из полей ввода
        try:
            self.config['port'] = self.port_entry.get()
            self.config['baudrate'] = int(self.baudrate_entry.get())
            self.config['device_address'] = int(self.device_addr_entry.get())
            self.config['register_1'] = int(self.reg1_entry.get())
            self.config['register_2'] = int(self.reg2_entry.get())
            self.config['range_1']['min'] = int(self.range1_min_entry.get())
            self.config['range_1']['max'] = int(self.range1_max_entry.get())
            self.config['range_1']['step'] = int(self.range1_step_entry.get())
            self.config['range_2']['min'] = int(self.range2_min_entry.get())
            self.config['range_2']['max'] = int(self.range2_max_entry.get())
            self.config['range_2']['step'] = int(self.range2_step_entry.get())
            self.config['delay_between_writes'] = float(self.delay_entry.get())
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", str(e))
    
    def create_widgets(self):
        # Основной фрейм с настройками
        settings_frame = ttk.LabelFrame(self.root, text="Параметры подключения и диапазоны", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=5)
        
        # Строка 1: порт, скорость, адрес
        row1 = ttk.Frame(settings_frame)
        row1.pack(fill='x', pady=2)
        ttk.Label(row1, text="Порт:").pack(side='left')
        self.port_entry = ttk.Entry(row1, width=15)
        self.port_entry.insert(0, self.config.get('port', '/dev/ttyUSB0'))
        self.port_entry.pack(side='left', padx=5)
        
        ttk.Label(row1, text="Скорость:").pack(side='left')
        self.baudrate_entry = ttk.Entry(row1, width=10)
        self.baudrate_entry.insert(0, str(self.config.get('baudrate', 9600)))
        self.baudrate_entry.pack(side='left', padx=5)
        
        ttk.Label(row1, text="Адрес устройства:").pack(side='left')
        self.device_addr_entry = ttk.Entry(row1, width=5)
        self.device_addr_entry.insert(0, str(self.config.get('device_address', 1)))
        self.device_addr_entry.pack(side='left', padx=5)
        
        # Строка 2: регистры
        row2 = ttk.Frame(settings_frame)
        row2.pack(fill='x', pady=2)
        ttk.Label(row2, text="Регистр параметра 1:").pack(side='left')
        self.reg1_entry = ttk.Entry(row2, width=8)
        self.reg1_entry.insert(0, str(self.config.get('register_1', 100)))
        self.reg1_entry.pack(side='left', padx=5)
        
        ttk.Label(row2, text="Регистр параметра 2:").pack(side='left')
        self.reg2_entry = ttk.Entry(row2, width=8)
        self.reg2_entry.insert(0, str(self.config.get('register_2', 101)))
        self.reg2_entry.pack(side='left', padx=5)
        
        ttk.Label(row2, text="Задержка (с):").pack(side='left')
        self.delay_entry = ttk.Entry(row2, width=5)
        self.delay_entry.insert(0, str(self.config.get('delay_between_writes', 1.0)))
        self.delay_entry.pack(side='left', padx=5)
        
        # Диапазон 1
        range1_frame = ttk.LabelFrame(settings_frame, text="Диапазон параметра 1")
        range1_frame.pack(fill='x', pady=5)
        row3 = ttk.Frame(range1_frame)
        row3.pack(fill='x')
        ttk.Label(row3, text="Мин:").pack(side='left')
        self.range1_min_entry = ttk.Entry(row3, width=8)
        self.range1_min_entry.insert(0, str(self.config['range_1']['min']))
        self.range1_min_entry.pack(side='left', padx=2)
        ttk.Label(row3, text="Макс:").pack(side='left')
        self.range1_max_entry = ttk.Entry(row3, width=8)
        self.range1_max_entry.insert(0, str(self.config['range_1']['max']))
        self.range1_max_entry.pack(side='left', padx=2)
        ttk.Label(row3, text="Шаг:").pack(side='left')
        self.range1_step_entry = ttk.Entry(row3, width=8)
        self.range1_step_entry.insert(0, str(self.config['range_1']['step']))
        self.range1_step_entry.pack(side='left', padx=2)
        
        # Диапазон 2
        range2_frame = ttk.LabelFrame(settings_frame, text="Диапазон параметра 2")
        range2_frame.pack(fill='x', pady=5)
        row4 = ttk.Frame(range2_frame)
        row4.pack(fill='x')
        ttk.Label(row4, text="Мин:").pack(side='left')
        self.range2_min_entry = ttk.Entry(row4, width=8)
        self.range2_min_entry.insert(0, str(self.config['range_2']['min']))
        self.range2_min_entry.pack(side='left', padx=2)
        ttk.Label(row4, text="Макс:").pack(side='left')
        self.range2_max_entry = ttk.Entry(row4, width=8)
        self.range2_max_entry.insert(0, str(self.config['range_2']['max']))
        self.range2_max_entry.pack(side='left', padx=2)
        ttk.Label(row4, text="Шаг:").pack(side='left')
        self.range2_step_entry = ttk.Entry(row4, width=8)
        self.range2_step_entry.insert(0, str(self.config['range_2']['step']))
        self.range2_step_entry.pack(side='left', padx=2)
        
        # Кнопка сохранения конфига (опционально)
        ttk.Button(settings_frame, text="Сохранить настройки", command=self.save_config).pack(pady=5)
        
        # Фрейм для текущих значений и прогресса
        status_frame = ttk.LabelFrame(self.root, text="Текущее состояние", padding=10)
        status_frame.pack(fill='x', padx=10, pady=5)
        
        # Текущие значения параметров
        row5 = ttk.Frame(status_frame)
        row5.pack(fill='x', pady=2)
        ttk.Label(row5, text="Параметр 1:").pack(side='left')
        self.current_val1 = tk.StringVar(value="—")
        ttk.Label(row5, textvariable=self.current_val1, font=('Arial', 12, 'bold')).pack(side='left', padx=10)
        
        ttk.Label(row5, text="Параметр 2:").pack(side='left')
        self.current_val2 = tk.StringVar(value="—")
        ttk.Label(row5, textvariable=self.current_val2, font=('Arial', 12, 'bold')).pack(side='left', padx=10)
        
        # Прогресс
        row6 = ttk.Frame(status_frame)
        row6.pack(fill='x', pady=5)
        ttk.Label(row6, text="Прогресс:").pack(side='left')
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(row6, variable=self.progress_var, maximum=100, length=300)
        self.progress_bar.pack(side='left', padx=10)
        
        self.progress_label = ttk.Label(row6, text="0/0")
        self.progress_label.pack(side='left')
        
        # Количество записей
        row7 = ttk.Frame(status_frame)
        row7.pack(fill='x', pady=2)
        ttk.Label(row7, text="Записей в логе:").pack(side='left')
        self.log_count = tk.StringVar(value="0")
        ttk.Label(row7, textvariable=self.log_count).pack(side='left', padx=5)
        
        # Кнопки управления
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="Старт", command=self.start_experiment)
        self.start_btn.pack(side='left', padx=5)
        
        self.pause_btn = ttk.Button(control_frame, text="Пауза", command=self.pause_experiment, state='disabled')
        self.pause_btn.pack(side='left', padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Стоп", command=self.stop_experiment, state='disabled')
        self.stop_btn.pack(side='left', padx=5)
        
        # Текстовый лог сообщений
        log_frame = ttk.LabelFrame(self.root, text="Лог событий", padding=5)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state='normal')
        self.log_text.pack(fill='both', expand=True)
        
        # Строка для выбора файла лога
        file_frame = ttk.Frame(self.root)
        file_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(file_frame, text="Файл лога:").pack(side='left')
        self.log_file_entry = ttk.Entry(file_frame)
        self.log_file_entry.insert(0, self.config.get('log_file', 'data/log.csv'))
        self.log_file_entry.pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(file_frame, text="Обзор", command=self.browse_log_file).pack(side='left')
    
    def browse_log_file(self):
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if filename:
            self.log_file_entry.delete(0, tk.END)
            self.log_file_entry.insert(0, filename)
    
    def log_message(self, msg):
        """Добавление сообщения в лог-текст"""
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
    
    def update_progress(self, current, total, v1, v2, success1, success2):
        """Callback для обновления GUI из потока эксперимента"""
        # Используем after для безопасного вызова из другого потока
        self.root.after(0, self._do_update_progress, current, total, v1, v2, success1, success2)
    
    def _do_update_progress(self, current, total, v1, v2, success1, success2):
        self.current_val1.set(str(v1))
        self.current_val2.set(str(v2))
        if total > 0:
            percent = int(100 * current / total)
            self.progress_var.set(percent)
            self.progress_label.config(text=f"{current}/{total}")
        self.log_count.set(str(current))  # или можно хранить отдельно счетчик записей в логе
        # Можно также выводить сообщение об успехе/ошибке в лог событий
        status1 = "✓" if success1 else "✗"
        status2 = "✓" if success2 else "✗"
        self.log_message(f"Запись {current}/{total}: П1={v1}{status1}, П2={v2}{status2}")
    
    def start_experiment(self):
        """Запуск эксперимента"""
        # Проверяем, не запущен ли уже
        if self.runner and self.runner.is_alive():
            messagebox.showwarning("Предупреждение", "Эксперимент уже запущен")
            return
        
        # Создаём логгер
        log_filename = self.log_file_entry.get().strip()
        if not log_filename:
            messagebox.showerror("Ошибка", "Укажите файл для лога")
            return
        # Создаем директорию, если не существует
        os.makedirs(os.path.dirname(log_filename), exist_ok=True)
        self.logger = CSVLogger(log_filename)
        
        # Обновляем конфиг из полей ввода (чтобы runner использовал актуальные значения)
        self.save_config()
        
        # Создаём и запускаем поток эксперимента
        self.runner = ExperimentRunner(self.config, self.logger, gui_callback=self.update_progress)
        self.runner.start()
        
        # Обновляем состояние кнопок
        self.start_btn.config(state='disabled')
        self.pause_btn.config(state='normal', text='Пауза')
        self.stop_btn.config(state='normal')
        
        self.log_message("Эксперимент запущен")
    
    def pause_experiment(self):
        """Обработка паузы/продолжения"""
        if not self.runner or not self.runner.is_alive():
            return
        
        if self.runner.is_paused():
            self.runner.resume()
            self.pause_btn.config(text='Пауза')
            self.log_message("Эксперимент продолжен")
        else:
            self.runner.pause()
            self.pause_btn.config(text='Продолжить')
            self.log_message("Эксперимент приостановлен")
    
    def stop_experiment(self):
        """Остановка эксперимента"""
        if self.runner and self.runner.is_alive():
            self.runner.stop()
            # Ждем завершения потока (не блокируя GUI)
            self.root.after(100, self.check_stopped)
        else:
            self.reset_controls()
    
    def check_stopped(self):
        """Периодическая проверка завершения потока"""
        if self.runner and self.runner.is_alive():
            self.root.after(100, self.check_stopped)
        else:
            self.log_message("Эксперимент остановлен")
            self.reset_controls()
    
    def reset_controls(self):
        """Возврат кнопок в исходное состояние"""
        self.start_btn.config(state='normal')
        self.pause_btn.config(state='disabled', text='Пауза')
        self.stop_btn.config(state='disabled')
        self.runner = None
    
    def on_closing(self):
        """Обработка закрытия окна"""
        if self.runner and self.runner.is_alive():
            self.runner.stop()
            self.runner.join(timeout=2)
        self.root.destroy()

def main():
    root = tk.Tk()
    app = ModbusExperimentGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
