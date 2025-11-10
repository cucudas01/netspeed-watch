# NetSpeed Watch

네트워크 속도를 주기적으로 측정하고 CSV로 기록하며,
시간대별 품질 변화를 그래프로 시각화하는 Python 기반 유틸리티입니다.

---

## 📦 설치 방법

1.  가상환경 생성 및 활성화 (선택)
    ```bash
    python -m venv .venv
    .\.venv\Scripts\activate
    ```
2.  필수 패키지 설치
    ```bash
    python -m pip install -r requirements.txt
    ```

## GUI 설치 방법
    pyinstaller --onefile --windowed --add-data "src;src" main_gui.py

    
## CLI 실행 방법 

-   **1회 측정**
    ```bash
    python -m src.main --once
    ```
-   **주기적 측정**
    ```bash
    python -m src.main --loop 300
    ```
-   **주기적 측정 (횟수 지정)**
    ```bash
    python -m src.main --loop 300 --count 10
    ```
-   **그래프 생성**
    ```bash
    python -m src.main --plot
    ```
-   **로그 분석**
    -   전체 분석 (시간대별, 요일별)
        ```bash
        python -m src.main --analyze
        ```
    -   시간대별 분석 리포트
        ```bash
        python -m src.main --analyze hourly
        ```
    -   요일별 분석 리포트
        ```bash
        python -m src.main --analyze daily
        ```

---

## 🛠️ 주요 기능

-   Ping, Download, Upload 속도 측정
-   CSV 파일에 누적 기록
-   시간대별 속도 변화 그래프 시각화
-   시간대별/요일별 평균 속도 분석 리포트 제공