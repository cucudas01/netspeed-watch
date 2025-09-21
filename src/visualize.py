# src/visualize.py
from __future__ import annotations
import os
from pathlib import Path
import datetime as dt

# GUI 없는 서버에서도 저장 가능하도록 Agg 백엔드 사용
import matplotlib
if os.environ.get("DISPLAY", "") == "":
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def plot_logs(df: pd.DataFrame, save_dir: Path | None = None, show: bool = True):
    """
    df를 시간축 기준으로 정렬하여 ping/download/upload 각각 라인 차트 생성.
    - save_dir 지정 시 PNG 저장 (기본: data/plots/)
    - show=True이고 GUI가 있으면 plt.show()도 호출
    """
    if df is None or df.empty:
        print("No data to plot.")
        return

    df = df.copy()
    print('DataFrame columns:', df.columns)
    if "timestamp" not in df.columns:
        print("'timestamp' 컬럼이 없습니다. 실제 컬럼명을 확인하세요.")
        return
    df["time"] = df["timestamp"].apply(lambda t: dt.datetime.fromtimestamp(int(t)))
    df = df.sort_values("time")

    if save_dir is None:
        save_dir = Path(__file__).resolve().parent.parent / "data" / "plots"
    _ensure_dir(save_dir)

    metrics = [
        ("ping_ms", "Ping (ms)"),
        ("download_mbps", "Download (Mbps)"),
        ("upload_mbps", "Upload (Mbps)"),
    ]

    outputs = []
    for col, title in metrics:
        if col not in df.columns:
            continue
        plt.figure()
        plt.plot(df["time"], df[col])
        plt.title(title)
        plt.xlabel("Time")
        plt.ylabel(title)
        plt.tight_layout()

        out = save_dir / f"{col}.png"
        plt.savefig(out)

        outputs.append(out)
        if matplotlib.get_backend().lower() != "agg" and show:
            plt.show()
        plt.close()

    if outputs:
        print("Saved plots:")
        for p in outputs:
            print(f" - {p}")
