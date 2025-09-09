// API 기본 URL
const API_BASE = '/api/math-generation';

// MathJax 렌더링 함수
function renderMathJax(element) {
    if (window.MathJax) {
        MathJax.typesetPromise([element]).then(() => {
            console.log('MathJax 렌더링 완료');
        }).catch((err) => {
            console.error('MathJax 렌더링 오류:', err);
        });
    }
}

// 텍스트 포맷팅 (변수가 포함된 지수는 MathJax 처리)
function formatMathText(text) {
    if (!text) return text;
    
    // 이미 $ 로 감싸진 수식이 있으면 그대로 반환
    if (text.includes('$')) {
        return text;
    }
    
    // 변수가 포함된 지수 표현을 MathJax용으로 변환
    let formatted = text
        // 변수 지수: 2^a, x^n, (x+1)^2 등을 $2^a$, $x^n$, $(x+1)^2$로 변환
        .replace(/([a-zA-Z0-9()]+)\^([a-zA-Z][a-zA-Z0-9]*)/g, '$$1^{$2}$')
        
        // 복잡한 지수: 2^(n+1), x^(2a) 등
        .replace(/([a-zA-Z0-9()]+)\^(\([^)]+\))/g, '$$1^{$2}$')
        
        // 복잡한 식의 지수: (x+1)^(n-1) 등
        .replace(/(\([^)]+\))\^(\([^)]+\))/g, '$$1^{$2}$')
        
        // 중첩된 $ 기호 정리
        .replace(/\$\$+/g, '$')
        .replace(/\$([^$]*)\$\$([^$]*)\$/g, '$$$1$2$$');
    
    return formatted;
}

// 텍스트를 HTML로 안전하게 변환 (줄바꿈 처리 + 단계 형식 개선)
function textToHtml(text) {
    if (!text) return '';
    return text
        .replace(/\n/g, '<br>')
        // "단계 1:", "단계 2:" → "STEP1)", "STEP2)"로 변환
        .replace(/단계\s*(\d+)\s*[:：]/g, '<strong>STEP$1)</strong>')
        // "답:" → "답)"로 변환
        .replace(/답\s*[:：]/g, '<strong>답)</strong>')
        // "해설:" → "해설)"로 변환  
        .replace(/해설\s*[:：]/g, '<strong>해설)</strong>')
        // "풀이:" → "풀이)"로 변환
        .replace(/풀이\s*[:：]/g, '<strong>풀이)</strong>');
}

// 현재 활성 태스크
let activeTask = null;
let pollingInterval = null;
let currentEventSource = null;

// 채점 관련 전역 변수
let currentWorksheet = null;
let multipleChoiceAnswers = {};

