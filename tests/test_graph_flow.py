"""그래프 전체 흐름 테스트 (PRD 성공 기준 1·3·6·7·9, SERVICE §14.1). 가짜 LLM으로 5문항 세션을 끝까지 돈다.

가짜 채점 점수로 등급을 조절한다: 모든 항목 3점 → IM, 4점 → IH, 5점 → AL, 2점 → IL, 1점 → IL 미달.
"""

import json

import pytest

from opic import graph as g
from opic.config import ROOT_DIR
from opic.llm import LLMError
from opic.storage import list_sessions

ANSWER = "I usually go jogging in the park every morning with my dog."


@pytest.fixture
def env(fake_llm, monkeypatch, tmp_path):
    monkeypatch.setenv("SURVEY_FILE", str(ROOT_DIR / "opic_survey.md"))
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path / "history"))
    return fake_llm, g.build_graph(), tmp_path / "history"


def scores(n):
    return {"grammar": n, "vocabulary": n, "organization": n, "task": n}


def question(i):
    return {"question": f"Tell me about topic number {i} in detail.", "question_type": "묘사"}


FEEDBACK = {"corrections": [], "alternatives": ["A better sentence."], "translation": None}


def first_options(payload):
    return {item["id"]: [item["options"][0]["label"]] for item in payload["items"]}


class Session:
    """그래프를 한 단계씩 밀면서 payload 종류를 기록한다."""

    def __init__(self, fake, graph):
        self.fake, self.graph = fake, graph
        self.sid, self.payload = g.start_session(graph)
        self.kinds = [self.payload["kind"]]

    def send(self, value):
        self.payload = g.resume(self.sid, value, self.graph)
        self.kinds.append(self.payload["kind"])
        return self.payload

    def submit_survey(self, level):
        self.fake.push(question(1))
        return self.send({"answers": first_options(self.payload), "level": level})

    def answer_item(self, n_score, answer=ANSWER, feedback=FEEDBACK):
        assert self.payload["kind"] == "answer"
        self.fake.push(scores(n_score), feedback)
        return self.send(answer)

    def next_item(self, i):
        """피드백 확인 → 다음 질문 (interviewer 응답을 미리 넣어 둔다)."""
        assert self.payload["kind"] == "feedback"
        self.fake.push(question(i))
        return self.send(True)

    @property
    def state(self):
        return g.get_state(self.sid, self.graph)


def run_items(s, item_scores, start=1, adjust=None):
    """item_scores 순서대로 답하고, 3문항 뒤 adjust(True/False/None=질문 안 나와야 함)를 처리한다."""
    for offset, n in enumerate(item_scores):
        i = start + offset
        s.answer_item(n)
        if i == 3 and adjust is not None:
            assert s.send(True)["kind"] == "adjust"  # 조정 확인은 LLM 호출 없음
            s.fake.push(question(4))
            s.send(adjust)
        elif i < 5:
            s.next_item(i + 1)
    return s


# ── 기본 흐름 ──────────────────────────────────────────────────────
def test_full_session_without_adjustment(env):
    fake, graph, history = env
    s = Session(fake, graph)
    assert s.payload["kind"] == "survey"
    s.submit_survey("IM")
    run_items(s, [3, 3, 3, 3, 3])

    assert s.payload["kind"] == "feedback" and s.payload["is_last"] is True
    done = s.send(True)
    assert done["kind"] == "done" and done["session_id"] == s.sid
    assert done["summary"] == {
        "item_grades": ["IM"] * 5, "average_grade": "IM",
        "initial_level": "IM", "final_level": "IM", "level_changed": False,
    }
    assert s.kinds == ["survey"] + ["answer", "feedback"] * 5 + ["done"]  # adjust 없음

    st = s.state
    assert st["done"] is True and len(st["items"]) == 5 and st["difficulty_checked"] is True
    assert st["adjust_proposal"] is None and st["level_history"] == []
    # 저장된 기록
    saved = json.loads((history / f"{s.sid}.json").read_text(encoding="utf-8"))
    assert saved["summary"]["average_grade"] == "IM" and len(saved["items"]) == 5
    assert [e["session_id"] for e in list_sessions(history)] == [s.sid]


