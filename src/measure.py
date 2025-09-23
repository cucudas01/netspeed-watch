# src/measure.py
from __future__ import annotations
import subprocess
import platform
import time
import re
from typing import Tuple

import speedtest


def measure_ping(host: str = "8.8.8.8", count: int = 1, timeout_s: int = 2) -> float:
    """
    평균 지연(ms) 반환. OS 기본 ping 유틸을 호출해 결과를 파싱한다.
    - Windows 한글 로케일의 '시간=..ms'와 영어 'time=..ms' 모두 대응
    - 실패 시 float('nan') 반환
    """
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", str(count), "-w", str(timeout_s * 1000), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout_s), host]

    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        out = e.output

    # ✅ 다국어 대응: time= / 시간=  모두 인식 (예: time=12ms, 시간=12.3 ms)
    m = re.search(r"(time|시간)\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*ms", out, re.IGNORECASE)
    if m:
        try:
            return float(m.group(2))
        except:
            pass

    # macOS/Linux 요약(rtt/round-trip) 라인 파싱
    for line in out.splitlines():
        low = line.lower()
        if ("min/avg/max" in low or "round-trip min/avg/max" in low) and "ms" in low:
            try:
                stats = low.split("=")[1].split("ms")[0].strip()  # "0.032/0.045/0.050/0.000"
                avg = float(stats.split("/")[1])
                return avg
            except:
                pass

    return float("nan")


def measure_bandwidth() -> Tuple[float, float]:
    """
    Speedtest.net 기반 다운로드/업로드 속도(Mbps) 측정.
    """
    s = speedtest.Speedtest()
    s.get_best_server()
    down_bps = s.download()
    up_bps = s.upload()
    return (down_bps / 1_000_000, up_bps / 1_000_000)


def safe_measure() -> dict:
    """
    단일 측정 묶음(핑 + 대역폭). 대역폭 실패 시 NaN 기록.
    """
    ts = int(time.time())
    ping_ms = measure_ping()
    try:
        down_mbps, up_mbps = measure_bandwidth()
    except speedtest.SpeedtestException: 
        down_mbps, up_mbps = float("nan"), float("nan")
    return {
        "timestamp": ts,
        "ping_ms": ping_ms,
        "download_mbps": down_mbps,
        "upload_mbps": up_mbps,
    }

