# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 작업 규칙
- 무엇을 만드는지 기획은 PRD.md, 아키텍처는 SERVICE.md가 기준이다. 애매하면 추측하지 말고 물어본다.
- 스택: Python, LangGraph, Bedrock (기본 global.anthropic.claude-sonnet-4-5-20250929-v1:0, 폴백 global.anthropic.claude-haiku-4-5-20251001-v1:0) -> 필요 시 모델은 조정해서 사용하거나 복수의 모델을 상황에 맞춰 변경하여 중단없이 쓸 수 있게 한다.
- 괜찮은 레퍼런스 코드를 깃허브에서 찾아서 레퍼런스로 삼거나 (있을 경우) 현재 ref 폴더 내 코드를 참조한다. 절대 사용자의 허락없이 신규 프레임워크 또는 라이브러리를 들이지 않는다.
- 한 번에 TASK.md의 작업 하나만 한다.
- 계산, 규칙 판정은 LLM이 아니라 파이썬 코드로 하는 원칙으로 진행한다. 필요시 LLM 판정부분을 덧붙여 추가한다.
- API 키는 .env에서 읽는다.

# 문서 구조
- `PRD.md` — 기능 목표, 사용자 시나리오, 요구사항, 범위 (무엇을)
- `SERVICE.md` — 모듈 구성, LangGraph 그래프, API, 데이터 흐름, 외부 연동, 모델 폴백 전략 (어떻게)
- `TASK.md` — 작업 체크리스트와 작업 로그. 세션 시작 시 "현재 진행 중"과 마지막 로그를 먼저 확인하고, 작업 완료 시 체크 및 로그를 갱신한다.
- `opic_survey.md` — 설문 원본 데이터 (링커리어 2026 정리 글 기반, 비공식). 형식은 SERVICE.md §10
- `evals/` — 실제 모델로 채점 품질을 재는 평가 세트·스크립트 (SERVICE.md §14.2, 수동 실행)

# 개발 명령어
Phase 0~5 구현 완료. Phase 6(트레이스·가드레일)만 남아 있다.

- 설치 (Python 3.14): `python -m venv .venv` → `.venv\Scripts\python -m pip install -r requirements.txt`
- 자격 증명: `.env.example`을 `.env`로 복사해 AWS 액세스 키 **또는** `AWS_PROFILE` 중 하나와 `AWS_REGION`을 채운다. 키가 필요한 것은 앱 실행·`evals/`뿐이고, pytest는 키 없이 돈다.
- 앱 실행: `.venv\Scripts\python -m streamlit run src/opic/app.py`
- 테스트 전체: `.venv\Scripts\python -m pytest -q` (`pytest.ini`: `testpaths=tests`, `pythonpath=src`, 실제 LLM 호출 없음)
- 테스트 하나만: `.venv\Scripts\python -m pytest tests/test_graph_flow.py::test_adjust_up_accepted_changes_level_for_items_4_and_5 -q`
- 평가(`evals/`)는 실제 Bedrock을 호출하므로(비용 발생) pytest와 별도로 수동 실행한다. 결과는 `evals/results/`(커밋 제외).
  - 채점 평가: `.venv\Scripts\python evals\run_scorer_eval.py` (키 없이 흐름만 확인: `--fake`, 일부만: `--only s001,s013`)
  - 평가 세트 재생성(검수 반영 후): `.venv\Scripts\python evals\scorer\build_golden.py`
  - 화면 경로 E2E(5문항 세션·폴백·대체 설문): `.venv\Scripts\python evals\run_e2e.py`

# 코드 구조 (상세는 SERVICE.md §2, §3, §9)
흐름: `app.py`(Streamlit) → `graph.py` API(`start_session`/`resume`/`retry`) → LangGraph 고정 순서 워크플로.
한 문항: `interviewer_agent` → `await_answer`(HITL) → `scorer_agent` → `score_and_grade`(Py) → `feedback_agent` → `record_item`(Py) → `show_feedback`(HITL). 분기 5곳은 `routing.py`의 파이썬 함수가 정한다(슈퍼바이저 없음).

- `src/opic/rules/` — 등급·감점·상한·난이도·주제 배정·검증·요약. LLM 없는 순수 함수이며, 판정은 반드시 여기서 한다.
- `src/opic/tools/` — 한글 감지(`korean.py`, 단어 기준 비율), 설문 파싱(`survey.py`), 레벨 지침(`level.py`).
- `src/opic/agents/` — LLM 에이전트 4종. 순수 함수(예: `score_answer`) + 노드 `run(state)` 2층 구조. 출력은 동적 Pydantic 스키마로 검증한다.
- `src/opic/llm.py` — **모든 LLM 호출의 단일 진입점** `invoke_llm`(재시도·폴백·메타데이터·훅). Bedrock을 다른 곳에서 직접 부르지 않는다.
- `src/opic/prompts/*.md` — `id`/`version` 머리말 + `[system]`/`[user]`. 프롬프트를 바꾸면 version을 올리고 채점 평가를 다시 돌린다.
- `src/opic/graph.py` — 노드·엣지 조립과 API. HITL 노드는 재개할 때 처음부터 다시 실행되므로 interrupt 앞에 부작용을 두지 않고, 입력 처리는 `apply_*` 순수 함수에 둔다.
- `src/opic/state.py` — State 타입·상수(`LEVELS`, `GRADES`(인덱스=순서값), `SESSION_ITEMS`). `config.py` — `.env` 설정, `storage.py` — 완료 세션 JSON 저장.
- `data/` — `levels.json`(레벨별 유형·지침), `rubric.json`(가중치·등급 구간·한글 감점·최소 단어), `default_topics.json`, `history/`(세션 JSON).
- 테스트는 `tests/conftest.py`의 `fake_llm` fixture(`llm.set_model_factory`로 가짜 모델 주입, 응답 큐·호출 기록)를 쓴다. 공용 샘플은 `tests/fixtures/`.
- `.env`, `data/history/`, `logs/`, `evals/results/`, `PRD_SERVICE.md`, `graph.png`는 커밋하지 않는다(`.gitignore`).