// 채점용 워크시트 목록 새로고침 (함수 선언을 앞쪽으로 이동)
async function refreshWorksheetsForGrading() {
    try {
        console.log('워크시트 목록 로드 시도...');
        const response = await fetch(`${API_BASE}/worksheets?limit=50`);
        console.log('응답 상태:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('받은 데이터:', data);
        
        const worksheetSelect = document.getElementById('worksheet-select-grading');
        if (!worksheetSelect) {
            console.error('워크시트 선택 요소를 찾을 수 없습니다');
            return;
        }
        
        worksheetSelect.innerHTML = '<option value="">워크시트를 선택하세요</option>';
        
        if (data.worksheets && data.worksheets.length > 0) {
            console.log('워크시트 개수:', data.worksheets.length);
            data.worksheets.forEach(worksheet => {
                const option = document.createElement('option');
                option.value = worksheet.id;
                option.textContent = `#${worksheet.id} - ${worksheet.title} (${worksheet.school_level} ${worksheet.grade}학년)`;
                worksheetSelect.appendChild(option);
            });
        } else {
            console.log('워크시트가 없거나 데이터 구조가 다름');
            const option = document.createElement('option');
            option.value = "";
            option.textContent = "생성된 워크시트가 없습니다";
            worksheetSelect.appendChild(option);
        }
        
    } catch (error) {
        console.error('워크시트 목록 로드 오류:', error);
        alert('워크시트 목록 로드 오류: ' + error.message);
    }
}

// 선택한 워크시트 불러오기
async function loadSelectedWorksheetForGrading() {
    const worksheetId = document.getElementById('worksheet-select-grading').value;
    if (!worksheetId) {
        alert('워크시트를 선택하세요.');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/worksheets/${worksheetId}`);
        if (!response.ok) {
            throw new Error('워크시트를 찾을 수 없습니다.');
        }
        
        const data = await response.json();
        currentWorksheet = data;
        
        // 시험지 설정 및 표시
        setupExamPaper(data);
        
        // 시험지로 스크롤은 setupExamPaper 함수에서 처리됩니다.
        
    } catch (error) {
        alert('워크시트 로드 오류: ' + error.message);
    }
}

// 시험지 설정 함수
function setupExamPaper(data) {
    const examPaper = document.getElementById('exam-paper');
    const worksheet = data.worksheet;
    const problems = data.problems;
    
    // 시험지 헤더 정보 설정
    document.getElementById('paper-grade').textContent = `${worksheet.school_level} ${worksheet.grade}학년`;
    document.getElementById('exam-date').textContent = new Date().toLocaleDateString('ko-KR');
    
    // 객관식과 주관식 문제 분리
    const mcProblems = problems.filter(p => p.problem_type === 'multiple_choice');
    const subjectiveProblems = problems.filter(p => p.problem_type !== 'multiple_choice');
    
    // 객관식 섹션 설정
    if (mcProblems.length > 0) {
        setupMultipleChoiceSection(mcProblems);
        document.getElementById('multiple-choice-section').style.display = 'block';
    } else {
        document.getElementById('multiple-choice-section').style.display = 'none';
    }
    
    // 주관식 섹션 설정
    if (subjectiveProblems.length > 0) {
        setupSubjectiveSection(subjectiveProblems);
        document.getElementById('subjective-section').style.display = 'block';
    } else {
        document.getElementById('subjective-section').style.display = 'none';
    }
    
    // 시험지 표시
    examPaper.style.display = 'block';
    examPaper.scrollIntoView({ behavior: 'smooth' });
}

// 객관식 섹션 설정
function setupMultipleChoiceSection(mcProblems) {
    const mcAnswersDiv = document.getElementById('multiple-choice-answers');
    let mcHtml = '';
    
    mcProblems.forEach(problem => {
        // 문제 텍스트에 LaTeX 수식 포맷팅 적용
        const formattedQuestion = formatMathText(problem.question);
        
        mcHtml += `
            <div class="mc-problem tex2jax_process">
                <h5>문제 ${problem.sequence_order}</h5>
                <div><strong>${textToHtml(formattedQuestion)}</strong></div>
                <div class="mc-choices">
        `;
        
        if (problem.choices) {
            problem.choices.forEach((choice, index) => {
                const choiceLabel = String.fromCharCode(65 + index); // A, B, C, D
                const formattedChoice = formatMathText(choice);
                mcHtml += `
                    <label class="mc-choice tex2jax_process">
                        <input type="radio" name="problem_${problem.id}" value="${choiceLabel}">
                        ${choiceLabel}. ${textToHtml(formattedChoice)}
                    </label>
                `;
            });
        }
        
        mcHtml += `
                </div>
            </div>
        `;
    });
    
    mcAnswersDiv.innerHTML = mcHtml;
    
    // MathJax 렌더링
    setTimeout(() => renderMathJax(mcAnswersDiv), 100);
}

// 주관식 섹션 설정
function setupSubjectiveSection(subjectiveProblems) {
    const subjectiveDiv = document.getElementById('subjective-answers');
    let subjectiveHtml = '';
    
    subjectiveProblems.forEach(problem => {
        // 문제 텍스트에 LaTeX 수식 포맷팅 적용
        const formattedQuestion = formatMathText(problem.question);
        
        subjectiveHtml += `
            <div class="subjective-problem tex2jax_process">
                <h5>문제 ${problem.sequence_order}</h5>
                <div><strong>${textToHtml(formattedQuestion)}</strong></div>
                <div class="canvas-tools">
                    <button onclick="clearCanvas(${problem.id})" type="button">지우기</button>
                    <button onclick="changeCanvasColor(${problem.id}, '#000000', this)" type="button" class="active">검정</button>
                    <button onclick="changeCanvasColor(${problem.id}, '#0066cc', this)" type="button">파랑</button>
                    <button onclick="changeCanvasColor(${problem.id}, '#cc0000', this)" type="button">빨강</button>
                    <span>선 굵기: </span>
                    <input type="range" min="1" max="10" value="2" onchange="changeLineWidth(${problem.id}, this.value)">
                </div>
                <canvas 
                    id="canvas_${problem.id}" 
                    class="drawing-canvas" 
                    width="500" 
                    height="150"
                    data-problem-id="${problem.id}"
                    onmousedown="startDrawing(event, ${problem.id})"
                    onmousemove="draw(event, ${problem.id})"
                    onmouseup="stopDrawing()"
                    onmouseleave="stopDrawing()"
                    ontouchstart="startDrawingTouch(event, ${problem.id})"
                    ontouchmove="drawTouch(event, ${problem.id})"
                    ontouchend="stopDrawing()"
                ></canvas>
            </div>
        `;
    });
    
    subjectiveDiv.innerHTML = subjectiveHtml;
    
    // MathJax 렌더링
    setTimeout(() => renderMathJax(subjectiveDiv), 100);
    
    // 캔버스 초기화
    subjectiveProblems.forEach(problem => {
        initializeCanvas(problem.id);
    });
}

// 탭 관리
function showTab(tabName) {
    // 모든 탭 비활성화
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // 선택한 탭 활성화
    document.getElementById(`${tabName}-tab`).classList.add('active');
    document.querySelector(`[onclick="showTab('${tabName}')"]`).classList.add('active');
    
    // 채점 탭 선택 시 워크시트 목록 새로고침
    if (tabName === 'grading') {
        setTimeout(() => {
            refreshWorksheetsForGrading();
        }, 100);
    }
    
    // 채점 이력 탭 선택 시 이력 로드
    if (tabName === 'grading-history') {
        setTimeout(() => {
            loadGradingHistory();
            loadWorksheetFilterOptions();
        }, 100);
    }
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// 앱 초기화
async function initializeApp() {
    await loadUnits();
    setupEventListeners();
    // 페이지가 완전히 로드된 후 워크시트 목록 로드
    setTimeout(() => {
        refreshWorksheetsForGrading();
        loadWorksheetsForEdit();
    }, 100);
}

// 대단원 목록 로드
async function loadUnits() {
    try {
        const response = await fetch(`${API_BASE}/curriculum/units`);
        const data = await response.json();
        
        const unitSelect = document.getElementById('unit-select');
        if (unitSelect && data.units) {
            unitSelect.innerHTML = '<option value="">대단원을 선택하세요</option>';
            
            data.units.forEach(unit => {
                const option = document.createElement('option');
                option.value = JSON.stringify({
                    unit_number: unit.unit_number,
                    unit_name: unit.unit_name
                });
                option.textContent = `${unit.unit_number}. ${unit.unit_name}`;
                unitSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('대단원 목록 로드 오류:', error);
    }
}

// 이벤트 리스너 설정
function setupEventListeners() {
    // 문제 생성 폼
    const generationForm = document.getElementById('generation-form');
    if (generationForm) {
        generationForm.addEventListener('submit', handleGenerationSubmit);
    }
    
    // 대단원 선택 시 소단원 로드
    const unitSelect = document.getElementById('unit-select');
    if (unitSelect) {
        unitSelect.addEventListener('change', handleUnitChange);
    }
}

// 대단원 변경 처리
async function handleUnitChange(e) {
    const unitData = e.target.value;
    const chapterSelect = document.getElementById('chapter-select');
    
    if (!unitData) {
        chapterSelect.innerHTML = '<option value="">먼저 대단원을 선택하세요</option>';
        chapterSelect.disabled = true;
        return;
    }
    
    try {
        const unit = JSON.parse(unitData);
        const response = await fetch(`${API_BASE}/curriculum/chapters?unit_name=${encodeURIComponent(unit.unit_name)}`);
        const data = await response.json();
        
        chapterSelect.innerHTML = '<option value="">소단원을 선택하세요</option>';
        
        if (data.chapters && data.chapters.length > 0) {
            data.chapters.forEach(chapter => {
                const option = document.createElement('option');
                option.value = JSON.stringify({
                    unit_number: unit.unit_number,
                    unit_name: unit.unit_name,
                    chapter_number: chapter.chapter_number,
                    chapter_name: chapter.chapter_name,
                    learning_objectives: chapter.learning_objectives,
                    keywords: chapter.keywords
                });
                option.textContent = `${chapter.chapter_number}. ${chapter.chapter_name}`;
                chapterSelect.appendChild(option);
            });
            chapterSelect.disabled = false;
        } else {
            chapterSelect.innerHTML = '<option value="">해당 대단원의 소단원이 없습니다</option>';
        }
        
    } catch (error) {
        console.error('소단원 목록 로드 오류:', error);
        chapterSelect.innerHTML = '<option value="">소단원 로드 실패</option>';
    }
}

// 문제 생성 제출 처리
async function handleGenerationSubmit(e) {
    e.preventDefault();
    
    // 폼 데이터 수집
    const formData = collectGenerationFormData();
    
    // 비율 검증
    if (!validateRatios(formData)) {
        return;
    }
    
    // UI 업데이트
    updateGenerationUI('loading');
    
    try {
        // 비동기 문제 생성 시작
        const response = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '문제 생성 요청 실패');
        }
        
        const data = await response.json();
        activeTask = data.task_id;
        
        // SSE를 통한 실시간 상태 확인
        startSSEConnection(data.task_id);
        
        // 결과 표시
        displayGenerationResult({
            task_id: data.task_id,
            status: 'PENDING',
            message: data.message
        });
        
    } catch (error) {
        console.error('생성 오류:', error);
        displayError('generation-result', error.message);
        updateGenerationUI('error');
    }
}

// 폼 데이터 수집
function collectGenerationFormData() {
    const chapterData = JSON.parse(document.getElementById('chapter-select').value);
    
    return {
        school_level: document.getElementById('school-level').value,
        grade: parseInt(document.getElementById('grade').value),
        semester: document.getElementById('semester').value,
        unit_number: chapterData.unit_number,
        chapter: {
            unit_name: chapterData.unit_name,
            chapter_number: chapterData.chapter_number,
            chapter_name: chapterData.chapter_name,
            learning_objectives: chapterData.learning_objectives,
            keywords: chapterData.keywords
        },
        problem_count: document.getElementById('problem-count').value,
        difficulty_ratio: {
            A: parseInt(document.getElementById('diff-a').value),
            B: parseInt(document.getElementById('diff-b').value),
            C: parseInt(document.getElementById('diff-c').value)
        },
        problem_type_ratio: {
            multiple_choice: parseInt(document.getElementById('type-mc').value),
            essay: parseInt(document.getElementById('type-essay').value),
            short_answer: parseInt(document.getElementById('type-short').value)
        },
        user_text: document.getElementById('user-text').value
    };
}

// 비율 검증
function validateRatios(formData) {
    const diffSum = formData.difficulty_ratio.A + formData.difficulty_ratio.B + formData.difficulty_ratio.C;
    const typeSum = formData.problem_type_ratio.multiple_choice + formData.problem_type_ratio.essay + formData.problem_type_ratio.short_answer;
    
    if (diffSum !== 100) {
        alert('난이도 비율의 합이 100%가 되어야 합니다.');
        return false;
    }
    
    if (typeSum !== 100) {
        alert('문제 유형 비율의 합이 100%가 되어야 합니다.');
        return false;
    }
    
    return true;
}

// UI 상태 업데이트
function updateGenerationUI(state) {
    const progressContainer = document.getElementById('generation-progress');
    const resultContainer = document.getElementById('generation-result');
    const submitButton = document.querySelector('#generation-form button[type="submit"]');
    
    switch (state) {
        case 'loading':
            progressContainer.style.display = 'block';
            resultContainer.innerHTML = '';
            submitButton.disabled = true;
            updateProgress(0, '문제 생성 요청 중...');
            break;
        case 'success':
            progressContainer.style.display = 'none';
            submitButton.disabled = false;
            break;
        case 'error':
            progressContainer.style.display = 'none';
            submitButton.disabled = false;
            break;
    }
}

// 진행률 업데이트
function updateProgress(percentage, message) {
    const progressFill = document.querySelector('#generation-progress .progress-fill');
    const progressText = document.querySelector('#generation-progress .progress-text');
    
    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
    }
    if (progressText) {
        progressText.textContent = message;
    }
}

// SSE 연결 시작
function startSSEConnection(taskId) {
    // 기존 연결 정리
    if (currentEventSource) {
        currentEventSource.close();
    }
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
    
    // SSE 연결 생성
    currentEventSource = new EventSource(`${API_BASE}/tasks/${taskId}/stream`);
    
    currentEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleTaskUpdate(data);
        } catch (error) {
            console.error('SSE 데이터 파싱 오류:', error);
        }
    };
    
    currentEventSource.onerror = function(event) {
        console.error('SSE 연결 오류:', event);
        // SSE 연결 실패 시 폴링으로 대체
        console.log('SSE 실패로 폴링 방식으로 전환합니다.');
        currentEventSource.close();
        currentEventSource = null;
        startPolling(taskId);
    };
    
    currentEventSource.onopen = function(event) {
        console.log('SSE 연결이 열렸습니다.');
    };
}

// 폴링 시작 (SSE 대체용)
function startPolling(taskId) {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    
    pollingInterval = setInterval(async () => {
        await checkTaskStatus(taskId);
    }, 2000); // 2초마다 확인
}

// 연결 중지 (SSE 또는 폴링)
function stopConnection() {
    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

// 태스크 상태 확인
async function checkTaskStatus(taskId = null) {
    const targetTaskId = taskId || document.getElementById('task-id').value;
    
    if (!targetTaskId) {
        alert('태스크 ID를 입력하세요.');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/tasks/${targetTaskId}`);
        const data = await response.json();
        
        if (taskId) {
            // 자동 폴링인 경우
            handleTaskUpdate(data);
        } else {
            // 수동 확인인 경우
            displayTaskStatus(data);
        }
        
    } catch (error) {
        console.error('태스크 상태 확인 오류:', error);
        if (!taskId) {
            displayError('status-result', error.message);
        }
    }
}

