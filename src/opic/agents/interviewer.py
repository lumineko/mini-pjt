"""Interviewer Agent (PRD F-03 / SERVICE §3 interviewer_agent).

- 주제는 파이썬이 배정한 것(topic_plan)만 쓴다.
- 질문 유형은 현재 레벨의 후보(levels.json) 안에서 LLM이 고른다. 후보 밖이면 Pydantic 검증 실패 → 다음 모델.
- 질문에 한글이 섞이면 검증 실패로 본다(영어 질문만).
- topic_keywords: 질문 속 주제 단어 1~3개(영어). 출력 가드레일(guardrails.py)이 질문에 실제로 있는지 확인한다.
"""

from typing import Literal

from pydantic import BaseModel, Field, create_model, field_validator

from opic.agents import build_messages, call_metadata
from opic.llm import invoke_llm
from opic.prompts import load_prompt
from opic.state import Level
from opic.tools.korean import detect_korean
from opic.tools.level import PreviousQuestion, get_level_guide, get_previous_questions

PROMPT = load_prompt("interviewer")


class _QuestionBase(BaseModel):
    question: str = Field(min_length=10, description="The question in English")

    @field_validator("question")
    @classmethod
    def _english_only(cls, value: str) -> str:
        if detect_korean(value)["korean_words"]:
            raise ValueError("질문에 한글이 들어 있습니다")
        return value.strip()

    topic_keywords: list[str] = Field(
        min_length=1, max_length=3,
        description="1-3 English words or short phrases, copied from the question, that show the assigned topic",
    )

    @field_validator("topic_keywords")
    @classmethod
    def _keywords_english(cls, value: list[str]) -> list[str]:
        value = [v.strip() for v in value if v.strip()]
        if not value:
            raise ValueError("주제 키워드가 비어 있습니다")
        if any(detect_korean(v)["korean_words"] for v in value):
            raise ValueError("주제 키워드에 한글이 들어 있습니다")
        return value


def question_schema(question_types: list[str]) -> type[BaseModel]:
    """question_type을 후보 목록으로 제한한 스키마."""
    return create_model(
        "InterviewerOutput",
        __base__=_QuestionBase,
        question_type=(Literal[tuple(question_types)], Field(description="One of the allowed question types")),
    )


def format_previous(previous: list[PreviousQuestion]) -> str:
    if not previous:
        return "(none)"
    return "\n".join(f"{i}. [{p['question_type']}] {p['question']} (topic: {p['topic']})" for i, p in enumerate(previous, 1))


def format_profile(state) -> str:
    """profile 문항 응답을 '주제: 보기' 목록으로 (배경 정보)."""
    answers = state.get("survey_answers") or {}
    parts = [
        f"{item['topic']} - {item['question']} {', '.join(answers[item['id']])}"
        for item in state.get("survey_items") or []
        if item["kind"] == "profile" and answers.get(item["id"])
    ]
    return "; ".join(parts) or "(none)"


def generate_question(
    topic: str,
    level: Level,
    previous: list[PreviousQuestion],
    profile: str = "(none)",
    metadata: dict | None = None,
) -> tuple[str, str]:
    guide = get_level_guide(level)
    out = invoke_llm(
        "interviewer",
        build_messages(
            PROMPT,
            level=level,
            level_guide=guide["guide"],
            question_types=", ".join(guide["question_types"]),
            topic=topic,
            profile=profile,
            previous_questions=format_previous(previous),
        ),
        schema=question_schema(guide["question_types"]),
        metadata={"node": "interviewer_agent", "prompt": PROMPT.ref, **(metadata or {})},
    )
    return out.question, out.question_type


def run(state) -> dict:
    index = len(state["items"])
    question, question_type = generate_question(
        topic=state["topic_plan"][index],
        level=state["current_level"],
        previous=get_previous_questions(state),
        profile=format_profile(state),
        metadata=call_metadata(state, "interviewer_agent", PROMPT),
    )
    return {"current_question": question, "current_question_type": question_type}
