"""data/*.json 초안의 형식·일관성 검사 (값이 조정돼도 깨지면 안 되는 규칙만 확인)."""

import json

import pytest

from opic.config import DATA_DIR

LEVELS = ["IL", "IM", "IH", "AL"]


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def test_default_topics():
    topics = _load("default_topics.json")
    assert topics == ["직업", "거주지", "여가활동", "취미/관심사", "운동", "휴가/출장"]


def test_levels_order_and_keys():
    data = _load("levels.json")
    assert data["order"] == LEVELS
    assert list(data["levels"]) == LEVELS


@pytest.mark.parametrize("level", LEVELS)
def test_each_level_has_types_and_guide(level):
    entry = _load("levels.json")["levels"][level]
    assert len(entry["question_types"]) >= 2  # "이전 유형과 겹치지 않게" 규칙이 항상 가능하도록
    assert len(set(entry["question_types"])) == len(entry["question_types"])
    assert entry["guide"].strip()


def test_levels_question_types_are_cumulative():
    levels = _load("levels.json")["levels"]
    for lower, upper in zip(LEVELS, LEVELS[1:]):
        assert set(levels[lower]["question_types"]) <= set(levels[upper]["question_types"])


def test_rubric_weights_and_scale():
    rubric = _load("rubric.json")
    assert sum(i["weight"] for i in rubric["items"]) == pytest.approx(1.0)
    assert len({i["key"] for i in rubric["items"]}) == len(rubric["items"])
    assert rubric["scale"] == {"min": 1, "max": 5}


def test_rubric_grade_bands_descending_within_scale():
    rubric = _load("rubric.json")
    bands = rubric["grade_bands"]
    assert [b["grade"] for b in bands] == list(reversed(LEVELS))
    mins = [b["min"] for b in bands]
    assert mins == sorted(mins, reverse=True)
    assert all(rubric["scale"]["min"] <= m <= rubric["scale"]["max"] for m in mins)


def test_rubric_rules():
    rubric = _load("rubric.json")
    assert rubric["below_lowest"] == "IL 미달"
    assert rubric["grade_cap_offset"] == 1
    assert rubric["korean"]["penalty_per_10pct"] >= 0
    assert 0 < rubric["korean"]["fail_threshold"] <= 1
    assert rubric["min_words"] >= 1
