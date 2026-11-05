"""LLM 에이전트 4종 (SERVICE §3 노드).

각 모듈은 두 층으로 되어 있다.
- 순수 함수(예: `score_answer`): 입력값 → 결과. 평가 스크립트·테스트가 직접 부른다.
- 노드 함수 `run(state)`: State에서 입력을 꺼내 순수 함수를 부르고, 바뀐 필드만 dict로 돌려준다(Phase 4 그래프가 사용).

LLM 호출은 모두 `opic.llm.invoke_llm`을 거친다(SERVICE §13 #1).
"""

from langchain_core.messages import HumanMessage, SystemMessage

from opic.prompts import Prompt


def build_messages(prompt: Prompt, **values: object) -> list:
    system, user = prompt.render(**values)
    return [SystemMessage(system), HumanMessage(user)]


def call_metadata(state, node: str, prompt: Prompt) -> dict:
    """SERVICE §13 #2 호출 메타데이터."""
    return {
        "session_id": state.get("session_id"),
        "node": node,
        "item_index": len(state.get("items") or []) + 1,
        "prompt": prompt.ref,
    }
