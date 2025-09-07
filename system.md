# 수학 문제 생성 시스템 구조

## 전체 아키텍처

```
사용자 → 웹 인터페이스 → FastAPI → Celery → AI 서비스 → 데이터베이스
```

## 시스템 흐름도

### 1. 문제 생성 프로세스
```
1. 사용자가 웹에서 문제 생성 요청
2. FastAPI가 요청을 받아 Celery 태스크 생성
3. Celery Worker가 백그라운드에서 처리:
   - AI 서비스(Gemini API)로 문제 생성
   - 생성된 문제를 DB에 저장
   - 워크시트로 그룹화
4. 사용자가 태스크 상태 확인 후 결과 조회
```

### 2. 채점 프로세스
```
1. 사용자가 답안 입력/업로드
2. Celery Worker가 채점 처리:
   - 객관식: 직접 비교
   - 주관식: OCR → AI 채점
3. 채점 결과 DB 저장 후 반환
```

## 핵심 컴포넌트

### FastAPI 서버 (main.py)
- REST API 엔드포인트 제공
- CORS 설정으로 웹 인터페이스 연동
- Static 파일 서빙

### Celery 비동기 처리 (celery_worker.py, app/tasks.py)
- 문제 생성: `generate_math_problems_task`
- 채점 처리: `grade_problems_task`, `grade_problems_mixed_task`
- Redis를 메시지 브로커로 사용

### 데이터베이스 모델
- **Worksheet**: 문제집 (여러 문제를 그룹화)
- **Problem**: 개별 문제
- **MathGeneration**: 생성 세션 정보
- **MathProblemType**: 문제 유형 정의

### AI 서비스 (app/services/ai_service.py)
- Google Gemini API 연동
- JSON 파싱 3단계 fallback 처리
- 문제 생성 및 채점

### 비즈니스 로직 (app/services/math_generation_service.py)
- 교육과정 데이터 관리
- 문제 생성 로직
- 워크시트 관리

## 데이터 흐름

### 교육과정 데이터
```
data/middle1_math_curriculum.json
└── 중학교 1학년 교육과정 구조
    ├── 대단원 (자연수의 성질, 정수와 유리수 등)
    └── 소단원 (소인수분해, 최대공약수 등)
```

### 문제 유형 데이터
```
data/math_problem_types.json
└── 문제 유형별 템플릿
    ├── 객관식 (multiple_choice)
    ├── 주관식 (essay)
    └── 단답형 (short_answer)
```

### 문제 생성 워크플로우
```
1. 사용자 입력 파라미터
   ├── 학교급/학년/학기
   ├── 단원/소단원 선택
   ├── 문제수 (10/20개)
   ├── 난이도 비율 (A:B:C)
   ├── 유형 비율 (객관식:주관식:단답형)
   └── 추가 요구사항

2. AI 프롬프트 생성
   ├── 교육과정 데이터 삽입
   ├── 문제 유형 템플릿 삽입
   └── 사용자 요구사항 반영

3. Gemini API 호출
   ├── 구조화된 JSON 응답 요청
   ├── 3단계 fallback 파싱
   └── 문제별 메타데이터 생성

4. 데이터베이스 저장
   ├── Worksheet 생성
   ├── Problem 개별 저장
   └── MathGeneration 세션 기록
```

## 기술 스택 상세

### 백엔드
- **FastAPI**: 비동기 웹 프레임워크
- **SQLAlchemy**: ORM (PostgreSQL/SQLite)
- **Pydantic**: 데이터 검증
- **Celery**: 분산 태스크 큐
- **Redis**: 메시지 브로커

### AI/ML
- **Google Gemini API**: 문제 생성 및 채점
- **OCR**: 손글씨 답안 인식 (예정)

### 프론트엔드
- **Vanilla JS**: 웹 인터페이스
- **HTML5 Canvas**: 그리기 답안 입력

## 배포 환경

### 개발 환경
```bash
# 터미널 1: FastAPI 서버
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 터미널 2: Celery Worker
python celery_worker.py

# 필수 서비스
- PostgreSQL: 데이터베이스
- Redis: Celery 브로커
```

### 접속 URL
- 웹 인터페이스: http://localhost:8000/static/index.html
- API 문서: http://localhost:8000/docs
- API 베이스: http://localhost:8000/api/math-generation

## 주요 API 엔드포인트

### 교육과정 관련
- `GET /curriculum/structure` - 교육과정 구조 조회
- `GET /curriculum/units` - 대단원 목록
- `GET /curriculum/chapters` - 소단원 목록

### 문제 생성
- `POST /generate` - 문제 생성 시작 (비동기)
- `GET /tasks/{task_id}` - 태스크 상태 확인
- `GET /generation/history` - 생성 이력

### 워크시트 관리
- `GET /worksheets` - 워크시트 목록
- `GET /worksheets/{id}` - 워크시트 상세

### 채점
- `POST /worksheets/{id}/grade` - OCR 채점
- `POST /worksheets/{id}/grade-canvas` - 캔버스 채점
- `POST /worksheets/{id}/grade-mixed` - 혼합 채점

## 성능 특성

- **문제 생성 시간**: 10문제 기준 25-30초
- **JSON 파싱 성공률**: 99%+ (3단계 fallback)
- **동시 처리**: Celery Worker 스케일링 가능
- **데이터베이스**: PostgreSQL 트랜잭션 보장

## 확장 계획

### 단기
- 문제 편집 기능
- PDF 내보내기
- 사용자 인증

### 중기  
- 다른 학년 지원
- 문제 유형 확장
- 성능 최적화

### 장기
- 다과목 지원
- 학습 분석
- 개인화 추천