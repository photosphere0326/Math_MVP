from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, AsyncGenerator
from celery.result import AsyncResult
import asyncio
import json

from ..database import get_db
from ..schemas.math_generation import (
    MathProblemGenerationRequest, 
    SchoolLevel
)
from ..services.math_generation_service import MathGenerationService
from ..tasks import generate_math_problems_task, grade_problems_task, grade_problems_mixed_task
from ..celery_app import celery_app

router = APIRouter()
math_service = MathGenerationService()


@router.get("/curriculum/structure")
async def get_curriculum_structure(
    school_level: Optional[SchoolLevel] = Query(None, description="학교급 필터"),
    db: Session = Depends(get_db)
):
    try:
        structure = math_service.get_curriculum_structure(
            db, 
            school_level.value if school_level else None
        )
        return {"structure": structure}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"교육과정 구조 조회 중 오류: {str(e)}"
        )


@router.get("/curriculum/units")
async def get_units():
    try:
        units = math_service.get_units()
        return {"units": units}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대단원 목록 조회 중 오류: {str(e)}"
        )


@router.get("/curriculum/chapters")
async def get_chapters_by_unit(unit_name: str = Query(..., description="대단원명")):
    try:
        chapters = math_service.get_chapters_by_unit(unit_name)
        return {"chapters": chapters}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"소단원 목록 조회 중 오류: {str(e)}"
        )


@router.post("/generate")
async def generate_math_problems(
    request: MathProblemGenerationRequest,
    db: Session = Depends(get_db)
):
    try:
        task = generate_math_problems_task.delay(
            request_data=request.model_dump(),
            user_id=1
        )
        
        return {
            "task_id": task.id,
            "status": "PENDING",
            "message": "문제 생성이 시작되었습니다. /tasks/{task_id} 엔드포인트로 진행 상황을 확인하세요."
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문제 생성 요청 중 오류 발생: {str(e)}"
        )


@router.get("/generation/history")
async def get_generation_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    try:
        history = math_service.get_generation_history(db, user_id=1, skip=skip, limit=limit)
        
        result = []
        for session in history:
            result.append({
                "generation_id": session.generation_id,
                "school_level": session.school_level,
                "grade": session.grade,
                "semester": session.semester,
                "chapter_name": session.chapter_name,
                "problem_count": session.problem_count,
                "total_generated": session.total_generated,
                "created_at": session.created_at.isoformat()
            })
        
        return {"history": result, "total": len(result)}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"생성 이력 조회 중 오류: {str(e)}"
        )


@router.get("/generation/{generation_id}")
async def get_generation_detail(
    generation_id: str,
    db: Session = Depends(get_db)
):
    try:
        session = math_service.get_generation_detail(db, generation_id, user_id=1)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 생성 세션을 찾을 수 없습니다"
            )
        
        from ..models.problem import Problem
        from ..models.worksheet import Worksheet
        worksheet = db.query(Worksheet)\
            .filter(Worksheet.generation_id == generation_id)\
            .first()
            
        if not worksheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 생성 세션의 워크시트를 찾을 수 없습니다"
            )
        
        problems = db.query(Problem)\
            .filter(Problem.worksheet_id == worksheet.id)\
            .order_by(Problem.sequence_order)\
            .all()
        
        problem_list = []
        for problem in problems:
            import json
            problem_dict = {
                "id": problem.id,
                "problem_type": problem.problem_type.value,
                "difficulty": problem.difficulty.value,
                "question": problem.question,
                "choices": json.loads(problem.choices) if problem.choices else None,
                "correct_answer": problem.correct_answer,
                "explanation": problem.explanation,
                "latex_content": problem.latex_content
            }
            problem_list.append(problem_dict)
        
        return {
            "generation_info": {
                "generation_id": session.generation_id,
                "school_level": session.school_level,
                "grade": session.grade,
                "semester": session.semester,
                "unit_name": session.unit_name,
                "chapter_name": session.chapter_name,
                "problem_count": session.problem_count,
                "difficulty_ratio": session.difficulty_ratio,
                "problem_type_ratio": session.problem_type_ratio,
                "user_text": session.user_text,
                "actual_difficulty_distribution": session.actual_difficulty_distribution,
                "actual_type_distribution": session.actual_type_distribution,
                "total_generated": session.total_generated,
                "created_at": session.created_at.isoformat()
            },
            "problems": problem_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 상세 조회 중 오류: {str(e)}"
        )


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        if result.state == 'PENDING':
            return {
                "task_id": task_id,
                "status": "PENDING",
                "message": "태스크가 대기 중입니다."
            }
        elif result.state == 'PROGRESS':
            return {
                "task_id": task_id,
                "status": "PROGRESS",
                "current": result.info.get('current', 0),
                "total": result.info.get('total', 100),
                "message": result.info.get('status', '처리 중...')
            }
        elif result.state == 'SUCCESS':
            return {
                "task_id": task_id,
                "status": "SUCCESS",
                "result": result.result
            }
        elif result.state == 'FAILURE':
            return {
                "task_id": task_id,
                "status": "FAILURE",
                "error": str(result.info) if result.info else "알 수 없는 오류가 발생했습니다."
            }
        else:
            return {
                "task_id": task_id,
                "status": result.state,
                "info": result.info
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"태스크 상태 조회 중 오류: {str(e)}"
        )


