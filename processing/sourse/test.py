import http_file
import parse_file   

add = 'http://10.163.1.148/runs/raw/2025/251217-18/'
filename = 'temp.raw'


filesList = http_file.find_raw_files_on_page(add)

for i in filesList:
    print('________________________________________________________')
    print(i)
    http_file.quick_get(i, filename)
    actived = parse_file.count_channel_activations_fast(filename, 0)
    print('________________________________________________________')
    print(actived)
    print('________________________________________________________')
    input()
    total, stats = parse_file.get_channel_stats_fast(filename, 0)
    print(f"Всего срабатываний: {total}")
    print("По ячейкам:")
    for cell in range(16):
        count = stats.get(cell, 0)
        if count > 0:
            print(f"  Ячейка {cell}: {count} раз")
    input()
