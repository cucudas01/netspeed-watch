# NetSpeed Watch

네트워크 속도를 주기적으로 측정하고 CSV로 기록하며,  
시간대별 품질 변화를 그래프로 시각화하는 Python 기반 유틸리티입니다.

---

## 📦 설치 방법

1. 가상환경 생성 및 활성화 (선택)
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
2. 필수 패키지 설치
    python -m pip install -r requirements.txt

## 실행 방법
    1회 측정
    python -m src.main --once

    주기적 측정 (예: 5분 간격)
    python -m src.main --loop 300

    그래프 생성
    python -m src.main --plot

🛠️ 주요 기능

Ping, Download, Upload 속도 측정

CSV 파일에 누적 기록

시간대별 그래프 시각화

