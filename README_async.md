# 비동기 처리 구조 개선

## 개선사항

기존 FastAPI 동기 처리에서 Celery + Redis를 사용한 비동기 처리로 개선:

### 1. 추가된 패키지
- `celery==5.3.4`: 비동기 작업 처리
- `redis==5.0.1`: 메시지 브로커 및 결과 백엔드

### 2. 새로운 파일들

#### `app/celery_app.py`
- Celery 애플리케이션 설정 및 초기화
- Redis 브로커 설정
- 태스크 라우팅 및 큐 설정

#### `app/tasks.py`
- 비동기 태스크 정의
- `generate_math_problems_task`: 수학 문제 생성
- `grade_problems_task`: 문제 채점
- 진행률 추적 기능

#### `celery_worker.py`
- Celery Worker 실행 스크립트

#### `docker-compose.yml`
- Redis와 PostgreSQL 서비스 정의
- 개발환경 구성

### 3. 수정된 파일들

#### `app/models/worksheet.py`
- `WorksheetStatus`에 `PROCESSING`, `FAILED` 상태 추가
- `celery_task_id`, `error_message`, `completed_at` 필드 추가

#### `app/routers/math_generation.py`
- `/generate` 엔드포인트를 비동기 처리로 변경
- `/tasks/{task_id}`: 태스크 상태 조회 엔드포인트
- `/worksheets/{worksheet_id}/grade`: 채점 엔드포인트 추가

## 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. Redis와 PostgreSQL 실행
```bash
docker-compose up -d
```

### 3. 환경변수 설정
`.env` 파일 생성 (`.env.example` 참조)

### 4. 데이터베이스 마이그레이션
```bash
alembic upgrade head
```

### 5. Celery Worker 실행
```bash
python celery_worker.py
```

### 6. FastAPI 서버 실행
```bash
uvicorn main:app --reload
```

## API 사용법

### 문제 생성 (비동기)
```http
POST /api/math-generation/generate
```
→ `task_id` 반환

### 태스크 상태 확인
```http
GET /api/math-generation/tasks/{task_id}
```

### 채점 (비동기)
```http
POST /api/math-generation/worksheets/{worksheet_id}/grade
```

## 장점

1. **성능 개선**: 긴 작업이 API 응답을 블로킹하지 않음
2. **확장성**: 여러 Worker로 부하 분산 가능
3. **안정성**: 작업 실패 시 재시도 및 오류 추적
4. **사용자 경험**: 실시간 진행률 확인 가능