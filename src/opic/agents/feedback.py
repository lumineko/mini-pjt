"""Feedback Agent (PRD F-06, F-07, F-13 / SERVICE §3 feedback_agent).

- score_and_grade 다음에 실행되어 판정된 등급을 입력으로 받는다(고정 순서, PRD §6).
- corrections(없으면 빈 목록 → UI "교정 사항 없음"), alternatives(1~3개), translation(한글 구간이 있을 때만).
- 한글 구간이 있는데 번역이 비면 검증 실패 → 다음 모델. 한글이 없으면 번역은 None으로 맞춘다.
"""

from pydantic import BaseModel, Field, create_model

from opic.agents import build_messages, call_metadata
from opic.agents.scorer import format_spans
from opic.llm import invoke_llm
from opic.prompts import load_prompt, wrap_answer
from opic.state import Correction, Feedback, Grade, KoreanSpan, Level

PROMPT = load_prompt("feedback")
MAX_CORRECTIONS = 5


class CorrectionModel(BaseModel):
    original: str = Field(min_length=1, description="Learner's original sentence (English)")
    corrected: str = Field(min_length=1, description="Corrected sentence (English)")
    reason: str = Field(min_length=1, description="Why, in Korean")


def feedback_schema(needs_translation: bool) -> type[BaseModel]:
    translation = (
        (str, Field(min_length=1, description="Whole answer with Korean parts translated into English"))
        if needs_translation
        else (str | None, Field(default=None, description="null when there is no Korean"))
    )
    return create_model(
        "FeedbackOutput",
        corrections=(list[CorrectionModel], Field(default_factory=list, max_length=MAX_CORRECTIONS)),
        alternatives=(list[str], Field(min_length=1, max_length=3, description="Better English sentences")),
        translation=translation,
    )


def generate_feedback(
    question: str,
    level: Level,
    answer: str,
    grade: Grade,
    achieved: bool,
    korean_spans: list[KoreanSpan],
    *,
    metadata: dict | None = None,
) -> Feedback:
    needs_translation = bool(korean_spans)
    out = invoke_llm(
        "feedback",
        build_messages(
            PROMPT,
            level=level,
            question=question,
            grade=grade,
            achieved="yes" if achieved else "no",
            korean_spans=format_spans(korean_spans),
            answer=wrap_answer(answer),
        ),
        schema=feedback_schema(needs_translation),
        # 출력 가드레일(guardrails.py)용: needs_translation은 번역 누락, guard_answer는 교정 원문이 답변에 있는지 확인
        # (guard_answer는 트레이스에 기록하지 않는다)
        metadata={
            "node": "feedback_agent", "prompt": PROMPT.ref, **(metadata or {}),
            "needs_translation": needs_translation, "guard_answer": answer,
        },
    )
    alternatives = [a.strip() for a in out.alternatives if a.strip()]
    if not alternatives:
        raise ValueError("대체 문장이 비어 있습니다")
    return Feedback(
        corrections=[Correction(original=c.original, corrected=c.corrected, reason=c.reason) for c in out.corrections],
        alternatives=alternatives,
        translation=out.translation.strip() if needs_translation and out.translation else None,
    )


def run(state) -> dict:
    pending = state["pending"]
    grading = pending["grading"]
    feedback = generate_feedback(
        state["current_question"],
        state["current_level"],
        state["current_answer"],
        grading["grade"],
        grading["achieved"],
        pending["korean_spans"],
        metadata=call_metadata(state, "feedback_agent", PROMPT),
    )
    return {"pending": {**pending, "feedback": feedback}}
