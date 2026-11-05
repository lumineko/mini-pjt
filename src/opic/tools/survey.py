"""설문 파일 파싱과 대체 주제 선택 (PRD F-01 / SERVICE §10 opic_survey.md 파싱 규칙).

파싱 규칙:
- `## 주제` 아래 `- 질문: 보기 | 보기`. 질문과 보기는 첫 번째 `": "`로 나눈다.
- `## [프로필] X`는 kind=profile(주제 이름 X), 나머지 `##`는 kind=topic.
- 보기 끝의 `★` 개수를 recommend(0~3, 넘으면 3)로 저장하고 label에서는 ★를 뗀다.
- `>`로 시작하는 줄은 안내문(survey_notice). 여러 줄이면 줄바꿈으로 잇는다.
- `<!-- -->` 주석(여러 줄 포함)과 `#` 제목은 무시한다.
- 보기가 없거나 형식이 틀린 줄, 첫 `##` 이전의 문항 줄은 건너뛴다. 빈 보기·중복 보기는 뺀다.
- 파일이 없거나 비었거나 topic 문항이 0개면 None → survey_agent가 fallback으로 넘어간다.

문항 id는 `{주제}-{주제 안 순번}` (예: "직업-1", "운동-1")으로, 같은 파일이면 항상 같다.
"""

import json
import logging
import random
import re
from pathlib import Path
from typing import TypedDict

from opic.config import DATA_DIR
from opic.state import SurveyItem, SurveyKind, SurveyOption

logger = logging.getLogger(__name__)

MAX_RECOMMEND = 3
_PROFILE_PREFIX = "[프로필]"
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_STARS = re.compile(r"★+$")


class ParsedSurvey(TypedDict):
    items: list[SurveyItem]
    notice: str | None


def _parse_option(raw: str) -> SurveyOption | None:
    raw = raw.strip()
    m = _STARS.search(raw)
    stars = len(m.group()) if m else 0
    label = raw[: m.start()].strip() if m else raw
    if not label:
        return None
    return SurveyOption(label=label, recommend=min(stars, MAX_RECOMMEND))


def _parse_heading(line: str) -> tuple[str, SurveyKind] | None:
    name = line[3:].strip()
    kind: SurveyKind = "topic"
    if name.startswith(_PROFILE_PREFIX):
        name = name[len(_PROFILE_PREFIX):].strip()
        kind = "profile"
    return (name, kind) if name else None


def parse_survey(text: str) -> ParsedSurvey:
    """설문 텍스트를 문항 목록과 안내문으로 바꾼다 (topic 0개 여부는 판단하지 않음)."""
    text = _COMMENT.sub("", text)
    items: list[SurveyItem] = []
    notices: list[str] = []
    current: tuple[str, SurveyKind] | None = None
    counts: dict[str, int] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            notice = line.lstrip(">").strip()
            if notice:
                notices.append(notice)
        elif line.startswith("## "):
            current = _parse_heading(line)
        elif line.startswith("#"):
            continue  # 다른 수준의 제목은 무시
        elif line.startswith("- ") and current is not None:
            question, sep, rest = line[2:].partition(": ")
            question = question.strip()
            if not sep or not question:
                logger.debug("설문 줄 건너뜀(형식): %s", line)
                continue
            options: list[SurveyOption] = []
            for part in rest.split("|"):
                option = _parse_option(part)
                if option and all(o["label"] != option["label"] for o in options):
                    options.append(option)
            if not options:
                logger.debug("설문 줄 건너뜀(보기 없음): %s", line)
                continue
            topic, kind = current
            counts[topic] = counts.get(topic, 0) + 1
            items.append(
                SurveyItem(id=f"{topic}-{counts[topic]}", topic=topic, kind=kind, question=question, options=options)
            )

    return ParsedSurvey(items=items, notice="\n".join(notices) or None)


def load_survey_file(path: Path) -> ParsedSurvey | None:
    """설문 파일을 읽는다. 없거나 비었거나 topic 문항이 0개면 None(fallback)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        logger.info("설문 파일 없음 → fallback: %s", path)
        return None
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("설문 파일을 읽지 못함 → fallback: %s (%s)", path, exc)
        return None

    parsed = parse_survey(text)
    if not any(item["kind"] == "topic" for item in parsed["items"]):
        logger.info("설문 파일에 topic 문항 없음 → fallback: %s", path)
        return None
    return parsed


def load_default_topics(path: Path = DATA_DIR / "default_topics.json") -> list[str]:
    topics = json.loads(path.read_text(encoding="utf-8"))
    if not topics:
        raise ValueError(f"기본 주제가 비어 있습니다: {path}")
    return topics


def pick_default_topic(rng: random.Random | None = None, topics: list[str] | None = None) -> str:
    """fallback 설문에 쓸 기본 주제 1개를 무작위로 고른다 (테스트는 rng를 고정해서 넘긴다)."""
    topics = topics if topics is not None else load_default_topics()
    return (rng or random).choice(topics)
