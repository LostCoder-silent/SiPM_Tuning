import csv
from datetime import datetime

class CSVLogger:
    def __init__(self, filename):
        self.filename = filename
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'param1', 'param2', 'success1', 'success2'])

    def log(self, param1, param2, success1, success2):
        with open(self.filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().isoformat(), param1, param2, success1, success2])
