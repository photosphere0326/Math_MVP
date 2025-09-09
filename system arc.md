- 교사
  - 로그인 / 회원가입
    - 반 개설 → 초대코드 생성 후 공유
  - 레벨테스트 생성 후 배포 (필요 시) → 학생별 결과 확인
  - 문제 생성
    - 과목, 범위, 난이도, 문제 수, 유형 선택
    - AI 자동 문제 생성
  - 문제 편집
    - 보기 항목/순서/난이도 조정
    - 배점, 해설 톤 수정
  - 배포
    - 특정 학생/그룹/전체 대상 선택
    - 응시 기간 설정, 알림 발송
    - 미제출 학생 자동 리마인드
  - 실시간 응시 현황 확인 → 응시, 미응시, 제출률 확인
  - 자동 채점 결과 검토
    - 자동 채점 결과 검토 및 수정
    - 성취도 리포트 확인
  - 오답 저장소 + 오답 노트 → 재출제
  - 학생별 또는 그룹별 성취 리포트 확인
  - 학부모에게 요약 리포트 자동 전송
  - 자신있는 문제들 MarketPlace에 올림
- 학생

  - 회원가입 → 초대코드 입력 → 반 참여
  - 로그인 / 접속 → PC 또는 모바일 앱 접속
  - 레벨테스트 응시 (처음 입장인 경우)
  - 시험 알림 수신
  - 문제 풀이
    - 객관식 : 터치 선택
    - 단답형, 서술형 : 텍스트 입력
  - 시험 제출 → 객관식, 단답형은 즉시 점수 확인, 서술형은 잠정 점수 확인
  - 피드백 확인 → 채점 결과 및 해설 확인, 오답노트 열람
  - 재학습 → 틀린 문제 기반 반복 학습
  - 개인 성취도 그래프 확인

- 학부모
  - 자녀 학습 현황 알림 수신 → 쪽지로 결과 전송
  - 결과 확인 → 점수, 등수, 평균, 성취도 리포트

## 기술적 구현 흐름 및 기술스택

### 1. 프론트엔드 (Next.js + TypeScript + Tailwind CSS)
- **Next.js 14** (App Router, Server Components)
- **TypeScript** (타입 안전성 보장)
- **Tailwind CSS** (유틸리티 퍼스트 스타일링)
- **JWT 토큰 기반 인증** (교사/학생/학부모 역할 구분)

### 2. 백엔드 API (FastAPI)
- **FastAPI** (고성능 Python 웹 프레임워크)
- **Pydantic** (데이터 검증 및 직렬화)
- **JWT 인증** (토큰 기반 인증 시스템)
- **CORS 미들웨어** (크로스 오리진 요청 처리)

### 3. 데이터베이스 (PostgreSQL)
- **PostgreSQL** (메인 관계형 데이터베이스)
- **SQLAlchemy ORM** (데이터베이스 모델링)
- **Alembic** (데이터베이스 마이그레이션)
- **Connection Pooling** (연결 풀 관리)

### 4. 캐시 & 세션 (Redis)
- **Redis** (세션 저장소, 캐싱)
- **초대코드 임시 저장** (TTL 기반 만료 관리)
- **실시간 응시 현황 캐싱**
- **Rate Limiting** (API 호출 제한)

### 5. 비동기 작업 처리 (Celery)
- **Celery** (분산 작업 큐 시스템)
- **Redis Broker** (메시지 브로커)
- **자동 채점 작업** (백그라운드 처리)
- **리마인드 알림** (스케줄된 작업)
- **리포트 생성** (PDF 생성 등 무거운 작업)

### 6. AI 문제 생성 (Gemini API)
- **Google Gemini API** (문제 자동 생성)
- **Prompt Engineering** (과목별, 난이도별 템플릿)
- **Text Generation** (객관식, 단답형, 서술형 문제 생성)
- **Content Safety** (부적절한 내용 필터링)

### 7. 이미지 처리 (Google Vision API)
- **Google Vision API** (이미지 텍스트 추출)
- **OCR 기능** (손글씨 답안 인식)
- **이미지 문제 분석** (그래프, 도표 인식)
- **Document AI** (시험지 스캔 처리)

### 8. 컨테이너화 (Docker)
- **Docker Compose** (멀티 컨테이너 오케스트레이션)
- **Frontend Container** (Next.js 앱)
- **Backend Container** (FastAPI 서버)
- **Database Container** (PostgreSQL)
- **Redis Container** (캐시 서버)
- **Celery Worker Container** (백그라운드 작업)

### 9. 기능별 구현 흐름

#### 교사 회원가입 & 로그인
```
1. Next.js → 회원가입/로그인 폼 제출
2. FastAPI → 사용자 정보 검증 (Pydantic)
3. PostgreSQL → 사용자 정보 저장/조회
4. FastAPI → JWT 토큰 생성 & 반환
5. Next.js → 토큰 저장 (localStorage) & 대시보드 이동
```

#### 반 개설 & 초대코드 생성
```
1. Next.js → 반 생성 요청 (교사 JWT 포함)
2. FastAPI → JWT 검증 & 교사 권한 확인
3. PostgreSQL → 반 정보 저장 (teacher_id, class_name 등)
4. FastAPI → UUID 기반 초대코드 생성
5. Redis → 초대코드 임시 저장 (TTL: 24시간)
6. Next.js → 초대코드 화면에 표시
```