// 태스크 업데이트 처리
function handleTaskUpdate(data) {
    switch (data.status) {
        case 'PENDING':
            updateProgress(10, data.message || '대기 중...');
            break;
        case 'PROGRESS':
            updateProgress(data.current || 0, data.message || '처리 중...');
            break;
        case 'SUCCESS':
            stopConnection();
            updateGenerationUI('success');
            displayGenerationSuccess(data.result);
            // 문제 생성 완료 알림
            alert('🎉 문제지 생성이 완료되었습니다!\n\n📋 총 ' + (data.result.total_generated || 0) + '개의 문제가 생성되었습니다.');
            break;
        case 'FAILURE':
            stopConnection();
            updateGenerationUI('error');
            displayError('generation-result', data.error || '작업이 실패했습니다.');
            break;
    }
}

// 생성 결과 표시
function displayGenerationResult(data) {
    const resultDiv = document.getElementById('generation-result');
    resultDiv.innerHTML = `
        <div class="result-item">
            <h4>문제 생성 시작됨</h4>
            <p><strong>태스크 ID:</strong> ${data.task_id}</p>
            <p><strong>상태:</strong> <span class="status-${data.status.toLowerCase()}">${getStatusText(data.status)}</span></p>
            <p>${data.message}</p>
        </div>
    `;
}

// 생성 성공 결과 표시
function displayGenerationSuccess(result) {
    const resultDiv = document.getElementById('generation-result');
    
    let problemsHtml = '';
    if (result.problems && result.problems.length > 0) {
        problemsHtml = result.problems.map(problem => {
            const formattedQuestion = formatMathText(problem.question);
            const formattedAnswer = formatMathText(problem.correct_answer);
            const formattedExplanation = formatMathText(problem.explanation);
            
            return `
                <div class="problem-item tex2jax_process">
                    <div class="problem-header">
                        문제 ${problem.sequence_order}번 [${problem.difficulty}단계, ${getTypeLabel(problem.problem_type)}]
                    </div>
                    <div class="problem-content">
                        <strong>문제:</strong> ${textToHtml(formattedQuestion)}
                    </div>
                    ${problem.choices ? `
                        <div class="choices">
                            <strong>선택지:</strong><br>
                            ${problem.choices.map((choice, idx) => `${String.fromCharCode(65 + idx)}. ${textToHtml(formatMathText(choice))}`).join('<br>')}
                        </div>
                    ` : ''}
                    <div><strong>정답:</strong> ${textToHtml(formattedAnswer)}</div>
                    <div class="explanation">
                        <strong>해설:</strong> ${textToHtml(formattedExplanation)}
                    </div>
                </div>
            `;
        }).join('');
    }
    
    resultDiv.innerHTML = `
        <div class="result-item fade-in">
            <h4>문제 생성 완료!</h4>
            <p><strong>워크시트 ID:</strong> ${result.worksheet_id}</p>
            <p><strong>생성된 문제 수:</strong> ${result.total_generated}개</p>
            <p><strong>실제 난이도 분포:</strong> A${result.actual_difficulty_distribution?.A || 0}개, B${result.actual_difficulty_distribution?.B || 0}개, C${result.actual_difficulty_distribution?.C || 0}개</p>
        </div>
        <div class="problems-container tex2jax_process">
            ${problemsHtml}
        </div>
    `;
    
    // MathJax 렌더링
    setTimeout(() => renderMathJax(resultDiv), 100);
    
    // 워크시트 ID를 채점 탭에 자동 입력
    const worksheetIdInput = document.getElementById('worksheet-id');
    if (worksheetIdInput && result.worksheet_id) {
        worksheetIdInput.value = result.worksheet_id;
    }
}

// 채점 시작
async function startGrading() {
    const worksheetId = document.getElementById('worksheet-id').value;
    const answersText = document.getElementById('answers').value;
    
    if (!worksheetId || !answersText) {
        alert('워크시트 ID와 답안을 입력하세요.');
        return;
    }
    
    let answers;
    try {
        answers = JSON.parse(answersText);
    } catch (error) {
        alert('답안 형식이 올바르지 않습니다. JSON 형태로 입력하세요.');
        return;
    }
    
    // UI 업데이트
    const progressContainer = document.getElementById('grading-progress');
    const resultContainer = document.getElementById('grading-result');
    progressContainer.style.display = 'block';
    resultContainer.innerHTML = '';
    updateGradingProgress(0, '채점 시작 중...');
    
    try {
        const response = await fetch(`${API_BASE}/worksheets/${worksheetId}/grade`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(answers)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '채점 요청 실패');
        }
        
        const data = await response.json();
        
        // SSE를 통한 채점 상태 확인
        startGradingSSE(data.task_id);
        
        displayGradingResult({
            task_id: data.task_id,
            status: 'PENDING',
            message: data.message
        });
        
    } catch (error) {
        console.error('채점 오류:', error);
        displayError('grading-result', error.message);
        progressContainer.style.display = 'none';
    }
}

