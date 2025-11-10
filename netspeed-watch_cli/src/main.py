# src/main.py
from __future__ import annotations
import argparse
import time
import sys 
from typing import Optional
from pathlib import Path # Path 객체 사용을 위해 추가

# GUI와 분리하기 위해 .storage, .measure, .visualize를 명시적으로 사용
try:
    # storage에서 DEFAULT_LOG_PATH를 임포트하여 기본값으로 사용
    from .storage import append_row, load_logs, DEFAULT_LOG_PATH
    from .measure import safe_measure
    from .visualize import plot_logs, analyze_logs
except ImportError:
    # (python -m src.main으로 실행하지 않고)
    # (src 폴더 내에서 python main.py로 실행한 경우)
    print("ImportError: .으로 시작하는 상대 경로 임포트에 실패했습니다.")
    print("프로젝트 최상위(src 폴더의 부모)에서 'python -m src.main'으로 실행하세요.")
    sys.exit(1)


def run_once(host: str, log_path: Path):
    """ 1회 측정 및 저장을 실행합니다. """
    print(f"측정 중... (핑 대상: {host}, 평균 1분 소요)")
    # safe_measure에 host 인자 전달
    row = safe_measure(host=host)
    
    try:
        # append_row에 log_path 인자 전달
        append_row(row, log_path=log_path)
        print(f"[OK] logged to {log_path.name}: {row}")
    except Exception as e:
        print(f"[ERROR] CSV 저장 실패 ({log_path.name}): {e}")

def run_loop(interval_sec: int, count: Optional[int], host: str, log_path: Path):
    """ 주기적 측정을 실행합니다. """
    try:
        if count:
            for i in range(count):
                print(f"[{i + 1}/{count}] ", end="")
                # run_once에 host와 log_path 전달
                run_once(host=host, log_path=log_path)
                if i < count - 1:  # 마지막 실행 후에는 대기하지 않음
                    print(f"{interval_sec}초 후 다음 측정을 시작합니다.")
                    time.sleep(interval_sec)
            print("Finished.")
        else:
            print("자동 측정을 시작합니다. (중지하려면 Ctrl+C)")
            while True:
                # run_once에 host와 log_path 전달
                run_once(host=host, log_path=log_path)
                print(f"{interval_sec}초 후 다음 측정을 시작합니다.")
                time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    """ CLI 명령어를 파싱하고 해당 기능을 실행합니다. """
    p = argparse.ArgumentParser(description="NetSpeed Watch CLI")
    
    # --- 실행 모드 그룹 ---
    g = p.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="Measure once and append to CSV")
    g.add_argument("--loop", type=int, help="Measure every N seconds (e.g., 300)")
    g.add_argument("--plot", action="store_true", help="Generate charts from CSV")
    g.add_argument("--analyze", nargs='?', const='all', choices=['hourly', 'daily', 'all'],
                   help="Analyze logs. Specify 'hourly' or 'daily' for specific reports.")
    
    # --- 설정 옵션 그룹 ---
    s = p.add_argument_group("Configuration Options")
    s.add_argument("--host", type=str, default="8.8.8.8",
                   help="Host to ping for latency check (default: 8.8.8.8)")
    s.add_argument("--output", type=Path, default=DEFAULT_LOG_PATH,
                   help=f"Path to the CSV log file (default: {DEFAULT_LOG_PATH})")
    s.add_argument("--count", type=int, help="Number of times to measure with --loop. Runs indefinitely if not specified.")

    args = p.parse_args()
    
    # --output으로 받은 경로를 log_path 변수로 사용
    log_path = args.output

    if args.count and not args.loop:
        p.error("--count can only be used with --loop.")

    if args.once:
        run_once(host=args.host, log_path=log_path)
    elif args.loop:
        if args.loop <= 0:
            p.error("--loop must be a positive integer (seconds)")
        if args.count and args.count <= 0:
            p.error("--count must be a positive integer")
        run_loop(args.loop, args.count, host=args.host, log_path=log_path)
    elif args.plot:
        print(f"로그 파일({log_path.name})을 불러와 그래프를 생성합니다...")
        # load_logs에 log_path 전달
        df = load_logs(log_path=log_path)
        plot_logs(df, show=True)
    elif args.analyze:
        print(f"로그 파일({log_path.name})을 불러와 리포트를 생성합니다...")
        # load_logs에 log_path 전달
        df = load_logs(log_path=log_path)
        analyze_logs(df, by=args.analyze)
    else:
        p.print_help()

if __name__ == "__main__":
    main()