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


@celery_app.task(bind=True, name="app.tasks.grade_problems_mixed_task")
def grade_problems_mixed_task(self, worksheet_id: int, multiple_choice_answers: dict, canvas_answers: dict, user_id: int):
    """혼합형 채점 태스크 - 객관식: 체크박스, 서술형/단답형: OCR"""
    
    task_id = self.request.id
    db = SessionLocal()
    
    try:
        from .services.ai_service import AIService
        ai_service = AIService()
        
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
        total_count = len(problems)
        
        # 문제수에 따른 배점 계산
        points_per_problem = 10 if total_count == 10 else 5 if total_count == 20 else 100 // total_count
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 10, 'total': 100, 'status': 'OCR로 손글씨 답안 추출 중...'}
        )
        
        # 각 문제별 OCR 결과 저장
        ocr_results = {}
        if canvas_answers:
            import base64
            for problem_id, canvas_data in canvas_answers.items():
                if canvas_data and canvas_data.startswith('data:image/png;base64,'):
                    try:
                        # base64 데이터에서 이미지 부분만 추출
                        image_data = canvas_data.split(',')[1]
                        handwritten_image_data = base64.b64decode(image_data)
                        
                        # 문제별 OCR 처리
                        ocr_text = ai_service.ocr_handwriting(handwritten_image_data)
                        ocr_results[problem_id] = ocr_text
                        print(f"🔍 디버그: 문제 {problem_id} OCR 결과: {ocr_text[:50]}...")
                    except Exception as e:
                        print(f"🔍 OCR 오류 (문제 {problem_id}): {str(e)}")
                        ocr_results[problem_id] = ""
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 20, 'total': 100, 'status': '답안 분석 및 채점 중...'}
        )
        
        # 채점 결과 저장
        grading_results = []
        correct_count = 0
        total_score = 0
        
        for i, problem in enumerate(problems):
            if problem.problem_type == "multiple_choice":
                # 객관식: 체크박스로 받은 답안 사용
                user_answer = multiple_choice_answers.get(str(problem.id), "")
                result = _grade_objective_problem(problem, user_answer, points_per_problem)
                result["input_method"] = "checkbox"
            else:
                # 서술형/단답형: 해당 문제의 개별 OCR 결과 사용
                user_answer = ocr_results.get(str(problem.id), "")
                print(f"🔍 디버그: 문제 {problem.id} 답안: '{user_answer}'")
                
                if problem.problem_type == "essay":
                    result = _grade_essay_problem(ai_service, problem, user_answer, points_per_problem)
                else:  # short_answer
                    result = _grade_objective_problem(problem, user_answer, points_per_problem)
                result["input_method"] = "handwriting_ocr"
            
            grading_results.append(result)
            
            if result["is_correct"]:
                correct_count += 1
            total_score += result.get("score", 0)
            
            # 진행률 업데이트
            progress = 20 + (i + 1) / total_count * 70
            self.update_state(
                state='PROGRESS',
                meta={'current': progress, 'total': 100, 'status': f'채점 중... ({i+1}/{total_count})'}
            )
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 95, 'total': 100, 'status': '결과 저장 중...'}
        )
        
        # 결과 반환
        result = {
            "worksheet_id": worksheet_id,
            "total_problems": total_count,
            "correct_count": correct_count,
            "total_score": total_score,
            "points_per_problem": points_per_problem,
            "max_possible_score": total_count * points_per_problem,
            "ocr_results": ocr_results,
            "multiple_choice_answers": multiple_choice_answers,
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


@celery_app.task(bind=True, name="app.tasks.grade_problems_task")
def grade_problems_task(self, worksheet_id: int, image_data: bytes, user_id: int):
    """비동기 문제 채점 태스크 - OCR 기반 채점"""
    
    task_id = self.request.id
    db = SessionLocal()
    
    try:
        from .services.ai_service import AIService
        ai_service = AIService()
        
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
            meta={'current': 10, 'total': 100, 'status': 'OCR로 답안 추출 중...'}
        )
        
        # OCR로 학생 답안 추출
        ocr_text = ai_service.ocr_handwriting(image_data)
        if not ocr_text:
            raise ValueError("답안지에서 텍스트를 인식할 수 없습니다.")
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 20, 'total': 100, 'status': '답안 분석 중...'}
        )
        
        # 채점 결과 저장
        grading_results = []
        correct_count = 0
        total_score = 0
        total_count = len(problems)
        
        # 문제수에 따른 배점 계산
        points_per_problem = 10 if total_count == 10 else 5 if total_count == 20 else 100 // total_count
        
        for i, problem in enumerate(problems):
            # OCR 텍스트에서 해당 문제의 답안 추출 (간단한 구현)
            # 실제로는 더 정교한 답안 매칭 로직이 필요할 수 있음
            user_answer = _extract_answer_from_ocr(ocr_text, problem.id, i + 1)
            
            # 문제 유형별 채점 처리
            if problem.problem_type == "essay":
                # 서술형: 1차 키워드 검사 → 2차 AI 채점
                result = _grade_essay_problem(ai_service, problem, user_answer, points_per_problem)
            else:
                # 객관식/단답형: 직접 비교
                result = _grade_objective_problem(problem, user_answer, points_per_problem)
            
            grading_results.append(result)
            
            if result["is_correct"]:
                correct_count += 1
            total_score += result.get("score", 0)
            
            # 진행률 업데이트
            progress = 20 + (i + 1) / total_count * 70
            self.update_state(
                state='PROGRESS',
                meta={'current': progress, 'total': 100, 'status': f'채점 중... ({i+1}/{total_count})'}
            )
        
        # 최종 점수 계산 (총점 기준)
        final_total_score = total_score
        
        # 진행률 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 95, 'total': 100, 'status': '결과 저장 중...'}
        )
        
        # 결과 반환
        result = {
            "worksheet_id": worksheet_id,
            "total_problems": total_count,
            "correct_count": correct_count,
            "total_score": final_total_score,
            "points_per_problem": points_per_problem,
            "max_possible_score": total_count * points_per_problem,
            "ocr_text": ocr_text,
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


def _extract_answer_from_ocr(ocr_text: str, problem_id: int, problem_number: int) -> str:
    """OCR 텍스트에서 특정 문제의 답안을 추출"""
    # 간단한 구현: 문제 번호를 기준으로 답안 추출
    # 실제로는 더 정교한 패턴 매칭이 필요할 수 있음
    lines = ocr_text.split('\n')
    
    # 문제 번호 패턴 찾기
    for i, line in enumerate(lines):
        if f"{problem_number}." in line or f"{problem_number})" in line:
            # 해당 줄에서 답안 부분 추출
            answer_part = line.split(f"{problem_number}.")[-1].split(f"{problem_number})")[-1]
            return answer_part.strip()
    
    # 패턴을 찾지 못한 경우 전체 텍스트 반환
    return ocr_text.strip()


def _grade_essay_problem(ai_service, problem: Problem, user_answer: str, points_per_problem: int) -> dict:
    """서술형 문제 채점: 1차 키워드 검사 → 2차 AI 채점"""
    
    # 1차 채점: 핵심 키워드 포함 여부 확인
    correct_answer_keywords = problem.correct_answer.lower().split()
    user_answer_lower = user_answer.lower()
    
    keyword_matches = 0
    for keyword in correct_answer_keywords:
        if keyword in user_answer_lower:
            keyword_matches += 1
    
    keyword_score_ratio = (keyword_matches / len(correct_answer_keywords)) if correct_answer_keywords else 0
    
    # 2차 채점: AI 심층 분석
    ai_result = ai_service.grade_math_answer(
        question=problem.question,
        correct_answer=problem.correct_answer,
        student_answer=user_answer,
        explanation=problem.explanation,
        problem_type="essay"
    )
    
    # 최종 점수: AI 점수 기준으로 문제별 배점 적용
    ai_score_ratio = ai_result.get("score", 0) / 100
    final_score = points_per_problem * ai_score_ratio
    
    return {
        "problem_id": problem.id,
        "problem_type": "essay",
        "user_answer": user_answer,
        "correct_answer": problem.correct_answer,
        "is_correct": final_score >= (points_per_problem * 0.6),  # 60% 이상이면 정답
        "score": final_score,
        "points_per_problem": points_per_problem,
        "keyword_score_ratio": keyword_score_ratio,
        "ai_score": ai_result.get("score", 0),
        "ai_feedback": ai_result.get("feedback", ""),
        "strengths": ai_result.get("strengths", ""),
        "improvements": ai_result.get("improvements", ""),
        "explanation": problem.explanation
    }


def _grade_objective_problem(problem: Problem, user_answer: str, points_per_problem: int) -> dict:
    """객관식/단답형 문제 채점: 직접 비교"""
    
    # 객관식인 경우 선택지 인덱스를 실제 선택지 내용으로 변환
    actual_user_answer = user_answer
    if problem.problem_type == "multiple_choice" and problem.choices:
        # A, B, C, D를 0, 1, 2, 3 인덱스로 변환
        choice_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        if user_answer.upper() in choice_map:
            try:
                import json
                choices = json.loads(problem.choices)
                choice_index = choice_map[user_answer.upper()]
                if 0 <= choice_index < len(choices):
                    actual_user_answer = choices[choice_index]
            except (json.JSONDecodeError, IndexError):
                pass  # 변환 실패시 원래 답안 그대로 사용
    
    # 답안 정규화 및 비교 (수학 답안에 맞게 개선)
    correct_normalized = problem.correct_answer.strip().lower()
    user_normalized = actual_user_answer.strip().lower()
    
    # 기본 문자열 매칭
    is_correct = correct_normalized == user_normalized
    
    # 수학 답안의 경우 유연한 매칭 적용
    if not is_correct and problem.problem_type == "short_answer":
        import re
        
        # 정답에서 숫자나 수식 부분만 추출
        correct_values = re.findall(r'-?\d+(?:\.\d+)?', correct_normalized)
        user_values = re.findall(r'-?\d+(?:\.\d+)?', user_normalized)
        
        # 추출된 숫자들이 일치하는지 확인
        if correct_values and user_values:
            is_correct = correct_values == user_values
            print(f"🔍 디버그: 수학 답안 매칭 - 정답 숫자: {correct_values}, 학생 숫자: {user_values}, 결과: {is_correct}")
        
        # 추가적으로 콤마로 분리된 값들 비교 (a=3, b=-5 vs 3,-5)
        if not is_correct:
            # 콤마로 분리하여 숫자만 추출
            correct_parts = [part.strip() for part in correct_normalized.replace('=', ',').split(',')]
            user_parts = [part.strip() for part in user_normalized.split(',')]
            
            correct_nums = []
            user_nums = []
            
            for part in correct_parts:
                nums = re.findall(r'-?\d+(?:\.\d+)?', part)
                correct_nums.extend(nums)
            
            for part in user_parts:
                nums = re.findall(r'-?\d+(?:\.\d+)?', part)
                user_nums.extend(nums)
            
            is_correct = correct_nums == user_nums
            print(f"🔍 디버그: 콤마 분리 매칭 - 정답 숫자: {correct_nums}, 학생 숫자: {user_nums}, 결과: {is_correct}")
    score = points_per_problem if is_correct else 0
    
    return {
        "problem_id": problem.id,
        "problem_type": problem.problem_type,
        "user_answer": user_answer,  # 원래 사용자 입력 (A, B, C, D)
        "actual_user_answer": actual_user_answer,  # 변환된 실제 답안 내용
        "correct_answer": problem.correct_answer,
        "is_correct": is_correct,
        "score": score,
        "points_per_problem": points_per_problem,
        "explanation": problem.explanation
    }


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