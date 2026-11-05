"""난이도 점검·조정 규칙 (PRD F-12 / SERVICE §3 check_difficulty, apply_level). 순수 함수.

- 3문항 최종 등급(상한 적용 후)의 평균 등급(rules.scoring.average_grade)을 현재 목표 레벨과 비교한다.
- 같으면 제안 없음. 높으면 up, 낮거나 "IL 미달"이면 down.
- 차이가 두 단계 이상이어도 **항상 한 단계만** 제안한다.
- AL에서 up, IL에서 down은 제안하지 않는다.
- 세션당 1회인지, 3문항 뒤인지는 그래프(routing, difficulty_checked)가 지킨다.
"""

from collections.abc import Sequence

from opic.rules.scoring import average_grade, grade_ordinal, level_ordinal
from opic.state import LEVELS, AdjustProposal, Grade, Level, LevelChange

CHECK_AFTER_ITEMS = 3


def propose_adjustment(grades: Sequence[Grade], current_level: Level) -> AdjustProposal | None:
    """평균 등급과 목표 레벨을 비교해 한 단계 조정 제안을 만든다. 조정할 필요가 없으면 None."""
    if len(grades) != CHECK_AFTER_ITEMS:
        raise ValueError(f"난이도 점검은 {CHECK_AFTER_ITEMS}문항 등급으로 합니다: {len(grades)}개 받음")

    avg = grade_ordinal(average_grade(grades))
    target = level_ordinal(current_level)
    index = LEVELS.index(current_level)

    if avg > target and index < len(LEVELS) - 1:
        return AdjustProposal(direction="up", suggested_level=LEVELS[index + 1])
    if avg < target and index > 0:
        return AdjustProposal(direction="down", suggested_level=LEVELS[index - 1])
    return None


def apply_adjustment(
    current_level: Level, proposal: AdjustProposal, after_item: int
) -> tuple[Level, LevelChange]:
    """수락된 제안을 적용한다. 새 레벨과 level_history에 넣을 기록을 돌려준다."""
    step = 1 if proposal["direction"] == "up" else -1
    expected = LEVELS.index(current_level) + step
    if not 0 <= expected < len(LEVELS) or LEVELS[expected] != proposal["suggested_level"]:
        raise ValueError(f"현재 레벨 {current_level}에 맞지 않는 제안입니다: {proposal}")

    new_level = proposal["suggested_level"]
    change: LevelChange = {"after_item": after_item, "from": current_level, "to": new_level}
    return new_level, change