@router.get("/tasks/{task_id}/stream")
async def stream_task_status(task_id: str):
    """SSE를 통한 실시간 태스크 상태 스트리밍"""
    
    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            result = AsyncResult(task_id, app=celery_app)
            
            while True:
                # 태스크 상태 확인
                if result.state == 'PENDING':
                    data = {
                        "task_id": task_id,
                        "status": "PENDING",
                        "message": "태스크가 대기 중입니다."
                    }
                elif result.state == 'PROGRESS':
                    data = {
                        "task_id": task_id,
                        "status": "PROGRESS",
                        "current": result.info.get('current', 0),
                        "total": result.info.get('total', 100),
                        "message": result.info.get('status', '처리 중...')
                    }
                elif result.state == 'SUCCESS':
                    data = {
                        "task_id": task_id,
                        "status": "SUCCESS",
                        "result": result.result
                    }
                    # 성공 시 스트림 종료
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    break
                elif result.state == 'FAILURE':
                    data = {
                        "task_id": task_id,
                        "status": "FAILURE",
                        "error": str(result.info) if result.info else "알 수 없는 오류가 발생했습니다."
                    }
                    # 실패 시 스트림 종료
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    break
                else:
                    data = {
                        "task_id": task_id,
                        "status": result.state,
                        "info": result.info
                    }
                
                # SSE 형식으로 데이터 전송
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                # 태스크가 완료되었으면 종료
                if result.state in ['SUCCESS', 'FAILURE']:
                    break
                
                # 1초 대기
                await asyncio.sleep(1)
                
        except Exception as e:
            error_data = {
                "task_id": task_id,
                "status": "ERROR",
                "error": f"스트리밍 중 오류: {str(e)}"
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.get("/worksheets")
async def get_worksheets(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    try:
        from ..models.worksheet import Worksheet
        
        worksheets = db.query(Worksheet)\
            .filter(Worksheet.created_by == 1)\
            .order_by(Worksheet.created_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
        
        result = []
        for worksheet in worksheets:
            result.append({
                "id": worksheet.id,
                "title": worksheet.title,
                "school_level": worksheet.school_level,
                "grade": worksheet.grade,
                "semester": worksheet.semester,
                "unit_name": worksheet.unit_name,
                "chapter_name": worksheet.chapter_name,
                "problem_count": worksheet.problem_count,
                "difficulty_ratio": worksheet.difficulty_ratio,
                "problem_type_ratio": worksheet.problem_type_ratio,
                "user_prompt": worksheet.user_prompt,
                "actual_difficulty_distribution": worksheet.actual_difficulty_distribution,
                "actual_type_distribution": worksheet.actual_type_distribution,
                "status": worksheet.status.value,
                "created_at": worksheet.created_at.isoformat()
            })
        
        return {"worksheets": result, "total": len(result)}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"워크시트 목록 조회 중 오류: {str(e)}"
        )


@router.get("/worksheets/{worksheet_id}")
async def get_worksheet_detail(
    worksheet_id: int,
    db: Session = Depends(get_db)
):
    try:
        from ..models.worksheet import Worksheet
        from ..models.problem import Problem
        
        worksheet = db.query(Worksheet)\
            .filter(Worksheet.id == worksheet_id, Worksheet.created_by == 1)\
            .first()
        
        if not worksheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="워크시트를 찾을 수 없습니다."
            )
        
        problems = db.query(Problem)\
            .filter(Problem.worksheet_id == worksheet_id)\
            .order_by(Problem.sequence_order)\
            .all()
        
        problem_list = []
        for problem in problems:
            import json
            problem_dict = {
                "id": problem.id,
                "sequence_order": problem.sequence_order,
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
            }
            problem_list.append(problem_dict)
        
        return {
            "worksheet": {
                "id": worksheet.id,
                "title": worksheet.title,
                "school_level": worksheet.school_level,
                "grade": worksheet.grade,
                "semester": worksheet.semester,
                "unit_name": worksheet.unit_name,
                "chapter_name": worksheet.chapter_name,
                "problem_count": worksheet.problem_count,
                "difficulty_ratio": worksheet.difficulty_ratio,
                "problem_type_ratio": worksheet.problem_type_ratio,
                "user_prompt": worksheet.user_prompt,
                "generation_id": worksheet.generation_id,
                "actual_difficulty_distribution": worksheet.actual_difficulty_distribution,
                "actual_type_distribution": worksheet.actual_type_distribution,
                "status": worksheet.status.value,
                "created_at": worksheet.created_at.isoformat()
            },
            "problems": problem_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"워크시트 상세 조회 중 오류: {str(e)}"
        )


@router.post("/worksheets/{worksheet_id}/grade")
async def grade_worksheet(
    worksheet_id: int,
    answer_sheet: UploadFile = File(..., description="답안지 이미지 파일"),
    db: Session = Depends(get_db)
):
    try:
        from ..models.worksheet import Worksheet
        worksheet = db.query(Worksheet).filter(Worksheet.id == worksheet_id).first()
        if not worksheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="워크시트를 찾을 수 없습니다."
            )
        
        if not answer_sheet:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="답안지 이미지가 필요합니다."
            )
        
        allowed_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]
        if not any(answer_sheet.filename.lower().endswith(ext) for ext in allowed_extensions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="지원되는 이미지 형식: JPG, PNG, BMP, TIFF"
            )
        
        image_data = await answer_sheet.read()
        
        task = grade_problems_task.delay(
            worksheet_id=worksheet_id,
            image_data=image_data,
            user_id=1
        )
        
        return {
            "task_id": task.id,
            "status": "PENDING",
            "message": "답안지 OCR 처리 및 채점이 시작되었습니다. /tasks/{task_id} 엔드포인트로 진행 상황을 확인하세요.",
            "uploaded_file": answer_sheet.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채점 요청 중 오류 발생: {str(e)}"
        )


