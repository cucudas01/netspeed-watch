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
    (기존과 동일 - 수정 없음)
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
    except Exception:
        return float("nan")

    m = re.search(r"(time|시간)\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*ms", out, re.IGNORECASE)
    if m:
        try:
            return float(m.group(2))
        except:
            pass

    for line in out.splitlines():
        low = line.lower()
        if ("min/avg/max" in low or "round-trip min/avg/max" in low) and "ms" in low:
            try:
                stats = low.split("=")[1].split("ms")[0].strip()
                avg = float(stats.split("/")[1])
                return avg
            except:
                pass

    return float("nan")


def measure_bandwidth() -> Tuple[float, float]:
    """
    (기존과 동일 - 수정 없음)
    """
    s = speedtest.Speedtest()
    s.get_best_server()
    down_bps = s.download()
    up_bps = s.upload()
    return (down_bps / 1_000_000, up_bps / 1_000_000)


def safe_measure(host: str = "8.8.8.8") -> dict: # <-- host 인자 추가
    """
    단일 측정 묶음(핑 + 대역폭). 대역폭 실패 시 NaN 기록.
    """
    ts = int(time.time())
    ping_ms = measure_ping(host=host) # <-- host 인자 전달
    try:
        down_mbps, up_mbps = measure_bandwidth()
    except speedtest.SpeedtestException: 
        down_mbps, up_mbps = float("nan"), float("nan")
    except Exception:
        down_mbps, up_mbps = float("nan"), float("nan")
        
    return {
        "timestamp": ts,
        "ping_ms": ping_ms,
        "download_mbps": down_mbps,
        "upload_mbps": up_mbps,
    }