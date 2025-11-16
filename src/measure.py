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
    (기존과 동일)
    평균 지연(ms) 반환. OS 기본 ping 유틸을 호출해 결과를 파싱한다.
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


def measure_bandwidth() -> Tuple[float, float, str]:
    """
    [수정됨] Speedtest.net 기반 다운/업로드(Mbps) 및 'IP 주소' 측정.
    """
    s = speedtest.Speedtest()
    s.get_best_server()
    down_bps = s.download()
    up_bps = s.upload()
    
    # [추가] 결과에서 클라이언트 IP 주소 가져오기
    ip_address = s.results.client['ip']
    
    return (down_bps / 1_000_000, up_bps / 1_000_000, ip_address)


def safe_measure(host: str = "8.8.8.8") -> dict:
    """
    [수정됨] 단일 측정 묶음(핑 + 대역폭 + IP).
    """
    ts = int(time.time())
    ping_ms = measure_ping(host=host)
    ip_address = "N/A" # [추가] IP 기본값
    try:
        # [수정] 3개의 반환값(down, up, ip)을 받음
        down_mbps, up_mbps, ip_address = measure_bandwidth()
    except speedtest.SpeedtestException: 
        down_mbps, up_mbps = float("nan"), float("nan")
    except Exception:
        down_mbps, up_mbps = float("nan"), float("nan")
        
    return {
        "timestamp": ts,
        "ping_ms": ping_ms,
        "download_mbps": down_mbps,
        "upload_mbps": up_mbps,
        "ip_address": ip_address # [추가] IP 주소 필드
    }