// 채점 SSE 시작
function startGradingSSE(taskId) {
    // 기존 연결 정리
    if (currentEventSource) {
        currentEventSource.close();
    }
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
    
    // SSE 연결 생성
    currentEventSource = new EventSource(`${API_BASE}/tasks/${taskId}/stream`);
    
    currentEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleGradingUpdate(data);
        } catch (error) {
            console.error('채점 SSE 데이터 파싱 오류:', error);
        }
    };
    
    currentEventSource.onerror = function(event) {
        console.error('채점 SSE 연결 오류:', event);
        currentEventSource.close();
        currentEventSource = null;
        // SSE 실패 시 폴링으로 대체
        startGradingPolling(taskId);
    };
}

// 채점 업데이트 처리
function handleGradingUpdate(data) {
    switch (data.status) {
        case 'PENDING':
            updateGradingProgress(10, data.message || '대기 중...');
            break;
        case 'PROGRESS':
            updateGradingProgress(data.current || 0, data.message || '채점 중...');
            break;
        case 'SUCCESS':
            stopConnection();
            document.getElementById('grading-progress').style.display = 'none';
            displayFinalGradingResult(data.result);
            break;
        case 'FAILURE':
            stopConnection();
            document.getElementById('grading-progress').style.display = 'none';
            displayError('grading-result', data.error || '채점이 실패했습니다.');
            break;
    }
}

// 채점 폴링 시작 (SSE 대체용)
function startGradingPolling(taskId) {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    
    pollingInterval = setInterval(async () => {
        await checkGradingStatus(taskId);
    }, 1000);
}

// 채점 상태 확인
async function checkGradingStatus(taskId) {
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`);
        const data = await response.json();
        
        switch (data.status) {
            case 'PENDING':
                updateGradingProgress(10, data.message || '대기 중...');
                break;
            case 'PROGRESS':
                updateGradingProgress(data.current || 0, data.message || '채점 중...');
                break;
            case 'SUCCESS':
                stopPolling();
                document.getElementById('grading-progress').style.display = 'none';
                displayFinalGradingResult(data.result);
                break;
            case 'FAILURE':
                stopPolling();
                document.getElementById('grading-progress').style.display = 'none';
                displayError('grading-result', data.error || '채점이 실패했습니다.');
                break;
        }
        
    } catch (error) {
        console.error('채점 상태 확인 오류:', error);
    }
}

// 채점 진행률 업데이트
function updateGradingProgress(percentage, message) {
    const progressFill = document.querySelector('#grading-progress .progress-fill');
    const progressText = document.querySelector('#grading-progress .progress-text');
    
    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
    }
    if (progressText) {
        progressText.textContent = message;
    }
}

// 채점 결과 표시
function displayGradingResult(data) {
    const resultDiv = document.getElementById('grading-result');
    resultDiv.innerHTML = `
        <div class="result-item">
            <h4>채점 시작됨</h4>
            <p><strong>태스크 ID:</strong> ${data.task_id}</p>
            <p><strong>상태:</strong> <span class="status-${data.status.toLowerCase()}">${getStatusText(data.status)}</span></p>
            <p>${data.message}</p>
        </div>
    `;
}


// 태스크 상태 표시
function displayTaskStatus(data) {
    const resultDiv = document.getElementById('status-result');
    resultDiv.innerHTML = `
        <div class="result-item">
            <h4>태스크 상태</h4>
            <p><strong>태스크 ID:</strong> ${data.task_id}</p>
            <p><strong>상태:</strong> <span class="status-${data.status.toLowerCase()}">${getStatusText(data.status)}</span></p>
            ${data.current !== undefined ? `<p><strong>진행률:</strong> ${data.current}%</p>` : ''}
            ${data.message ? `<p><strong>메시지:</strong> ${data.message}</p>` : ''}
            ${data.error ? `<p><strong>오류:</strong> ${data.error}</p>` : ''}
            ${data.result ? `<div class="json-display">${JSON.stringify(data.result, null, 2)}</div>` : ''}
        </div>
    `;
}

// 오류 표시
function displayError(containerId, message) {
    const container = document.getElementById(containerId);
    container.innerHTML = `
        <div class="result-item" style="border-color: #e74c3c; background-color: #fdf2f2;">
            <h4 style="color: #e74c3c;">오류 발생</h4>
            <p>${message}</p>
        </div>
    `;
}

// 상태 텍스트 변환
function getStatusText(status) {
    const statusMap = {
        'PENDING': '대기 중',
        'PROGRESS': '처리 중',
        'SUCCESS': '완료',
        'FAILURE': '실패'
    };
    return statusMap[status] || status;
}

// 문제 유형 라벨 변환
function getTypeLabel(type) {
    const typeMap = {
        'multiple_choice': '객관식',
        'essay': '주관식',
        'short_answer': '단답형'
    };
    return typeMap[type] || type;
}

// 워크시트 목록 로드
async function loadWorksheets() {
    try {
        const response = await fetch(`${API_BASE}/worksheets`);
        const data = await response.json();
        
        const worksheetsListDiv = document.getElementById('worksheets-list');
        
        if (data.worksheets && data.worksheets.length > 0) {
            const worksheetsHtml = data.worksheets.map(worksheet => `
                <div class="worksheet-item" data-worksheet-id="${worksheet.id}">
                    <div class="worksheet-header">
                        <h4>${worksheet.title}</h4>
                        <span class="worksheet-date">${new Date(worksheet.created_at).toLocaleString('ko-KR')}</span>
                    </div>
                    <div class="worksheet-info">
                        <div class="info-row">
                            <span><strong>학교급:</strong> ${worksheet.school_level} ${worksheet.grade}학년 ${worksheet.semester}</span>
                            <span><strong>소단원:</strong> ${worksheet.chapter_name}</span>
                        </div>
                        <div class="info-row">
                            <span><strong>문제 수:</strong> ${worksheet.problem_count}개</span>
                            <span><strong>상태:</strong> ${worksheet.status}</span>
                        </div>
                        <div class="info-row">
                            <span><strong>난이도 분포:</strong> A${worksheet.actual_difficulty_distribution?.A || 0}개, B${worksheet.actual_difficulty_distribution?.B || 0}개, C${worksheet.actual_difficulty_distribution?.C || 0}개</span>
                        </div>
                        <div class="info-row">
                            <span><strong>요청 내용:</strong> ${worksheet.user_prompt}</span>
                        </div>
                    </div>
                    <div class="worksheet-actions">
                        <button class="btn-secondary" onclick="viewWorksheetDetail(${worksheet.id})">문제 보기</button>
                        <button class="btn-secondary" onclick="useForGrading(${worksheet.id})">채점하기</button>
                    </div>
                </div>
            `).join('');
            
            worksheetsListDiv.innerHTML = worksheetsHtml;
        } else {
            worksheetsListDiv.innerHTML = `
                <div class="no-data">
                    <p>생성된 문제지가 없습니다.</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('워크시트 목록 로드 오류:', error);
        document.getElementById('worksheets-list').innerHTML = `
            <div class="result-item" style="border-color: #e74c3c; background-color: #fdf2f2;">
                <h4 style="color: #e74c3c;">오류 발생</h4>
                <p>워크시트 목록을 불러올 수 없습니다: ${error.message}</p>
            </div>
        `;
    }
}

