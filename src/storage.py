# src/storage.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_PATH = DATA_DIR / "logs.csv"


def append_row(row: Dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([row])
    if not LOG_PATH.exists():
        df.to_csv(LOG_PATH, index=False)
    else:
        df.to_csv(LOG_PATH, mode="a", header=False, index=False)


def load_logs() -> Optional[pd.DataFrame]:
    if not LOG_PATH.exists():
        return None
    return pd.read_csv(LOG_PATH)
