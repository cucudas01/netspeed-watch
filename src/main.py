# src/main.py
from __future__ import annotations
import argparse
import time

from typing import Optional
from .storage import append_row, load_logs
from .measure import safe_measure
from .visualize import plot_logs, analyze_logs

def run_once():
    row = safe_measure()
    append_row(row)
    print(f"[OK] logged: {row}")

def run_loop(interval_sec: int, count: Optional[int] = None):
    try:
        if count:
            for i in range(count):
                print(f"[{i + 1}/{count}] ", end="")
                run_once()
                if i < count - 1:  # 마지막 실행 후에는 대기하지 않음
                    time.sleep(interval_sec)
            print("Finished.")
        else:
            while True:
                run_once()
                time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    p = argparse.ArgumentParser(description="NetSpeed Watch CLI")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="Measure once and append to CSV")
    g.add_argument("--loop", type=int, help="Measure every N seconds (e.g., 300)")
    g.add_argument("--plot", action="store_true", help="Generate charts from CSV")
    g.add_argument("--analyze", nargs='?', const='all', choices=['hourly', 'daily', 'all'],
                   help="Analyze logs. Specify 'hourly' or 'daily' for specific reports.")
    p.add_argument("--count", type=int, help="Number of times to measure with --loop. Runs indefinitely if not specified.")
    args = p.parse_args()

    if args.count and not args.loop:
        p.error("--count can only be used with --loop.")

    if args.once:
        run_once()
    elif args.loop:
        if args.loop <= 0:
            p.error("--loop must be a positive integer (seconds)")
        if args.count and args.count <= 0:
            p.error("--count must be a positive integer")
        run_loop(args.loop, args.count)
    elif args.plot:
        df = load_logs()
        plot_logs(df, show=True)
    elif args.analyze:
        df = load_logs()
        analyze_logs(df, by=args.analyze)
    else:
        p.print_help()

if __name__ == "__main__":
    main()