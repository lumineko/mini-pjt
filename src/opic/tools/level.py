"""레벨별 출제 지침과 이전 질문 조회 (SERVICE §3 interviewer_agent의 도구).

- `get_level_guide(level)`: levels.json의 질문 유형 후보와 guide.
- `get_previous_questions(state)`: 이번 세션에서 이미 낸 질문·유형·주제 (중복 출제 방지용).
LLM 도구 바인딩은 Phase 3 에이전트에서 이 함수들을 감싸서 한다.
"""

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

from opic.config import DATA_DIR
from opic.state import LEVELS, Level

_LEVELS_FILE = DATA_DIR / "levels.json"


class LevelGuide(TypedDict):
    level: Level
    question_types: list[str]
    guide: str


class PreviousQuestion(TypedDict):
    question: str
    question_type: str
    topic: str
    level: Level


@lru_cache(maxsize=4)
def load_levels(path: Path = _LEVELS_FILE) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if list(data.get("order", [])) != list(LEVELS):
        raise ValueError(f"levels.json의 order가 {LEVELS}와 다릅니다: {data.get('order')}")
    return data


def get_level_guide(level: Level, path: Path = _LEVELS_FILE) -> LevelGuide:
    if level not in LEVELS:
        raise ValueError(f"알 수 없는 레벨: {level!r}")
    entry = load_levels(path)["levels"][level]
    return LevelGuide(level=level, question_types=list(entry["question_types"]), guide=entry["guide"])


def get_previous_questions(state: Mapping[str, Any]) -> list[PreviousQuestion]:
    """완료 문항(items) 순서대로. 아직 채점 중인 현재 질문은 포함하지 않는다."""
    return [
        PreviousQuestion(
            question=item["question"],
            question_type=item["question_type"],
            topic=item["topic"],
            level=item["level"],
        )
        for item in state.get("items", [])
    ]
