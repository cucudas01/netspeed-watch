# src/storage.py
from __future__ import annotations
from pathlib import Path, PurePath
from typing import Optional, Dict
import pandas as pd
import sys
import csv

if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path.cwd()

DATA_DIR = ROOT / "data"
# 기본 로그 경로를 상수로 정의
DEFAULT_LOG_PATH = DATA_DIR / "logs.csv"

def append_row(row: Dict, log_path: Path = DEFAULT_LOG_PATH):
    """
    지정된 log_path에 한 행을 추가합니다.
    """
    # DATA_DIR 대신 log_path.parent를 기준으로 디렉토리 생성
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = log_path.exists()
    
    with open(log_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader() # 파일이 없으면 헤더 작성
        writer.writerow(row)


def load_logs(log_path: Path = DEFAULT_LOG_PATH) -> Optional[pd.DataFrame]:
    """
    지정된 log_path에서 로그를 불러옵니다.
    """
    if not log_path.exists():
        # 로그 파일이 없을 때 사용자에게 명확히 알려줌
        print(f"로그 파일을 찾을 수 없습니다: {log_path}")
        return None
    
    try:
        return pd.read_csv(log_path)
    except pd.errors.EmptyDataError:
        # 파일은 있지만 비어있을 경우
        print(f"로그 파일이 비어있습니다: {log_path}")
        return None
    except Exception as e:
        print(f"로그 파일 로드 중 오류 발생: {e}")
        return None