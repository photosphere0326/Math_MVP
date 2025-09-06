📚 서버 시작/종료 가이드

🚀 서버 시작하기 (2개 터미널 필요)

터미널 1 - FastAPI 서버

cd /Users/hangwang-gu/Documents/Qt_Project/backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

터미널 2 - Celery Worker

cd /Users/hangwang-gu/Documents/Qt_Project/backend
python celery_worker.py

🌐 접속 URL

- 웹 인터페이스: http://localhost:8000/static/index.html
- API 문서: http://localhost:8000/docs

🛑 서버 종료하기

각 터미널에서 Ctrl + C 누르면 됩니다.

⚙️ 필수 서비스 (항상 실행되어야 함)

- PostgreSQL: 데이터베이스 서버
- Redis: Celery 메시지 브로커 (백그라운드 작업용)

🔧 서비스 확인 명령어

# PostgreSQL 상태 확인

pg_ctl status

# Redis 상태 확인

redis-cli ping

# 실행 중인 프로세스 확인

ps aux | grep -E "(uvicorn|celery)"

📁 프로젝트 구조

backend/
├── main.py # FastAPI 앱
├── celery_worker.py # Celery Worker
├── .env # 환경변수 (DB 연결 정보)
└── static/index.html # 웹 인터페이스

이제 2개 터미널만 열어서 위 명령어들로 서버를 시작하시면 됩니다!
