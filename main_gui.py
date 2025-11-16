# netspeed-watch/main_gui.py
import sys
import os
import time
from pathlib import Path 
import re 

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

try:
    # [수정] delete_log 임포트
    from src.storage import append_row, load_logs, delete_log
    from src.measure import safe_measure
    from src.visualize import plot_logs, analyze_logs
except ImportError:
    messagebox.showerror(
        "모듈 임포트 오류", 
        "'src' 폴더에서 모듈을 불러오는 데 실패했습니다.\n"
        "main_gui.py 파일이 'src' 폴더와 같은 위치(최상위 폴더)에 있는지 확인하세요."
    )
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


class NetSpeedApp:
    PLACEHOLDER_HOST = "8.8.8.8 (기본: Google 서버)" 
    PLACEHOLDER_COLOR = "grey"
    
    def __init__(self, root):
        self.root = root
        self.root.title("NetSpeed Watch v2.3 (IP Analysis)")
        self.root.geometry("500x550") 

        self.measure_thread = None
        self.loop_thread = None
        self.stop_event = threading.Event() 

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 0. 설정 프레임 (기존과 동일) ---
        config_frame = ttk.LabelFrame(main_frame, text="설정 (Options)", padding="10")
        config_frame.pack(fill=tk.X, pady=5)
        config_frame.columnconfigure(1, weight=1) 

        self.style = ttk.Style(self.root)
        self.style.configure("Placeholder.TEntry", foreground=self.PLACEHOLDER_COLOR)
        
        ttk.Label(config_frame, text="핑 대상 (Host):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.host_entry = ttk.Entry(config_frame)
        self.host_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        
        self._set_host_placeholder() 
        self.host_entry.bind("<FocusIn>", self._on_host_focus_in)
        self.host_entry.bind("<FocusOut>", self._on_host_focus_out)
        
        ttk.Label(config_frame, text="IP 필터 (Analyze):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.ip_entry = ttk.Entry(config_frame)
        self.ip_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        self.ip_entry.insert(0, "(비워두면 전체 분석)")
        self.ip_entry.config(style="Placeholder.TEntry")
        self.ip_entry.bind("<FocusIn>", self._on_ip_focus_in)
        self.ip_entry.bind("<FocusOut>", self._on_ip_focus_out)
        

        # --- 1. 1회 측정 (기존과 동일) ---
        self.measure_button = ttk.Button(
            main_frame,
            text="속도 측정 시작 (1회)",
            command=self.start_measure_thread
        )
        self.measure_button.pack(pady=5, fill=tk.X)

        # --- 구분선 (기존과 동일) ---
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        # --- 2. 자동 측정 (Loop) (기존과 동일) ---
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
        self.start_loop_button = ttk.Button(loop_button_frame, text="자동 측정 시작", command=self.start_loop_thread)
        self.start_loop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.stop_loop_button = ttk.Button(loop_button_frame, text="자동 측정 중지", command=self.stop_loop_thread, state=tk.DISABLED)
        self.stop_loop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # --- 3. 분석 도구 (수정됨) ---
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
        
        # [추가] 삭제 버튼
        self.delete_button = ttk.Button(
            analysis_frame,
            text="로그 삭제 (Delete)",
            command=self.run_delete_log # 신규 핸들러 연결
        )
        self.delete_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)


        # --- 4. 상태 및 로그 출력 (기존과 동일) ---
        self.status_label = ttk.Label(main_frame, text="대기 중...")
        self.status_label.pack(pady=5)
        self.result_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.result_text.pack(pady=5, fill=tk.BOTH, expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- 플레이스홀더 헬퍼 함수 (기존과 동일) ---
    def _set_host_placeholder(self):
        self.host_entry.insert(0, self.PLACEHOLDER_HOST)
        self.host_entry.config(style="Placeholder.TEntry")

    def _on_host_focus_in(self, event):
        if self.host_entry.get() == self.PLACEHOLDER_HOST:
            self.host_entry.delete(0, tk.END)
            self.host_entry.config(style="TEntry") 

    def _on_host_focus_out(self, event):
        if not self.host_entry.get():
            self._set_host_placeholder()

    def _on_ip_focus_in(self, event):
        if self.ip_entry.get() == "(비워두면 전체 분석)":
            self.ip_entry.delete(0, tk.END)
            self.ip_entry.config(style="TEntry")
    
    def _on_ip_focus_out(self, event):
        if not self.ip_entry.get():
            self.ip_entry.insert(0, "(비워두면 전체 분석)")
            self.ip_entry.config(style="Placeholder.TEntry")

    # --- 입력값 getter 헬퍼 함수 (기존과 동일) ---
    def get_host(self) -> str:
        text = self.host_entry.get()
        if text == self.PLACEHOLDER_HOST or not text:
            return "8.8.8.8"
        return text 
    
    def get_ip_filter(self) -> str | None:
        text = self.ip_entry.get()
        if text == "(비워두면 전체 분석)" or not text:
            return None
        return text 

    def on_closing(self):
        # ... (기존과 동일) ...
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
        # ... (기존과 동일) ...
        if self.root.winfo_exists():
            self.result_text.config(state=tk.NORMAL)
            self.result_text.insert(tk.END, message + "\n")
            self.result_text.see(tk.END) 
            self.result_text.config(state=tk.DISABLED)

    def _lock_ui_for_measurement(self, is_looping=False):
        """ [수정됨] 삭제 버튼 비활성화 """
        self.host_entry.config(state=tk.DISABLED)
        self.ip_entry.config(state=tk.DISABLED)
        
        self.measure_button.config(state=tk.DISABLED)
        self.plot_button.config(state=tk.DISABLED)
        self.analyze_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED) # [추가]
        
        if is_looping:
            self.start_loop_button.config(state=tk.DISABLED)
            self.stop_loop_button.config(state=tk.NORMAL)
            self.interval_entry.config(state=tk.DISABLED)
            self.count_entry.config(state=tk.DISABLED)
        else:
            self.start_loop_button.config(state=tk.DISABLED)
            self.stop_loop_button.config(state=tk.DISABLED)

    def _unlock_ui(self):
        """ [수정됨] 삭제 버튼 활성화 """
        if not self.root.winfo_exists():
            return
            
        self.host_entry.config(state=tk.NORMAL)
        if not self.host_entry.get():
            self._set_host_placeholder()
            
        self.ip_entry.config(state=tk.NORMAL)
        if not self.ip_entry.get():
            self._on_ip_focus_out(None)
        
        self.measure_button.config(state=tk.NORMAL)
        self.plot_button.config(state=tk.NORMAL)
        self.analyze_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL) # [추가]
        
        self.start_loop_button.config(state=tk.NORMAL)
        self.stop_loop_button.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.NORMAL)
        self.count_entry.config(state=tk.NORMAL)
        
        self.status_label.config(text="대기 중...")
        self.loop_thread = None
        self.measure_thread = None

    # --- 1. 1회 측정 로직 (기존과 동일) ---
    def start_measure_thread(self):
        self._lock_ui_for_measurement()
        host = self.get_host() 
        log_path = get_log_path_for_host(host)
        self.status_label.config(text=f"측정 중... (대상: {host})")
        self.measure_thread = threading.Thread(target=self.run_measure_once_worker, args=(host, log_path))
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

    # --- 2. 자동 측정 로직 (기존과 동일) ---
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
        host = self.get_host() 
        log_path = get_log_path_for_host(host)
        self.status_label.config(text=f"자동 측정 시작됨... (대상: {host})")
        self.loop_thread = threading.Thread(target=self.run_loop_worker, args=(interval_sec, count if count > 0 else None, host, log_path))
        self.loop_thread.daemon = True
        self.loop_thread.start()

    def run_loop_worker(self, interval_sec, count, host: str, log_path: Path):
        # ... (기존과 동일) ...
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
        # ... (기존과 동일) ...
        if self.loop_thread and self.loop_thread.is_alive():
            self.stop_event.set()
            self.stop_loop_button.config(state=tk.DISABLED)
            self.status_label.config(text="자동 측정 중지 중...")

    # --- 3. 분석 도구 로직 (기존과 동일) ---
    def run_plot(self):
        # ... (기존과 동일) ...
        self.status_label.config(text="그래프 생성 중...")
        host = self.get_host()
        log_path = get_log_path_for_host(host) 
        
        try:
            df = load_logs(log_path=log_path) 
            if df is None or df.empty:
                self._update_result_text(f"[{log_path.name}] 표시할 데이터가 없습니다.")
            else:
                plot_logs(df, show=True, host=host) 
        except Exception as e:
            self._update_result_text(f"[오류] {e}")
        self.status_label.config(text="대기 중...")

    def run_analyze(self):
        # ... (기존과 동일) ...
        self.status_label.config(text="로그 분석 중...")
        host = self.get_host()
        log_path = get_log_path_for_host(host)
        ip_filter = self.get_ip_filter() 

        try:
            df = load_logs(log_path=log_path) 
            if df is None or df.empty:
                self._update_result_text(f"[{log_path.name}] 분석할 데이터가 없습니다.")
                self.status_label.config(text="대기 중...")
                return

            f = io.StringIO()
            with redirect_stdout(f):
                analyze_logs(df, by='all', ip=ip_filter) 
            analysis_result = f.getvalue() 

            filename = f"{log_path.name}"
            if ip_filter:
                filename += f" (IP: {ip_filter})"
            
            self.show_analysis_window(analysis_result, filename)
            self._update_result_text(f"[{log_path.name}] 분석 결과(새 창)를 확인하세요.")
        except Exception as e:
            self._update_result_text(f"[오류] {e}")
            
        self.status_label.config(text="대기 중...")

    def show_analysis_window(self, content, filename=""):
        # ... (기존과 동일) ...
        top = tk.Toplevel(self.root)
        top.title(f"분석 리포트 ({filename})") 
        top.geometry("600x600")
        
        txt_area = scrolledtext.ScrolledText(top, wrap=tk.WORD, font=("Consolas", 10))
        txt_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt_area.insert(tk.INSERT, content)
        txt_area.config(state=tk.DISABLED)
        top.transient(self.root) 
        top.grab_set() 

    # --- [신규 함수 추가] ---
    def run_delete_log(self):
        """ '로그 삭제' 버튼 핸들러 """
        host = self.get_host()
        log_path = get_log_path_for_host(host)
        
        if not log_path.exists():
            messagebox.showinfo("알림", f"삭제할 로그 파일이 없습니다:\n{log_path.name}")
            return
            
        # 사용자에게 삭제 확인
        if messagebox.askyesno("삭제 확인", 
                               f"정말로 '{log_path.name}' 파일을 영구적으로 삭제하시겠습니까?\n"
                               "(이 작업은 되돌릴 수 없습니다)"):
            try:
                delete_log(log_path)
                self._update_result_text(f"[알림] '{log_path.name}' 파일을 삭제했습니다.")
            except Exception as e:
                messagebox.showerror("삭제 오류", f"파일 삭제 중 오류가 발생했습니다:\n{e}")
                self._update_result_text(f"[오류] '{log_path.name}' 파일 삭제 실패: {e}")


if __name__ == "__main__":
    main_root = tk.Tk()
    app = NetSpeedApp(main_root)
    main_root.mainloop()