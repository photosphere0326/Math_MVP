# 서버 실행 가이드

## 서버 시작 (2개 터미널)

터미널 1 - FastAPI:
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

터미널 2 - Celery Worker:
```bash
python celery_worker.py
```

## 접속 URL
- 웹: http://localhost:8000/static/index.html
- API: http://localhost:8000/docs

## 필수 서비스
- PostgreSQL
- Redis
