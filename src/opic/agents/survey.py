"""Survey Agent (PRD F-01 / SERVICE §3 survey_agent).

- 설문 파일 파싱 결과가 있으면 그대로 쓴다(LLM 호출 없음).
- 없으면 기본 6개 주제 중 1개를 파이썬이 무작위로 고르고, LLM이 그 주제의 선택형 설문 1개를 만든다.
  대체 설문은 직업·거주지가 뽑혀도 kind=topic이다.
"""

import logging
import random

from pydantic import BaseModel, Field, field_validator

from opic.agents import build_messages
from opic.config import load_settings
from opic.llm import invoke_llm
from opic.prompts import load_prompt
from opic.state import SurveyItem, SurveyOption
from opic.tools.survey import load_survey_file, pick_default_topic

logger = logging.getLogger(__name__)
PROMPT = load_prompt("survey")


class SurveyOutput(BaseModel):
    """대체 설문 1문항 (LLM 구조화 출력)."""

    question: str = Field(min_length=2, description="한국어 설문 문항 한 문장")
    options: list[str] = Field(min_length=4, max_length=12, description="한국어 보기 6~10개")

    @field_validator("options")
    @classmethod
    def _clean_options(cls, options: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(o.strip().rstrip("★").strip() for o in options if o.strip()))
        if len(cleaned) < 4:
            raise ValueError("서로 다른 보기가 4개 이상 필요합니다")
        return cleaned


def generate_fallback_survey(topic: str, metadata: dict | None = None) -> SurveyItem:
    out: SurveyOutput = invoke_llm(
        "survey",
        build_messages(PROMPT, topic=topic),
        schema=SurveyOutput,
        metadata={"node": "survey_agent", "prompt": PROMPT.ref, **(metadata or {})},
    )
    return SurveyItem(
        id=f"{topic}-1",
        topic=topic,
        kind="topic",
        question=out.question.strip(),
        options=[SurveyOption(label=label, recommend=0) for label in out.options],
    )


def run(state, rng: random.Random | None = None) -> dict:
    parsed = load_survey_file(load_settings().survey_file)
    if parsed is not None:
        return {"survey_source": "file", "survey_items": parsed["items"], "survey_notice": parsed["notice"]}

    topic = pick_default_topic(rng)
    logger.info("설문 fallback: 기본 주제 '%s'", topic)
    item = generate_fallback_survey(topic, metadata={"session_id": state.get("session_id")})
    return {"survey_source": "fallback", "survey_items": [item], "survey_notice": None}