def test_llm_call_order_is_fixed_per_item(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    run_items(s, [3, 3, 3, 3, 3])
    roles = [c["role"] for c in fake.calls]
    assert roles == ["interviewer", "scorer", "feedback"] * 5  # 슈퍼바이저 없이 항상 같은 순서


def test_feedback_receives_python_grade(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    s.answer_item(4)  # IH
    assert "Current grade of this answer: IH (goal IM achieved: yes)" in fake.user_text("feedback")
    item = s.payload["item"]
    assert item["grade"] == "IH" and item["achieved"] is True and item["level"] == "IM"


def test_topics_follow_topic_plan(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    run_items(s, [3, 3, 3, 3, 3])
    plan = s.state["topic_plan"]
    assert [i["topic"] for i in s.state["items"]] == plan
    prompts = [c for c in fake.calls if c["role"] == "interviewer"]
    assert all(f"Assigned topic: {t}" in c["messages"][1].content for c, t in zip(prompts, plan))


# ── 난이도 조정 (F-12) ─────────────────────────────────────────────
def test_adjust_up_accepted_changes_level_for_items_4_and_5(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    run_items(s, [4, 4, 4], adjust=True)  # IH × 3 → 상향 제안 → 수락

    assert s.payload["kind"] == "answer" and s.payload["level"] == "IH" and s.payload["item_index"] == 4
    assert "Target level: IH" in fake.user_text("interviewer")
    run_items(s, [5, 5], start=4)  # IH 문항 상한 AL
    done = s.send(True)

    items = s.state["items"]
    assert [i["level"] for i in items] == ["IM", "IM", "IM", "IH", "IH"]
    assert [i["grade"] for i in items] == ["IH", "IH", "IH", "AL", "AL"]
    assert s.state["level_history"] == [{"after_item": 3, "from": "IM", "to": "IH"}]
    assert done["summary"]["final_level"] == "IH" and done["summary"]["level_changed"] is True
    assert s.kinds.count("adjust") == 1


def test_adjust_payload(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    for i, n in enumerate([4, 4, 3], 1):
        s.answer_item(n)
        if i < 3:
            s.next_item(i + 1)
    payload = s.send(True)
    assert payload == {
        "kind": "adjust", "average_grade": "IH", "current_level": "IM",
        "proposal": {"direction": "up", "suggested_level": "IH"},
    }


def test_adjust_declined_keeps_level(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    run_items(s, [4, 4, 4], adjust=False)
    run_items(s, [4, 4], start=4)
    done = s.send(True)
    assert [i["level"] for i in s.state["items"]] == ["IM"] * 5
    assert [i["grade"] for i in s.state["items"]] == ["IH"] * 5  # 상한도 IM 기준(IH) 유지
    assert s.state["level_history"] == [] and s.state["adjust_applied"] is False
    assert done["summary"]["level_changed"] is False


def test_adjust_down_accepted(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IH")
    run_items(s, [2, 2, 1], adjust=True)  # IL, IL, IL 미달 → 평균 IL → 한 단계만 하향(IM)
    assert s.payload["level"] == "IM"
    run_items(s, [3, 3], start=4)
    s.send(True)
    assert s.state["level_history"] == [{"after_item": 3, "from": "IH", "to": "IM"}]


@pytest.mark.parametrize(
    "level, n_score",
    [
        ("AL", 5),  # AL에서는 상향 안 물음
        ("IL", 1),  # IL에서는 하향 안 물음 (IL 미달이어도)
        ("IM", 3),  # 같으면 안 물음
    ],
)
def test_no_adjust_question_at_boundaries(env, level, n_score):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey(level)
    run_items(s, [n_score] * 5)
    s.send(True)
    assert "adjust" not in s.kinds
    assert s.state["difficulty_checked"] is True and s.state["adjust_proposal"] is None


def test_difficulty_checked_only_once(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    run_items(s, [4, 4, 4], adjust=False)
    run_items(s, [4, 4], start=4)  # 4·5번이 계속 IH여도 다시 묻지 않음
    s.send(True)
    assert s.kinds.count("adjust") == 1


# ── 입력 검증 ──────────────────────────────────────────────────────
def test_invalid_answer_reasks_without_llm(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    calls_before = len(fake.calls)
    again = s.send("too short")
    assert again["kind"] == "answer" and again["item_index"] == 1 and "최소 5단어" in again["error"]
    assert len(fake.calls) == calls_before  # 채점 호출 없음
    s.answer_item(3)
    assert s.payload["kind"] == "feedback" and s.state["answer_error"] is None


def test_korean_answer_flow(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    korean = "저는 주말마다 공원에서 강아지와 산책을 해요."
    fb = {**FEEDBACK, "translation": "I take a walk with my dog in the park every weekend."}
    s.answer_item(5, answer=korean, feedback=fb)
    item = s.payload["item"]
    assert item["korean_ratio"] == 1.0 and item["grade"] == "IL 미달"  # 점수와 상관없이
    assert item["penalty"] == 2.0 and item["translation"].startswith("I take a walk")
    assert "Evaluate ONLY the English parts" in fake.system_text("scorer")


# ── 오류 복구 / 저장 ───────────────────────────────────────────────
def test_llm_failure_then_retry_continues(env):
    fake, graph, _ = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    fake.push(RuntimeError("primary down"), RuntimeError("fallback down"))  # 채점 두 모델 모두 실패
    with pytest.raises(LLMError):
        g.resume(s.sid, ANSWER, graph)
    assert s.state["current_answer"] == ANSWER and "rubric_scores" not in s.state["pending"]

    fake.push(scores(3), FEEDBACK)
    payload = g.retry(s.sid, graph)  # 마지막 체크포인트(채점 직전)부터
    assert payload["kind"] == "feedback" and payload["item"]["grade"] == "IM"


def test_incomplete_session_is_not_saved(env):
    fake, graph, history = env
    s = Session(fake, graph)
    s.submit_survey("IM")
    run_items(s, [3, 3])  # 2문항만 하고 중단
    assert not history.exists() or list(history.glob("*.json")) == []


def test_sessions_are_isolated(env):
    fake, graph, _ = env
    a, b = Session(fake, graph), Session(fake, graph)
    a.submit_survey("IM")
    b.submit_survey("AL")
    assert a.sid != b.sid
    assert a.payload["level"] == "IM" and b.payload["level"] == "AL"


def test_fallback_survey_flow(fake_llm, monkeypatch, tmp_path):
    monkeypatch.setenv("SURVEY_FILE", str(tmp_path / "missing.md"))
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path / "history"))
    fake_llm.push({"question": "어떤 운동을 하나요?", "options": ["조깅", "수영", "요가", "등산"]})
    graph = g.build_graph()
    sid, payload = g.start_session(graph)
    assert payload["kind"] == "survey" and payload["source"] == "fallback"
    assert len(payload["items"]) == 1 and payload["items"][0]["kind"] == "topic"

    fake_llm.push(question(1))
    asked = g.resume(sid, {"answers": {payload["items"][0]["id"]: ["수영", "요가"]}, "level": "IL"}, graph)
    assert asked["kind"] == "answer"
    assert g.get_state(sid, graph)["topic_plan"] == ["수영", "요가", "수영", "요가", "수영"]
