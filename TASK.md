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
- [x] `tools/survey.py` + `tests/test_survey.py` (파싱, [프로필]/★/안내문 처리, fallback 조건)
- [x] `tools/level.py` + `tests/test_level.py`, `storage.py` + `tests/test_storage.py`

> 테스트 규칙 (SERVICE §14): 각 태스크는 대응 테스트 통과가 완료 조건이다. 공용 테스트 데이터는 `tests/fixtures/`에 한 번 만들어 재사용한다.

### Phase 2.5. 채점 평가 세트 (SERVICE §14.2, Phase 3 scorer 착수 전)
- [x] `evals/scorer/golden.jsonl` 초안 작성: 30~50건, 레벨별 분포 + 경계 사례(한글 혼합·전부 한글·지시문·주제 이탈·짧은 답변). 각 건에 질문, 출제 레벨, 제안 기대 등급
- [x] **사용자 검수**: 기대 등급 확인·수정 (검수 완료 전 Phase 3 scorer 프롬프트 확정 금지)
- [x] `evals/run_scorer_eval.py` 작성 (지표는 파이썬으로 계산, 결과는 `evals/results/`에 프롬프트 버전별 저장)

### Phase 3. LLM·에이전트
- [x] `llm.py` Bedrock 클라이언트 + 용도별 모델 매핑 + 재시도·폴백 + 트레이스 메타데이터 전달 + pre/post 훅 자리 (SERVICE §13) + `tests/test_llm_fallback.py`
- [x] `prompts/` 4종 survey, interviewer, scorer, feedback (id/version 헤더 포함)
- [x] `agents/` survey, interviewer, scorer, feedback + 가짜 LLM 테스트 (`tests/test_agents.py`)
- [x] scorer 평가 실행 → 목표 지표 달성까지 `prompts/scorer.md`·`rubric.json` 조정 (SERVICE §14.2) — scorer@1 목표 달성(정확 61.1%), scorer@2로 개선(정확 83.3%)

### Phase 4. 그래프
- [x] `routing.py` 분기 함수 5개 (SERVICE §3) + `tests/test_routing.py`
- [x] `graph.py` 고정 엣지·조건 분기 조립, `record_item` 노드, HITL interrupt, `start_session`/`resume`/`get_state`
- [x] `tests/test_graph_flow.py` (fake LLM으로 5문항, 문항 안 순서 scorer → score_and_grade → feedback, 3문항 점검, 조정 흐름)

### Phase 5. UI·마무리
- [x] `app.py` Streamlit (설문, 레벨, 문항·피드백, 조정 확인, 요약, 기록)
- [x] 실제 Bedrock으로 E2E 확인 (PRD 성공 기준 1~10) — `evals/run_e2e.py`, 13/13 통과
- [x] CLAUDE.md 실행·테스트 명령 갱신

