from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..schemas.math_generation import (
    MathProblemGenerationRequest, 
    MathProblemGenerationResponse, 
    CurriculumStructureResponse,
    SchoolLevel
)
from ..services.math_generation_service import MathGenerationService

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


@router.post("/generate", response_model=MathProblemGenerationResponse)
async def generate_math_problems(
    request: MathProblemGenerationRequest,
    db: Session = Depends(get_db)
):
    """
    수학 문제 생성
    
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
    """
    try:
        result = math_service.generate_problems(db, request, user_id=1)
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문제 생성 중 오류 발생: {str(e)}"
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
        
        # 생성된 문제들 조회
        from ..models.problem import Problem
        from ..models.math_generation import GeneratedProblemSet
        
        problems = db.query(Problem)\
            .join(GeneratedProblemSet)\
            .filter(GeneratedProblemSet.generation_id == generation_id)\
            .order_by(GeneratedProblemSet.sequence_order)\
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