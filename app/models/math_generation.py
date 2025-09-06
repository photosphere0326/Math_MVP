from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class MathProblemGeneration(Base):
    """수학 문제 생성 세션 기록"""
    __tablename__ = "math_problem_generations"
    
    id = Column(Integer, primary_key=True, index=True)
    generation_id = Column(String, unique=True, nullable=False, index=True)
    
    # 교육과정 정보
    school_level = Column(String, nullable=False)  # "초등학교", "중학교", "고등학교"
    grade = Column(Integer, nullable=False)
    semester = Column(String, nullable=False)
    unit_number = Column(String, nullable=False)
    unit_name = Column(String, nullable=False)
    chapter_number = Column(String, nullable=False)
    chapter_name = Column(String, nullable=False)
    
    # 생성 설정
    problem_count = Column(Integer, nullable=False)  # 10 or 20
    difficulty_ratio = Column(JSON, nullable=False)  # {"A": 30, "B": 40, "C": 30}
    problem_type_ratio = Column(JSON, nullable=False)  # {"multiple_choice": 50, "essay": 30, "short_answer": 20}
    
    # 사용자 입력
    user_text = Column(Text, nullable=False)
    
    # 생성 결과 요약
    actual_difficulty_distribution = Column(JSON)  # 실제 생성된 난이도 분포
    actual_type_distribution = Column(JSON)  # 실제 생성된 유형 분포
    total_generated = Column(Integer)  # 실제 생성된 문제 수
    
    # 메타데이터
    created_by = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 관계
    # problems relationship removed since Problem model no longer exists


# GeneratedProblemSet 모델 제거됨 - Problem 테이블의 sequence_order와 worksheet_id로 대체