"""채점 판정 규칙 (PRD F-05, F-11, F-13 / SERVICE §10 rubric.json). LLM 없이 동작하는 순수 함수.

흐름: 루브릭 항목 점수(LLM) → 가중 합산 → 한글 감점 → 등급 구간 → 출제 레벨 +1 상한 → 달성 여부.

- 점수 계산값은 소수 둘째 자리로 반올림한 뒤 등급 구간과 비교한다.
  (부동소수 오차로 3.7이 3.6999…가 되어 한 등급 낮게 나오는 일을 막는다)
- 한글 비율이 임계값(fail_threshold) 이상이면 점수와 상관없이 "IL 미달"이다.
- 평균 등급은 순서값(IL 미달=0 … AL=4)의 평균을 반올림한다. .5는 올린다.
"""

import json
import math
from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from opic.config import DATA_DIR
from opic.state import GRADES, LEVELS, Grade, Grading, Level

Rubric = Mapping[str, Any]
_DECIMALS = 2


def load_rubric(path: Path = DATA_DIR / "rubric.json") -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _round(value: float) -> float:
    return round(value, _DECIMALS)


# ── 순서값 ─────────────────────────────────────────────────────────
def grade_ordinal(grade: Grade) -> int:
    """IL 미달=0, IL=1, IM=2, IH=3, AL=4."""
    if grade not in GRADES:
        raise ValueError(f"알 수 없는 등급: {grade!r}")
    return GRADES.index(grade)


def level_ordinal(level: Level) -> int:
    """레벨을 등급 순서값으로 (IL=1 … AL=4)."""
    if level not in LEVELS:
        raise ValueError(f"알 수 없는 레벨: {level!r}")
    return GRADES.index(level)


# ── 점수 계산 ──────────────────────────────────────────────────────
def weighted_score(scores: Mapping[str, int], rubric: Rubric) -> float:
    """항목 점수 × 가중치의 합. 항목이 빠지거나 남거나 척도를 벗어나면 ValueError."""
    keys = [item["key"] for item in rubric["items"]]
    if set(scores) != set(keys):
        raise ValueError(f"루브릭 항목이 맞지 않습니다: 기대 {sorted(keys)}, 받음 {sorted(scores)}")

    lo, hi = rubric["scale"]["min"], rubric["scale"]["max"]
    for key, value in scores.items():
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            raise ValueError(f"{key} 점수는 {lo}~{hi} 정수여야 합니다: {value!r}")

    return _round(sum(scores[item["key"]] * item["weight"] for item in rubric["items"]))


def _check_ratio(korean_ratio: float) -> None:
    if not (isinstance(korean_ratio, (int, float)) and math.isfinite(korean_ratio) and 0 <= korean_ratio <= 1):
        raise ValueError(f"한글 비율은 0~1 이어야 합니다: {korean_ratio!r}")


def korean_penalty(korean_ratio: float, rubric: Rubric) -> float:
    """한글 비율 10%당 penalty_per_10pct 감점 (비율에 비례, 구간 없이 연속)."""
    _check_ratio(korean_ratio)
    return _round(korean_ratio * 10 * rubric["korean"]["penalty_per_10pct"])


def is_korean_fail(korean_ratio: float, rubric: Rubric) -> bool:
    """한글 비율이 임계값 이상이면 True ("IL 미달" 강제)."""
    _check_ratio(korean_ratio)
    return korean_ratio >= rubric["korean"]["fail_threshold"]


# ── 등급 ───────────────────────────────────────────────────────────
def grade_from_score(score: float, rubric: Rubric) -> Grade:
    """등급 구간을 위에서부터 보고 처음으로 min 이상인 등급. 모두 미달이면 "IL 미달"."""
    score = _round(score)
    for band in sorted(rubric["grade_bands"], key=lambda b: b["min"], reverse=True):
        if score >= band["min"]:
            return band["grade"]
    return rubric["below_lowest"]


def grade_cap(level: Level, rubric: Rubric) -> Grade:
    """출제 레벨 + grade_cap_offset 단계 (AL을 넘지 않음)."""
    index = min(LEVELS.index(level) + rubric["grade_cap_offset"], len(LEVELS) - 1)
    return LEVELS[index]


def apply_cap(grade: Grade, level: Level, rubric: Rubric) -> Grade:
    cap = grade_cap(level, rubric)
    return grade if grade_ordinal(grade) <= grade_ordinal(cap) else cap


def is_achieved(grade: Grade, target_level: Level) -> bool:
    return grade_ordinal(grade) >= level_ordinal(target_level)


def grade_answer(
    scores: Mapping[str, int],
    korean_ratio: float,
    level: Level,
    rubric: Rubric,
) -> Grading:
    """score_and_grade 노드의 계산 전체. level은 출제 레벨이자 목표 레벨(PRD F-02)."""
    weighted = weighted_score(scores, rubric)
    penalty = korean_penalty(korean_ratio, rubric)
    final = _round(weighted - penalty)

    raw = rubric["below_lowest"] if is_korean_fail(korean_ratio, rubric) else grade_from_score(final, rubric)
    grade = apply_cap(raw, level, rubric)
    return Grading(
        weighted_score=weighted,
        penalty=penalty,
        final_score=final,
        raw_grade=raw,
        grade=grade,
        achieved=is_achieved(grade, level),
    )


# ── 평균 등급 ──────────────────────────────────────────────────────
def average_grade(grades: Iterable[Grade]) -> Grade:
    """순서값 평균을 반올림(.5는 올림)한 등급 (PRD F-11, F-12)."""
    ordinals = [grade_ordinal(g) for g in grades]
    if not ordinals:
        raise ValueError("평균을 낼 등급이 없습니다")
    mean = Decimal(sum(ordinals)) / Decimal(len(ordinals))
    return GRADES[int(mean.quantize(Decimal(1), rounding=ROUND_HALF_UP))]
