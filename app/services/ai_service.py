import os
import json
import google.generativeai as genai
from google.cloud import vision
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

class AIService:
    def __init__(self):
        # Gemini API 키 설정
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", "AIzaSyCOX4_nCgcCTTvIf-abckxtC10xTMqzwzM"))
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Google Vision API 키 설정
        self.vision_api_key = "AIzaSyCVjBI7eFbggDVLZVU0hRloQk0HAgjp5vE"
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

        # 참고 문제 가져오기 - 난이도별 맞춤형 참고
        reference_problems = self._get_smart_reference_problems(
            curriculum_data.get('chapter_name', ''), 
            difficulty_ratio if difficulty_ratio else {"A": 30, "B": 40, "C": 30}
        )
        print(f" 디버그: 챕터={curriculum_data.get('chapter_name')}")
        print(f" 참고 문제: {reference_problems[:200]}...")

        # 문제 개수는 매개변수로 전달받음 (기본값 1개)

        prompt = f"""중학교 수학 문제 출제 전문가입니다. 다음 교육과정에 맞는 문제를 생성해주세요.

 교육과정: {curriculum_data.get('grade')} {curriculum_data.get('semester')} - {curriculum_data.get('unit_name')} > {curriculum_data.get('chapter_name')}
 사용자 요청: "{user_prompt}"
 난이도 분배: {difficulty_distribution}

 **범용 난이도 기준** (모든 단원 적용):

**A단계 (기본/개념)**
- 단일 개념의 직접적 적용
- 정의, 공식을 그대로 사용하는 문제  
- 1-2단계 계산으로 해결
- 예시: 기본 공식 대입, 개념 확인, 용어 정의

**B단계 (응용/연산)**  
- 2-3개 개념을 조합한 문제
- 여러 단계의 계산 과정 필요
- 문제 상황을 수식으로 변환
- 예시: 응용 문제, 도형의 성질 활용, 방정식 세우기

**C단계 (심화/사고)**
- 복합적 조건 분석이 필요
- 여러 단원 지식을 융합
- 창의적 접근이나 추론 과정 포함  
- 예시: 조건 분석, 경우의 수, 증명 과정

{reference_problems}

 **생성 규칙**:
1. 정확히 {problem_count}개 문제를 난이도 순서대로 생성
2. 각 문제의 difficulty 필드를 분배에 맞게 정확히 설정
3. 수학 표기: x², √16, 2³×5² (중학생 표준 표기법)
4. 해설은 난이도에 맞게 간결하게 (A:1문장, B:2-3문장, C:3-4문장)
5. 교육과정 범위를 벗어나지 않도록 주의

JSON 배열로 응답:
[
  {{
    "question": "문제 내용",
    "choices": ["①", "②", "③", "④"] 또는 null,
    "correct_answer": "정답",
    "explanation": "간결한 해설",
    "problem_type": "multiple_choice/short_answer/essay", 
    "difficulty": "A/B/C",
    "has_diagram": true/false,
    "diagram_type": "geometry/coordinate/graph/algebra/etc",
    "diagram_elements": {{"objects": [], "values": {{}}, "labels": []}}
  }}
]"""

        try:
            response = self.model.generate_content(prompt)
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
            print(f" OCR 디버그: image_data 타입: {type(image_data)}")
            print(f" OCR 디버그: image_data 크기: {len(image_data) if image_data else 'None'}")
            
            if not image_data:
                print(" OCR 디버그: image_data가 비어있음")
                return ""
            
            # REST API 방식으로 Google Vision API 호출
            import requests
            import base64
            
            # 이미지 데이터를 base64로 인코딩
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Google Vision API REST 엔드포인트
            url = f"https://vision.googleapis.com/v1/images:annotate?key={self.vision_api_key}"
            
            payload = {
                "requests": [
                    {
                        "image": {
                            "content": image_base64
                        },
                        "features": [
                            {
                                "type": "TEXT_DETECTION",
                                "maxResults": 1
                            }
                        ]
                    }
                ]
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            print(f" OCR 디버그: Google Vision API 호출 시작")
            response = requests.post(url, json=payload, headers=headers)
            print(f" OCR 디버그: 응답 상태코드: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f" OCR 디버그: 응답 데이터: {str(result)[:200]}...")
                
                if 'responses' in result and result['responses']:
                    response_data = result['responses'][0]
                    if 'textAnnotations' in response_data and response_data['textAnnotations']:
                        detected_text = response_data['textAnnotations'][0]['description']
                        print(f" OCR 디버그: 인식된 텍스트: {detected_text[:50]}...")
                        return detected_text.strip()
                    else:
                        print(" OCR 디버그: textAnnotations가 비어있음")
                        return ""
                else:
                    print(" OCR 디버그: responses가 비어있음")
                    return ""
            else:
                error_msg = response.text
                print(f" OCR API 오류: {response.status_code} - {error_msg}")
                return ""
                
        except Exception as e:
            import traceback
            print(f"OCR 처리 오류: {str(e)}")
            print(f"OCR 오류 상세: {traceback.format_exc()}")
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
            response = self.model.generate_content(prompt)
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



    def _get_smart_reference_problems(self, chapter_name: str, difficulty_ratio: dict) -> str:
        """난이도 분배에 맞춘 스마트 참고 문제 제공"""
        try:
            import os
            import json
            
            problem_types_file_path = os.path.join(os.path.dirname(__file__), "../../data/math_problem_types.json")
            
            with open(problem_types_file_path, 'r', encoding='utf-8') as f:
                problem_types_data = json.load(f)
            
            # 챕터명으로 문제 유형 찾기
            chapter_problem_types = []
            for chapter_data in problem_types_data["math_problem_types"]:
                if chapter_data["chapter_name"] == chapter_name:
                    chapter_problem_types = chapter_data["problem_types"]
                    break
            
            if not chapter_problem_types:
                return f"'{chapter_name}' 챕터의 참고 문제를 찾을 수 없습니다."
            
            # 난이도별 문제 유형 분배
            total_types = len(chapter_problem_types)
            a_types = chapter_problem_types[:total_types//3] if total_types >= 3 else [chapter_problem_types[0]]
            b_types = chapter_problem_types[total_types//3:2*total_types//3] if total_types >= 6 else chapter_problem_types[1:2] if total_types >= 2 else []
            c_types = chapter_problem_types[2*total_types//3:] if total_types >= 3 else chapter_problem_types[-1:] if total_types >= 3 else []
            
            # 요청된 난이도 비율에 따라 참고 문제 구성
            reference_text = f" **{chapter_name} 참고 문제 유형:**\n\n"
            
            if difficulty_ratio.get('A', 0) > 0 and a_types:
                reference_text += f" **A단계 유형**: {', '.join(a_types[:4])}\n"
                reference_text += "   → 기본 개념과 정의를 직접 적용하는 문제로 변형\n\n"
            
            if difficulty_ratio.get('B', 0) > 0 and b_types:  
                reference_text += f" **B단계 유형**: {', '.join(b_types[:4])}\n" 
                reference_text += "   → 계산 과정과 공식 적용이 포함된 응용 문제로 변형\n\n"
                
            if difficulty_ratio.get('C', 0) > 0 and c_types:
                reference_text += f" **C단계 유형**: {', '.join(c_types[:4])}\n"
                reference_text += "   → 조건 분석과 종합적 사고가 필요한 심화 문제로 변형\n\n"
            
            return reference_text
            
        except Exception as e:
            print(f"스마트 참고 문제 로드 오류: {str(e)}")
            return f"'{chapter_name}' 참고 문제 로드 중 오류 발생"

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

 난이도별 문제 생성 가이드:
A단계: 위 유형 중에서 가장 기본적인 개념만 사용하여 단순한 계산이나 정의 확인 문제로 변형
B단계: 위 유형을 기반으로 2~3개 개념을 조합하거나 여러 단계의 풀이 과정이 필요한 문제로 변형
C단계: 위 유형을 확장하여 창의적 접근이나 종합적 추론이 필요한 고난도 문제로 변형
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