// 워크시트 상세 조회
async function viewWorksheetDetail(worksheetId) {
    try {
        const response = await fetch(`${API_BASE}/worksheets/${worksheetId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || '워크시트 조회 실패');
        }
        
        const worksheet = data.worksheet;
        const problems = data.problems;
        
        let problemsHtml = '';
        if (problems && problems.length > 0) {
            problemsHtml = problems.map(problem => {
                const formattedQuestion = formatMathText(problem.question);
                const formattedAnswer = formatMathText(problem.correct_answer);
                const formattedExplanation = formatMathText(problem.explanation);
                
                return `
                    <div class="problem-item tex2jax_process">
                        <div class="problem-header">
                            문제 ${problem.sequence_order}번 [${problem.difficulty}단계, ${getTypeLabel(problem.problem_type)}]
                        </div>
                        <div class="problem-content">
                            <strong>문제:</strong> ${textToHtml(formattedQuestion)}
                        </div>
                        ${problem.choices ? `
                            <div class="choices">
                                <strong>선택지:</strong><br>
                                ${problem.choices.map((choice, idx) => `${String.fromCharCode(65 + idx)}. ${textToHtml(formatMathText(choice))}`).join('<br>')}
                            </div>
                        ` : ''}
                        <div><strong>정답:</strong> ${textToHtml(formattedAnswer)}</div>
                        <div class="explanation">
                            <strong>해설:</strong> ${textToHtml(formattedExplanation)}
                        </div>
                        ${problem.has_diagram ? `
                            <div class="diagram-info">
                                <strong>그림:</strong> ${problem.diagram_type} 유형
                            </div>
                        ` : ''}
                    </div>
                `;
            }).join('');
        }
        
        const worksheetDetailDiv = document.getElementById('worksheet-detail');
        worksheetDetailDiv.innerHTML = `
            <div class="worksheet-detail-info">
                <h4>${worksheet.title}</h4>
                <div class="detail-meta">
                    <p><strong>생성 일시:</strong> ${new Date(worksheet.created_at).toLocaleString('ko-KR')}</p>
                    <p><strong>학교급:</strong> ${worksheet.school_level} ${worksheet.grade}학년 ${worksheet.semester}</p>
                    <p><strong>대단원:</strong> ${worksheet.unit_name}</p>
                    <p><strong>소단원:</strong> ${worksheet.chapter_name}</p>
                    <p><strong>문제 수:</strong> ${worksheet.problem_count}개</p>
                    <p><strong>요청 내용:</strong> ${worksheet.user_prompt}</p>
                    <p><strong>실제 난이도 분포:</strong> A${worksheet.actual_difficulty_distribution?.A || 0}개, B${worksheet.actual_difficulty_distribution?.B || 0}개, C${worksheet.actual_difficulty_distribution?.C || 0}개</p>
                </div>
            </div>
            <div class="problems-container tex2jax_process">
                ${problemsHtml}
            </div>
        `;
        
        // MathJax 렌더링
        setTimeout(() => renderMathJax(worksheetDetailDiv), 100);
        
        // 상세보기 섹션 표시
        document.getElementById('worksheet-detail-section').style.display = 'block';
        
        // 상세보기로 스크롤
        document.getElementById('worksheet-detail-section').scrollIntoView({ 
            behavior: 'smooth' 
        });
        
    } catch (error) {
        console.error('워크시트 상세 조회 오류:', error);
        document.getElementById('worksheet-detail').innerHTML = `
            <div class="result-item" style="border-color: #e74c3c; background-color: #fdf2f2;">
                <h4 style="color: #e74c3c;">오류 발생</h4>
                <p>워크시트 상세 정보를 불러올 수 없습니다: ${error.message}</p>
            </div>
        `;
        document.getElementById('worksheet-detail-section').style.display = 'block';
    }
}

// 채점용으로 워크시트 사용
function useForGrading(worksheetId) {
    // 채점 탭으로 이동
    showTab('grading');
    
    // 워크시트 선택
    const worksheetSelect = document.getElementById('worksheet-select-grading');
    if (worksheetSelect) {
        worksheetSelect.value = worksheetId;
        loadSelectedWorksheetForGrading();
    }
    
    // 채점 탭으로 스크롤
    document.getElementById('grading-tab').scrollIntoView({ 
        behavior: 'smooth' 
    });
}

// 시험 답안 제출
async function submitExamAnswers() {
    if (!currentWorksheet) {
        alert('먼저 시험지를 로드하세요.');
        return;
    }
    
    // 객관식 답안 수집
    const mcAnswers = {};
    document.querySelectorAll('input[type="radio"]:checked').forEach(radio => {
        const problemId = radio.name.replace('problem_', '');
        mcAnswers[problemId] = radio.value;
    });
    
    // 캔버스 그림 데이터 수집
    const canvasData = {};
    const canvases = document.querySelectorAll('.drawing-canvas');
    console.log('캔버스 개수:', canvases.length);
    canvases.forEach(canvas => {
        const problemId = canvas.dataset.problemId;
        const dataURL = canvas.toDataURL('image/png');
        canvasData[problemId] = dataURL;
        console.log(`캔버스 ${problemId} 데이터 크기:`, dataURL.length, 'bytes');
    });
    console.log('수집된 캔버스 데이터:', Object.keys(canvasData));
    
    // UI 업데이트
    const progressContainer = document.getElementById('grading-progress');
    const resultContainer = document.getElementById('grading-result');
    progressContainer.style.display = 'block';
    resultContainer.innerHTML = '';
    updateGradingProgress(0, '채점 시작 중...');
    
    try {
        const response = await fetch(`${API_BASE}/worksheets/${currentWorksheet.worksheet.id}/grade-canvas`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                multiple_choice_answers: mcAnswers,
                canvas_answers: canvasData
            })
        });
        
        if (!response.ok) {
            throw new Error('채점 요청 실패');
        }
        
        const result = await response.json();
        activeTask = result.task_id;
        
        // SSE를 통한 진행 상황 모니터링 시작
        startGradingSSE(result.task_id);
        
    } catch (error) {
        progressContainer.style.display = 'none';
        alert('채점 오류: ' + error.message);
    }
}

// 채점 진행률 업데이트
function updateGradingProgress(percentage, status) {
    const progressFill = document.querySelector('#grading-progress .progress-fill');
    const progressText = document.querySelector('#grading-progress .progress-text');
    
    if (progressFill && progressText) {
        progressFill.style.width = `${percentage}%`;
        progressText.textContent = status;
    }
}

// 채점 상태 폴링 시작
function startGradingPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/tasks/${activeTask}`);
            const data = await response.json();
            
            if (data.status === 'PROGRESS') {
                updateGradingProgress(data.current || 0, data.message || '처리 중...');
            } else if (data.status === 'SUCCESS') {
                stopConnection();
                displayFinalGradingResult(data.result);
                document.getElementById('grading-progress').style.display = 'none';
            } else if (data.status === 'FAILURE') {
                stopConnection();
                document.getElementById('grading-progress').style.display = 'none';
                alert('채점 실패: ' + data.error);
            }
        } catch (error) {
            console.error('상태 확인 오류:', error);
        }
    }, 1000);
}