@router.post("/worksheets/{worksheet_id}/grade-canvas")
async def grade_worksheet_canvas(
    worksheet_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    try:
        print(f"🔍 채점 요청 시작: worksheet_id={worksheet_id}")
        
        from ..models.worksheet import Worksheet
        worksheet = db.query(Worksheet).filter(Worksheet.id == worksheet_id).first()
        if not worksheet:
            print(f"❌ 워크시트 {worksheet_id}를 찾을 수 없음")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="워크시트를 찾을 수 없습니다."
            )
        
        print(f"✅ 워크시트 발견: {worksheet.title}")
        
        multiple_choice_answers = request.get("multiple_choice_answers", {})
        canvas_answers = request.get("canvas_answers", {})
        
        print(f"🔍 요청 데이터: MC답안={len(multiple_choice_answers)}, 캔버스답안={len(canvas_answers)}")
        
        task = grade_problems_mixed_task.delay(
            worksheet_id=worksheet_id,
            multiple_choice_answers=multiple_choice_answers,
            canvas_answers=canvas_answers,
            user_id=1
        )
        
        print(f"✅ Celery 태스크 시작: {task.id}")
        
        return {
            "task_id": task.id,
            "status": "PENDING",
            "message": "캔버스 채점이 시작되었습니다. 객관식은 라디오 버튼으로, 주관식은 캔버스 그림으로 처리됩니다.",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 채점 요청 오류: {str(e)}")
        print(f"❌ 오류 타입: {type(e).__name__}")
        import traceback
        print(f"❌ 스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"캔버스 채점 요청 중 오류 발생: {str(e)}"
        )


@router.post("/worksheets/{worksheet_id}/grade-mixed")
async def grade_worksheet_mixed(
    worksheet_id: int,
    multiple_choice_answers: dict = {},
    handwritten_answer_sheet: Optional[UploadFile] = File(None, description="손글씨 답안지 이미지 (서술형/단답형)"),
    db: Session = Depends(get_db)
):
    try:
        from ..models.worksheet import Worksheet
        worksheet = db.query(Worksheet).filter(Worksheet.id == worksheet_id).first()
        if not worksheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="워크시트를 찾을 수 없습니다."
            )
        
        handwritten_image_data = None
        if handwritten_answer_sheet and handwritten_answer_sheet.filename:
            allowed_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]
            if not any(handwritten_answer_sheet.filename.lower().endswith(ext) for ext in allowed_extensions):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="지원되는 이미지 형식: JPG, PNG, BMP, TIFF"
                )
            handwritten_image_data = await handwritten_answer_sheet.read()
        
        task = grade_problems_mixed_task.delay(
            worksheet_id=worksheet_id,
            multiple_choice_answers=multiple_choice_answers,
            handwritten_image_data=handwritten_image_data,
            user_id=1
        )
        
        return {
            "task_id": task.id,
            "status": "PENDING",
            "message": "혼합형 채점이 시작되었습니다. 객관식은 체크박스로, 서술형/단답형은 OCR로 처리됩니다.",
            "multiple_choice_count": len(multiple_choice_answers),
            "has_handwritten_answers": handwritten_image_data is not None,
            "handwritten_file": handwritten_answer_sheet.filename if handwritten_answer_sheet else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"혼합형 채점 요청 중 오류 발생: {str(e)}"
        )


