from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


class SchoolLevel(str, Enum):
    ELEMENTARY = "초등학교"
    MIDDLE = "중학교"
    HIGH = "고등학교"


class Semester(str, Enum):
    FIRST = "1학기"
    SECOND = "2학기"


class ProblemCount(str, Enum):
    """문제 개수 선택 (드롭다운용)"""
    TEN = "10문제"
    TWENTY = "20문제"
    
    @property
    def value_int(self) -> int:
        """정수 값 반환"""
        return 10 if self == ProblemCount.TEN else 20


class DifficultyRatio(BaseModel):
    """난이도 비율 설정 (A:B:C)"""
    A: int = Field(ge=0, le=100, description="상급 난이도 비율")
    B: int = Field(ge=0, le=100, description="중급 난이도 비율") 
    C: int = Field(ge=0, le=100, description="하급 난이도 비율")
    
    def model_post_init(self, __context):
        total = self.A + self.B + self.C
        if total != 100:
            raise ValueError("난이도 비율의 합은 100이어야 합니다")


class ProblemTypeRatio(BaseModel):
    """문제 유형 비율 설정 (객관식:주관식:단답형)"""
    multiple_choice: int = Field(ge=0, le=100, description="객관식 비율")
    essay: int = Field(ge=0, le=100, description="주관식 비율")
    short_answer: int = Field(ge=0, le=100, description="단답형 비율")
    
    def model_post_init(self, __context):
        total = self.multiple_choice + self.essay + self.short_answer
        if total != 100:
            raise ValueError("문제 유형 비율의 합은 100이어야 합니다")


class ChapterInfo(BaseModel):
    """소단원 정보"""
    chapter_number: str
    chapter_name: str
    unit_name: str


class MathProblemGenerationRequest(BaseModel):
    """수학 문제 생성 요청 스키마"""
    # 교육과정 선택
    school_level: SchoolLevel = Field(description="초/중/고 선택")
    grade: int = Field(ge=1, le=6, description="학년 (초:1-6, 중고:1-3)")
    semester: Semester = Field(description="학기")
    unit_number: str = Field(description="단원 번호 (I, II, III, IV)")
    chapter: ChapterInfo = Field(description="소단원 정보")
    
    # 문제 생성 설정
    problem_count: ProblemCount = Field(description="총 문제 수")
    difficulty_ratio: DifficultyRatio = Field(description="난이도 비율")
    problem_type_ratio: ProblemTypeRatio = Field(description="문제 유형 비율")
    
    # 세부사항
    user_text: str = Field(description="사용자 직접 입력 세부사항")
    
    
class UnitInfo(BaseModel):
    """대단원 정보"""
    unit_number: str
    unit_name: str
    chapters: List[ChapterInfo]


class GradeInfo(BaseModel):
    """학년별 정보"""
    grade: int
    semesters: Dict[str, List[UnitInfo]]


class CurriculumStructureResponse(BaseModel):
    """교육과정 구조 응답"""
    school_level: SchoolLevel
    grades: Dict[str, GradeInfo]  # key: "1", "2", "3"...


class GenerationSummary(BaseModel):
    """생성 요약 정보"""
    total_problems: int
    difficulty_distribution: Dict[str, int]  # {"A": 3, "B": 4, "C": 3}
    type_distribution: Dict[str, int]  # {"multiple_choice": 5, "essay": 3, "short_answer": 2}


class MathProblemGenerationResponse(BaseModel):
    """수학 문제 생성 응답"""
    generation_id: str = Field(description="생성 세션 ID")
    worksheet_id: int = Field(description="워크시트 ID")
    school_level: str
    grade: int
    semester: str
    unit_name: str
    chapter_name: str
    problem_count: int
    difficulty_ratio: Dict[str, int]
    problem_type_ratio: Dict[str, int]
    user_prompt: str
    actual_difficulty_distribution: Dict[str, int]
    actual_type_distribution: Dict[str, int]
    problems: List[dict] = Field(description="생성된 문제 목록")
    total_generated: int
    created_at: str