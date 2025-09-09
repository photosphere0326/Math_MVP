from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base

class GradingSession(Base):
    """채점 세션 테이블 - 한 번의 채점 작업을 나타냄"""
    __tablename__ = "grading_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    worksheet_id = Column(Integer, ForeignKey("worksheets.id"), nullable=False)
    celery_task_id = Column(String(255), unique=True, index=True)
    
    # 전체 채점 결과
    total_problems = Column(Integer, nullable=False)
    correct_count = Column(Integer, nullable=False, default=0)
    total_score = Column(Float, nullable=False, default=0.0)
    max_possible_score = Column(Float, nullable=False)
    points_per_problem = Column(Float, nullable=False)
    
    # OCR 관련 정보
    ocr_text = Column(Text)  # 전체 OCR 추출 텍스트 (이미지 업로드 방식)
    ocr_results = Column(JSON)  # 문제별 OCR 결과 (캔버스 방식)
    
    # 답안 정보
    multiple_choice_answers = Column(JSON)  # 객관식 답안
    input_method = Column(String(50))  # "image_upload", "canvas", "mixed"
    
    # 메타 정보
    graded_at = Column(DateTime, default=datetime.utcnow)
    graded_by = Column(Integer, nullable=False)  # user_id
    
    # 관계
    problem_results = relationship("ProblemGradingResult", back_populates="grading_session", cascade="all, delete-orphan")


class ProblemGradingResult(Base):
    """문제별 채점 결과 테이블"""
    __tablename__ = "problem_grading_results"
    
    id = Column(Integer, primary_key=True, index=True)
    grading_session_id = Column(Integer, ForeignKey("grading_sessions.id"), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    
    # 답안 정보
    user_answer = Column(Text)  # 학생이 제출한 답안
    actual_user_answer = Column(Text)  # 변환된 실제 답안 (객관식의 경우)
    correct_answer = Column(Text, nullable=False)
    
    # 채점 결과
    is_correct = Column(Boolean, nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    points_per_problem = Column(Float, nullable=False)
    
    # 문제 정보
    problem_type = Column(String(50), nullable=False)  # multiple_choice, essay, short_answer
    difficulty = Column(String(10))  # A, B, C
    input_method = Column(String(50))  # checkbox, handwriting_ocr, canvas
    
    # AI 채점 결과 (서술형)
    ai_score = Column(Float)  # AI가 매긴 점수 (0-100)
    ai_feedback = Column(Text)  # AI 피드백
    strengths = Column(Text)  # 잘한 점
    improvements = Column(Text)  # 개선점
    keyword_score_ratio = Column(Float)  # 키워드 매칭 비율
    
    # 설명
    explanation = Column(Text)  # 문제 해설
    
    # 관계
    grading_session = relationship("GradingSession", back_populates="problem_results")