@router.put("/worksheets/{worksheet_id}")
async def update_worksheet(
    worksheet_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    try:
        from ..models.worksheet import Worksheet
        from ..models.problem import Problem
        
        worksheet = db.query(Worksheet)\
            .filter(Worksheet.id == worksheet_id, Worksheet.created_by == 1)\
            .first()
        
        if not worksheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="워크시트를 찾을 수 없습니다."
            )
        
        if "title" in request:
            worksheet.title = request["title"]
        if "user_prompt" in request:
            worksheet.user_prompt = request["user_prompt"]
        if "difficulty_ratio" in request:
            worksheet.difficulty_ratio = request["difficulty_ratio"]
        if "problem_type_ratio" in request:
            worksheet.problem_type_ratio = request["problem_type_ratio"]
        
        if "problems" in request:
            for problem_data in request["problems"]:
                problem_id = problem_data.get("id")
                if problem_id:
                    problem = db.query(Problem)\
                        .filter(Problem.id == problem_id, Problem.worksheet_id == worksheet_id)\
                        .first()
                    
                    if problem:
                        if "question" in problem_data:
                            problem.question = problem_data["question"]
                        if "choices" in problem_data:
                            import json
                            problem.choices = json.dumps(problem_data["choices"], ensure_ascii=False)
                        if "correct_answer" in problem_data:
                            problem.correct_answer = problem_data["correct_answer"]
                        if "explanation" in problem_data:
                            problem.explanation = problem_data["explanation"]
                        if "difficulty" in problem_data:
                            problem.difficulty = problem_data["difficulty"]
                        if "problem_type" in problem_data:
                            problem.problem_type = problem_data["problem_type"]
                        if "latex_content" in problem_data:
                            problem.latex_content = problem_data["latex_content"]
        
        db.commit()
        db.refresh(worksheet)
        
        return {
            "message": "워크시트가 성공적으로 수정되었습니다.",
            "worksheet_id": worksheet_id,
            "updated_at": worksheet.updated_at.isoformat() if worksheet.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"워크시트 수정 중 오류 발생: {str(e)}"
        )


