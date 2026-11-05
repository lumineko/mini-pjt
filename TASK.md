# TASK.md — 작업 체크리스트 및 진행 기록

## 사용 규칙
- 한 번에 하나의 작업만 진행한다.
- 작업 시작 시 "현재 진행 중"으로 옮기고, 완료 시 `[x]` 체크 후 "작업 로그"에 기록한다.
- 세션이 바뀌면 이 파일의 "현재 진행 중"과 마지막 로그부터 이어간다.

## 현재 진행 중
- (없음)

## 백로그
### Phase 0. 기획/설계
- [x] 기본 설계서 파일 생성 (SERVICE.md, PRD.md, TASK.md, CLAUDE.md)
- [x] PRD.md 작성 (목표, 시나리오, 요구사항, 범위)
- [x] SERVICE.md 작성 (모듈, 그래프 구조, API, 데이터 흐름, 외부 연동)
- [x] 작업 분할 후 이 백로그 구체화

### Phase 1. 프로젝트 스캐폴딩
- [x] 디렉터리 구조 + `.gitignore`(.env, data/history/, logs/, evals/results/, __pycache__/, .venv/) + `requirements.txt` (streamlit, langgraph, langchain-aws, python-dotenv, pytest — 승인됨) + 가상환경 설치 확인 (Python 3.14, 비호환 시 3.12)
- [x] `.env.example` + `config.py` 설정 로더 + `tests/test_config.py`
- [x] 데이터 초안: `data/default_topics.json`, `data/levels.json`, `data/rubric.json` + `tests/test_data_files.py`
- [x] `state.py` 타입 정의 + `tests/test_state.py`

### Phase 2. 규칙·도구 (Python, 테스트 우선)
- [x] `rules/scoring.py` + `tests/test_scoring.py` (가중 합산, 한글 감점, 등급, IL 미달)
- [x] `tools/korean.py` + `tests/test_korean.py`
- [x] `rules/difficulty.py` + `tests/test_difficulty.py` (AL/IL 경계 포함)
- [x] `rules/topic.py` + `tests/test_topic.py`, `rules/validation.py` + `tests/test_validation.py`
- [x] `rules/summary.py` + `tests/test_summary.py`
- [ ] `tools/survey.py` + `tests/test_survey.py` (파싱, [프로필]/★/안내문 처리, fallback 조건)
- [ ] `tools/level.py` + `tests/test_level.py`, `storage.py` + `tests/test_storage.py`

> 테스트 규칙 (SERVICE §14): 각 태스크는 대응 테스트 통과가 완료 조건이다. 공용 테스트 데이터는 `tests/fixtures/`에 한 번 만들어 재사용한다.

### Phase 2.5. 채점 평가 세트 (SERVICE §14.2, Phase 3 scorer 착수 전)
- [ ] `evals/scorer/golden.jsonl` 초안 작성: 30~50건, 레벨별 분포 + 경계 사례(한글 혼합·전부 한글·지시문·주제 이탈·짧은 답변). 각 건에 질문, 출제 레벨, 제안 기대 등급
- [ ] **사용자 검수**: 기대 등급 확인·수정 (검수 완료 전 Phase 3 scorer 프롬프트 확정 금지)
- [ ] `evals/run_scorer_eval.py` 작성 (지표는 파이썬으로 계산, 결과는 `evals/results/`에 프롬프트 버전별 저장)

### Phase 3. LLM·에이전트
- [ ] `llm.py` Bedrock 클라이언트 + 용도별 모델 매핑 + 재시도·폴백 + 트레이스 메타데이터 전달 + pre/post 훅 자리 (SERVICE §13) + `tests/test_llm_fallback.py`
- [ ] `prompts/` 4종 survey, interviewer, scorer, feedback (id/version 헤더 포함)
- [ ] `agents/` survey, interviewer, scorer, feedback + 가짜 LLM 테스트 (`tests/test_agents.py`)
- [ ] scorer 평가 실행 → 목표 지표 달성까지 `prompts/scorer.md`·`rubric.json` 조정 (SERVICE §14.2)

### Phase 4. 그래프
- [ ] `routing.py` 분기 함수 5개 (SERVICE §3) + `tests/test_routing.py`
- [ ] `graph.py` 고정 엣지·조건 분기 조립, `record_item` 노드, HITL interrupt, `start_session`/`resume`/`get_state`
- [ ] `tests/test_graph_flow.py` (fake LLM으로 5문항, 문항 안 순서 scorer → score_and_grade → feedback, 3문항 점검, 조정 흐름)

