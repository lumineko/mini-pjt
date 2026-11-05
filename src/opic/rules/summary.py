"""세션 요약 (PRD F-11 / SERVICE §3 summarize). 순수 함수.

- 문항별 최종 등급(상한 적용 후)을 나열하고, 순서값 평균을 반올림한 평균 등급을 낸다(rules.scoring).
- 최종 레벨은 레벨 변경 이력의 마지막 `to`, 이력이 없으면 시작 레벨이다.
"""

from collections.abc import Sequence

from opic.rules.scoring import average_grade
from opic.state import SESSION_ITEMS, ItemResult, Level, LevelChange, SessionSummary


def summarize(
    items: Sequence[ItemResult],
    initial_level: Level,
    level_history: Sequence[LevelChange] = (),
) -> SessionSummary:
    if len(items) != SESSION_ITEMS:
        raise ValueError(f"세션 요약은 {SESSION_ITEMS}문항을 마친 뒤에 합니다: {len(items)}개 받음")

    level = initial_level
    for change in level_history:
        if change["from"] != level:
            raise ValueError(f"레벨 변경 이력이 이어지지 않습니다: {level} → {change}")
        level = change["to"]

    grades = [item["grade"] for item in items]
    return SessionSummary(
        item_grades=grades,
        average_grade=average_grade(grades),
        initial_level=initial_level,
        final_level=level,
        level_changed=level != initial_level,
    )
