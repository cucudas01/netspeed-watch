# main_gui.py
import sys
import os
import time
from pathlib import Path 

# PyInstaller --windowed mode 'fileno' 오류 해결용 패치
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from contextlib import redirect_stdout
import io

# 'src' 폴더에서 핵심 로직들을 임포트
try:
    from src.storage import append_row, load_logs, DEFAULT_LOG_PATH
    from src.measure import safe_measure
    from src.visualize import plot_logs, analyze_logs
except ImportError:
    messagebox.showerror(
        "모듈 임포트 오류", 
        "'src' 폴더에서 모듈을 불러오는 데 실패했습니다.\n"
        "main_gui.py 파일이 'src' 폴더와 같은 위치(최상위 폴더)에 있는지 확인하세요."
    )
    sys.exit(1)

class NetSpeedApp:
    # --- 플레이스홀더 상수 정의 ---
    PLACEHOLDER_HOST = "8.8.8.8 (기본: Google 서버)"
    PLACEHOLDER_COLOR = "grey"
    
    def __init__(self, root):
        self.root = root
        self.root.title("NetSpeed Watch v2.1 (Configurable)")
        self.root.geometry("500x550") 

        # --- 스레드 제어용 변수 ---
        self.measure_thread = None
        self.loop_thread = None
        self.stop_event = threading.Event() 

        # --- 메인 프레임 ---
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 0. 설정 프레임 (수정됨) ---
        config_frame = ttk.LabelFrame(main_frame, text="설정 (Options)", padding="10")
        config_frame.pack(fill=tk.X, pady=5)
        config_frame.columnconfigure(1, weight=1) 

        # --- 플레이스홀더 스타일 설정 ---
        self.style = ttk.Style(self.root)
        # 'Placeholder.TEntry'라는 새 스타일 정의
        self.style.configure("Placeholder.TEntry", foreground=self.PLACEHOLDER_COLOR)
        
        ttk.Label(config_frame, text="핑 대상 (Host):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.host_entry = ttk.Entry(config_frame)
        self.host_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        # 기본값 insert 대신 플레이스홀더 설정 함수 호출
        self._set_host_placeholder() 
        # 이벤트 바인딩
        self.host_entry.bind("<FocusIn>", self._on_host_focus_in)
        self.host_entry.bind("<FocusOut>", self._on_host_focus_out)
        
        ttk.Label(config_frame, text="로그 파일 (Output):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.log_path_entry = ttk.Entry(config_frame)
        self.log_path_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        self.log_path_entry.insert(0, str(DEFAULT_LOG_PATH)) 

        # --- 1. 1회 측정 ---
        self.measure_button = ttk.Button(
            main_frame,
            text="속도 측정 시작 (1회)",
            command=self.start_measure_thread
        )
        self.measure_button.pack(pady=5, fill=tk.X)

        # --- 구분선 ---
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        # --- 2. 자동 측정 (Loop) ---
        loop_frame = ttk.LabelFrame(main_frame, text="자동 측정 (Loop)", padding="10")
        loop_frame.pack(fill=tk.X)

        controls_frame = ttk.Frame(loop_frame)
        controls_frame.pack(fill=tk.X)
        
        ttk.Label(controls_frame, text="측정 간격(초):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.interval_entry = ttk.Entry(controls_frame, width=10)
        self.interval_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.interval_entry.insert(0, "300") 

        ttk.Label(controls_frame, text="측정 횟수(0=무제한):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.count_entry = ttk.Entry(controls_frame, width=10)
        self.count_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        self.count_entry.insert(0, "0") 

        loop_button_frame = ttk.Frame(loop_frame)
        loop_button_frame.pack(fill=tk.X, pady=5)

        self.start_loop_button = ttk.Button(
            loop_button_frame,
            text="자동 측정 시작",
            command=self.start_loop_thread
        )
        self.start_loop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.stop_loop_button = ttk.Button(
            loop_button_frame,
            text="자동 측정 중지",
            command=self.stop_loop_thread,
            state=tk.DISABLED
        )
        self.stop_loop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)


        # --- 3. 분석 도구 ---
        analysis_frame = ttk.Frame(main_frame)
        analysis_frame.pack(fill=tk.X, pady=10)
        
        self.plot_button = ttk.Button(
            analysis_frame,
            text="그래프 보기 (Plot)",
            command=self.run_plot
        )
        self.plot_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.analyze_button = ttk.Button(
            analysis_frame,
            text="로그 분석 (Analyze)",
            command=self.run_analyze
        )
        self.analyze_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # --- 4. 상태 및 로그 출력 ---
        self.status_label = ttk.Label(main_frame, text="대기 중...")
        self.status_label.pack(pady=5)

        self.result_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.result_text.pack(pady=5, fill=tk.BOTH, expand=True)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- 플레이스홀더 헬퍼 함수 (신규) ---
    def _set_host_placeholder(self):
        """ 호스트 입력창을 플레이스홀더 상태로 설정합니다. """
        self.host_entry.insert(0, self.PLACEHOLDER_HOST)
        self.host_entry.config(style="Placeholder.TEntry")

    def _on_host_focus_in(self, event):
        """ 호스트 입력창에 포커스가 가면 플레이스홀더를 제거합니다. """
        if self.host_entry.get() == self.PLACEHOLDER_HOST:
            self.host_entry.delete(0, tk.END)
            self.host_entry.config(style="TEntry") # 기본 스타일로 복원

    def _on_host_focus_out(self, event):
        """ 호스트 입력창에서 포커스가 나오고 비어있으면 플레이스홀더를 복원합니다. """
        if not self.host_entry.get():
            self._set_host_placeholder()

    # --- 입력값 getter 헬퍼 함수 (수정됨) ---
    def get_host(self) -> str:
        """ 호스트 입력창의 값을 읽어옵니다. 플레이스홀더 상태면 기본값을 반환합니다. """
        text = self.host_entry.get()
        # 플레이스홀더거나 비어있으면 실제 기본값 8.8.8.8 반환
        if text == self.PLACEHOLDER_HOST or not text:
            return "8.8.8.8"
        return text # 사용자가 입력한 값 반환

    def get_log_path(self) -> Path:
        try:
            p = Path(self.log_path_entry.get())
            return p
        except Exception:
            return DEFAULT_LOG_PATH 

    def on_closing(self):
        if self.loop_thread and self.loop_thread.is_alive():
            if messagebox.askyesno("확인", "자동 측정이 실행 중입니다. 종료하시겠습니까?"):
                self.stop_loop_thread()
                self.root.destroy()
            else:
                return 
        self.root.destroy()

    def _update_status(self, message):
        self.status_label.config(text=message)

    def _update_result_text(self, message):
        if self.root.winfo_exists():
            self.result_text.config(state=tk.NORMAL)
            self.result_text.insert(tk.END, message + "\n")
            self.result_text.see(tk.END) 
            self.result_text.config(state=tk.DISABLED)

    def _lock_ui_for_measurement(self, is_looping=False):
        self.host_entry.config(state=tk.DISABLED)
        self.log_path_entry.config(state=tk.DISABLED)
        
        self.measure_button.config(state=tk.DISABLED)
        self.plot_button.config(state=tk.DISABLED)
        self.analyze_button.config(state=tk.DISABLED)
        
        if is_looping:
            self.start_loop_button.config(state=tk.DISABLED)
            self.stop_loop_button.config(state=tk.NORMAL)
            self.interval_entry.config(state=tk.DISABLED)
            self.count_entry.config(state=tk.DISABLED)
        else:
            self.start_loop_button.config(state=tk.DISABLED)
            self.stop_loop_button.config(state=tk.DISABLED)

    def _unlock_ui(self):
        if not self.root.winfo_exists():
            return
            
        self.host_entry.config(state=tk.NORMAL)
        # 작업 완료 후에도 비어있으면 플레이스홀더 복원 (수정됨)
        if not self.host_entry.get():
            self._set_host_placeholder()
            
        self.log_path_entry.config(state=tk.NORMAL)

        self.measure_button.config(state=tk.NORMAL)
        self.plot_button.config(state=tk.NORMAL)
        self.analyze_button.config(state=tk.NORMAL)
        
        self.start_loop_button.config(state=tk.NORMAL)
        self.stop_loop_button.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.NORMAL)
        self.count_entry.config(state=tk.NORMAL)
        
        self.status_label.config(text="대기 중...")
        self.loop_thread = None
        self.measure_thread = None

    # --- 1. 1회 측정 로직 (수정됨) ---
    def start_measure_thread(self):
        self._lock_ui_for_measurement()
        
        host = self.get_host() # 수정된 get_host 사용
        log_path = self.get_log_path()
        
        self.status_label.config(text=f"측정 중... (대상: {host})")

        self.measure_thread = threading.Thread(
            target=self.run_measure_once_worker,
            args=(host, log_path) 
        )
        self.measure_thread.daemon = True
        self.measure_thread.start()

    def run_measure_once_worker(self, host: str, log_path: Path):
        try:
            row = safe_measure(host=host) 
            append_row(row, log_path=log_path) 
            result_message = f"[측정 완료] {row}"
        except Exception as e:
            result_message = f"[오류 발생] {e}"
        
        self.root.after(0, self.update_gui_after_measure, result_message)

    def update_gui_after_measure(self, result_message):
        self._update_result_text(result_message)
        self._unlock_ui()

    # --- 2. 자동 측정 로직 (수정됨) ---
    def start_loop_thread(self):
        try:
            interval_sec = int(self.interval_entry.get())
            count = int(self.count_entry.get())
            
            if interval_sec <= 0:
                messagebox.showerror("입력 오류", "측정 간격은 0보다 커야 합니다.")
                return
            if count < 0:
                messagebox.showerror("입력 오류", "측정 횟수는 0 이상이어야 합니다.")
                return
        except ValueError:
            messagebox.showerror("입력 오류", "간격과 횟수는 숫자여야 합니다.")
            return

        self.stop_event.clear() 
        self._lock_ui_for_measurement(is_looping=True)
        
        host = self.get_host() # 수정된 get_host 사용
        log_path = self.get_log_path()
        
        self.status_label.config(text=f"자동 측정 시작됨... (대상: {host})")

        self.loop_thread = threading.Thread(
            target=self.run_loop_worker,
            args=(interval_sec, count if count > 0 else None, host, log_path)
        )
        self.loop_thread.daemon = True
        self.loop_thread.start()

    def run_loop_worker(self, interval_sec, count, host: str, log_path: Path):
        i = 0
        while not self.stop_event.is_set():
            i += 1
            
            count_str = f"{i}/{count}" if count else f"{i}회"
            self.root.after(0, self._update_status, f"자동 측정 중... ({count_str})")
            
            try:
                row = safe_measure(host=host)
                append_row(row, log_path=log_path)
                self.root.after(0, self._update_result_text, f"[자동 측정 {i}회] {row}")
            except Exception as e:
                self.root.after(0, self._update_result_text, f"[자동 측정 오류] {e}")

            if count and i >= count:
                self.root.after(0, self._update_status, f"자동 측정 완료 ({count}회).")
                break
            
            wait_time = 0
            while wait_time < interval_sec and not self.stop_event.is_set():
                time.sleep(1) 
                wait_time += 1
                
                remaining = interval_sec - wait_time
                if remaining > 0 and not self.stop_event.is_set():
                     self.root.after(0, self._update_status, f"다음 측정까지 {remaining}초...")

        if self.stop_event.is_set():
            self.root.after(0, self._update_status, "자동 측정이 중지되었습니다.")
        
        self.root.after(0, self._unlock_ui) 

    def stop_loop_thread(self):
        if self.loop_thread and self.loop_thread.is_alive():
            self.stop_event.set()
            self.stop_loop_button.config(state=tk.DISABLED)
            self.status_label.config(text="자동 측정 중지 중...")

    # --- 3. 분석 도구 로직 (기존과 동일) ---
    def run_plot(self):
        self.status_label.config(text="그래프 생성 중...")
        log_path = self.get_log_path() 
        
        try:
            df = load_logs(log_path=log_path) 
            if df is None or df.empty:
                self._update_result_text(f"[{log_path.name}] 표시할 데이터가 없습니다.")
            else:
                plot_logs(df, show=True) 
                self._update_result_text("[알림] 그래프 창을 확인하세요. (그래프 창을 닫아야 프로그램이 다시 반응합니다)")
        except Exception as e:
            self._update_result_text(f"[오류] {e}")
        self.status_label.config(text="대기 중...")

    def run_analyze(self):
        self.status_label.config(text="로그 분석 중...")
        log_path = self.get_log_path() 

        try:
            df = load_logs(log_path=log_path) 
            if df is None or df.empty:
                self._update_result_text(f"[{log_path.name}] 분석할 데이터가 없습니다.")
                self.status_label.config(text="대기 중...")
                return

            f = io.StringIO()
            with redirect_stdout(f):
                analyze_logs(df, by='all') 
            analysis_result = f.getvalue() 

            self.show_analysis_window(analysis_result, log_path.name) 
            self._update_result_text(f"[{log_path.name}] 분석 결과(새 창)를 확인하세요.")
        except Exception as e:
            self._update_result_text(f"[오류] {e}")
            
        self.status_label.config(text="대기 중...")

    def show_analysis_window(self, content, filename=""):
        top = tk.Toplevel(self.root)
        top.title(f"분석 리포트 ({filename})") 
        top.geometry("600x600")
        
        txt_area = scrolledtext.ScrolledText(top, wrap=tk.WORD, font=("Consolas", 10))
        txt_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt_area.insert(tk.INSERT, content)
        txt_area.config(state=tk.DISABLED)
        top.transient(self.root) 
        top.grab_set() 


if __name__ == "__main__":
    main_root = tk.Tk()
    app = NetSpeedApp(main_root)
    main_root.mainloop()