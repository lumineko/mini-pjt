"""입력 검증 (PRD F-01, F-02, F-04 / SERVICE §3 ask_survey_and_level, await_answer). 순수 함수.

모든 함수는 통과하면 None, 실패하면 사용자에게 보여 줄 한국어 안내문을 돌려준다.
노드는 이 값을 survey_error / answer_error에 그대로 넣고, UI도 같은 함수로 먼저 막는다(SERVICE §4).
"""

from collections.abc import Mapping, Sequence

from opic.state import LEVELS, SurveyItem
from opic.tools.korean import count_words


def validate_answer(text: str | None, min_words: int) -> str | None:
    """빈 답변·최소 단어 수 미만이면 안내문. 단어는 tools.korean 정의(한글 단어 포함)."""
    if text is None or not text.strip():
        return "답변을 입력해 주세요."
    words = count_words(text)
    if words < min_words:
        return f"답변은 최소 {min_words}단어 이상 입력해 주세요. (현재 {words}단어)"
    return None


def validate_level(level: str | None) -> str | None:
    if level not in LEVELS:
        return f"목표 레벨을 선택해 주세요. ({' / '.join(LEVELS)})"
    return None


def validate_survey_answers(
    survey_items: Sequence[SurveyItem], survey_answers: Mapping[str, Sequence[str]]
) -> str | None:
    """profile 문항은 정확히 1개, topic 문항은 1개 이상, 보기에 있는 값만."""
    known_ids = {item["id"] for item in survey_items}
    unknown = sorted(set(survey_answers) - known_ids)
    if unknown:
        return f"알 수 없는 설문 문항입니다: {', '.join(unknown)}"

    for item in survey_items:
        chosen = list(survey_answers.get(item["id"], ()))
        labels = {option["label"] for option in item["options"]}
        invalid = [c for c in chosen if c not in labels]
        if invalid:
            return f"'{item['question']}'에 없는 보기입니다: {', '.join(invalid)}"
        if len(set(chosen)) != len(chosen):
            return f"'{item['question']}'에서 같은 보기를 두 번 선택했습니다."
        if item["kind"] == "profile" and len(chosen) != 1:
            return f"'{item['question']}'에서 보기를 하나만 선택해 주세요."
        if item["kind"] == "topic" and not chosen:
            return f"'{item['question']}'에서 보기를 하나 이상 선택해 주세요."
    return None
