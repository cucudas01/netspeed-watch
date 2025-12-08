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

# --- 시스템 트레이 라이브러리 ---
try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("모듈 누락", "pystray와 Pillow 모듈이 필요합니다.\n'pip install -r requirements.txt'를 실행하세요.")
    sys.exit(1)

try:
    from src.storage import append_row, load_logs, delete_log
    from src.measure import safe_measure
    from src.visualize import plot_logs, analyze_logs
except ImportError:
    messagebox.showerror("모듈 임포트 오류", "'src' 폴더를 찾을 수 없습니다.")
    sys.exit(1)

if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path.cwd()

DATA_DIR = ROOT / "data"

def get_log_path_for_host(host: str) -> Path:
    safe_filename = re.sub(r'[^\w\.-]', '_', host)
    return DATA_DIR / f"logs_{safe_filename}.csv"


class NetSpeedApp:
    # 색상 및 폰트 설정
    COLOR_BG = "#f0f0f0"
    COLOR_PRIMARY = "#0078d7" # 윈도우 블루
    COLOR_WHITE = "#ffffff"
    FONT_MAIN = ("Segoe UI", 10)
    FONT_BOLD = ("Segoe UI", 10, "bold")
    FONT_TITLE = ("Segoe UI", 12, "bold")
    
    PLACEHOLDER_HOST = "8.8.8.8 (기본: Google 서버)" 
    PLACEHOLDER_COLOR = "grey"
    
    def __init__(self, root):
        self.root = root
        self.root.title("NetSpeed Watch v3.0 (Modern UI)")
        self.root.geometry("520x680")
        self.root.configure(bg=self.COLOR_BG)

        self.measure_thread = None
        self.loop_thread = None
        self.stop_event = threading.Event() 
        self.tray_icon = None
        self.is_minimized = False

        # --- 스타일 설정 ---
        self.style = ttk.Style()
        self.style.theme_use('clam') # 깔끔한 테마
        
        # 공통 스타일
        self.style.configure("TFrame", background=self.COLOR_BG)
        self.style.configure("TLabel", background=self.COLOR_BG, font=self.FONT_MAIN)
        self.style.configure("TLabelframe", background=self.COLOR_BG, font=self.FONT_BOLD)
        self.style.configure("TLabelframe.Label", background=self.COLOR_BG, font=self.FONT_BOLD, foreground=self.COLOR_PRIMARY)
        
        # 버튼 스타일
        self.style.configure("TButton", font=self.FONT_MAIN, padding=6)
        self.style.map("TButton", background=[("active", "#e1e1e1")])
        
        # 강조 버튼 (Accent)
        self.style.configure("Accent.TButton", font=self.FONT_BOLD, foreground="white", background=self.COLOR_PRIMARY)
        self.style.map("Accent.TButton", background=[("active", "#005a9e")])

        # 체크박스
        self.style.configure("TCheckbutton", background=self.COLOR_BG, font=self.FONT_MAIN)

        # --- 메인 컨테이너 ---
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 1. 설정 섹션 ---
        config_frame = ttk.LabelFrame(main_frame, text="⚙️ 측정 설정", padding="15")
        config_frame.pack(fill=tk.X, pady=(0, 15))
        config_frame.columnconfigure(1, weight=1) 

        # 핑 대상
        ttk.Label(config_frame, text="핑 대상 (Host):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.host_entry = ttk.Entry(config_frame, font=self.FONT_MAIN)
        self.host_entry.grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=5)
        self._set_host_placeholder()
        self.host_entry.bind("<FocusIn>", self._on_host_focus_in)
        self.host_entry.bind("<FocusOut>", self._on_host_focus_out)

        # IP 필터
        ttk.Label(config_frame, text="IP 필터 (분석용):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.ip_entry = ttk.Entry(config_frame, font=self.FONT_MAIN)
        self.ip_entry.grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=5)
        self.ip_entry.insert(0, "(비워두면 전체 분석)")
        self.ip_entry.config(foreground=self.PLACEHOLDER_COLOR)
        self.ip_entry.bind("<FocusIn>", self._on_ip_focus_in)
        self.ip_entry.bind("<FocusOut>", self._on_ip_focus_out)

        # 트레이 옵션
        self.tray_var = tk.BooleanVar(value=True)
        self.tray_check = ttk.Checkbutton(
            config_frame, 
            text="창 닫기(X) 시 트레이로 숨기기 (백그라운드 실행)", 
            variable=self.tray_var
        )
        self.tray_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))

        # --- 2. 실행 섹션 (1회 / 반복) ---
        action_frame = ttk.LabelFrame(main_frame, text="🚀 측정 실행", padding="15")
        action_frame.pack(fill=tk.X, pady=(0, 15))

        # 1회 측정 버튼 (강조 스타일)
        self.measure_button = ttk.Button(
            action_frame,
            text="⚡ 즉시 속도 측정 (1회)",
            style="Accent.TButton",
            command=self.start_measure_thread
        )
        self.measure_button.pack(fill=tk.X, pady=(0, 10))

        ttk.Separator(action_frame, orient='horizontal').pack(fill='x', pady=10)

        # 자동 측정 설정
        loop_ctrl_frame = ttk.Frame(action_frame)
        loop_ctrl_frame.pack(fill=tk.X)
        
        ttk.Label(loop_ctrl_frame, text="간격(초):").pack(side=tk.LEFT)
        self.interval_entry = ttk.Entry(loop_ctrl_frame, width=8, justify="center", font=self.FONT_MAIN)
        self.interval_entry.pack(side=tk.LEFT, padx=5)
        self.interval_entry.insert(0, "300")

        ttk.Label(loop_ctrl_frame, text="횟수(0=무제한):").pack(side=tk.LEFT, padx=(10, 0))
        self.count_entry = ttk.Entry(loop_ctrl_frame, width=8, justify="center", font=self.FONT_MAIN)
        self.count_entry.pack(side=tk.LEFT, padx=5)
        self.count_entry.insert(0, "0")

        # 자동 측정 버튼 그룹
        loop_btn_frame = ttk.Frame(action_frame)
        loop_btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_loop_button = ttk.Button(
            loop_btn_frame, text="▶ 자동 측정 시작", command=self.start_loop_thread
        )
        self.start_loop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        self.stop_loop_button = ttk.Button(
            loop_btn_frame, text="⏹ 중지", command=self.stop_loop_thread, state=tk.DISABLED
        )
        self.stop_loop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # --- 3. 분석 및 관리 ---
        manage_frame = ttk.Frame(main_frame)
        manage_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.plot_button = ttk.Button(manage_frame, text="📈 그래프", command=self.run_plot)
        self.plot_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        self.analyze_button = ttk.Button(manage_frame, text="📊 분석 리포트", command=self.run_analyze)
        self.analyze_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.delete_button = ttk.Button(manage_frame, text="🗑️ 로그 삭제", command=self.run_delete_log)
        self.delete_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # --- 4. 로그 섹션 ---
        log_frame = ttk.LabelFrame(main_frame, text="📝 실행 로그", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(log_frame, text="준비 완료", foreground="#666666")
        self.status_label.pack(anchor=tk.W, pady=(0, 5))

        self.result_text = scrolledtext.ScrolledText(
            log_frame, height=8, state=tk.DISABLED, font=("Consolas", 9),
            bg="white", relief="flat", padx=5, pady=5
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        
        # 윈도우 설정
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.run_tray_icon()

    # --- 트레이 아이콘 ---
    def _create_icon_image(self):
        image = Image.new('RGB', (64, 64), color=(0, 0, 0))
        dc = ImageDraw.Draw(image)
        dc.rectangle((0, 0, 64, 64), fill=self.COLOR_PRIMARY) 
        dc.rectangle((16, 16, 48, 48), fill="white")
        return image

    def run_tray_icon(self):
        def setup_tray(icon): icon.visible = True
        def on_open_click(icon, item): self.root.after(0, self.show_window)
        def on_exit_click(icon, item): self.root.after(0, self.quit_app)

        image = self._create_icon_image()
        menu = (item('열기 (Open)', on_open_click, default=True), item('종료 (Exit)', on_exit_click))
        self.tray_icon = pystray.Icon("NetSpeedWatch", image, "NetSpeed Watch", menu)
        threading.Thread(target=self.tray_icon.run, args=(setup_tray,), daemon=True).start()

    def show_window(self):
        self.root.deiconify()
        self.is_minimized = False

    def quit_app(self):
        if self.tray_icon: self.tray_icon.stop()
        if self.loop_thread and self.loop_thread.is_alive(): self.stop_event.set()
        self.root.destroy()
        sys.exit(0)

    # --- 플레이스홀더 로직 ---
    def _set_host_placeholder(self):
        self.host_entry.insert(0, self.PLACEHOLDER_HOST)
        self.host_entry.config(foreground=self.PLACEHOLDER_COLOR)
    def _on_host_focus_in(self, event):
        if self.host_entry.get() == self.PLACEHOLDER_HOST:
            self.host_entry.delete(0, tk.END)
            self.host_entry.config(foreground="black")
    def _on_host_focus_out(self, event):
        if not self.host_entry.get():
            self._set_host_placeholder()
    def _on_ip_focus_in(self, event):
        if self.ip_entry.get() == "(비워두면 전체 분석)":
            self.ip_entry.delete(0, tk.END)
            self.ip_entry.config(foreground="black")
    def _on_ip_focus_out(self, event):
        if not self.ip_entry.get():
            self.ip_entry.insert(0, "(비워두면 전체 분석)")
            self.ip_entry.config(foreground=self.PLACEHOLDER_COLOR)

    # --- Getters ---
    def get_host(self) -> str:
        text = self.host_entry.get()
        if text == self.PLACEHOLDER_HOST or not text: return "8.8.8.8"
        return text 
    def get_ip_filter(self) -> str | None:
        text = self.ip_entry.get()
        if text == "(비워두면 전체 분석)" or not text: return None
        return text 

    # --- UI 제어 ---
    def on_closing(self):
        if self.tray_var.get():
            self.root.withdraw()
            self.is_minimized = True
            if self.tray_icon:
                try: self.tray_icon.notify("백그라운드에서 실행 중입니다.", "NetSpeed Watch")
                except: pass
        else:
            if self.loop_thread and self.loop_thread.is_alive():
                if messagebox.askyesno("확인", "측정 중입니다. 종료하시겠습니까?"): self.quit_app()
            else:
                self.quit_app()

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
        self.ip_entry.config(state=tk.DISABLED)
        self.measure_button.config(state=tk.DISABLED)
        self.plot_button.config(state=tk.DISABLED)
        self.analyze_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        if is_looping:
            self.start_loop_button.config(state=tk.DISABLED)
            self.stop_loop_button.config(state=tk.NORMAL)
            self.interval_entry.config(state=tk.DISABLED)
            self.count_entry.config(state=tk.DISABLED)
        else:
            self.start_loop_button.config(state=tk.DISABLED)
            self.stop_loop_button.config(state=tk.DISABLED)

    def _unlock_ui(self):
        if not self.root.winfo_exists(): return
        self.host_entry.config(state=tk.NORMAL)
        if not self.host_entry.get(): self._set_host_placeholder()
        self.ip_entry.config(state=tk.NORMAL)
        if not self.ip_entry.get(): self._on_ip_focus_out(None)
        
        self.measure_button.config(state=tk.NORMAL)
        self.plot_button.config(state=tk.NORMAL)
        self.analyze_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL)
        self.start_loop_button.config(state=tk.NORMAL)
        self.stop_loop_button.config(state=tk.DISABLED)
        self.interval_entry.config(state=tk.NORMAL)
        self.count_entry.config(state=tk.NORMAL)
        self.status_label.config(text="대기 중...")
        self.loop_thread = None
        self.measure_thread = None

    # --- 기능 연결 ---
    def start_measure_thread(self):
        self._lock_ui_for_measurement()
        host = self.get_host() 
        log_path = get_log_path_for_host(host)
        self._update_status(f"🚀 측정 시작... (대상: {host})")
        self.measure_thread = threading.Thread(target=self.run_measure_once_worker, args=(host, log_path))
        self.measure_thread.daemon = True
        self.measure_thread.start()

    def run_measure_once_worker(self, host: str, log_path: Path):
        try:
            row = safe_measure(host=host) 
            append_row(row, log_path=log_path) 
            result_message = f"[완료] Ping:{row.get('ping_ms')}ms, Down:{row.get('download_mbps'):.1f}M, Up:{row.get('upload_mbps'):.1f}M"
        except Exception as e:
            result_message = f"[오류] {e}"
        self.root.after(0, self.update_gui_after_measure, result_message)

    def update_gui_after_measure(self, result_message):
        self._update_result_text(result_message)
        self._unlock_ui()

    def start_loop_thread(self):
        try:
            interval_sec = int(self.interval_entry.get())
            count = int(self.count_entry.get())
            if interval_sec <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("입력 오류", "간격과 횟수는 올바른 숫자여야 합니다.")
            return

        self.stop_event.clear() 
        self._lock_ui_for_measurement(is_looping=True)
        host = self.get_host() 
        log_path = get_log_path_for_host(host)
        self._update_status(f"🔄 자동 측정 중... (대상: {host})")
        self.loop_thread = threading.Thread(target=self.run_loop_worker, args=(interval_sec, count if count > 0 else None, host, log_path))
        self.loop_thread.daemon = True
        self.loop_thread.start()

    def run_loop_worker(self, interval_sec, count, host: str, log_path: Path):
        i = 0
        while not self.stop_event.is_set():
            i += 1
            count_str = f"{i}/{count}" if count else f"{i}회"
            self.root.after(0, self._update_status, f"🔄 자동 측정 진행 중 ({count_str})")
            try:
                row = safe_measure(host=host)
                append_row(row, log_path=log_path)
                msg = f"[{i}회] P:{row.get('ping_ms')}ms D:{row.get('download_mbps'):.1f}M U:{row.get('upload_mbps'):.1f}M"
                self.root.after(0, self._update_result_text, msg)
            except Exception as e:
                self.root.after(0, self._update_result_text, f"[오류] {e}")
            
            if count and i >= count:
                self.root.after(0, self._update_status, f"✅ 자동 측정 완료 ({count}회)")
                break
            
            wait_time = 0
            while wait_time < interval_sec and not self.stop_event.is_set():
                time.sleep(1) 
                wait_time += 1
                remaining = interval_sec - wait_time
                if remaining > 0 and not self.stop_event.is_set():
                     self.root.after(0, self._update_status, f"⏳ 다음 측정까지 {remaining}초...")
        if self.stop_event.is_set():
            self.root.after(0, self._update_status, "⏹ 자동 측정이 중지되었습니다.")
        self.root.after(0, self._unlock_ui) 

    def stop_loop_thread(self):
        if self.loop_thread and self.loop_thread.is_alive():
            self.stop_event.set()
            self.stop_loop_button.config(state=tk.DISABLED)
            self._update_status("중지 요청 중...")

    def run_plot(self):
        self._update_status("📈 그래프 생성 중...")
        host = self.get_host()
        log_path = get_log_path_for_host(host) 
        try:
            df = load_logs(log_path=log_path) 
            if df is None or df.empty:
                self._update_result_text(f"⚠️ [{log_path.name}] 표시할 데이터가 없습니다.")
            else:
                plot_logs(df, show=True, host=host) 
        except Exception as e:
            self._update_result_text(f"[오류] {e}")
        self._update_status("대기 중...")

    def run_analyze(self):
        self._update_status("📊 로그 분석 중...")
        host = self.get_host()
        log_path = get_log_path_for_host(host)
        ip_filter = self.get_ip_filter() 
        try:
            df = load_logs(log_path=log_path) 
            if df is None or df.empty:
                self._update_result_text(f"⚠️ [{log_path.name}] 분석할 데이터가 없습니다.")
                self._update_status("대기 중...")
                return
            f = io.StringIO()
            with redirect_stdout(f):
                analyze_logs(df, by='all', ip=ip_filter) 
            analysis_result = f.getvalue() 
            filename = f"{log_path.name}"
            if ip_filter: filename += f" (IP: {ip_filter})"
            self.show_analysis_window(analysis_result, filename)
            self._update_result_text(f"✅ 분석 완료. 결과 창을 확인하세요.")
        except Exception as e:
            self._update_result_text(f"[오류] {e}")
        self._update_status("대기 중...")

    def show_analysis_window(self, content, filename=""):
        top = tk.Toplevel(self.root)
        top.title(f"분석 리포트 - {filename}") 
        top.geometry("650x650")
        txt_area = scrolledtext.ScrolledText(top, wrap=tk.WORD, font=("Consolas", 10), padx=10, pady=10)
        txt_area.pack(fill=tk.BOTH, expand=True)
        txt_area.insert(tk.INSERT, content)
        txt_area.config(state=tk.DISABLED)

    def run_delete_log(self):
        host = self.get_host()
        log_path = get_log_path_for_host(host)
        if not log_path.exists():
            messagebox.showinfo("알림", f"삭제할 로그 파일이 없습니다:\n{log_path.name}")
            return
        if messagebox.askyesno("삭제 확인", f"경고: '{log_path.name}' 파일을 영구적으로 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."):
            try:
                delete_log(log_path)
                self._update_result_text(f"🗑️ '{log_path.name}' 파일을 삭제했습니다.")
            except Exception as e:
                messagebox.showerror("오류", f"삭제 실패: {e}")

if __name__ == "__main__":
    main_root = tk.Tk()
    app = NetSpeedApp(main_root)
    main_root.mainloop()