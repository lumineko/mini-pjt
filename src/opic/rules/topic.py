"""문항별 주제 배정 (PRD F-03 / SERVICE §3 ask_survey_and_level). 순수 함수, 무작위 없음.

규칙 (2026-11-05 확정: 주제별 번갈아):
- `kind=topic` 문항에서 고른 보기만 쓴다. `kind=profile`(직업·거주지)은 배경 정보라 제외한다.
- 설문 주제(SurveyItem.topic, 예: 여가활동·운동)별로 고른 보기를 모은다.
  주제 순서와 주제 안의 보기 순서는 **설문 파일 순서**를 따른다(선택한 순서와 무관 → 같은 선택이면 같은 배정).
- 주제를 돌아가며 아직 안 쓴 보기를 하나씩 뽑는다. 다 쓴 주제는 건너뛴다.
- 모든 보기를 다 쓰면 처음부터 다시 돈다(고른 보기가 n개보다 적을 때만 반복).

예) 여가 [영화, 공연, 콘서트, 카페], 운동 [조깅] → [영화, 조깅, 공연, 콘서트, 카페]
    여가 [영화], 운동 [조깅] → [영화, 조깅, 영화, 조깅, 영화]
"""

from collections.abc import Mapping, Sequence

from opic.state import SurveyItem

SESSION_ITEMS = 5


def selected_by_topic(
    survey_items: Sequence[SurveyItem], survey_answers: Mapping[str, Sequence[str]]
) -> dict[str, list[str]]:
    """설문 주제별로 고른 보기 목록 (설문 순서, 중복 제거, 보기에 없는 값은 무시)."""
    groups: dict[str, list[str]] = {}
    for item in survey_items:
        if item["kind"] != "topic":
            continue
        chosen = set(survey_answers.get(item["id"], ()))
        bucket = groups.setdefault(item["topic"], [])
        for option in item["options"]:
            if option["label"] in chosen and option["label"] not in bucket:
                bucket.append(option["label"])
    return {topic: labels for topic, labels in groups.items() if labels}


def assign_topics(
    survey_items: Sequence[SurveyItem],
    survey_answers: Mapping[str, Sequence[str]],
    n: int = SESSION_ITEMS,
) -> list[str]:
    """문항 1~n에 배정할 주제(보기 이름) 목록."""
    if n < 1:
        raise ValueError(f"배정할 문항 수는 1 이상이어야 합니다: {n}")
    groups = list(selected_by_topic(survey_items, survey_answers).values())
    if not groups:
        raise ValueError("주제 배정에 쓸 선택이 없습니다 (topic 문항에서 1개 이상 선택 필요)")

    plan: list[str] = []
    while len(plan) < n:
        queues = [list(labels) for labels in groups]  # 한 바퀴(모든 보기 소진)마다 새로 시작
        while any(queues) and len(plan) < n:
            for queue in queues:
                if queue and len(plan) < n:
                    plan.append(queue.pop(0))
    return plan