// 채점 완료 결과 표시 (통합 함수)
function displayFinalGradingResult(result) {
    const resultContainer = document.getElementById('grading-result');
    
    let resultHtml = `
        <div class="result-item fade-in">
            <h4>채점 완료</h4>
            <div class="score-summary">
                <p><strong>총 점수:</strong> ${result.total_score}점 / ${result.max_possible_score}점</p>
                <p><strong>정답 개수:</strong> ${result.correct_count}개 / ${result.total_problems}개</p>
                <p><strong>문제당 배점:</strong> ${result.points_per_problem}점</p>
            </div>
    `;
    
    if (result.ocr_text) {
        resultHtml += `
            <div class="ocr-result">
                <h5>OCR 추출 텍스트:</h5>
                <pre style="background: #f5f5f5; padding: 10px; border-radius: 4px;">${result.ocr_text}</pre>
            </div>
        `;
    }
    
    resultHtml += '<div class="detailed-results"><h5>문제별 채점 결과:</h5>';
    
    result.grading_results.forEach(item => {
        const isCorrect = item.is_correct;
        const borderColor = isCorrect ? '#27ae60' : '#e74c3c';
        
        const formattedUserAnswer = formatMathText(item.user_answer || '없음');
        const formattedCorrectAnswer = formatMathText(item.correct_answer || '');
        const formattedAiFeedback = formatMathText(item.ai_feedback || '');
        const formattedStrengths = formatMathText(item.strengths || '');
        const formattedImprovements = formatMathText(item.improvements || '');
        
        resultHtml += `
            <div class="result-item tex2jax_process" style="border-color: ${borderColor}; margin-bottom: 15px;">
                <h6>문제 ${item.problem_id} (${item.input_method || '알 수 없음'}) - ${item.score}점</h6>
                <p><strong>학생 답안:</strong> ${textToHtml(formattedUserAnswer)}</p>
                <p><strong>정답:</strong> ${textToHtml(formattedCorrectAnswer)}</p>
                <p><strong>결과:</strong> ${isCorrect ? '정답' : '오답'}</p>
                
                ${item.ai_feedback ? `<p><strong>AI 피드백:</strong> ${textToHtml(formattedAiFeedback)}</p>` : ''}
                ${item.strengths ? `<p><strong>잘한 점:</strong> ${textToHtml(formattedStrengths)}</p>` : ''}
                ${item.improvements ? `<p><strong>개선점:</strong> ${textToHtml(formattedImprovements)}</p>` : ''}
            </div>
        `;
    });
    
    resultHtml += '</div></div>';
    
    resultContainer.innerHTML = resultHtml;
    
    // MathJax 렌더링
    setTimeout(() => renderMathJax(resultContainer), 100);
}

// 캔버스 관련 변수
let isDrawing = false;
let canvasContexts = {};
let currentColors = {};
let currentLineWidths = {};

// 캔버스 초기화
function initializeCanvas(problemId) {
    const canvas = document.getElementById(`canvas_${problemId}`);
    const ctx = canvas.getContext('2d');
    
    // 캔버스 설정
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2;
    
    // 배경을 흰색으로 설정
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // 전역 변수에 저장
    canvasContexts[problemId] = ctx;
    currentColors[problemId] = '#000000';
    currentLineWidths[problemId] = 2;
}

// 마우스 그리기 시작
function startDrawing(e, problemId) {
    isDrawing = true;
    const canvas = document.getElementById(`canvas_${problemId}`);
    const rect = canvas.getBoundingClientRect();
    const ctx = canvasContexts[problemId];
    
    ctx.beginPath();
    ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
}

// 마우스 그리기
function draw(e, problemId) {
    if (!isDrawing) return;
    
    const canvas = document.getElementById(`canvas_${problemId}`);
    const rect = canvas.getBoundingClientRect();
    const ctx = canvasContexts[problemId];
    
    ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
    ctx.stroke();
}

// 그리기 종료
function stopDrawing() {
    isDrawing = false;
}

// 터치 그리기 시작
function startDrawingTouch(e, problemId) {
    e.preventDefault();
    const touch = e.touches[0];
    const canvas = document.getElementById(`canvas_${problemId}`);
    const rect = canvas.getBoundingClientRect();
    const ctx = canvasContexts[problemId];
    
    isDrawing = true;
    ctx.beginPath();
    ctx.moveTo(touch.clientX - rect.left, touch.clientY - rect.top);
}

// 터치 그리기
function drawTouch(e, problemId) {
    if (!isDrawing) return;
    e.preventDefault();
    
    const touch = e.touches[0];
    const canvas = document.getElementById(`canvas_${problemId}`);
    const rect = canvas.getBoundingClientRect();
    const ctx = canvasContexts[problemId];
    
    ctx.lineTo(touch.clientX - rect.left, touch.clientY - rect.top);
    ctx.stroke();
}

// 캔버스 지우기
function clearCanvas(problemId) {
    const canvas = document.getElementById(`canvas_${problemId}`);
    const ctx = canvasContexts[problemId];
    
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = currentColors[problemId];
}

// 색상 변경
function changeCanvasColor(problemId, color, buttonElement) {
    const ctx = canvasContexts[problemId];
    ctx.strokeStyle = color;
    currentColors[problemId] = color;
    
    // 버튼 활성화 상태 변경
    const canvasElement = document.getElementById(`canvas_${problemId}`);
    const buttons = canvasElement.parentNode.querySelectorAll('.canvas-tools button');
    buttons.forEach(btn => btn.classList.remove('active'));
    if (buttonElement) {
        buttonElement.classList.add('active');
    }
}

// 선 굵기 변경
function changeLineWidth(problemId, width) {
    const ctx = canvasContexts[problemId];
    ctx.lineWidth = width;
    currentLineWidths[problemId] = width;
}

// 편집 관련 변수
let currentEditWorksheet = null;
let originalWorksheetData = null;

