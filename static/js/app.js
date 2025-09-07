// API 기본 URL
const API_BASE = '/api/math-generation';

// 현재 활성 태스크
let activeTask = null;
let pollingInterval = null;

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
        mcHtml += `
            <div class="mc-problem">
                <h5>문제 ${problem.sequence_order}</h5>
                <p><strong>${problem.question}</strong></p>
                <div class="mc-choices">
        `;
        
        if (problem.choices) {
            problem.choices.forEach((choice, index) => {
                const choiceLabel = String.fromCharCode(65 + index); // A, B, C, D
                mcHtml += `
                    <label class="mc-choice">
                        <input type="radio" name="problem_${problem.id}" value="${choiceLabel}">
                        ${choiceLabel}. ${choice}
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
}

// 주관식 섹션 설정
function setupSubjectiveSection(subjectiveProblems) {
    const subjectiveDiv = document.getElementById('subjective-answers');
    let subjectiveHtml = '';
    
    subjectiveProblems.forEach(problem => {
        subjectiveHtml += `
            <div class="subjective-problem">
                <h5>문제 ${problem.sequence_order}</h5>
                <p><strong>${problem.question}</strong></p>
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
        
        // 태스크 상태를 주기적으로 확인
        startPolling(data.task_id);
        
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

// 폴링 시작
function startPolling(taskId) {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    
    pollingInterval = setInterval(async () => {
        await checkTaskStatus(taskId);
    }, 2000); // 2초마다 확인
}

// 폴링 중지
function stopPolling() {
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
            stopPolling();
            updateGenerationUI('success');
            displayGenerationSuccess(data.result);
            break;
        case 'FAILURE':
            stopPolling();
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
        problemsHtml = result.problems.map(problem => `
            <div class="problem-item">
                <div class="problem-header">
                    문제 ${problem.sequence_order}번 [${problem.difficulty}단계, ${getTypeLabel(problem.problem_type)}]
                </div>
                <div class="problem-content">
                    <strong>문제:</strong> ${problem.question}
                </div>
                ${problem.choices ? `
                    <div class="choices">
                        <strong>선택지:</strong><br>
                        ${problem.choices.map((choice, idx) => `${idx + 1}. ${choice}`).join('<br>')}
                    </div>
                ` : ''}
                <div><strong>정답:</strong> ${problem.correct_answer}</div>
                <div class="explanation">
                    <strong>해설:</strong> ${problem.explanation}
                </div>
            </div>
        `).join('');
    }
    
    resultDiv.innerHTML = `
        <div class="result-item fade-in">
            <h4>문제 생성 완료!</h4>
            <p><strong>워크시트 ID:</strong> ${result.worksheet_id}</p>
            <p><strong>생성된 문제 수:</strong> ${result.total_generated}개</p>
            <p><strong>실제 난이도 분포:</strong> A${result.actual_difficulty_distribution?.A || 0}개, B${result.actual_difficulty_distribution?.B || 0}개, C${result.actual_difficulty_distribution?.C || 0}개</p>
        </div>
        <div class="problems-container">
            ${problemsHtml}
        </div>
    `;
    
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
        
        // 채점 태스크 폴링 시작
        startGradingPolling(data.task_id);
        
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

// 채점 폴링 시작
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
                displayGradingSuccess(data.result);
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

// 채점 성공 결과 표시
function displayGradingSuccess(result) {
    const resultDiv = document.getElementById('grading-result');
    
    let gradingHtml = '';
    if (result.grading_results && result.grading_results.length > 0) {
        gradingHtml = result.grading_results.map(item => `
            <div class="problem-item">
                <div class="problem-header">
                    문제 ${item.problem_id}번 ${item.is_correct ? '✅ 정답' : '❌ 오답'}
                </div>
                <div><strong>제출한 답:</strong> ${item.user_answer}</div>
                <div><strong>정답:</strong> ${item.correct_answer}</div>
                <div class="explanation">
                    <strong>해설:</strong> ${item.explanation}
                </div>
            </div>
        `).join('');
    }
    
    resultDiv.innerHTML = `
        <div class="result-item fade-in">
            <h4>채점 완료!</h4>
            <p><strong>총 문제 수:</strong> ${result.total_problems}개</p>
            <p><strong>정답 수:</strong> ${result.correct_count}개</p>
            <p><strong>점수:</strong> ${result.score.toFixed(1)}점</p>
        </div>
        <div class="grading-container">
            ${gradingHtml}
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
            problemsHtml = problems.map(problem => `
                <div class="problem-item">
                    <div class="problem-header">
                        문제 ${problem.sequence_order}번 [${problem.difficulty}단계, ${getTypeLabel(problem.problem_type)}]
                    </div>
                    <div class="problem-content">
                        <strong>문제:</strong> ${problem.question}
                    </div>
                    ${problem.choices ? `
                        <div class="choices">
                            <strong>선택지:</strong><br>
                            ${problem.choices.map((choice, idx) => `${idx + 1}. ${choice}`).join('<br>')}
                        </div>
                    ` : ''}
                    <div><strong>정답:</strong> ${problem.correct_answer}</div>
                    <div class="explanation">
                        <strong>해설:</strong> ${problem.explanation}
                    </div>
                    ${problem.has_diagram ? `
                        <div class="diagram-info">
                            <strong>그림:</strong> ${problem.diagram_type} 유형
                        </div>
                    ` : ''}
                </div>
            `).join('');
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
            <div class="problems-container">
                ${problemsHtml}
            </div>
        `;
        
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
        
        // 진행 상황 모니터링 시작
        startGradingPolling();
        
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
                clearInterval(pollingInterval);
                displayGradingResult(data.result);
                document.getElementById('grading-progress').style.display = 'none';
            } else if (data.status === 'FAILURE') {
                clearInterval(pollingInterval);
                document.getElementById('grading-progress').style.display = 'none';
                alert('채점 실패: ' + data.error);
            }
        } catch (error) {
            console.error('상태 확인 오류:', error);
        }
    }, 1000);
}

// 채점 결과 표시
function displayGradingResult(result) {
    const resultContainer = document.getElementById('grading-result');
    
    let resultHtml = `
        <div class="result-item">
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
        
        resultHtml += `
            <div class="result-item" style="border-color: ${borderColor}; margin-bottom: 15px;">
                <h6>문제 ${item.problem_id} (${item.input_method || '알 수 없음'}) - ${item.score}점</h6>
                <p><strong>학생 답안:</strong> ${item.user_answer || '없음'}</p>
                <p><strong>정답:</strong> ${item.correct_answer}</p>
                <p><strong>결과:</strong> ${isCorrect ? '정답' : '오답'}</p>
                
                ${item.ai_feedback ? `<p><strong>AI 피드백:</strong> ${item.ai_feedback}</p>` : ''}
                ${item.strengths ? `<p><strong>잘한 점:</strong> ${item.strengths}</p>` : ''}
                ${item.improvements ? `<p><strong>개선점:</strong> ${item.improvements}</p>` : ''}
            </div>
        `;
    });
    
    resultHtml += '</div></div>';
    
    resultContainer.innerHTML = resultHtml;
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