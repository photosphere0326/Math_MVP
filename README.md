# Math Problem Generation API

중학교 수학 문제 AI 생성 플랫폼

## 기술 스택
- FastAPI, PostgreSQL, Redis, Celery
- Google Gemini API
- SQLAlchemy, Pydantic

## 구조
```
app/
├── models/          # DB 모델
├── schemas/         # Pydantic 스키마  
├── services/        # 비즈니스 로직
└── routers/         # API 엔드포인트
data/               # 교육과정 데이터
static/             # 웹 인터페이스
```
## 실행
```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
python celery_worker.py  # 별도 터미널
```

## API
- 웹: http://localhost:8000/static/index.html
- 문서: http://localhost:8000/docs