import os
import json
from google import genai
from google.genai import types
from google.cloud import vision
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

class AIService:
    def __init__(self):
        # Gemini API 키 설정
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY", "AIzaSyCOX4_nCgcCTTvIf-abckxtC10xTMqzwzM")
        )
        self.model_name = "gemini-2.5-flash"
        
        # Google Vision은 API 키 방식으로 초기화
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ""  # 빈 값으로 설정하여 API 키 사용

    def generate_math_problem(self, curriculum_data: Dict, user_prompt: str, problem_count: int = 1, difficulty_ratio: Dict = None) -> Dict:
        """Gemini를 이용한 수학 문제 생성"""
        
        # 난이도 비율을 이용한 문제별 난이도 계산
        if difficulty_ratio:
            # 비율에 따른 각 난이도별 문제 개수 계산
            total_problems = problem_count
            a_count = round(total_problems * difficulty_ratio['A'] / 100)
            b_count = round(total_problems * difficulty_ratio['B'] / 100)
            c_count = total_problems - a_count - b_count  # 나머지는 C
            
            difficulty_distribution = f"A단계 {a_count}개, B단계 {b_count}개, C단계 {c_count}개"
        else:
            # 사용자 프롬프트에서 난이도 분석 (기존 로직)
            difficulty_level = "중"  # 기본값
            user_prompt_lower = user_prompt.lower()
            
            # ABC 단계 처리
            if any(keyword in user_prompt for keyword in ["C", "C단계", "최고", "최상", "고난도", "어려운", "심화"]):
                difficulty_level = "C"
            elif any(keyword in user_prompt for keyword in ["A", "A단계", "기초", "쉬운", "기본"]):
                difficulty_level = "A"  
            else:
                difficulty_level = "B"
            
            difficulty_distribution = f"모든 문제 {difficulty_level}단계"

        # 참고 문제 가져오기 - 모든 난이도를 포함
        reference_problems = self._get_reference_problems(
            curriculum_data.get('chapter_name', ''), 
            "ALL"  # 모든 난이도의 참고 문제 포함
        )
        print(f"🔍 디버그: 챕터={curriculum_data.get('chapter_name')}")
        print(f"📚 참고 문제: {reference_problems[:200]}...")

        # 문제 개수는 매개변수로 전달받음 (기본값 1개)

        prompt = f"""당신은 중학교 수학 문제 출제 전문가입니다. 교육과정에 맞는 정확하고 체계적인 문제를 생성해주세요.

교육과정 정보:
- 학년: {curriculum_data.get('grade')} {curriculum_data.get('semester')}
- 대단원: {curriculum_data.get('unit_name')}
- 소단원: {curriculum_data.get('chapter_name')}
- 학습목표: {curriculum_data.get('learning_objectives')}
- 핵심 키워드: {curriculum_data.get('keywords')}

사용자 요청:
"{user_prompt}"

⭐ 중요한 난이도 분배 요구사항:
{difficulty_distribution}

{reference_problems}

생성 조건:
1. 위 교육과정 범위 내에서 정확히 {problem_count}개 문제 생성
2. 참고 문제의 스타일을 반영하되 완전히 새로운 문제 생성 (복사 금지)
3. ⭐ 각 문제의 난이도를 위 분배 요구사항에 정확히 맞춰 생성 (가장 중요!)
4. 사용자가 요청한 문제 유형(객관식/주관식)을 정확히 반영
5. 명확하고 이해하기 쉬운 문제 설명
6. 정확한 정답과 단계별 해설 포함
7. 수학 기호나 수식은 일반 텍스트로 표기 (LaTeX 사용하지 말것)
8. 그림이 필요한 문제인 경우 문제에 "그림 참조" 표시

⚠️ 중요: 
- 반드시 정확히 {problem_count}개 문제를 JSON 배열 형태로 생성하세요!
- 각 문제의 "difficulty" 필드를 위 난이도 분배에 맞춰 정확히 설정하세요!

응답 형식 (JSON 배열 - {problem_count}개 문제):
[
  {{
    "question": "문제 내용",
    "choices": ["선택지1", "선택지2", "선택지3", "선택지4"] (객관식인 경우, 주관식은 null),
    "correct_answer": "정답",
    "explanation": "단계별 해설 (일반 텍스트로 작성)",
    "problem_type": "multiple_choice" 또는 "short_answer" 또는 "essay",
    "difficulty": "A" 또는 "B" 또는 "C" (위 분배에 맞춰),
    "has_diagram": true/false,
    "diagram_type": "concentration" 또는 "train" 또는 "geometry" 또는 "graph" 등,
    "diagram_elements": {{
      "objects": ["비커", "소금물", "물"] 또는 ["열차", "다리", "터널"] 등 그려야 할 요소들,
      "values": {{"농도": "10%", "양": "300g"}} 또는 {{"열차길이": "200m", "속력": "60km/h"}} 등 표시할 값들,
      "labels": ["초기 상태", "최종 상태"] 등 라벨 정보
    }}
  }},
  ... ({problem_count}개 문제까지)
]

다시 한번 강조: {problem_count}개 문제를 반드시 생성하세요!
"""

        try:
            from google.genai import types
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
                )
            ]
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            content = response.text
            
            # JSON 부분만 추출
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                json_str = content
            
            # JSON 정리 및 파싱
            problems_array = self._clean_and_parse_json(json_str)
            return problems_array if isinstance(problems_array, list) else [problems_array]
            
        except Exception as e:
            import traceback
            error_msg = f"Gemini 수학 문제 생성 오류: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            raise Exception(error_msg)

    def ocr_handwriting(self, image_data: bytes) -> str:
        """Google Vision을 이용한 손글씨 OCR"""
        try:
            # Google Vision 클라이언트 생성 (API 키 사용)
            client = vision.ImageAnnotatorClient()
            
            image = vision.Image(content=image_data)
            response = client.text_detection(image=image)
            
            texts = response.text_annotations
            if texts:
                detected_text = texts[0].description
                return detected_text.strip()
            else:
                return ""
                
        except Exception as e:
            print(f"OCR 처리 오류: {str(e)}")
            return ""

    def grade_math_answer(self, question: str, correct_answer: str, student_answer: str, explanation: str, problem_type: str = "essay") -> Dict:
        """Gemini를 이용한 수학 답안 채점"""
        
        # 서술형인 경우 풀이과정과 정답을 모두 고려
        if problem_type.lower() == "essay":
            prompt = f"""당신은 중학교 수학 채점 전문가입니다. 학생의 답안을 정확하고 공정하게 평가하여 건설적인 피드백을 제공해주세요.

다음 수학 문제의 학생 답안을 채점해주세요.

문제: {question}
정답: {correct_answer}
해설: {explanation}

학생 답안: {student_answer}

서술형 채점 기준:
1. 최종 정답의 정확성 (40점)
2. 풀이 과정의 논리성과 타당성 (40점)
3. 수학적 표기와 계산의 정확성 (20점)

특별 고려사항:
- 최종 답이 틀려도 풀이 과정이 올바르면 부분점수 부여
- 풀이 과정이 없고 답만 맞으면 70%만 점수 부여
- 창의적이고 다른 방법의 올바른 풀이도 인정
- 계산 실수는 과정이 맞으면 10점만 감점

응답 형식 (JSON):
{{
    "score": 점수(0-100),
    "is_correct": true/false,
    "feedback": "상세한 피드백 (풀이과정과 정답에 대한 구체적 평가)",
    "strengths": "잘한 부분",
    "improvements": "개선할 부분",
    "process_score": 풀이과정점수(0-60),
    "answer_score": 정답점수(0-40)
}}
"""
        else:
            prompt = f"""당신은 중학교 수학 채점 전문가입니다. 학생의 답안을 정확하고 공정하게 평가하여 건설적인 피드백을 제공해주세요.

다음 수학 문제의 학생 답안을 채점해주세요.

문제: {question}
정답: {correct_answer}
해설: {explanation}

학생 답안: {student_answer}

채점 기준:
1. 정답 여부 (50점)
2. 풀이 과정의 논리성 (30점)
3. 계산의 정확성 (20점)

응답 형식 (JSON):
{{
    "score": 점수(0-100),
    "is_correct": true/false,
    "feedback": "상세한 피드백",
    "strengths": "잘한 부분",
    "improvements": "개선할 부분"
}}
"""

        try:
            from google.genai import types
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
                )
            ]
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            content = response.text
            
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                json_str = content
            
            return json.loads(json_str)
            
        except Exception as e:
            print(f"Gemini 수학 채점 오류: {str(e)}")
            return {
                "score": 0,
                "is_correct": False,
                "feedback": "채점 중 오류가 발생했습니다.",
                "strengths": "",
                "improvements": ""
            }



    def _get_reference_problems(self, chapter_name: str, difficulty_level: str) -> str:
        """JSON 파일에서 챕터의 문제 유형들을 가져와서 참고 정보로 제공"""
        try:
            import os
            import json
            
            # math_problem_types.json 파일 읽기
            problem_types_file_path = os.path.join(os.path.dirname(__file__), "../../data/math_problem_types.json")
            
            with open(problem_types_file_path, 'r', encoding='utf-8') as f:
                problem_types_data = json.load(f)
            
            # 챕터명으로 문제 유형 찾기
            chapter_problem_types = []
            for chapter_data in problem_types_data["math_problem_types"]:
                if chapter_data["chapter_name"] == chapter_name:
                    chapter_problem_types = chapter_data["problem_types"]
                    break
            
            if chapter_problem_types:
                if difficulty_level == "ALL":
                    # 모든 난이도의 참고 문제 포함
                    selected_types = chapter_problem_types[:12]  # 최대 12개 유형
                    types_text = "\n- ".join(selected_types)
                    
                    return f"""
**참고 문제 유형 (모든 난이도 - {chapter_name}):**

다음 유형의 문제들을 참고하여 A, B, C 각 단계에 적합한 난이도로 다양하게 문제를 생성하세요:

- {types_text}

A단계: 기본 개념의 단순 적용
B단계: 기본 개념의 확장 적용
C단계: 심화 응용 및 창의적 사고 필요
                    """
                else:
                    # 기존 로직 (특정 난이도)
                    total_types = len(chapter_problem_types)
                    difficulty_map = {
                        "A": {"start": 0, "count": total_types // 3 if total_types >= 3 else total_types},  # 처음 1/3
                        "B": {"start": total_types // 3, "count": total_types // 3 if total_types >= 6 else max(1, total_types - total_types // 3)},  # 중간 1/3  
                        "C": {"start": 2 * total_types // 3, "count": total_types - 2 * total_types // 3 if total_types >= 3 else max(1, total_types // 2)}  # 마지막 1/3
                    }
                    
                    if difficulty_level in difficulty_map and total_types > 0:
                        mapping = difficulty_map[difficulty_level]
                        start_idx = min(mapping["start"], total_types - 1)
                        end_idx = min(mapping["start"] + mapping["count"], total_types)
                        selected_types = chapter_problem_types[start_idx:end_idx]
                    else:
                        selected_types = chapter_problem_types[:5]  # 기본값
                    
                    # 참고 문제 유형 텍스트 생성
                    types_text = "\n- ".join(selected_types[:8])  # 최대 8개 유형만
                    
                    return f"""
**참고 문제 유형 ({difficulty_level}단계 - {chapter_name}):**

다음 유형의 문제들을 참고하여 비슷한 수준과 스타일의 문제를 생성하세요:

- {types_text}

이 유형들 중에서 사용자 요청에 가장 적합한 유형을 선택하여 {difficulty_level}단계 수준에 맞는 문제를 생성해주세요.
                    """
            else:
                return f"""
**참고 문제 유형 ({difficulty_level}단계):**
'{chapter_name}' 챕터의 문제 유형을 찾을 수 없습니다. 
기본 수학 교육과정에 맞는 {difficulty_level}단계 수준의 문제를 생성해주세요.
                """
                
        except Exception as e:
            print(f"참고 문제 로드 오류: {str(e)}")
            return f"""
**참고 문제 유형 ({difficulty_level}단계):**
문제 유형 로드 중 오류가 발생했습니다. 
교육과정에 맞는 {difficulty_level}단계 수준의 문제를 생성해주세요.
            """
    
    def _clean_and_parse_json(self, json_str: str):
        """JSON 문자열을 정리하고 파싱"""
        import re
        
        try:
            # 1차 시도: 원본 그대로 파싱
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"1차 JSON 파싱 실패: {str(e)}")
            
            try:
                # 2차 시도: 기본적인 정리
                cleaned = json_str.strip()
                
                # 제어 문자 제거 (탭, 개행 등을 안전한 형태로 변환)
                cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', cleaned)
                
                # 백슬래시 문제 해결
                cleaned = cleaned.replace('\\\\', '\\')
                cleaned = cleaned.replace('\\"', '"')
                cleaned = cleaned.replace('\\n', '\\n')  # 개행은 유지
                cleaned = cleaned.replace('\\t', '\\t')  # 탭은 유지
                
                return json.loads(cleaned)
            except json.JSONDecodeError as e2:
                print(f"2차 JSON 파싱 실패: {str(e2)}")
                
                try:
                    # 3차 시도: 더 강력한 정리 (문제 부분만 추출 시도)
                    # JSON 배열 패턴 찾기
                    array_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
                    if array_match:
                        array_part = array_match.group(0)
                        return json.loads(array_part)
                    else:
                        raise e2
                except (json.JSONDecodeError, Exception) as e3:
                    print(f"3차 JSON 파싱 실패: {str(e3)}")
                    print(f"문제가 있는 JSON 앞부분: {json_str[:200]}...")
                    raise Exception(f"JSON 파싱 완전 실패: {str(e3)}")