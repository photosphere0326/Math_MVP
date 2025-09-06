from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from celery.result import AsyncResult

from ..database import get_db
from ..schemas.math_generation import (
    MathProblemGenerationRequest, 
    MathProblemGenerationResponse, 
    CurriculumStructureResponse,
    SchoolLevel
)
from ..services.math_generation_service import MathGenerationService
from ..tasks import generate_math_problems_task, grade_problems_task
from ..celery_app import celery_app

router = APIRouter()
math_service = MathGenerationService()


@router.get("/curriculum/structure")
async def get_curriculum_structure(
    school_level: Optional[SchoolLevel] = Query(None, description="학교급 필터"),
    db: Session = Depends(get_db)
):
    """교육과정 구조 조회 - 초/중/고 > 학년 > 학기 > 단원 > 소단원"""
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
    """대단원 목록 조회"""
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
    """특정 대단원의 소단원 목록 조회"""
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
    """
    수학 문제 생성 (비동기)
    
    단계별 선택:
    1. 초/중/고 선택
    2. 학년 선택 (초: 1-6, 중고: 1-3)
    3. 학기 선택 (1학기/2학기)
    4. 단원 선택 (I, II, III, IV)
    5. 소단원(챕터) 선택
    6. 총 문제수 설정 (10문제 or 20문제)
    7. 난이도 비율 선택 (A:B:C)
    8. 유형 비율 선택 (객관식:주관식:단답형)
    9. 세부사항 텍스트 입력
    
    반환값: task_id를 통해 진행 상황을 추적할 수 있습니다.
    """
    try:
        # Celery 태스크 시작
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
    """문제 생성 이력 조회"""
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
    """특정 생성 세션 상세 조회"""
    try:
        session = math_service.get_generation_detail(db, generation_id, user_id=1)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 생성 세션을 찾을 수 없습니다"
            )
        
        # 생성된 문제들 조회 (generation_id로 워크시트를 찾은 후 문제들 조회)
        from ..models.problem import Problem
        from ..models.worksheet import Worksheet
        
        # generation_id로 워크시트 찾기
        worksheet = db.query(Worksheet)\
            .filter(Worksheet.generation_id == generation_id)\
            .first()
            
        if not worksheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 생성 세션의 워크시트를 찾을 수 없습니다"
            )
        
        # 워크시트의 문제들 조회
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
    """태스크 상태 및 결과 조회"""
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


@router.get("/worksheets")
async def get_worksheets(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """워크시트 목록 조회"""
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
    """워크시트 상세 조회"""
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
        
        # 워크시트의 문제들 조회
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
    answers: dict,  # {"problem_id": "answer", ...} 형태
    db: Session = Depends(get_db)
):
    """워크시트 채점 (비동기)"""
    try:
        # 워크시트 존재 확인
        from ..models.worksheet import Worksheet
        worksheet = db.query(Worksheet).filter(Worksheet.id == worksheet_id).first()
        if not worksheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="워크시트를 찾을 수 없습니다."
            )
        
        # Celery 태스크 시작
        task = grade_problems_task.delay(
            worksheet_id=worksheet_id,
            answers=answers,
            user_id=1
        )
        
        return {
            "task_id": task.id,
            "status": "PENDING",
            "message": "채점이 시작되었습니다. /tasks/{task_id} 엔드포인트로 진행 상황을 확인하세요."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채점 요청 중 오류 발생: {str(e)}"
        )