import json
import os
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from ..schemas.math_generation import MathProblemGenerationRequest, MathProblemGenerationResponse
from ..services.ai_service import AIService
from ..models.math_generation import MathProblemGeneration
from ..models.problem import Problem
from ..models.worksheet import Worksheet, WorksheetStatus
import uuid
from datetime import datetime


class MathGenerationService:
    """수학 문제 생성 서비스"""
    
    def __init__(self):
        self.ai_service = AIService()
    
    def get_curriculum_structure(self, db: Session, school_level: Optional[str] = None) -> Dict:
        """교육과정 구조 조회 - 중1 1학기에 초점"""
        
        # middle1_math_curriculum.json 파일 읽기
        curriculum_file_path = os.path.join(os.path.dirname(__file__), "../../data/middle1_math_curriculum.json")
        
        try:
            with open(curriculum_file_path, 'r', encoding='utf-8') as f:
                curriculum_data = json.load(f)
        except FileNotFoundError:
            return {"error": "교육과정 데이터 파일을 찾을 수 없습니다."}
        except json.JSONDecodeError:
            return {"error": "교육과정 데이터 파일 형식이 올바르지 않습니다."}
        
        # 중1 1학기에 초점을 맞춘 구조화
        structure = {
            "school_levels": [
                {"value": "초등학교", "label": "초등학교", "grades": list(range(1, 7))},
                {"value": "중학교", "label": "중학교", "grades": list(range(1, 4))},
                {"value": "고등학교", "label": "고등학교", "grades": list(range(1, 4))}
            ]
        }
        
        # 중1 1학기 데이터를 기반으로 상세 구조 생성
        middle1_1semester = {}
        units = {}
        
        for item in curriculum_data:
            if item["grade"] == "중1" and item["semester"] == "1학기":
                unit_number = item["unit_number"]
                unit_name = item["unit_name"]
                
                if unit_number not in units:
                    units[unit_number] = {
                        "unit_number": unit_number,
                        "unit_name": unit_name,
                        "chapters": []
                    }
                
                units[unit_number]["chapters"].append({
                    "chapter_number": item["chapter_number"],
                    "chapter_name": item["chapter_name"],
                    "unit_name": unit_name,
                    "learning_objectives": item["learning_objectives"],
                    "keywords": item["keywords"],
                    "difficulty_levels": json.loads(item["difficulty_levels"]) if isinstance(item["difficulty_levels"], str) else item["difficulty_levels"]
                })
        
        middle1_1semester = {
            "grade": "중1",
            "semester": "1학기", 
            "units": list(units.values())
        }
        
        structure["middle1_1semester"] = middle1_1semester
        
        return structure
    
    def get_units(self) -> List[Dict]:
        """대단원 목록 조회"""
        curriculum_file_path = os.path.join(os.path.dirname(__file__), "../../data/middle1_math_curriculum.json")
        
        try:
            with open(curriculum_file_path, 'r', encoding='utf-8') as f:
                curriculum_data = json.load(f)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            return []
        
        units = {}
        for item in curriculum_data:
            if item["grade"] == "중1" and item["semester"] == "1학기":
                unit_name = item["unit_name"]
                if unit_name not in units:
                    units[unit_name] = {
                        "unit_number": item["unit_number"],
                        "unit_name": unit_name
                    }
        
        return list(units.values())
    
    def get_chapters_by_unit(self, unit_name: str) -> List[Dict]:
        """특정 대단원의 소단원 목록 조회"""
        curriculum_file_path = os.path.join(os.path.dirname(__file__), "../../data/middle1_math_curriculum.json")
        
        try:
            with open(curriculum_file_path, 'r', encoding='utf-8') as f:
                curriculum_data = json.load(f)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            return []
        
        chapters = []
        for item in curriculum_data:
            if (item["grade"] == "중1" and 
                item["semester"] == "1학기" and 
                item["unit_name"] == unit_name):
                chapters.append({
                    "unit_name": item["unit_name"],
                    "chapter_number": item["chapter_number"],
                    "chapter_name": item["chapter_name"],
                    "learning_objectives": item["learning_objectives"],
                    "keywords": item["keywords"]
                })
        
        return chapters
    
    def generate_problems(self, db: Session, request: MathProblemGenerationRequest, user_id: int) -> MathProblemGenerationResponse:
        """수학 문제 생성"""
        
        # 1. 생성 ID 생성
        generation_id = str(uuid.uuid4())
        
        # 2. 교육과정 데이터 가져오기
        curriculum_data = self._get_curriculum_data(request)
        
        # 3. 문제 유형 데이터 가져오기
        problem_types = self._get_problem_types(request.chapter.chapter_name)
        
        # 4. AI 서비스를 통한 문제 생성
        generated_problems = self._generate_problems_with_ai(
            curriculum_data=curriculum_data,
            problem_types=problem_types,
            request=request
        )
        
        # 5. 워크시트 생성
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
            actual_difficulty_distribution=self._calculate_difficulty_distribution(generated_problems),
            actual_type_distribution=self._calculate_type_distribution(generated_problems),
            status=WorksheetStatus.COMPLETED,
            created_by=user_id
        )
        
        db.add(worksheet)
        db.flush()
        
        # 6. 생성 세션 저장
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
            actual_difficulty_distribution=self._calculate_difficulty_distribution(generated_problems),
            actual_type_distribution=self._calculate_type_distribution(generated_problems),
            total_generated=len(generated_problems),
            created_by=user_id
        )
        
        db.add(generation_session)
        db.flush()
        
        # 7. 생성된 문제들을 워크시트에 연결하여 저장
        problem_responses = []
        for i, problem_data in enumerate(generated_problems):
            problem = Problem(
                worksheet_id=worksheet.id,  # 워크시트에 연결
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
        
        db.commit()
        
        # 8. 응답 생성 (워크시트 정보 포함)
        return MathProblemGenerationResponse(
            generation_id=generation_id,
            worksheet_id=worksheet.id,  # 워크시트 ID 추가
            school_level=request.school_level.value,
            grade=request.grade,
            semester=request.semester.value,
            unit_name=request.chapter.unit_name,
            chapter_name=request.chapter.chapter_name,
            problem_count=request.problem_count.value_int,
            difficulty_ratio=request.difficulty_ratio.model_dump(),
            problem_type_ratio=request.problem_type_ratio.model_dump(),
            user_prompt=request.user_text,
            actual_difficulty_distribution=self._calculate_difficulty_distribution(generated_problems),
            actual_type_distribution=self._calculate_type_distribution(generated_problems),
            problems=problem_responses,
            total_generated=len(generated_problems),
            created_at=datetime.now().isoformat()
        )
    
    def get_generation_history(self, db: Session, user_id: int, skip: int = 0, limit: int = 10) -> List[MathProblemGeneration]:
        """문제 생성 이력 조회"""
        return db.query(MathProblemGeneration)\
            .filter(MathProblemGeneration.created_by == user_id)\
            .order_by(MathProblemGeneration.created_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    def get_generation_detail(self, db: Session, generation_id: str, user_id: int) -> Optional[MathProblemGeneration]:
        """특정 생성 세션 상세 조회"""
        return db.query(MathProblemGeneration)\
            .filter(
                MathProblemGeneration.generation_id == generation_id,
                MathProblemGeneration.created_by == user_id
            )\
            .first()
    
    def _get_curriculum_data(self, request: MathProblemGenerationRequest) -> Dict:
        """요청에서 교육과정 데이터 추출"""
        return {
            'grade': f"{request.school_level.value[:-2]}{request.grade}",  # "중1"
            'semester': request.semester.value,
            'unit_name': request.chapter.unit_name,
            'chapter_name': request.chapter.chapter_name,
            'learning_objectives': getattr(request.chapter, 'learning_objectives', ''),
            'keywords': getattr(request.chapter, 'keywords', request.chapter.chapter_name)
        }
    
    def _get_problem_types(self, chapter_name: str) -> List[str]:
        """챕터명에 해당하는 문제 유형들 조회"""
        try:
            problem_types_file_path = os.path.join(os.path.dirname(__file__), "../../data/math_problem_types.json")
            
            with open(problem_types_file_path, 'r', encoding='utf-8') as f:
                problem_types_data = json.load(f)
            
            # 챕터명으로 문제 유형 찾기
            for chapter_data in problem_types_data["math_problem_types"]:
                if chapter_data["chapter_name"] == chapter_name:
                    return chapter_data["problem_types"]
            
            return []
        except Exception as e:
            print(f"문제 유형 로드 오류: {str(e)}")
            return []
    
    def _generate_problems_with_ai(self, curriculum_data: Dict, problem_types: List[str], request: MathProblemGenerationRequest) -> List[Dict]:
        """AI를 통한 문제 생성"""
        
        # 문제 유형 정보를 사용자 프롬프트에 추가
        enhanced_prompt = f"""
{request.user_text}

다음 문제 유형들 중에서 다양하게 선택하여 문제를 생성해주세요:
{', '.join(problem_types[:10])}  

문제 생성 요구사항:
- 총 {request.problem_count.value_int}개 문제
- 난이도 비율: A단계 {request.difficulty_ratio.A}%, B단계 {request.difficulty_ratio.B}%, C단계 {request.difficulty_ratio.C}%
- 유형 비율: 객관식 {request.problem_type_ratio.multiple_choice}%, 주관식 {request.problem_type_ratio.essay}%, 단답형 {request.problem_type_ratio.short_answer}%
- 위 문제 유형들을 참고하여 다양한 유형의 문제를 포함해주세요
        """
        
        try:
            # AI 서비스 호출 - 난이도 비율 정보 추가로 전달
            problems = self.ai_service.generate_math_problem(
                curriculum_data=curriculum_data,
                user_prompt=enhanced_prompt,
                problem_count=request.problem_count.value_int,
                difficulty_ratio=request.difficulty_ratio.model_dump()
            )
            
            return problems if isinstance(problems, list) else [problems]
            
        except Exception as e:
            print(f"AI 문제 생성 오류: {str(e)}")
            # 기본 문제 생성
            return self._generate_fallback_problems(request.problem_count.value_int, curriculum_data)
    
    def _generate_fallback_problems(self, count: int, curriculum_data: Dict) -> List[Dict]:
        """AI 오류시 기본 문제 생성"""
        problems = []
        for i in range(count):
            problems.append({
                "question": f"[{curriculum_data.get('chapter_name', '수학')}] 기본 문제 {i+1}번",
                "choices": ["선택지 1", "선택지 2", "선택지 3", "선택지 4"],
                "correct_answer": "선택지 1",
                "explanation": f"{curriculum_data.get('chapter_name', '수학')} 관련 기본 해설",
                "problem_type": "multiple_choice",
                "difficulty": "B"
            })
        return problems
    
    def _calculate_difficulty_distribution(self, problems: List[Dict]) -> Dict[str, int]:
        """난이도 분포 계산"""
        distribution = {"A": 0, "B": 0, "C": 0}
        for problem in problems:
            difficulty = problem.get("difficulty", "B")
            if difficulty in distribution:
                distribution[difficulty] += 1
        return distribution
    
    def _calculate_type_distribution(self, problems: List[Dict]) -> Dict[str, int]:
        """유형 분포 계산"""
        distribution = {"multiple_choice": 0, "essay": 0, "short_answer": 0}
        for problem in problems:
            problem_type = problem.get("problem_type", "multiple_choice")
            if problem_type in distribution:
                distribution[problem_type] += 1
        return distribution