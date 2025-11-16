# netspeed-watch_cli/src/visualize.py
from __future__ import annotations
import os
import sys
from pathlib import Path
import datetime as dt
import re 

import matplotlib
if os.environ.get("DISPLAY", "") == "":
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def plot_logs(df: pd.DataFrame, save_dir: Path | None = None, show: bool = True, host: str | None = None):
    """
    (기존과 동일 - 'host' 기반 저장)
    """
    if df is None or df.empty:
        print("No data to plot.")
        return

    df = df.copy()
    
    if "timestamp" not in df.columns:
        print("'timestamp' 컬럼이 없습니다. 실제 컬럼명을 확인하세요.")
        return
        
    df["time"] = df["timestamp"].apply(lambda t: dt.datetime.fromtimestamp(int(t)))
    df = df.sort_values("time")

    if save_dir is None:
        if getattr(sys, 'frozen', False):
            ROOT = Path(sys.executable).parent
        else:
            ROOT = Path.cwd()
        save_dir = ROOT / "data" / "plots"

    if host:
        safe_host_dir = re.sub(r'[^\w\.-]', '_', host)
        save_dir = save_dir / safe_host_dir
        
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
        plt.grid(True)
        plt.tight_layout()

        out = save_dir / f"{col}.png"
        plt.savefig(out)

        outputs.append(out)
        if matplotlib.get_backend().lower() != "agg" and show:
            plt.show()
        plt.close()

    if outputs:
        print(f"Saved plots to: {save_dir.resolve()}")
        for p in outputs:
            print(f" - {p.name}")

def analyze_logs(df: pd.DataFrame, by: str = "all", ip: str | None = None):
    """
    [수정됨] df를 분석, 'ip'가 제공되면 해당 IP로 필터링 후 리포트 출력
    """
    if df is None or df.empty:
        print("No data to analyze.")
        return

    df = df.copy()
    
    # --- [추가] IP 필터링 로직 ---
    if "ip_address" not in df.columns:
        print("\n[알림] 'ip_address' 컬럼이 로그에 없습니다. (이전 버전 로그)")
        if ip:
            print(f"[오류] 'ip_address' 컬럼이 없어 {ip}로 필터링할 수 없습니다.")
            return
    else:
        # IP가 명시된 경우, 필터링 수행
        if ip:
            available_ips = df['ip_address'].unique()
            if ip not in available_ips:
                print(f"\n[오류] IP {ip}를 로그에서 찾을 수 없습니다.")
                print(f"사용 가능한 IP: {available_ips}")
                return
            
            print(f"\n--- [필터 적용됨] IP: {ip} ---")
            df = df[df['ip_address'] == ip] # IP로 필터링
        else:
            # IP가 명시되진 않았지만, 컬럼이 존재할 경우, 사용 가능한 IP 목록 표시
            available_ips = df['ip_address'].dropna().unique()
            if len(available_ips) > 1:
                print(f"\n[알림] 이 로그에는 여러 IP가 있습니다: {available_ips}")
                print("   (특정 IP만 보려면 --ip 옵션을 사용하세요)")
    # --- [여기까지 추가] ---


    if df is None or df.empty:
        print("필터링 결과 데이터가 없습니다.")
        return

    if "timestamp" not in df.columns:
        print("'timestamp' 컬럼이 없습니다.")
        return
    
    # (이하 기존 분석 로직)
    df["time"] = df["timestamp"].apply(lambda t: dt.datetime.fromtimestamp(int(t)))
    df["hour"] = df["time"].dt.hour
    df["day_of_week"] = df["time"].dt.day_name()

    print("\n--- NetSpeed Analysis Report ---")

    print("\n[Overall Average]")
    print(f"Total Measurements: {len(df)}")
    print(f"Ping: {df['ping_ms'].mean():.2f} ms")
    print(f"Download: {df['download_mbps'].mean():.2f} Mbps")
    print(f"Upload: {df['upload_mbps'].mean():.2f} Mbps")

    print("\n[참고: 일반적인 인터넷 상품별 속도 기준 (대칭형 기준)]")
    print("---------------------------------------------------------")
    print("| 상품명       | 다운로드/업로드 (Mbps) | 핑 (ms)      |")
    print("---------------------------------------------------------")
    print("| 100M 광랜    | 80 - 100             | 1 - 10       |")
    print("| 500M 기가라이트| 400 - 500           | 1 - 5        |")
    print("| 1G 기가      | 850 - 950            | 1 - 5        |")
    print("---------------------------------------------------------")

    if by in ["hourly", "all"]:
        print("\n[Hourly Average]")
        hourly_avg = df.groupby("hour")[["ping_ms", "download_mbps", "upload_mbps"]].mean()
        print(hourly_avg.to_string()) 

    if by in ["daily", "all"]:
        print("\n[Day of Week Average]")
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        daily_avg = df.groupby("day_of_week")[["ping_ms", "download_mbps", "upload_mbps"]].mean().reindex(days)
        print(daily_avg.to_string())

    print("\n--- End of Report ---")