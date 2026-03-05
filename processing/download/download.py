from http_file import download_files_by_range

downloaded = download_files_by_range(
    csv_path="log.csv",
    base_url="http://10.163.1.148/runs/raw/",
    year="2026",
    timestamp_column="timestamp",  # или 0
    download_dir="./raw_files",
    resume=True,
    monitor=False,          # или True для постоянного отслеживания
    max_files=None          # скачать все
)
