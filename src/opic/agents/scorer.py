"""Scorer Agent (PRD F-05, F-13 / SERVICE §3 scorer_agent, §14.2 평가 규약).

- LLM은 루브릭 항목별 1~5 정수 점수만 낸다. 등급·감점·상한은 rules.scoring(파이썬)이 계산한다.
- 영어 부분만 평가하고 한글 구간은 무시하도록 프롬프트에 명시한다(한글 감점은 한 번만).
- 답변은 wrap_answer로 <answer> 태그에 격리한다.
"""

import json

from pydantic import BaseModel, Field, create_model

from opic.agents import build_messages, call_metadata
from opic.llm import invoke_llm
from opic.prompts import load_prompt, wrap_answer
from opic.rules.scoring import load_rubric
from opic.state import KoreanSpan, Level

PROMPT = load_prompt("scorer")
PROMPT_ID = PROMPT.id
PROMPT_VERSION = PROMPT.version


def scores_schema(rubric: dict) -> type[BaseModel]:
    lo, hi = rubric["scale"]["min"], rubric["scale"]["max"]
    fields = {
        item["key"]: (int, Field(ge=lo, le=hi, description=f"{item.get('label', item['key'])}: {item.get('description', '')}"))
        for item in rubric["items"]
    }
    return create_model("RubricScores", **fields)


def format_rubric(rubric: dict) -> str:
    return "\n".join(
        f"- {item['key']} ({item.get('label', '')}): {item.get('description', '')}" for item in rubric["items"]
    )


def format_spans(spans: list[KoreanSpan]) -> str:
    return json.dumps([s["text"] for s in spans], ensure_ascii=False) if spans else "(none)"


def score_answer(
    question: str,
    level: Level,
    answer: str,
    korean_spans: list[KoreanSpan],
    *,
    rubric: dict | None = None,
    metadata: dict | None = None,
) -> dict[str, int]:
    """평가 규약 함수 (evals/run_scorer_eval.py). rubric 항목 key별 1~5 정수."""
    rubric = rubric or load_rubric()
    out = invoke_llm(
        "scorer",
        build_messages(
            PROMPT,
            level=level,
            rubric=format_rubric(rubric),
            question=question,
            korean_spans=format_spans(korean_spans),
            answer=wrap_answer(answer),
        ),
        schema=scores_schema(rubric),
        metadata={"node": "scorer_agent", "prompt": PROMPT.ref, **(metadata or {})},
    )
    return {item["key"]: int(getattr(out, item["key"])) for item in rubric["items"]}


def run(state) -> dict:
    pending = state["pending"]
    scores = score_answer(
        state["current_question"],
        state["current_level"],
        state["current_answer"],
        pending["korean_spans"],
        metadata=call_metadata(state, "scorer_agent", PROMPT),
    )
    return {"pending": {**pending, "rubric_scores": scores}}