// 편집용 워크시트 목록 로드
async function loadWorksheetsForEdit() {
    try {
        const response = await fetch(`${API_BASE}/worksheets?limit=50`);
        if (!response.ok) throw new Error('워크시트 목록을 불러올 수 없습니다.');
        
        const data = await response.json();
        const worksheetSelect = document.getElementById('worksheet-select-edit');
        
        worksheetSelect.innerHTML = '<option value="">문제지를 선택하세요</option>';
        
        data.worksheets.forEach(worksheet => {
            const option = document.createElement('option');
            option.value = worksheet.id;
            option.textContent = `${worksheet.title} (${worksheet.school_level} ${worksheet.grade}학년)`;
            worksheetSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('워크시트 목록 로드 오류:', error);
        alert('워크시트 목록을 불러올 수 없습니다: ' + error.message);
    }
}

// 편집을 위한 워크시트 로드
async function loadWorksheetForEdit() {
    const worksheetId = document.getElementById('worksheet-select-edit').value;
    if (!worksheetId) {
        alert('편집할 문제지를 선택하세요.');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/worksheets/${worksheetId}`);
        if (!response.ok) throw new Error('워크시트 정보를 불러올 수 없습니다.');
        
        const data = await response.json();
        currentEditWorksheet = data;
        originalWorksheetData = JSON.parse(JSON.stringify(data)); // 깊은 복사
        
        // 편집 UI 표시
        displayWorksheetForEdit(data);
        document.getElementById('edit-worksheet').style.display = 'block';
        
        // 편집 영역으로 스크롤
        document.getElementById('edit-worksheet').scrollIntoView({ 
            behavior: 'smooth' 
        });
        
    } catch (error) {
        console.error('워크시트 로드 오류:', error);
        alert('워크시트를 불러올 수 없습니다: ' + error.message);
    }
}

// 편집용 워크시트 표시
function displayWorksheetForEdit(data) {
    const { worksheet, problems } = data;
    
    // 기본 정보 입력 필드에 값 설정
    document.getElementById('edit-title').value = worksheet.title;
    document.getElementById('edit-user-prompt').value = worksheet.user_prompt;
    
    // 문제 목록 표시
    const problemsContainer = document.getElementById('problems-list-edit');
    problemsContainer.innerHTML = '';
    
    problems.forEach((problem, index) => {
        const problemDiv = createProblemEditElement(problem, index + 1);
        problemsContainer.appendChild(problemDiv);
    });
    
    // MathJax 렌더링
    setTimeout(() => renderMathJax(problemsContainer), 100);
}

// 편집 가능한 문제 요소 생성
function createProblemEditElement(problem, sequence) {
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-edit-item';
    problemDiv.dataset.problemId = problem.id;
    
    let choicesHtml = '';
    if (problem.choices) {
        const choices = typeof problem.choices === 'string' ? 
            JSON.parse(problem.choices) : problem.choices;
        
        choicesHtml = choices.map((choice, idx) => `
            <div class="choice-edit">
                <label>선택지 ${idx + 1}:</label>
                <input type="text" class="choice-input" data-choice-index="${idx}" value="${choice}">
            </div>
        `).join('');
    }
    
    problemDiv.innerHTML = `
        <div class="problem-header">
            <h5>문제 ${sequence}</h5>
            <div class="problem-meta">
                <span class="problem-type">${problem.problem_type}</span>
                <span class="problem-difficulty">${problem.difficulty}단계</span>
            </div>
        </div>
        
        <div class="problem-edit-fields">
            <div class="form-group">
                <label>문제:</label>
                <textarea class="edit-textarea problem-question" rows="3">${problem.question}</textarea>
            </div>
            
            ${choicesHtml ? `
                <div class="form-group">
                    <label>선택지:</label>
                    <div class="choices-container">
                        ${choicesHtml}
                    </div>
                </div>
            ` : ''}
            
            <div class="form-group">
                <label>정답:</label>
                <input type="text" class="edit-input problem-answer" value="${problem.correct_answer}">
            </div>
            
            <div class="form-group">
                <label>해설:</label>
                <textarea class="edit-textarea problem-explanation" rows="3">${problem.explanation || ''}</textarea>
            </div>
            
            <div class="form-group">
                <label>난이도:</label>
                <select class="problem-difficulty-select">
                    <option value="A" ${problem.difficulty === 'A' ? 'selected' : ''}>A단계</option>
                    <option value="B" ${problem.difficulty === 'B' ? 'selected' : ''}>B단계</option>
                    <option value="C" ${problem.difficulty === 'C' ? 'selected' : ''}>C단계</option>
                </select>
            </div>
        </div>
    `;
    
    return problemDiv;
}

// 워크시트 저장
async function saveWorksheet() {
    if (!currentEditWorksheet) {
        alert('편집 중인 워크시트가 없습니다.');
        return;
    }
    
    try {
        // 편집된 데이터 수집
        const updatedData = {
            title: document.getElementById('edit-title').value,
            user_prompt: document.getElementById('edit-user-prompt').value,
            problems: []
        };
        
        // 각 문제의 편집된 데이터 수집
        const problemElements = document.querySelectorAll('.problem-edit-item');
        problemElements.forEach(element => {
            const problemId = element.dataset.problemId;
            const question = element.querySelector('.problem-question').value;
            const answer = element.querySelector('.problem-answer').value;
            const explanation = element.querySelector('.problem-explanation').value;
            const difficulty = element.querySelector('.problem-difficulty-select').value;
            
            // 선택지 수집 (객관식인 경우)
            const choiceInputs = element.querySelectorAll('.choice-input');
            const choices = Array.from(choiceInputs).map(input => input.value);
            
            const problemData = {
                id: parseInt(problemId),
                question: question,
                correct_answer: answer,
                explanation: explanation,
                difficulty: difficulty
            };
            
            if (choices.length > 0) {
                problemData.choices = choices;
            }
            
            updatedData.problems.push(problemData);
        });
        
        // 서버에 저장 요청
        const response = await fetch(`${API_BASE}/worksheets/${currentEditWorksheet.worksheet.id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updatedData)
        });
        
        if (!response.ok) {
            throw new Error('저장에 실패했습니다.');
        }
        
        await response.json();
        
        document.getElementById('edit-result').innerHTML = `
            <div class="result-item" style="border-color: #27ae60; background-color: #d5f4e6;">
                <h4 style="color: #27ae60;">저장 완료</h4>
                <p>워크시트가 성공적으로 저장되었습니다.</p>
                <p><strong>저장 시간:</strong> ${new Date().toLocaleString()}</p>
            </div>
        `;
        
        // 원본 데이터 업데이트
        originalWorksheetData = JSON.parse(JSON.stringify(currentEditWorksheet));
        
    } catch (error) {
        console.error('저장 오류:', error);
        document.getElementById('edit-result').innerHTML = `
            <div class="result-item" style="border-color: #e74c3c; background-color: #fdf2f2;">
                <h4 style="color: #e74c3c;">저장 실패</h4>
                <p>워크시트 저장 중 오류가 발생했습니다: ${error.message}</p>
            </div>
        `;
    }
}

// 편집 취소
function cancelEdit() {
    if (confirm('편집을 취소하시겠습니까? 저장하지 않은 변경사항이 손실됩니다.')) {
        document.getElementById('edit-worksheet').style.display = 'none';
        document.getElementById('worksheet-select-edit').value = '';
        document.getElementById('edit-result').innerHTML = '';
        currentEditWorksheet = null;
        originalWorksheetData = null;
    }
}

// 채점 이력 관련 함수들
let currentGradingHistory = [];
let filteredGradingHistory = [];

