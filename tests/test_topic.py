"""rules/topic.py 테스트 (PRD F-03, 주제별 번갈아 배정)."""

import pytest

from fixtures.survey_items import SURVEY_ITEMS, valid_answers
from opic.rules.topic import SESSION_ITEMS, assign_topics, selected_by_topic


def test_doc_example_interleaves_topics_without_repeat():
    answers = {
        "job-1": ["사업/회사"], "home-1": ["홀로 거주"],
        "leisure-1": ["영화 보기", "공연 보기", "콘서트 보기", "카페 가기"], "sport-1": ["조깅"],
    }
    assert assign_topics(SURVEY_ITEMS, answers) == ["영화 보기", "조깅", "공연 보기", "콘서트 보기", "카페 가기"]


def test_one_option_per_topic_rotates():
    assert assign_topics(SURVEY_ITEMS, valid_answers()) == ["영화 보기", "독서", "조깅", "영화 보기", "독서"]


def test_repeats_only_after_all_options_used():
    answers = {"job-1": ["군복무"], "home-1": ["홀로 거주"], "leisure-1": ["영화 보기"], "sport-1": ["조깅"]}
    assert assign_topics(SURVEY_ITEMS, answers) == ["영화 보기", "조깅", "영화 보기", "조깅", "영화 보기"]


def test_single_selection_fills_all_items():
    answers = {"job-1": ["군복무"], "home-1": ["홀로 거주"], "sport-1": ["수영"]}
    assert assign_topics(SURVEY_ITEMS, answers) == ["수영"] * 5


def test_profile_items_are_never_assigned():
    plan = assign_topics(SURVEY_ITEMS, valid_answers())
    assert not {"사업/회사", "홀로 거주"} & set(plan)


def test_order_follows_survey_not_selection_order():
    a = valid_answers(**{"sport-1": ["수영", "조깅"]})
    b = valid_answers(**{"sport-1": ["조깅", "수영"]})
    assert assign_topics(SURVEY_ITEMS, a) == assign_topics(SURVEY_ITEMS, b)
    assert selected_by_topic(SURVEY_ITEMS, a)["운동"] == ["조깅", "수영"]


def test_many_selections_spread_across_topics():
    answers = valid_answers(
        **{"leisure-1": ["영화 보기", "공연 보기", "콘서트 보기", "카페 가기"], "hobby-1": ["독서"], "sport-1": ["조깅"]}
    )
    plan = assign_topics(SURVEY_ITEMS, answers)
    assert plan[:3] == ["영화 보기", "독서", "조깅"]  # 첫 바퀴에 모든 주제가 한 번씩
    assert len(set(plan)) == 5  # 보기가 충분하면 반복 없음


def test_unknown_labels_and_duplicates_are_ignored():
    answers = valid_answers(**{"sport-1": ["조깅", "조깅", "없는 운동"]})
    assert selected_by_topic(SURVEY_ITEMS, answers)["운동"] == ["조깅"]


def test_custom_n():
    assert assign_topics(SURVEY_ITEMS, valid_answers(), n=2) == ["영화 보기", "독서"]
    assert SESSION_ITEMS == 5


@pytest.mark.parametrize(
    "answers",
    [{}, {"job-1": ["군복무"], "home-1": ["홀로 거주"]}, {"leisure-1": []}],
)
def test_no_topic_selection_raises(answers):
    with pytest.raises(ValueError):
        assign_topics(SURVEY_ITEMS, answers)


def test_invalid_n_raises():
    with pytest.raises(ValueError):
        assign_topics(SURVEY_ITEMS, valid_answers(), n=0)


def test_deterministic():
    answers = valid_answers(**{"leisure-1": ["카페 가기", "영화 보기"]})
    assert all(assign_topics(SURVEY_ITEMS, answers) == assign_topics(SURVEY_ITEMS, answers) for _ in range(10))