#### AI 수학 문제 생성 (구체적 예시)
```
1. Next.js → 문제 생성 요청 (과목: 수학, 범위: 이차함수, 난이도: 중, 개수: 10)
2. FastAPI → 요청 검증 & 교사 권한 확인
3. FastAPI → Celery에 비동기 작업 등록 (task_id 생성)
4. Redis → Celery 작업 큐에 저장
5. Next.js → task_id 받고 진행률 폴링 시작

백그라운드 처리:
6. Celery Worker → Redis에서 작업 가져옴
7. Celery → Gemini API 호출 (프롬프트: "이차함수 중급 문제 10개 생성")
8. Gemini API → JSON 형태 문제 반환
9. Celery → 문제 유효성 검증
10. PostgreSQL → 생성된 문제들 저장
11. Redis → 작업 완료 상태 업데이트

클라이언트 수신:
12. Next.js → 폴링으로 완료 확인
13. FastAPI → 생성된 문제 목록 반환
14. Next.js → 문제 목록 화면에 표시
```

#### 문제 편집 & 수정
```
1. Next.js → 특정 문제 편집 요청
2. FastAPI → 문제 소유권 확인 (교사 본인 문제인지)
3. PostgreSQL → 기존 문제 데이터 조회
4. Next.js → 편집 폼에 기존 데이터 로드
5. Next.js → 수정 내용 제출
6. FastAPI → 수정 내용 검증
7. PostgreSQL → 문제 업데이트 (version 관리)
```

#### 시험 배포 & 스케줄링
```
1. Next.js → 시험 생성 & 배포 설정 (대상 학생, 기간 설정)
2. FastAPI → 시험 정보 생성
3. PostgreSQL → 시험 메타데이터 저장
4. FastAPI → Celery에 알림 작업 스케줄링
5. Redis → 스케줄된 작업 저장

알림 발송 (스케줄된 시간):
6. Celery Beat → 스케줄러가 알림 작업 트리거
7. Celery Worker → 대상 학생 목록 조회
8. PostgreSQL → 학생 연락처 정보 가져옴
9. 각종 알림 채널 (이메일, 푸시 등) 발송
```

#### 학생 시험 응시
```
1. Next.js → 학생 로그인 & 시험 목록 조회
2. FastAPI → 학생 권한 & 시험 접근 권한 확인
3. PostgreSQL → 시험 문제 조회
4. Next.js → 문제 화면 렌더링
5. Next.js → 학생 답안 실시간 임시 저장 (localStorage)
6. Redis → 응시 현황 실시간 업데이트 (교사 모니터링용)
```

#### 답안 제출 & 자동 채점
```
객관식/단답형:
1. Next.js → 답안 제출
2. FastAPI → 즉시 정답 비교 채점
3. PostgreSQL → 채점 결과 저장
4. Next.js → 즉시 점수 표시

서술형 (Gemini 채점):
1. Next.js → 서술형 답안 제출
2. FastAPI → Celery에 채점 작업 등록
3. Redis → 채점 작업 큐 저장
4. Celery Worker → Gemini API 호출 (채점 프롬프트)
5. Gemini API → 점수 & 피드백 반환
6. PostgreSQL → 채점 결과 저장
7. Next.js → 폴링으로 채점 완료 확인 후 결과 표시

이미지 답안 (손글씨):
1. Next.js → 이미지 업로드
2. FastAPI → 이미지 파일 검증 & 저장
3. FastAPI → Celery에 OCR 작업 등록
4. Redis → OCR 작업 큐 저장
5. Celery Worker → Google Vision API 호출 (OCR 처리)
6. Google Vision API → 이미지에서 텍스트 추출
7. Celery Worker → 추출된 텍스트를 Gemini API로 채점 요청
8. Gemini API → 채점 결과 & 피드백 반환
9. PostgreSQL → OCR 텍스트 + 채점 결과 저장
10. Next.js → 폴링으로 완료 확인 후 결과 표시
```

#### 실시간 응시 현황 모니터링
```
1. Next.js (교사) → 실시간 모니터링 페이지 접속
2. FastAPI → WebSocket 연결 설정
3. Redis → 실시간 응시 상태 조회
4. WebSocket → 응시율, 제출률 실시간 전송
5. Next.js → 실시간 차트 업데이트 (Chart.js)
```

#### 성취도 리포트 생성
```
1. Next.js → 리포트 생성 요청
2. FastAPI → 리포트 생성 작업 Celery에 등록
3. Redis → 리포트 생성 작업 큐 저장
4. Celery Worker → PostgreSQL에서 성적 데이터 집계
5. Celery → 통계 계산 (평균, 표준편차, 등수 등)
6. Celery → PDF 생성 라이브러리로 리포트 생성
7. PostgreSQL → 생성된 리포트 메타데이터 저장
8. Next.js → 완료 폴링 후 리포트 다운로드 링크 제공
```

#### 오답 노트 & 재학습
```
1. Next.js → 학생의 오답 문제 조회
2. PostgreSQL → 틀린 문제 목록 & 오답 이유 분석
3. Gemini API → 유사 문제 생성 추천
4. Next.js → 오답 노트 & 추천 문제 표시
5. 재학습 진행 시 → 위의 시험 응시 플로우와 동일
```

#### 학부모 알림 & 리포트
```
1. Celery Beat → 주기적 학부모 알림 스케줄 트리거
2. PostgreSQL → 학생별 최근 성적 데이터 조회
3. Celery Worker → 학부모 연락처 정보 조회
4. 요약 리포트 생성 → 간단한 성적 요약
5. 이메일/SMS 발송 → 학부모에게 자동 전송
```

### 10. 배포 아키텍처
```
Docker Compose
├── next-app (포트 3000)
├── fastapi-server (포트 8000)  
├── postgresql (포트 5432)
├── redis (포트 6379)
├── celery-worker
└── celery-beat (스케줄러)
```
