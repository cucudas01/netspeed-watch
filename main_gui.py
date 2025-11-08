import sys
import os

# PyInstaller --windowed 모드 'fileno' 오류 해결용 패치
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")


# src/main_gui.py
# 이 파일은 main.py 대신 실행할 GUI 버전입니다.
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading  # GUI가 멈추지 않도록 스레드 사용

# ------------------------------------------------------------------
# 1. 기존에 만든 핵심 기능들을 그대로 가져옵니다.
# ------------------------------------------------------------------
from src.storage import append_row, load_logs
from src.measure import safe_measure
from src.visualize import plot_logs, analyze_logs
# ------------------------------------------------------------------
# 2. GUI 애플리케이션 클래스를 정의합니다.
# ------------------------------------------------------------------
class NetSpeedApp:
    def __init__(self, root):
        self.root = root
        self.root.title("네트워크 속도 측정 프로그램")
        self.root.geometry("450x300")

        # 프레임 설정
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. 실행 버튼
        self.measure_button = ttk.Button(
            main_frame,
            text="속도 측정 시작 (1회)",
            command=self.start_measure_thread  # 버튼 클릭 시 스레드 시작
        )
        self.measure_button.pack(pady=10, fill=tk.X)

        # 2. 기능 버튼 (분석, 시각화)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.plot_button = ttk.Button(
            button_frame,
            text="그래프 보기 (--plot)",
            command=self.run_plot
        )
        self.plot_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.analyze_button = ttk.Button(
            button_frame,
            text="로그 분석 (--analyze)",
            command=self.run_analyze
        )
        self.analyze_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)


        # 3. 상태 및 결과 표시 라벨
        self.status_label = ttk.Label(main_frame, text="대기 중...")
        self.status_label.pack(pady=5)

        self.result_text = tk.Text(main_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.result_text.pack(pady=5, fill=tk.BOTH, expand=True)

    def _update_result_text(self, message):
        """ 텍스트 위젯에 결과를 추가하는 도우미 함수 """
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, message + "\n")
        self.result_text.see(tk.END) # 스크롤을 맨 아래로
        self.result_text.config(state=tk.DISABLED)

    def start_measure_thread(self):
        """ 
        GUI가 얼어붙는 것을 방지하기 위해 
        속도 측정을 별도의 스레드에서 실행합니다.
        """
        self.measure_button.config(state=tk.DISABLED, text="측정 중...")
        self.status_label.config(text="측정 중... (최대 30초 소요)")
        
        # 스레드 생성 및 시작
        thread = threading.Thread(target=self.run_measure_once)
        thread.daemon = True # 메인 프로그램 종료 시 스레드도 종료
        thread.start()

    def run_measure_once(self):
        """ [스레드 작업] 실제 속도 측정 및 저장 로직 """
        try:
            # 1. 기존 측정 함수 호출
            row = safe_measure()
            
            # 2. 기존 저장 함수 호출
            append_row(row)
            
            result_message = f"[측정 완료] {row}"

        except Exception as e:
            result_message = f"[오류 발생] {e}"

        # GUI 업데이트는 메인 스레드에서 안전하게 실행
        self.root.after(0, self.update_gui_after_measure, result_message)

    def update_gui_after_measure(self, result_message):
        """ [메인 스레드] GUI 업데이트 """
        self.status_label.config(text="측정 완료. 다시 시작할 수 있습니다.")
        self._update_result_text(result_message)
        self.measure_button.config(state=tk.NORMAL, text="속도 측정 시작 (1회)")

    def run_plot(self):
        """ 그래프 보기 기능 실행 """
        self.status_label.config(text="그래프 생성 중...")
        try:
            df = load_logs()
            if df is None or df.empty:
                self._update_result_text("[알림] 표시할 데이터가 없습니다.")
            else:
                # 기존 plot_logs 함수가 plt.show()를 호출해 새 창을 띄웁니다.
                plot_logs(df, show=True) 
                self._update_result_text("[알림] 그래프 창을 확인하세요.")
        except Exception as e:
            self._update_result_text(f"[오류] {e}")
        self.status_label.config(text="대기 중...")

    def run_analyze(self):
        """ 
        분석 기능 실행 (새 창에 결과 표시)
        기존 analyze_logs는 print()로 출력하므로, 그 결과를 새 창으로 보냅니다.
        """
        self.status_label.config(text="로그 분석 중...")
        
        try:
            df = load_logs()
            if df is None or df.empty:
                self._update_result_text("[알림] 분석할 데이터가 없습니다.")
                self.status_label.config(text="대기 중...")
                return

            # 1. 분석 결과를 캡처하기 위해 임시 '파이프' 생성 (고급)
            import io
            from contextlib import redirect_stdout
            
            f = io.StringIO()
            with redirect_stdout(f):
                analyze_logs(df, by='all') # 기존 함수 실행
            analysis_result = f.getvalue() # print된 결과를 문자열로 가져옴

            # 2. 새 창(Toplevel)을 만들어 텍스트 위젯에 결과 표시
            self.show_analysis_window(analysis_result)
            self._update_result_text("[알림] 분석 결과(새 창)를 확인하세요.")

        except Exception as e:
            self._update_result_text(f"[오류] {e}")
            
        self.status_label.config(text="대기 중...")

    def show_analysis_window(self, content):
        """ 분석 결과를 보여줄 새 창 생성 """
        top = tk.Toplevel(self.root)
        top.title("분석 리포트 (--analyze all)")
        top.geometry("600x600")
        
        txt_area = scrolledtext.ScrolledText(top, wrap=tk.WORD)
        txt_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt_area.insert(tk.INSERT, content)
        txt_area.config(state=tk.DISABLED)

# ------------------------------------------------------------------
# 3. GUI 애플리케이션을 실행합니다.
# ------------------------------------------------------------------
if __name__ == "__main__":
    main_root = tk.Tk()
    app = NetSpeedApp(main_root)
    main_root.mainloop()