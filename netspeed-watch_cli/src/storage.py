# src/storage.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict
import pandas as pd
import sys
import csv
import os # <--- [추가] 파일 삭제를 위해 import

if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path.cwd()

DATA_DIR = ROOT / "data"

def append_row(row: Dict, log_path: Path):
    """
    (기존과 동일)
    지정된 log_path에 한 행을 추가합니다.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = log_path.exists()
    
    with open(log_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader() 
        writer.writerow(row)


def load_logs(log_path: Path) -> Optional[pd.DataFrame]:
    """
    (기존과 동일)
    지정된 log_path에서 로그를 불러옵니다.
    """
    if not log_path.exists():
        print(f"로그 파일을 찾을 수 없습니다: {log_path}")
        return None
    
    try:
        return pd.read_csv(log_path)
    except pd.errors.EmptyDataError:
        print(f"로그 파일이 비어있습니다: {log_path}")
        return None
    except Exception as e:
        print(f"로그 파일 로드 중 오류 발생: {e}")
        return None

# --- [신규 함수 추가] ---
def delete_log(log_path: Path) -> bool:
    """
    지정된 log_path의 파일을 삭제합니다.
    성공하면 True, 파일이 없으면 False를 반환합니다.
    """
    if log_path.exists():
        try:
            os.remove(log_path)
            return True
        except Exception as e:
            print(f"[ERROR] 파일 삭제 중 오류 발생: {e}")
            return False
    else:
        # 파일이 원래 없었음
        return False
# --- [여기까지 추가] ---