@router.put("/problems/{problem_id}")
async def update_problem(
    problem_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    try:
        from ..models.problem import Problem
        
        problem = db.query(Problem)\
            .join(Problem.worksheet)\
            .filter(Problem.id == problem_id)\
            .first()
        
        if not problem:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="문제를 찾을 수 없습니다."
            )
        
        if "question" in request:
            problem.question = request["question"]
        if "choices" in request:
            import json
            problem.choices = json.dumps(request["choices"], ensure_ascii=False)
        if "correct_answer" in request:
            problem.correct_answer = request["correct_answer"]
        if "explanation" in request:
            problem.explanation = request["explanation"]
        if "difficulty" in request:
            problem.difficulty = request["difficulty"]
        if "problem_type" in request:
            problem.problem_type = request["problem_type"]
        if "latex_content" in request:
            problem.latex_content = request["latex_content"]
        
        db.commit()
        db.refresh(problem)
        
        return {
            "message": "문제가 성공적으로 수정되었습니다.",
            "problem_id": problem_id,
            "updated_at": problem.updated_at.isoformat() if problem.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문제 수정 중 오류 발생: {str(e)}"
        )


@router.get("/grading-history")
async def get_grading_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    worksheet_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """채점 이력 조회"""
    try:
        from ..models.grading_result import GradingSession
        
        query = db.query(GradingSession).filter(GradingSession.graded_by == 1)
        
        if worksheet_id:
            query = query.filter(GradingSession.worksheet_id == worksheet_id)
        
        grading_sessions = query.order_by(GradingSession.graded_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
        
        result = []
        for session in grading_sessions:
            result.append({
                "grading_session_id": session.id,
                "worksheet_id": session.worksheet_id,
                "total_problems": session.total_problems,
                "correct_count": session.correct_count,
                "total_score": session.total_score,
                "max_possible_score": session.max_possible_score,
                "points_per_problem": session.points_per_problem,
                "input_method": session.input_method,
                "graded_at": session.graded_at.isoformat(),
                "celery_task_id": session.celery_task_id
            })
        
        return {"grading_history": result, "total": len(result)}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채점 이력 조회 중 오류: {str(e)}"
        )


@router.get("/grading-history/{grading_session_id}")
async def get_grading_session_detail(
    grading_session_id: int,
    db: Session = Depends(get_db)
):
    """채점 세션 상세 조회"""
    try:
        from ..models.grading_result import GradingSession, ProblemGradingResult
        
        session = db.query(GradingSession)\
            .filter(GradingSession.id == grading_session_id, GradingSession.graded_by == 1)\
            .first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="채점 세션을 찾을 수 없습니다"
            )
        
        problem_results = db.query(ProblemGradingResult)\
            .filter(ProblemGradingResult.grading_session_id == grading_session_id)\
            .all()
        
        problem_list = []
        for result in problem_results:
            problem_dict = {
                "problem_id": result.problem_id,
                "user_answer": result.user_answer,
                "actual_user_answer": result.actual_user_answer,
                "correct_answer": result.correct_answer,
                "is_correct": result.is_correct,
                "score": result.score,
                "points_per_problem": result.points_per_problem,
                "problem_type": result.problem_type,
                "input_method": result.input_method,
                "ai_score": result.ai_score,
                "ai_feedback": result.ai_feedback,
                "strengths": result.strengths,
                "improvements": result.improvements,
                "keyword_score_ratio": result.keyword_score_ratio,
                "explanation": result.explanation
            }
            problem_list.append(problem_dict)
        
        return {
            "grading_session": {
                "id": session.id,
                "worksheet_id": session.worksheet_id,
                "total_problems": session.total_problems,
                "correct_count": session.correct_count,
                "total_score": session.total_score,
                "max_possible_score": session.max_possible_score,
                "points_per_problem": session.points_per_problem,
                "ocr_text": session.ocr_text,
                "ocr_results": session.ocr_results,
                "multiple_choice_answers": session.multiple_choice_answers,
                "input_method": session.input_method,
                "graded_at": session.graded_at.isoformat(),
                "celery_task_id": session.celery_task_id
            },
            "problem_results": problem_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채점 세션 상세 조회 중 오류: {str(e)}"
        )