### Phase 5. UI·마무리
- [ ] `app.py` Streamlit (설문, 레벨, 문항·피드백, 조정 확인, 요약, 기록)
- [ ] 실제 Bedrock으로 E2E 확인 (PRD 성공 기준 1~10)
- [ ] CLAUDE.md 실행·테스트 명령 갱신

### Phase 6. 트레이스·가드레일 (SERVICE §13)
- [ ] 트레이스 저장 방식 결정 (로컬 JSONL / 외부 도구, 외부 도구는 사용자 승인 필요) 및 after_call 훅 구현
- [ ] 출력 가드레일 post 훅 (언어 검사, 번역 누락, 주제 이탈)
- [ ] Bedrock Guardrails 적용 여부 결정 및 guardrail_config 연결
- [ ] PRD §6 비기능 요구사항에 트레이스·가드레일 항목 반영

## 작업 로그
| 날짜 | 작업 | 결과 | 다음 할 일 |
|------|------|------|-----------|
| 2026-11-04 | 기본 설계서 파일 생성 | 4개 문서 골격 작성 완료 | PRD.md 작성 |
| 2026-11-04 | PRD.md 작성 (인터뷰 기반) | OPIc 텍스트 학습 프로그램 요구사항 확정, Streamlit 도입 승인 | SERVICE.md 작성 |
| 2026-11-04 | PRD 추가 기능 반영 | 5문항 세션, opic_survey.md 설문, 3문항 후 난이도 점검, 한글 감지·번역·감점 추가 (F-11~F-13) | SERVICE.md 작성 |
| 2026-11-04 | PRD 난이도 4단계(IL 추가) 반영 | IL/IM/IH/AL 4단계, 최하 미달 표기 "IL 미달", IL 하향 금지 | SERVICE.md 작성 |
| 2026-11-04 | SERVICE.md 작성 + 백로그 구체화 | 멀티 에이전트(LLM 슈퍼바이저 + Py guard), 에이전트 4종, HITL 3곳, 세션별 JSON, 라이브러리 승인 | Phase 1 스캐폴딩 |
| 2026-11-04 | PRD 재검토·보완 | 등급 상한(출제 레벨+1), 선택형 설문, 조정 폭 1단계, F-09 P0, 일관성 표현 수정, 최소 답변 길이, 미완료 세션 미저장. SERVICE.md 동기화 | Phase 1 스캐폴딩 |
| 2026-11-04 | SERVICE.md 재검토·보완 | 피드백 HITL 추가, State 필드 보강, guard 규칙 13개 재정의, 파이썬 순환 주제 배정, 데이터 스키마, 로깅, 인젝션 방지, 모델 Sonnet 4.5→Haiku 4.5(global) | Phase 1 스캐폴딩 |
| 2026-11-04 | opic_survey.md 작성 | 링커리어 2026 서베이 글 기반 6주제(프로필 2: 단일 선택, topic 4), ★ 추천 표시, 12개 규칙은 안내만. PRD F-01·SERVICE §3/§4/§10 동기화 | Phase 1 스캐폴딩 |
| 2026-11-04 | 트레이스·가드레일 확장 지점 설계 | SERVICE §13 추가(단일 진입점, 메타데이터, 프롬프트 버전, pre/post 훅), Phase 6 백로그 신설 | Phase 1 스캐폴딩 |
| 2026-11-04 | 테스트·평가 전략 반영 | SERVICE §14(태스크별 pytest, scorer 평가 세트·지표), 디렉터리 구조에 evals/ 추가, TASK Phase 2.5 신설·Phase 3 테스트 보강 | Phase 1 스캐폴딩 |
| 2026-11-04 | 4개 문서 통합 재검토 | 대체 설문 직업·거주지는 topic으로 처리, scorer는 영어 부분만 평가(이중 감점 방지), 질문 유형은 LLM이 레벨 후보 안에서 선택, PRD 성공 기준 10(채점 품질) 추가, .gitignore·누락 테스트·Python 버전·pydantic 명시, CLAUDE.md 문서 구조 보강 | Phase 1 스캐폴딩 |
| 2026-11-04 | Phase 1: 디렉터리 구조 + .gitignore + requirements.txt | src/opic 패키지 골격, data·logs·tests·evals 폴더, .gitignore, pytest.ini, requirements(~= 고정). Python 3.14 venv 설치 성공, tests/test_smoke.py 5개 통과 | `.env.example` + `config.py` |
| 2026-11-05 | 슈퍼바이저 제거 (개발 시간 단축) | 고정 순서 워크플로로 변경: 문항 안 순서 scorer → score_and_grade → feedback(등급 참고) → record_item, 분기는 `routing.py` 파이썬 함수 5개. PRD §6, SERVICE §1~3·5·7·9·11~14, CLAUDE.md 동기화, 프롬프트 4종 | `.env.example` + `config.py` |
| 2026-11-05 | Phase 1: `.env.example` + `config.py` | 인증은 액세스 키/프로필 둘 다 지원(둘 중 하나), 키 없어도 로드 가능(`has_credentials`로 확인), 빈 값은 기본값, 상대 경로는 루트 기준, 환경변수가 .env보다 우선, `setup_logging`(콘솔+logs/app.log, 중복 방지). 테스트 13개 추가, 전체 18개 통과 | 데이터 초안 (default_topics, levels, rubric) |
| 2026-11-05 | Phase 1: 데이터 초안 | default_topics 6개, levels.json 누적형 질문 유형 + 레벨별 guide 초안(사용자 검토 대상), rubric.json SERVICE §10 수치 + 항목 description. SERVICE §10 동기화. 형식 검사 테스트 추가 | `state.py` 타입 정의 |
| 2026-11-05 | Phase 1: `state.py` 타입 정의 | SessionState(SERVICE §3 23개 필드) + 하위 TypedDict(SurveyItem, Pending, Grading, Feedback, ItemResult, SessionSummary 등), Level/Grade 상수(순서값 = 인덱스), `new_session_state()`. 문서 필드·데이터 파일 일치, LangGraph 호환 테스트. 전체 37개 통과 | Phase 2 `rules/scoring.py` |
| 2026-11-05 | Phase 2: `rules/scoring.py` | 가중 합산(항목·척도 검증), 한글 비례 감점, 80% 이상 IL 미달, 등급 구간(소수 둘째 자리 반올림 후 비교), 출제 레벨+1 상한, 달성 여부, `grade_answer()` 통합, 순서값 평균(.5 올림). SERVICE §10 반영. 테스트 60개 추가, 전체 97개 통과 | `tools/korean.py` (한글 비율 정의 확정 필요) |
| 2026-11-05 | Phase 2: `tools/korean.py` | 한글 비율 **단어 기준** 확정(한글 들어간 단어/전체 단어, 숫자·문장부호만 있는 덩어리 제외), 최소 단어 수에 한글 단어 포함, 번역 구간 병합 규칙, `count_words` 공용. PRD F-04·F-13, SERVICE §2 반영. 테스트 24개 추가, 전체 121개 통과 | `rules/difficulty.py` |
| 2026-11-05 | Phase 2: `rules/difficulty.py` | `propose_adjustment`(3문항 평균 등급 vs 목표, 항상 한 단계, AL up·IL down 없음, IL 미달은 down, 정확히 3개 검증), `apply_adjustment`(새 레벨 + LevelChange, 잘못된 제안 거부). SERVICE §2 반영. 테스트 29개 추가, 전체 150개 통과 | `rules/topic.py` + `rules/validation.py` |
| 2026-11-05 | Phase 2: `rules/topic.py` + `rules/validation.py` | 주제 배정 **주제별 번갈아** 확정(설문 순서, 안 쓴 보기 우선, 다 쓴 뒤에만 반복, profile 제외). 검증: 답변(빈 값·최소 단어), 레벨, 설문 응답(profile 1·topic ≥1·보기 값·중복). 공용 샘플 `tests/fixtures/survey_items.py`. SERVICE §2 반영. 테스트 43개 추가, 전체 193개 통과 | `rules/summary.py` |
| 2026-11-05 | Phase 2: `rules/summary.py` | `summarize`: 문항별 등급, 평균 등급(scoring.average_grade), 시작·최종 레벨(이력 마지막 to), 변경 여부. 5문항·이력 연속성 검증. `SESSION_ITEMS`를 state.py 공용 상수로 이동. SERVICE §2 반영. 테스트 10개 추가, 전체 203개 통과 | `tools/survey.py` |
