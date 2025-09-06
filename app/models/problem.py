from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Problem(Base):
    """수학 문제 모델 - 워크시트에 속하는 문제 저장용"""
    __tablename__ = "problems"
    
    id = Column(Integer, primary_key=True, index=True)
    worksheet_id = Column(Integer, ForeignKey("worksheets.id"), nullable=False)  # 소속 워크시트
    sequence_order = Column(Integer, nullable=False)  # 워크시트 내 순서 (1, 2, 3, ...)
    
    # 문제 기본 정보
    problem_type = Column(String, nullable=False)  # "multiple_choice", "essay", "short_answer"
    difficulty = Column(String, nullable=False)  # "A", "B", "C"
    
    # 문제 내용
    question = Column(Text, nullable=False)  # 문제 텍스트
    choices = Column(JSON)  # 객관식 선택지 (JSON 배열)
    correct_answer = Column(Text, nullable=False)  # 정답
    explanation = Column(Text)  # 해설
    latex_content = Column(Text)  # LaTeX 수식이 포함된 내용
    image_url = Column(String)  # 문제 이미지 URL
    
    # 추가 정보 (diagram 관련)
    has_diagram = Column(String)  # true/false를 문자열로 저장
    diagram_type = Column(String)  # concentration, train, geometry, graph 등
    diagram_elements = Column(JSON)  # 다이어그램 요소들
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 관계
    worksheet = relationship("Worksheet", back_populates="problems")