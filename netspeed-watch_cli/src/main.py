# netspeed-watch_cli/src/main.py
from __future__ import annotations
import argparse
import time
import sys 
from typing import Optional
from pathlib import Path
import re 

try:
    # [수정] delete_log 임포트
    from .storage import append_row, load_logs, delete_log
    from .measure import safe_measure
    from .visualize import plot_logs, analyze_logs
except ImportError:
    print("ImportError: .으로 시작하는 상대 경로 임포트에 실패했습니다.")
    print("프로젝트 최상위(src 폴더의 부모)에서 'python -m src.main'으로 실행하세요.")
    sys.exit(1)

if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path.cwd()

DATA_DIR = ROOT / "data"

def get_log_path_for_host(host: str) -> Path:
    """(기존과 동일) 호스트 이름을 기반으로 .csv 파일 경로를 생성합니다."""
    safe_filename = re.sub(r'[^\w\.-]', '_', host)
    return DATA_DIR / f"logs_{safe_filename}.csv"


def run_once(host: str, log_path: Path):
    """ (기존과 동일) """
    print(f"측정 중... (핑 대상: {host}, 평균 1분 소요)")
    row = safe_measure(host=host)
    
    try:
        append_row(row, log_path=log_path)
        print(f"[OK] logged to {log_path.name}: {row}")
    except Exception as e:
        print(f"[ERROR] CSV 저장 실패 ({log_path.name}): {e}")

def run_loop(interval_sec: int, count: Optional[int], host: str, log_path: Path):
    """ (기존과 동일) """
    try:
        if count:
            for i in range(count):
                print(f"[{i + 1}/{count}] ", end="")
                run_once(host=host, log_path=log_path)
                if i < count - 1:
                    print(f"{interval_sec}초 후 다음 측정을 시작합니다.")
                    time.sleep(interval_sec)
            print("Finished.")
        else:
            print("자동 측정을 시작합니다. (중지하려면 Ctrl+C)")
            while True:
                run_once(host=host, log_path=log_path)
                print(f"{interval_sec}초 후 다음 측정을 시작합니다.")
                time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    """ [수정됨] --delete-log 옵션 추가 """
    p = argparse.ArgumentParser(description="NetSpeed Watch CLI")
    
    g = p.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="Measure once and append to CSV")
    g.add_argument("--loop", type=int, help="Measure every N seconds (e.g., 300)")
    g.add_argument("--plot", action="store_true", help="Generate charts from CSV")
    g.add_argument("--analyze", nargs='?', const='all', choices=['hourly', 'daily', 'all'],
                   help="Analyze logs. Specify 'hourly' or 'daily' for specific reports.")
    # [추가] 삭제 옵션
    g.add_argument("--delete-log", action="store_true", 
                   help="Delete the log file for the specified --host.")

    
    s = p.add_argument_group("Configuration Options")
    s.add_argument("--host", type=str, default="8.8.8.8",
                   help="Host to ping for latency check (default: 8.8.8.8). This determines the log filename.")
    s.add_argument("--count", type=int, help="Number of times to measure with --loop. Runs indefinitely if not specified.")
    s.add_argument("--ip", type=str, 
                   help="Filter analysis by a specific IP address (e.g., --analyze --ip 123.45.67.89)")

    args = p.parse_args()
    
    host = args.host
    log_path = get_log_path_for_host(host)

    if args.count and not args.loop:
        p.error("--count can only be used with --loop.")

    if args.once:
        run_once(host=host, log_path=log_path)
    elif args.loop:
        if args.loop <= 0:
            p.error("--loop must be a positive integer (seconds)")
        if args.count and args.count <= 0:
            p.error("--count must be a positive integer")
        run_loop(args.loop, args.count, host=host, log_path=log_path)
    elif args.plot:
        print(f"로그 파일({log_path.name})을 불러와 그래프를 생성합니다...")
        df = load_logs(log_path=log_path)
        plot_logs(df, show=True, host=host)
    elif args.analyze:
        print(f"로그 파일({log_path.name})을 불러와 리포트를 생성합니다...")
        df = load_logs(log_path=log_path)
        analyze_logs(df, by=args.analyze, ip=args.ip)
        
    # [추가] 삭제 로직
    elif args.delete_log:
        if not log_path.exists():
            print(f"삭제할 로그 파일이 없습니다: {log_path.name}")
            return

        try:
            # 사용자 확인
            confirm = input(f"정말로 '{log_path.name}' 파일을 삭제하시겠습니까? (y/n): ")
            if confirm.lower() == 'y':
                delete_log(log_path)
                print(f"'{log_path.name}' 파일을 삭제했습니다.")
            else:
                print("삭제를 취소했습니다.")
        except KeyboardInterrupt:
            print("\n삭제를 취소했습니다.")

    else:
        p.print_help()

if __name__ == "__main__":
    main()