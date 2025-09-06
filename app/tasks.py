from celery import current_task
from .celery_app import celery_app
from .database import SessionLocal
from .services.math_generation_service import MathGenerationService
from .schemas.math_generation import MathProblemGenerationRequest
from .models.worksheet import Worksheet, WorksheetStatus
from .models.math_generation import MathProblemGeneration
from .models.problem import Problem
import json
import uuid
from datetime import datetime
from sqlalchemy.orm import Session


@celery_app.task(bind=True, name="app.tasks.generate_math_problems_task")
def generate_math_problems_task(self, request_data: dict, user_id: int):
    """비동기 수학 문제 생성 태스크"""
    
    # 태스크 ID 생성
    task_id = self.request.id
    generation_id = str(uuid.uuid4())
    
    # 데이터베이스 세션 생성
    db = SessionLocal()
    
    try:
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '문제 생성 준비 중...'}
        )
        
        # 요청 데이터를 Pydantic 모델로 변환
        request = MathProblemGenerationRequest.model_validate(request_data)
        
        # 워크시트 초기 생성 (PROCESSING 상태)
        worksheet_title = f"{request.chapter.chapter_name} - {request.problem_count.value}"
        worksheet = Worksheet(
            title=worksheet_title,
            school_level=request.school_level.value,
            grade=request.grade,
            semester=request.semester.value,
            unit_number=request.unit_number,
            unit_name=request.chapter.unit_name,
            chapter_number=request.chapter.chapter_number,
            chapter_name=request.chapter.chapter_name,
            problem_count=request.problem_count.value_int,
            difficulty_ratio=request.difficulty_ratio.model_dump(),
            problem_type_ratio=request.problem_type_ratio.model_dump(),
            user_prompt=request.user_text,
            generation_id=generation_id,
            status=WorksheetStatus.PROCESSING,
            created_by=user_id,
            celery_task_id=task_id
        )
        
        db.add(worksheet)
        db.flush()
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 20, 'total': 100, 'status': '교육과정 데이터 로드 중...'}
        )
        
        # MathGenerationService 초기화
        math_service = MathGenerationService()
        
        # 교육과정 데이터 가져오기
        curriculum_data = math_service._get_curriculum_data(request)
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 40, 'total': 100, 'status': '문제 유형 분석 중...'}
        )
        
        # 문제 유형 데이터 가져오기
        problem_types = math_service._get_problem_types(request.chapter.chapter_name)
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 60, 'total': 100, 'status': 'AI로 문제 생성 중...'}
        )
        
        # AI 서비스를 통한 문제 생성
        generated_problems = math_service._generate_problems_with_ai(
            curriculum_data=curriculum_data,
            problem_types=problem_types,
            request=request
        )
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 80, 'total': 100, 'status': '문제 데이터베이스 저장 중...'}
        )
        
        # 생성 세션 저장
        generation_session = MathProblemGeneration(
            generation_id=generation_id,
            school_level=request.school_level.value,
            grade=request.grade,
            semester=request.semester.value,
            unit_number=request.unit_number,
            unit_name=request.chapter.unit_name,
            chapter_number=request.chapter.chapter_number,
            chapter_name=request.chapter.chapter_name,
            problem_count=request.problem_count.value_int,
            difficulty_ratio=request.difficulty_ratio.model_dump(),
            problem_type_ratio=request.problem_type_ratio.model_dump(),
            user_text=request.user_text,
            actual_difficulty_distribution=math_service._calculate_difficulty_distribution(generated_problems),
            actual_type_distribution=math_service._calculate_type_distribution(generated_problems),
            total_generated=len(generated_problems),
            created_by=user_id
        )
        
        db.add(generation_session)
        db.flush()
        
        # 생성된 문제들을 워크시트에 연결하여 저장
        problem_responses = []
        for i, problem_data in enumerate(generated_problems):
            problem = Problem(
                worksheet_id=worksheet.id,
                sequence_order=i + 1,
                problem_type=problem_data.get("problem_type", "multiple_choice"),
                difficulty=problem_data.get("difficulty", "B"),
                question=problem_data.get("question", ""),
                choices=json.dumps(problem_data.get("choices")) if problem_data.get("choices") else None,
                correct_answer=problem_data.get("correct_answer", ""),
                explanation=problem_data.get("explanation", ""),
                latex_content=problem_data.get("latex_content"),
                has_diagram=str(problem_data.get("has_diagram", False)).lower(),
                diagram_type=problem_data.get("diagram_type"),
                diagram_elements=json.dumps(problem_data.get("diagram_elements")) if problem_data.get("diagram_elements") else None
            )
            
            db.add(problem)
            db.flush()
            
            # GeneratedProblemSet 제거됨 - Problem 테이블의 sequence_order로 대체
            
            # 응답용 데이터 생성
            problem_responses.append({
                "id": problem.id,
                "sequence_order": i + 1,
                "problem_type": problem.problem_type,
                "difficulty": problem.difficulty,
                "question": problem.question,
                "choices": json.loads(problem.choices) if problem.choices else None,
                "correct_answer": problem.correct_answer,
                "explanation": problem.explanation,
                "latex_content": problem.latex_content,
                "has_diagram": problem.has_diagram == "true",
                "diagram_type": problem.diagram_type,
                "diagram_elements": json.loads(problem.diagram_elements) if problem.diagram_elements else None
            })
        
        # 워크시트 완료 상태로 업데이트
        worksheet.actual_difficulty_distribution = math_service._calculate_difficulty_distribution(generated_problems)
        worksheet.actual_type_distribution = math_service._calculate_type_distribution(generated_problems)
        worksheet.status = WorksheetStatus.COMPLETED
        worksheet.completed_at = datetime.now()
        
        db.commit()
        
        # 성공 결과 반환
        result = {
            "generation_id": generation_id,
            "worksheet_id": worksheet.id,
            "school_level": request.school_level.value,
            "grade": request.grade,
            "semester": request.semester.value,
            "unit_name": request.chapter.unit_name,
            "chapter_name": request.chapter.chapter_name,
            "problem_count": request.problem_count.value_int,
            "difficulty_ratio": request.difficulty_ratio.model_dump(),
            "problem_type_ratio": request.problem_type_ratio.model_dump(),
            "user_prompt": request.user_text,
            "actual_difficulty_distribution": math_service._calculate_difficulty_distribution(generated_problems),
            "actual_type_distribution": math_service._calculate_type_distribution(generated_problems),
            "problems": problem_responses,
            "total_generated": len(generated_problems),
            "created_at": datetime.now().isoformat()
        }
        
        return result
        
    except Exception as e:
        # 오류 발생 시 워크시트 상태를 FAILED로 변경
        if 'worksheet' in locals():
            worksheet.status = WorksheetStatus.FAILED
            worksheet.error_message = str(e)
            db.commit()
        
        # 태스크 실패 상태로 업데이트
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'status': '문제 생성 실패'}
        )
        raise
        
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.grade_problems_task")
def grade_problems_task(self, worksheet_id: int, answers: dict, user_id: int):
    """비동기 문제 채점 태스크"""
    
    task_id = self.request.id
    db = SessionLocal()
    
    try:
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '채점 준비 중...'}
        )
        
        # 워크시트와 문제들 조회
        worksheet = db.query(Worksheet).filter(Worksheet.id == worksheet_id).first()
        if not worksheet:
            raise ValueError("워크시트를 찾을 수 없습니다.")
        
        problems = db.query(Problem).filter(Problem.worksheet_id == worksheet_id).all()
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 20, 'total': 100, 'status': '답안 분석 중...'}
        )
        
        # 채점 결과 저장
        grading_results = []
        correct_count = 0
        total_count = len(problems)
        
        for i, problem in enumerate(problems):
            user_answer = answers.get(str(problem.id), "")
            is_correct = user_answer.strip().lower() == problem.correct_answer.strip().lower()
            
            if is_correct:
                correct_count += 1
            
            grading_results.append({
                "problem_id": problem.id,
                "user_answer": user_answer,
                "correct_answer": problem.correct_answer,
                "is_correct": is_correct,
                "explanation": problem.explanation
            })
            
            # 진행률 업데이트
            progress = 20 + (i + 1) / total_count * 60
            self.update_state(
                state='PROGRESS',
                meta={'current': progress, 'total': 100, 'status': f'채점 중... ({i+1}/{total_count})'}
            )
        
        # 채점 결과 계산
        score = (correct_count / total_count * 100) if total_count > 0 else 0
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': '결과 저장 중...'}
        )
        
        # 결과 반환
        result = {
            "worksheet_id": worksheet_id,
            "total_problems": total_count,
            "correct_count": correct_count,
            "score": score,
            "grading_results": grading_results,
            "graded_at": datetime.now().isoformat()
        }
        
        return result
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'status': '채점 실패'}
        )
        raise
        
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.get_task_status")
def get_task_status(self, task_id: str):
    """태스크 상태 조회"""
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id, app=celery_app)
    
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.successful() else None,
        "info": result.info
    }