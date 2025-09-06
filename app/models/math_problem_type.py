from sqlalchemy import Column, Integer, String, JSON, Text
from ..database import Base

class MathChapter(Base):
    __tablename__ = "math_chapters"
    
    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, unique=True, index=True)
    chapter_name = Column(String(100), nullable=False)
    problem_types = Column(JSON, nullable=False)  # 문제 유형 목록을 JSON으로 저장
    description = Column(Text, nullable=True)
    grade = Column(String(10), default="중1")  # 학년
    
    def __repr__(self):
        return f"<MathChapter(chapter_id={self.chapter_id}, name='{self.chapter_name}')>"