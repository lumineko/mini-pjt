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

# 개발 명령어 / 코드 구조
아직 코드가 없다. 프로젝트 스캐폴딩 후 실행·테스트 명령과 구조를 여기에 추가한다.

예정 구조 (상세는 SERVICE.md §2, §9):
- `src/opic/` — `app.py`(Streamlit), `graph.py`, `supervisor.py`(LLM 슈퍼바이저 + Python guard), `agents/`, `tools/`, `rules/`(순수 함수 판정 로직), `llm.py`(Bedrock 폴백)
- `data/` — `levels.json`, `rubric.json`, `default_topics.json`, `history/`(세션 JSON)
- 판정 로직(`rules/`)은 LLM 없이 단위 테스트 가능해야 한다.
