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

def analyze_logs(df: pd.DataFrame, by: str = "all"):
    """
    df를 분석하여 시간대별, 요일별 평균 속도 등 통계 리포트를 출력합니다.
    by: 'hourly', 'daily', 'all' 중 선택
    """
    if df is None or df.empty:
        print("No data to analyze.")
        return

    df = df.copy()
    if "timestamp" not in df.columns:
        print("'timestamp' 컬럼이 없습니다.")
        return

    df["time"] = df["timestamp"].apply(lambda t: dt.datetime.fromtimestamp(int(t)))
    df["hour"] = df["time"].dt.hour
    df["day_of_week"] = df["time"].dt.day_name()

    print("\n--- NetSpeed Analysis Report ---")

    # 전체 평균 (항상 표시)
    print("\n[Overall Average]")
    print(f"Ping: {df['ping_ms'].mean():.2f} ms")
    print(f"Download: {df['download_mbps'].mean():.2f} Mbps")
    print(f"Upload: {df['upload_mbps'].mean():.2f} Mbps")

    if by in ["hourly", "all"]:
        # 시간대별 평균
        print("\n[Hourly Average]")
        hourly_avg = df.groupby("hour")[["ping_ms", "download_mbps", "upload_mbps"]].mean()
        print(hourly_avg)

    if by in ["daily", "all"]:
        # 요일별 평균
        print("\n[Day of Week Average]")
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        daily_avg = df.groupby("day_of_week")[["ping_ms", "download_mbps", "upload_mbps"]].mean().reindex(days)
        print(daily_avg)

    print("\n--- End of Report ---")

