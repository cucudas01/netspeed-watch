# src/storage.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict
import pandas as pd
import csv



ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_PATH = DATA_DIR / "logs.csv"


def append_row(row: Dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = LOG_PATH.exists()
    
    with open(LOG_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader() # 파일이 없으면 헤더 작성
        writer.writerow(row)


def load_logs() -> Optional[pd.DataFrame]:
    if not LOG_PATH.exists():
        return None
    return pd.read_csv(LOG_PATH)
