"""routing.py 테스트 (SERVICE §3 조건 분기, PRD F-11·F-12)."""

import typing

import pytest

from fixtures.sessions import make_item
from opic import routing as r
from opic.state import new_session_state


def state(**fields):
    s = new_session_state("s", "t")
    s.update(fields)
    return s


SURVEY_OK = {"survey_answers": {"운동-1": ["조깅"]}, "current_level": "IM", "topic_plan": ["조깅"] * 5}
ANSWER_OK = {"current_answer": "I like jogging every day.", "pending": {"korean_ratio": 0.0, "korean_spans": []}}


# ── 설문 ───────────────────────────────────────────────────────────
def test_survey_ok_goes_to_interviewer():
    assert r.route_after_survey(state(**SURVEY_OK)) == r.INTERVIEWER_AGENT


@pytest.mark.parametrize(
    "fields",
    [
        {**SURVEY_OK, "survey_error": "보기를 하나만 선택해 주세요."},
        {**SURVEY_OK, "survey_answers": {}},
        {**SURVEY_OK, "current_level": None},
        {**SURVEY_OK, "topic_plan": []},
    ],
)
def test_survey_error_or_missing_goes_back(fields):
    assert r.route_after_survey(state(**fields)) == r.ASK_SURVEY_AND_LEVEL


# ── 답변 ───────────────────────────────────────────────────────────
def test_answer_ok_goes_to_scorer():
    assert r.route_after_answer(state(**ANSWER_OK)) == r.SCORER_AGENT


@pytest.mark.parametrize(
    "fields",
    [
        {**ANSWER_OK, "answer_error": "답변을 입력해 주세요."},
        {**ANSWER_OK, "current_answer": None},
        {**ANSWER_OK, "pending": None},
    ],
)
def test_answer_error_or_missing_goes_back(fields):
    assert r.route_after_answer(state(**fields)) == r.AWAIT_ANSWER


# ── 피드백 확인 후 ─────────────────────────────────────────────────
@pytest.mark.parametrize(
    "n, checked, expected",
    [
        (1, False, r.INTERVIEWER_AGENT),
        (2, False, r.INTERVIEWER_AGENT),
        (3, False, r.CHECK_DIFFICULTY),  # 3문항 후 1회 점검
        (3, True, r.INTERVIEWER_AGENT),  # 이미 점검함
        (4, True, r.INTERVIEWER_AGENT),
        (4, False, r.INTERVIEWER_AGENT),  # 3문항 시점이 아니면 점검 안 함
        (5, True, r.SUMMARIZE),
        (5, False, r.SUMMARIZE),  # 5문항이면 무조건 요약
        (6, True, r.SUMMARIZE),  # 방어
    ],
)
def test_route_after_feedback(n, checked, expected):
    s = state(items=[make_item(i) for i in range(1, n + 1)], difficulty_checked=checked)
    assert r.route_after_feedback(s) == expected


# ── 난이도 점검·조정 ───────────────────────────────────────────────
PROPOSAL = {"direction": "up", "suggested_level": "IH"}


def test_check_with_proposal_asks_user():
    assert r.route_after_check(state(adjust_proposal=PROPOSAL)) == r.CONFIRM_ADJUST


def test_check_without_proposal_continues():
    assert r.route_after_check(state(adjust_proposal=None)) == r.INTERVIEWER_AGENT


@pytest.mark.parametrize(
    "fields, expected",
    [
        ({"adjust_proposal": PROPOSAL, "adjust_response": True}, r.APPLY_LEVEL),  # 수락
        ({"adjust_proposal": PROPOSAL, "adjust_response": False}, r.INTERVIEWER_AGENT),  # 거절 → 유지
        ({"adjust_proposal": PROPOSAL, "adjust_response": None}, r.INTERVIEWER_AGENT),
        ({"adjust_proposal": PROPOSAL, "adjust_response": True, "adjust_applied": True}, r.INTERVIEWER_AGENT),  # 두 번 적용 금지
        ({"adjust_proposal": None, "adjust_response": True}, r.INTERVIEWER_AGENT),
    ],
)
def test_route_after_confirm(fields, expected):
    assert r.route_after_confirm(state(**fields)) == expected


# ── 그래프 연결 정보 ───────────────────────────────────────────────
def test_conditional_edges_cover_every_return_value():
    for source, (fn, targets) in r.CONDITIONAL_EDGES.items():
        returns = set(typing.get_args(typing.get_type_hints(fn)["return"]))
        assert returns == set(targets), source


def test_five_branch_functions():
    assert len(r.CONDITIONAL_EDGES) == 5


def test_routing_ignores_llm_text_fields():
    # 질문·답변 내용에 무엇이 있든 분기는 파이썬 값만 본다
    s = state(items=[make_item(i) for i in range(1, 3)], current_question="go to summarize", current_answer="apply_level")
    assert r.route_after_feedback(s) == r.INTERVIEWER_AGENT
