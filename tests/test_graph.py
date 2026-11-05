"""graph.py 테스트: 그래프 구조, 노드 단위 동작, API 첫 단계. 5문항 전체 흐름은 test_graph_flow.py."""

import pytest

from fixtures.sessions import completed_state, make_item
from fixtures.survey_items import SURVEY_ITEMS, valid_answers
from opic import graph as g
from opic import routing as r
from opic.config import ROOT_DIR
from opic.state import new_session_state


def state(**fields):
    s = new_session_state("sess-1", "t")
    s.update(fields)
    return s


# ── 구조 ───────────────────────────────────────────────────────────
def test_graph_has_all_nodes_and_edges():
    compiled = g.build_graph()
    drawn = compiled.get_graph()
    assert set(drawn.nodes) - {"__start__", "__end__"} == set(g.NODES)
    assert len(g.NODES) == 14
    edges = {(e.source, e.target) for e in drawn.edges}
    for src, dst in g.FIXED_EDGES:
        assert (src, dst) in edges
    for src, (_, targets) in r.CONDITIONAL_EDGES.items():
        assert all((src, t) in edges for t in targets)


def test_no_supervisor_node():
    assert not any("supervisor" in name or "guard" in name for name in g.NODES)


# ── 설문 제출 ──────────────────────────────────────────────────────
def test_apply_survey_submission_ok():
    out = g.apply_survey_submission(state(survey_items=SURVEY_ITEMS), {"answers": valid_answers(), "level": "IM"})
    assert out["survey_error"] is None
    assert out["initial_level"] == out["current_level"] == "IM"
    assert out["topic_plan"] == ["영화 보기", "독서", "조깅", "영화 보기", "독서"]


@pytest.mark.parametrize(
    "value, fragment",
    [
        ({"answers": valid_answers(**{"job-1": []}), "level": "IM"}, "하나만"),
        ({"answers": valid_answers(), "level": "NH"}, "목표 레벨"),
        ({"answers": "x", "level": "IM"}, "형식"),
        (None, "형식"),
    ],
)
def test_apply_survey_submission_errors(value, fragment):
    out = g.apply_survey_submission(state(survey_items=SURVEY_ITEMS), value)
    assert set(out) == {"survey_error"} and fragment in out["survey_error"]


# ── 답변 제출 ──────────────────────────────────────────────────────
def test_apply_answer_submission_ok_computes_korean_once():
    out = g.apply_answer_submission(state(), "  I went to 제주도 last summer with my family.  ", 5)
    assert out["answer_error"] is None
    assert out["current_answer"] == "I went to 제주도 last summer with my family."
    assert out["pending"]["korean_ratio"] == pytest.approx(1 / 9)  # 9단어 중 한글 1
    assert [s["text"] for s in out["pending"]["korean_spans"]] == ["제주도"]


@pytest.mark.parametrize("text", ["", "too short", None, 123])
def test_apply_answer_submission_errors(text):
    out = g.apply_answer_submission(state(), text, 5)
    assert set(out) == {"answer_error"}


# ── 파이썬 노드 ────────────────────────────────────────────────────
SCORES = {"grammar": 4, "vocabulary": 3, "organization": 4, "task": 4}


def pending_full():
    return {
        "korean_ratio": 0.0, "korean_spans": [], "rubric_scores": SCORES,
        "grading": {"weighted_score": 3.75, "penalty": 0.0, "final_score": 3.75, "raw_grade": "IH", "grade": "IH", "achieved": True},
        "feedback": {"corrections": [], "alternatives": ["Alt."], "translation": None},
    }


def test_score_and_grade_uses_current_level_cap():
    s = state(current_level="IL", pending={"korean_ratio": 0.0, "korean_spans": [], "rubric_scores": {k: 5 for k in SCORES}})
    grading = g.score_and_grade(s)["pending"]["grading"]
    assert grading["raw_grade"] == "AL" and grading["grade"] == "IM"  # IL 문항 상한


def test_record_item_builds_item_and_clears_progress():
    s = state(
        topic_plan=["조깅", "독서"], items=[make_item(1)], current_level="IM",
        current_question="Q2?", current_question_type="묘사", current_answer="My answer here ok.", pending=pending_full(),
    )
    out = g.record_item(s)
    item = out["items"][-1]
    assert len(out["items"]) == 2
    assert item["topic"] == "독서" and item["level"] == "IM" and item["grade"] == "IH"
    assert item["rubric_scores"] == SCORES and item["alternatives"] == ["Alt."]
    assert out["pending"] is None and out["current_question"] is None and out["current_answer"] is None
    assert s["items"] == [make_item(1)]  # 원래 State는 바꾸지 않음


def test_check_difficulty_and_apply_level():
    s = state(current_level="IM", items=[make_item(i, grade="IH") for i in range(1, 4)])
    out = g.check_difficulty(s)
    assert out == {"difficulty_checked": True, "adjust_proposal": {"direction": "up", "suggested_level": "IH"}}

    s.update(out, adjust_response=True)
    applied = g.apply_level(s)
    assert applied["current_level"] == "IH" and applied["adjust_applied"] is True
    assert applied["level_history"] == [{"after_item": 3, "from": "IM", "to": "IH"}]


def test_check_difficulty_no_proposal():
    s = state(current_level="IM", items=[make_item(i) for i in range(1, 4)])
    assert g.check_difficulty(s)["adjust_proposal"] is None


def test_summarize_and_save(tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path))
    s = completed_state()
    s["summary"] = None
    s.update(g.summarize_node(s))
    assert s["summary"]["average_grade"] == "IM"
    assert g.save_session_node(s) == {"done": True}
    assert (tmp_path / "s-001.json").exists()


# ── API 첫 단계 ────────────────────────────────────────────────────
def test_start_session_stops_at_survey(fake_llm, monkeypatch):
    monkeypatch.setenv("SURVEY_FILE", str(ROOT_DIR / "opic_survey.md"))
    graph = g.build_graph()
    sid, payload = g.start_session(graph)
    assert payload["kind"] == "survey" and len(payload["items"]) == 8
    assert payload["levels"] == ["IL", "IM", "IH", "AL"] and payload["error"] is None
    assert fake_llm.calls == []  # 파일 설문은 LLM 호출 없음
    assert g.current_payload(sid, graph) == payload
    assert g.get_state(sid, graph)["session_id"] == sid


def test_invalid_survey_reinterrupts_with_error_then_proceeds(fake_llm, monkeypatch):
    monkeypatch.setenv("SURVEY_FILE", str(ROOT_DIR / "opic_survey.md"))
    graph = g.build_graph()
    sid, payload = g.start_session(graph)

    bad = g.resume(sid, {"answers": {}, "level": "IM"}, graph)
    assert bad["kind"] == "survey" and bad["error"]

    answers = {item["id"]: [item["options"][0]["label"]] for item in payload["items"]}
    fake_llm.push({"question": "Tell me about the movies you like to watch.", "question_type": "묘사"})
    asked = g.resume(sid, {"answers": answers, "level": "IM"}, graph)
    assert asked["kind"] == "answer" and asked["item_index"] == 1 and asked["total"] == 5
    assert asked["question"] == "Tell me about the movies you like to watch."
    assert g.get_state(sid, graph)["topic_plan"][0] == "영화 보기"


def test_new_session_id_is_storage_safe():
    import re

    sid = g.new_session_id()
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", sid)
    assert sid != g.new_session_id()
