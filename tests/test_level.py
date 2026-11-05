"""tools/level.py 테스트."""

import json

import pytest

from fixtures.sessions import make_item
from opic.state import new_session_state
from opic.tools.level import get_level_guide, get_previous_questions, load_levels


@pytest.mark.parametrize("level", ["IL", "IM", "IH", "AL"])
def test_get_level_guide_from_real_file(level):
    g = get_level_guide(level)
    assert g["level"] == level
    assert len(g["question_types"]) >= 2 and g["guide"].strip()


def test_guide_types_match_file():
    data = load_levels()
    assert get_level_guide("IH")["question_types"] == data["levels"]["IH"]["question_types"]


def test_returned_list_is_a_copy():
    g = get_level_guide("IM")
    g["question_types"].append("변경")
    assert "변경" not in get_level_guide("IM")["question_types"]


@pytest.mark.parametrize("level", ["NH", "", None, "IL 미달"])
def test_unknown_level(level):
    with pytest.raises(ValueError):
        get_level_guide(level)


def test_wrong_order_in_file_is_rejected(tmp_path):
    path = tmp_path / "levels.json"
    path.write_text(json.dumps({"order": ["IM", "IL"], "levels": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        get_level_guide("IM", path)


def test_previous_questions_from_items():
    state = new_session_state("s", "t")
    assert get_previous_questions(state) == []
    state["items"] = [make_item(1, topic="영화 보기", question_type="습관"), make_item(2, level="IH")]
    state["current_question"] = "Current question not yet graded?"
    assert get_previous_questions(state) == [
        {"question": "Question 1?", "question_type": "습관", "topic": "영화 보기", "level": "IM"},
        {"question": "Question 2?", "question_type": "묘사", "topic": "조깅", "level": "IH"},
    ]
