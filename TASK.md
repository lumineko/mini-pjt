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
- [ ] 디렉터리 구조 + `requirements.txt` (streamlit, langgraph, langchain-aws, python-dotenv, pytest — 승인됨)
- [ ] `.env.example` + `config.py` 설정 로더
- [ ] 데이터 초안: `data/default_topics.json`, `data/levels.json`, `data/rubric.json`
- [ ] `state.py` 타입 정의

### Phase 2. 규칙·도구 (Python, 테스트 우선)
- [ ] `rules/scoring.py` + `tests/test_scoring.py` (가중 합산, 한글 감점, 등급, IL 미달)
- [ ] `tools/korean.py` + `tests/test_korean.py`
- [ ] `rules/difficulty.py` + `tests/test_difficulty.py` (AL/IL 경계 포함)
- [ ] `rules/topic.py` + `tests/test_topic.py`, `rules/validation.py` + `tests/test_validation.py`
- [ ] `rules/summary.py`
- [ ] `tools/survey.py` + `tests/test_survey.py` (파싱, [프로필]/★/안내문 처리, fallback 조건)
- [ ] `tools/level.py`, `storage.py`

### Phase 3. LLM·에이전트
- [ ] `llm.py` Bedrock 클라이언트 + 용도별 모델 매핑 + 재시도·폴백
- [ ] `prompts/` 5종
- [ ] `agents/` survey, interviewer, scorer, feedback

### Phase 4. 그래프
- [ ] `supervisor.py` guard_router + supervisor + 검증 + `tests/test_guard.py`
- [ ] `graph.py` 조립, HITL interrupt, `start_session`/`resume`/`get_state`
- [ ] `tests/test_graph_flow.py` (fake LLM으로 5문항, 3문항 점검, 조정 흐름)

### Phase 5. UI·마무리
- [ ] `app.py` Streamlit (설문, 레벨, 문항·피드백, 조정 확인, 요약, 기록)
- [ ] 실제 Bedrock으로 E2E 확인 (PRD 성공 기준 1~9)
- [ ] CLAUDE.md 실행·테스트 명령 갱신

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