### Phase 6. 트레이스·가드레일 (SERVICE §13)
- [x] 트레이스 저장 방식 결정 (로컬 JSONL / 외부 도구, 외부 도구는 사용자 승인 필요) 및 after_call 훅 구현
- [x] 출력 가드레일 post 훅 (언어 검사, 번역 누락, 주제 이탈)
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
| 2026-11-05 | Phase 2: `tools/survey.py` | `parse_survey`(첫 ": " 분리, [프로필] → profile, ★ → recommend 최대 3, 여러 줄 안내문, 주석·제목 무시, 빈·중복 보기 제거, id `{주제}-{순번}`), `load_survey_file`(없음·읽기 실패·topic 0개 → None), `pick_default_topic`(rng 주입). 실제 opic_survey.md 8문항 파싱 확인. SERVICE §2·§10 반영. 테스트 20개 추가, 전체 223개 통과 | `tools/level.py` + `storage.py` |
| 2026-11-05 | Phase 2: `tools/level.py` + `storage.py` (Phase 2 완료) | level: 레벨별 유형·guide 조회(order 검증, 사본 반환), 완료 문항 기반 이전 질문 목록. storage: 완료 세션만 저장(5문항+요약), 진행용 필드 제외, 임시 파일 후 교체, session_id 경로 조작 차단, 최신순 목록·깨진 파일 건너뜀. 공용 `tests/fixtures/sessions.py`. SERVICE §2 반영. 테스트 31개 추가, 전체 254개 통과 | Phase 2.5 채점 평가 세트 초안 |
| 2026-11-05 | Phase 2.5: golden.jsonl 초안 | 36건(기대 등급 IL 미달 6·IL 8·IM 8·IH 7·AL 7, 경계 사례 korean_mixed 4·korean_full 2·injection 3·off_topic 2·short 2·cap 3). `build_golden.py`(원본·생성기, 한글 비율·감점 자동 계산), 검수용 `REVIEW.md`, injection은 clean_answer 포함, `reviewed: false`. 일관성 검사 `tests/test_golden_set.py`. SERVICE §9·§14.2 반영. 전체 262개 통과 | **사용자 검수** (REVIEW.md) |
| 2026-11-05 | Phase 2.5: 사용자 검수 | 36건 제안 등급 그대로 확정, `reviewed: true`로 재생성 | `evals/run_scorer_eval.py` |
| 2026-11-05 | Phase 2.5: `evals/run_scorer_eval.py` (Phase 2.5 완료) | 채점 함수 주입 구조(규약 `score_answer(question, level, answer, korean_spans)`), 지표 5종 파이썬 계산·목표 판정, 일관성 표본 10건×3회, 인젝션 항목별 ±1, 검수 전 실행 거부, `--fake` 모드, 결과 JSON 저장. 지표 테스트 `tests/test_scorer_eval.py`. SERVICE §14.2·CLAUDE.md 명령 반영. 전체 271개 통과 | Phase 3 `llm.py` |
| 2026-11-05 | Phase 3: `llm.py` | `invoke_llm` 단일 진입점: 모델 목록 순회 루프(재시도 가능 오류만 1s·2s 백오프 재시도, 구조화 출력 실패·가드레일 위반·기타 오류는 바로 다음 모델, 전부 실패 시 LLMError), botocore 재시도 끔(total_max_attempts=1, 테스트로 발견), 용도별 temperature/max_tokens, 메타데이터·tags, before/after 훅(빈 목록), factory·sleep 주입. with_retry/with_fallbacks 대신 직접 루프로 변경(SERVICE §7). 테스트 25개 추가, 전체 296개 통과 | `prompts/` 4종 |
| 2026-11-05 | Phase 3: `prompts/` 4종 | survey(한국어 보기 6~10개), interviewer(영어 질문 1개, 배정 주제·레벨 후보 유형), scorer(1~5 절대 척도 앵커 = 등급 구간, 영어 부분만, 주제 이탈 task 1, 인젝션 무시), feedback(교정 이유 한국어·문장 영어, 대체 문장은 한 단계 위, 한글 부분 번역한 전체 답변) 모두 v1. 로더 `load_prompt`(머리말·[system]/[user]·`${}` 변수), `wrap_answer`(태그 무력화). SERVICE §2·§3·§13 반영. 테스트 23개 추가, 전체 319개 통과 | `agents/` 4종 |
| 2026-11-05 | Phase 3: `agents/` 4종 | 순수 함수 + 노드 `run(state)` 2층 구조. 동적 Pydantic 스키마(질문 유형 Literal·한글 질문 거부, rubric 항목별 1~5, 한글 있으면 번역 필수, 교정 ≤5·대체 1~3, 대체 설문 보기 정리). 노드는 pending을 이어 붙여 갱신. scorer.score_answer가 평가 규약 충족(run_scorer_eval 실제 모드 연결 확인). 공용 `tests/conftest.py` fake_llm. SERVICE §2·§9 반영. 테스트 25개 추가, 전체 344개 통과 | scorer 평가 실행 (Bedrock 키 필요) |
| 2026-11-05 | Phase 3: scorer 실제 평가 (Phase 3 완료) | 버그 수정: .env의 빈 `AWS_PROFILE=`/`AWS_SESSION_TOKEN=`을 boto3가 직접 읽어 실패 → `config.drop_blank_aws_vars`로 제거(테스트 2개). 평가 scorer@1 · Sonnet 4.5: 정확 61.1%, ±1 100%, 일관성 0.044, 인젝션 100%, 한글 100% → 목표 모두 통과. 불일치 14건: IH 수준 답변을 5점(AL)으로 주는 과대 채점 6건·IM→IH 3건, 주제 이탈 2건 IM(task 1이어도 다른 항목 높음), 한 단계 낮음 3건. 결과 `evals/results/20261105-101700_scorer@1.json`(커밋 제외) | Phase 4 `routing.py` (scorer v2 튜닝은 사용자 결정) |
| 2026-11-05 | Phase 3: scorer 프롬프트 v2 | 사용자 결정으로 프롬프트만 개선(루브릭·파이썬 규칙 변경 없음): 5점은 '고급 기능'이 보일 때만, 오류 없음만으로는 4점·단순 문장은 3점, 항목별 5점·4점 기준 명시, 항목마다 따로 판단. 결과 scorer@2: 정확 61.1%→**83.3%**, ±1 100%, 일관성 0.044→0.000, 인젝션·한글 100%. IH→AL 과대 6건·주제 이탈 2건 해소. 남은 6건은 경계 근처(IM→IH 3건 가중 3.75~4.25, 한 단계 낮음 3건). 결과 `evals/results/20261105-102159_scorer@2.json` | Phase 4 `routing.py` |
| 2026-11-05 | Phase 4: `routing.py` | 분기 함수 5개(SERVICE §3 표대로) + 방어 처리(필요 값 비면 같은 입력 노드, 5문항 이상 요약, 조정 중복 적용 금지), 노드 이름 상수, `CONDITIONAL_EDGES`(반환 타입과 도착 노드 일치 테스트), 분기 로그. SERVICE §2·§3 반영. 테스트 28개 추가, 전체 374개 통과 | `graph.py` 조립 |
| 2026-11-05 | Phase 4: `graph.py` | 노드 14개·고정 엣지 10개·조건 분기 5개 조립(슈퍼바이저 없음). HITL 4종 interrupt(재개 시 노드 재실행되므로 입력 처리는 순수 함수 `apply_*`로 분리), 파이썬 노드(score_and_grade, record_item, check_difficulty, apply_level, summarize, save_session). API `start_session`/`resume`/`retry`/`get_state`/`current_payload`, 세션 id는 저장 규칙 호환. SERVICE §2·§4(payload 키) 반영. `tests/test_graph.py` 20개 추가, 전체 394개 통과 | `tests/test_graph_flow.py` |
| 2026-11-05 | Phase 4: `tests/test_graph_flow.py` (Phase 4 완료) | 가짜 LLM으로 5문항 세션 끝까지: payload 순서, LLM 호출 순서(interviewer→scorer→feedback 고정), 피드백에 파이썬 등급 전달, 주제 배정 반영, 조정 상향 수락(4·5번 새 레벨·상한)·거절·하향·AL/IL/동일 경계·1회만, 짧은 답변 재입력(LLM 호출 없음), 전부 한글 IL 미달+번역, LLM 실패 후 retry 이어서, 미완료 미저장, 세션 분리, fallback 설문. 수정 없이 통과. 18개 추가, 전체 412개 통과 | Phase 5 `app.py` |
| 2026-11-05 | Phase 5: `app.py` | 사용자 결정: 사이드바 메뉴(연습/지난 기록, 진행 상황, 새 연습 시작). 화면: 설문(profile 라디오·topic 체크박스 3열·★ 표시·안내문·레벨), 문항(UI 선검증), 피드백(등급·달성·상한 안내·루브릭 표·감점·교정 or "교정 사항 없음"·대체 문장·번역), 조정 확인, 결과, 기록 목록·상세. LLM 실패 시 다시 시도. `tests/test_app.py`(Streamlit 내장 AppTest + fake LLM) 9개, 전체 421개 통과. 실제 서버 기동(health ok) 확인 | Bedrock E2E 확인 |
| 2026-11-05 | Phase 5: 실제 Bedrock E2E | `evals/run_e2e.py`(수동): AppTest로 app.py를 실제 Bedrock과 돌려 5문항 세션 완주(76s, 조정 질문 IM→IH 수락, 4·5번 IH 출제), 폴백(없는 기본 모델 → Haiku 자동 전환), 대체 설문(거주지, 보기 8개). PRD 성공 기준 1~10 + 추가 3개(질문 영어·배정 주제, 언어 규칙, 짧은 답변 화면 차단) **13/13 통과**. 답변 payload에 `topic` 추가(화면 표시, SERVICE §4). 기록은 evals/results/e2e_history(커밋 제외). 참고: 미리 써 둔 답변이 질문 세부와 어긋난 3·4·5번은 task 1~2점으로 낮게 채점됨(채점이 의도대로 동작) | CLAUDE.md 실행·테스트 명령 갱신 |
| 2026-11-05 | Phase 5: CLAUDE.md 명령 갱신 (Phase 5 완료) | 개발 명령어(설치, .env, 앱 실행, 테스트 전체·하나, 평가 3종)와 코드 구조(한 문항 흐름, 모듈별 규칙: 판정은 rules/, LLM은 invoke_llm만, 프롬프트 version, HITL 재실행 주의, fake_llm fixture, 커밋 제외 목록)로 다시 씀. 문서의 명령 실제 실행 확인 | Phase 6 트레이스·가드레일 (사용자 결정 필요) |
| 2026-11-05 | Phase 6: 트레이스 (로컬 JSONL) | 사용자 결정: 로컬 JSONL, 메타데이터+출력(입력·답변 원문 제외), 보존 제한 없음. `trace.py`(TraceRecorder·install·uninstall·read_traces, 시도 1번 = 한 줄, 잠금, 기록 실패는 경고만). `llm.py`에 `error_call_hooks` 추가(실패 시도도 기록, 예외 삼킴), 훅 metadata에 `elapsed_ms`. `TRACE_FILE`(기본 logs/traces.jsonl, off로 끔), app.py에서 설치, E2E는 evals/results에 따로. conftest에 훅 목록 복원 fixture. SERVICE §2·§8·§9·§11·§13 반영. `tests/test_trace.py` 13개, 전체 434개 통과 | 출력 가드레일 post 훅 |
| 2026-11-05 | Phase 6: 출력 가드레일 post 훅 | 사용자 결정: 주제 이탈은 키워드 자기검증(추가 LLM 호출 없음), 위반 시 다음 모델로 폴백. `guardrails.py`(after 훅 맨 앞): interviewer는 `topic_keywords` 중 일반 단어 아닌 것이 질문에 있는지(구는 모든 단어, 4글자 이상 앞부분 일치), feedback은 corrected·대체 문장 한글 없음, reason 한국어, 번역 누락·번역에 한글 남음(`needs_translation` 메타데이터). interviewer 스키마에 `topic_keywords`(1~3, 영어) 추가, 프롬프트 interviewer@2. app.py에서 설치. 테스트 `tests/test_guardrails.py` 31개 + 스키마 2개, 전체 467개 통과. 실제 Bedrock E2E 13/13 통과(위반 0건, 트레이스로 키워드·스로틀링 재시도 확인) | Bedrock Guardrails 적용 여부 결정 |
