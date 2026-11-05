"""state.py 테스트: SERVICE §3 필드와 데이터 파일 상수가 어긋나지 않는지 확인한다."""

import json
import typing

from opic import state
from opic.config import DATA_DIR
from opic.state import GRADES, LEVELS, ItemResult, Pending, SessionState, new_session_state

# SERVICE.md §3 State 표 (순서 포함)
SERVICE_STATE_FIELDS = [
    "session_id", "started_at", "survey_source", "survey_notice", "survey_items",
    "survey_answers", "survey_error", "topic_plan", "initial_level", "current_level",
    "level_history", "current_question", "current_question_type", "current_answer",
    "answer_error", "pending", "items", "difficulty_checked", "adjust_proposal",
    "adjust_response", "adjust_applied", "summary", "done",
]


def test_session_state_fields_match_service_doc():
    assert list(typing.get_type_hints(SessionState)) == SERVICE_STATE_FIELDS


def test_new_session_state_fills_every_field():
    s = new_session_state("sid", "2026-11-05T10:00:00")
    assert list(s) == SERVICE_STATE_FIELDS
    assert s["session_id"] == "sid"
    assert s["items"] == [] and s["pending"] is None and s["done"] is False


def test_new_session_state_lists_are_not_shared():
    a = new_session_state("a", "t")
    b = new_session_state("b", "t")
    a["items"].append({})
    assert b["items"] == []


def test_levels_match_levels_json():
    data = json.loads((DATA_DIR / "levels.json").read_text(encoding="utf-8"))
    assert list(LEVELS) == data["order"]
    assert typing.get_args(state.Level) == LEVELS


def test_grades_ordinal_and_below_lowest_match_rubric():
    rubric = json.loads((DATA_DIR / "rubric.json").read_text(encoding="utf-8"))
    assert GRADES[0] == rubric["below_lowest"]
    assert {g: i for i, g in enumerate(GRADES)} == {"IL 미달": 0, "IL": 1, "IM": 2, "IH": 3, "AL": 4}
    assert typing.get_args(state.Grade) == GRADES


def test_pending_optional_stage_fields():
    assert Pending.__required_keys__ == {"korean_ratio", "korean_spans"}
    assert Pending.__optional_keys__ == {"pii_types", "injection_flags", "rubric_scores", "grading", "feedback"}


def test_item_result_contains_grading_and_feedback_fields():
    keys = set(typing.get_type_hints(ItemResult))
    assert set(typing.get_type_hints(state.Grading)) <= keys
    assert set(typing.get_type_hints(state.Feedback)) <= keys


def test_level_change_uses_from_to_keys():
    assert set(typing.get_type_hints(state.LevelChange)) == {"after_item", "from", "to"}


def test_langgraph_accepts_session_state():
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(SessionState)
    g.add_node("noop", lambda s: {"done": True})
    g.add_edge(START, "noop")
    g.add_edge("noop", END)
    out = g.compile().invoke(new_session_state("sid", "t"))
    assert out["done"] is True and out["session_id"] == "sid"
