"""rules/validation.py 테스트 (PRD F-01, F-02, F-04)."""

import pytest

from fixtures.survey_items import SURVEY_ITEMS, valid_answers
from opic.rules.validation import validate_answer, validate_level, validate_survey_answers


# ── 답변 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [None, "", "   ", "\n\t"])
def test_empty_answer(text):
    assert validate_answer(text, 5) == "답변을 입력해 주세요."


@pytest.mark.parametrize(
    "text, ok",
    [
        ("I like to go jogging.", True),  # 5단어
        ("I like jogging very", False),  # 4단어
        ("I like jogging ... !!! 123", False),  # 문장부호·숫자는 단어 아님 → 3단어
        ("나는 어제 친구와 영화를 봤다", True),  # 한글 단어도 셈
        ("I went 제주도 last summer", True),
    ],
)
def test_min_words(text, ok):
    assert (validate_answer(text, 5) is None) is ok


def test_min_words_message_shows_counts():
    assert validate_answer("I like jogging", 5) == "답변은 최소 5단어 이상 입력해 주세요. (현재 3단어)"


def test_min_words_from_data_value():
    assert validate_answer("Hi there", 2) is None
    assert validate_answer("Hi", 2) is not None


# ── 레벨 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("level", ["IL", "IM", "IH", "AL"])
def test_valid_level(level):
    assert validate_level(level) is None


@pytest.mark.parametrize("level", [None, "", "NH", "im", "IL 미달"])
def test_invalid_level(level):
    assert validate_level(level) is not None


# ── 설문 ───────────────────────────────────────────────────────────
def test_valid_survey_answers():
    assert validate_survey_answers(SURVEY_ITEMS, valid_answers()) is None


def test_topic_allows_multiple():
    assert validate_survey_answers(SURVEY_ITEMS, valid_answers(**{"sport-1": ["조깅", "수영"]})) is None


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"job-1": []}, "하나만"),  # profile 0개
        ({"job-1": ["사업/회사", "군복무"]}, "하나만"),  # profile 2개
        ({"sport-1": []}, "하나 이상"),  # topic 0개
        ({"sport-1": ["골프"]}, "없는 보기"),
        ({"sport-1": ["조깅", "조깅"]}, "두 번"),
        ({"ghost-1": ["x"]}, "알 수 없는"),
    ],
)
def test_invalid_survey_answers(overrides, fragment):
    message = validate_survey_answers(SURVEY_ITEMS, valid_answers(**overrides))
    assert message is not None and fragment in message


def test_missing_item_answer_is_rejected():
    answers = valid_answers()
    answers.pop("hobby-1")
    assert "하나 이상" in validate_survey_answers(SURVEY_ITEMS, answers)