// 채점 이력 로드
async function loadGradingHistory() {
    try {
        console.log('채점 이력 로드 시도...');
        const response = await fetch(`${API_BASE}/grading-history?limit=50`);
        console.log('응답 상태:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('받은 데이터:', data);
        
        currentGradingHistory = data.grading_history || [];
        filteredGradingHistory = [...currentGradingHistory];
        
        displayGradingHistory(filteredGradingHistory);
        
    } catch (error) {
        console.error('채점 이력 로드 오류:', error);
        document.getElementById('grading-history-list').innerHTML = `
            <div class="result-item" style="border-color: #e74c3c; background-color: #fdf2f2;">
                <h4 style="color: #e74c3c;">오류 발생</h4>
                <p>채점 이력을 불러올 수 없습니다: ${error.message}</p>
            </div>
        `;
    }
}

// 채점 이력 표시
function displayGradingHistory(historyList) {
    const historyListDiv = document.getElementById('grading-history-list');
    
    if (historyList.length === 0) {
        historyListDiv.innerHTML = `
            <div class="no-data">
                <p>채점 이력이 없습니다.</p>
                <p>문제지를 채점하면 이곳에 결과가 표시됩니다.</p>
            </div>
        `;
        return;
    }
    
    const historyHtml = historyList.map(session => {
        const gradedDate = new Date(session.graded_at).toLocaleString('ko-KR');
        const scorePercentage = ((session.total_score / session.max_possible_score) * 100).toFixed(1);
        const inputMethodLabel = getInputMethodLabel(session.input_method);
        
        return `
            <div class="grading-history-item" data-session-id="${session.grading_session_id}">
                <div class="history-header">
                    <h4>채점 세션 #${session.grading_session_id}</h4>
                    <span class="grading-date">${gradedDate}</span>
                </div>
                <div class="history-info">
                    <div class="info-row">
                        <span><strong>문제지 ID:</strong> ${session.worksheet_id}</span>
                        <span><strong>입력 방식:</strong> ${inputMethodLabel}</span>
                    </div>
                    <div class="info-row">
                        <span><strong>총 문제:</strong> ${session.total_problems}개</span>
                        <span><strong>정답:</strong> ${session.correct_count}개</span>
                    </div>
                    <div class="info-row">
                        <span><strong>점수:</strong> ${session.total_score}/${session.max_possible_score}점 (${scorePercentage}%)</span>
                        <span><strong>배점:</strong> ${session.points_per_problem}점/문제</span>
                    </div>
                </div>
                <div class="history-actions">
                    <button class="btn-secondary" onclick="viewGradingDetail(${session.grading_session_id})">상세 보기</button>
                    <button class="btn-secondary" onclick="retakeWithWorksheet(${session.worksheet_id})">재시험</button>
                </div>
            </div>
        `;
    }).join('');
    
    historyListDiv.innerHTML = historyHtml;
}

// 입력 방식 라벨 변환
function getInputMethodLabel(inputMethod) {
    const methodMap = {
        'canvas': '캔버스 그리기',
        'image_upload': '이미지 업로드',
        'mixed': '혼합형'
    };
    return methodMap[inputMethod] || inputMethod;
}

// 채점 상세 결과 조회
async function viewGradingDetail(gradingSessionId) {
    try {
        console.log(`채점 상세 결과 로드: ${gradingSessionId}`);
        const response = await fetch(`${API_BASE}/grading-history/${gradingSessionId}`);
        
        if (!response.ok) {
            throw new Error('채점 상세 결과를 찾을 수 없습니다.');
        }
        
        const data = await response.json();
        displayGradingDetail(data);
        
    } catch (error) {
        console.error('채점 상세 조회 오류:', error);
        document.getElementById('grading-detail').innerHTML = `
            <div class="result-item" style="border-color: #e74c3c; background-color: #fdf2f2;">
                <h4 style="color: #e74c3c;">오류 발생</h4>
                <p>채점 상세 정보를 불러올 수 없습니다: ${error.message}</p>
            </div>
        `;
        document.getElementById('grading-detail-section').style.display = 'block';
    }
}

// 채점 상세 결과 표시
function displayGradingDetail(data) {
    const { grading_session, problem_results } = data;
    const gradingDetailDiv = document.getElementById('grading-detail');
    
    const gradedDate = new Date(grading_session.graded_at).toLocaleString('ko-KR');
    const scorePercentage = ((grading_session.total_score / grading_session.max_possible_score) * 100).toFixed(1);
    
    let detailHtml = `
        <div class="grading-session-info">
            <h4>채점 세션 #${grading_session.id} 상세 결과</h4>
            <div class="session-meta">
                <p><strong>채점 일시:</strong> ${gradedDate}</p>
                <p><strong>문제지 ID:</strong> ${grading_session.worksheet_id}</p>
                <p><strong>입력 방식:</strong> ${getInputMethodLabel(grading_session.input_method)}</p>
                <p><strong>총 점수:</strong> ${grading_session.total_score}/${grading_session.max_possible_score}점 (${scorePercentage}%)</p>
                <p><strong>정답률:</strong> ${grading_session.correct_count}/${grading_session.total_problems}개 정답</p>
            </div>
        </div>
    `;
    
    // OCR 결과 표시 (있는 경우)
    if (grading_session.ocr_text) {
        detailHtml += `
            <div class="ocr-result-section">
                <h5>OCR 추출 텍스트:</h5>
                <pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; max-height: 200px; overflow-y: auto;">${grading_session.ocr_text}</pre>
            </div>
        `;
    }
    
    // 객관식 답안 표시 (있는 경우)
    if (grading_session.multiple_choice_answers && Object.keys(grading_session.multiple_choice_answers).length > 0) {
        const mcAnswers = Object.entries(grading_session.multiple_choice_answers)
            .map(([problemId, answer]) => `문제 ${problemId}: ${answer}`)
            .join(', ');
        
        detailHtml += `
            <div class="mc-answers-section">
                <h5>객관식 답안:</h5>
                <p>${mcAnswers}</p>
            </div>
        `;
    }
    
    // 문제별 상세 결과
    detailHtml += '<div class="problem-results-section"><h5>문제별 채점 결과:</h5>';
    
    problem_results.forEach(result => {
        const isCorrect = result.is_correct;
        const borderColor = isCorrect ? '#27ae60' : '#e74c3c';
        const resultIcon = isCorrect ? '✅' : '❌';
        
        const formattedUserAnswer = formatMathText(result.user_answer || '답안 없음');
        const formattedCorrectAnswer = formatMathText(result.correct_answer || '');
        const formattedAiFeedback = formatMathText(result.ai_feedback || '');
        const formattedStrengths = formatMathText(result.strengths || '');
        const formattedImprovements = formatMathText(result.improvements || '');
        
        detailHtml += `
            <div class="problem-result-item tex2jax_process" style="border-color: ${borderColor}; border-left: 4px solid ${borderColor}; margin-bottom: 15px; padding: 15px; background: #f9f9f9;">
                <h6>${resultIcon} 문제 ${result.problem_id} (${result.problem_type}) - ${result.score}/${result.points_per_problem}점</h6>
                <p><strong>학생 답안:</strong> ${textToHtml(formattedUserAnswer)}</p>
                <p><strong>정답:</strong> ${textToHtml(formattedCorrectAnswer)}</p>
                
                ${result.ai_score ? `<p><strong>AI 점수:</strong> ${result.ai_score}/100점</p>` : ''}
                ${result.ai_feedback ? `<p><strong>AI 피드백:</strong> ${textToHtml(formattedAiFeedback)}</p>` : ''}
                ${result.strengths ? `<p><strong>잘한 점:</strong> ${textToHtml(formattedStrengths)}</p>` : ''}
                ${result.improvements ? `<p><strong>개선점:</strong> ${textToHtml(formattedImprovements)}</p>` : ''}
                ${result.explanation ? `<div class="explanation"><strong>해설:</strong> ${textToHtml(formatMathText(result.explanation))}</div>` : ''}
            </div>
        `;
    });
    
    detailHtml += '</div>';
    
    gradingDetailDiv.innerHTML = detailHtml;
    
    // MathJax 렌더링
    setTimeout(() => renderMathJax(gradingDetailDiv), 100);
    
    // 상세보기 섹션 표시 및 스크롤
    document.getElementById('grading-detail-section').style.display = 'block';
    document.getElementById('grading-detail-section').scrollIntoView({ 
        behavior: 'smooth' 
    });
}

// 워크시트 필터 옵션 로드
async function loadWorksheetFilterOptions() {
    try {
        const response = await fetch(`${API_BASE}/worksheets?limit=100`);
        if (!response.ok) return;
        
        const data = await response.json();
        const worksheetFilter = document.getElementById('worksheet-filter');
        
        // 기존 옵션 제거 (전체 보기 제외)
        while (worksheetFilter.children.length > 1) {
            worksheetFilter.removeChild(worksheetFilter.lastChild);
        }
        
        // 워크시트 옵션 추가
        data.worksheets.forEach(worksheet => {
            const option = document.createElement('option');
            option.value = worksheet.id;
            option.textContent = `#${worksheet.id} - ${worksheet.title}`;
            worksheetFilter.appendChild(option);
        });
        
    } catch (error) {
        console.error('워크시트 필터 옵션 로드 오류:', error);
    }
}

// 채점 이력 필터링
function filterGradingHistory() {
    const selectedWorksheetId = document.getElementById('worksheet-filter').value;
    
    if (selectedWorksheetId === '') {
        filteredGradingHistory = [...currentGradingHistory];
    } else {
        filteredGradingHistory = currentGradingHistory.filter(
            session => session.worksheet_id.toString() === selectedWorksheetId
        );
    }
    
    displayGradingHistory(filteredGradingHistory);
}

// 재시험 시작 (채점 탭으로 이동하여 해당 워크시트 선택)
function retakeWithWorksheet(worksheetId) {
    // 채점 탭으로 이동
    showTab('grading');
    
    // 워크시트 선택
    setTimeout(() => {
        const worksheetSelect = document.getElementById('worksheet-select-grading');
        if (worksheetSelect) {
            worksheetSelect.value = worksheetId;
            loadSelectedWorksheetForGrading();
        }
    }, 500);
    
    // 채점 탭으로 스크롤
    setTimeout(() => {
        document.getElementById('grading-tab').scrollIntoView({ 
            behavior: 'smooth' 
        });
    }, 100);
}