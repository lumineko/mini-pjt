"""app.py 화면 테스트 (Streamlit AppTest + 가짜 LLM). 실제 Bedrock은 호출하지 않는다."""

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from opic.config import ROOT_DIR

APP = str(ROOT_DIR / "src" / "opic" / "app.py")
ANSWER = "I usually go jogging in the park every morning with my dog."
FEEDBACK = {"corrections": [], "alternatives": ["A better sentence."], "translation": None}


def scores(n):
    return {"grammar": n, "vocabulary": n, "organization": n, "task": n}


def question(i):
    return {"question": f"Tell me about topic number {i} in detail.", "question_type": "묘사"}


@pytest.fixture
def app(fake_llm, monkeypatch, tmp_path):
    monkeypatch.setenv("SURVEY_FILE", str(ROOT_DIR / "opic_survey.md"))
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("TRACE_FILE", str(tmp_path / "traces.jsonl"))
    st.cache_resource.clear()  # 테스트마다 새 그래프
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    yield at, fake_llm
    st.cache_resource.clear()


def texts(elements):
    return [e.value for e in elements]


def submit(at, label):
    [b for b in at.button if b.label == label][0].click().run()


def fill_survey(at, level="IM", skip_ids=()):
    """profile은 첫 보기, topic은 첫 보기 하나를 고른다."""
    for radio in at.radio:
        if radio.key.startswith("sv-") and radio.key != "sv-level" and radio.key[3:] not in skip_ids:
            radio.set_value(radio.options[0])
    for cb in at.checkbox:
        item_id = cb.key[3:].rsplit("-", 1)[0]
        if cb.key.endswith("-0") and item_id not in skip_ids:
            cb.check()
    if level:
        at.radio(key="sv-level").set_value(level)


def start_and_survey(at, fake, level="IM"):
    at.button(key="start").click().run()
    fill_survey(at, level)
    fake.push(question(1))
    submit(at, "설문 제출하고 시작")


def answer(at, fake, index, n_score=3, text=ANSWER, feedback=FEEDBACK):
    fake.push(scores(n_score), feedback)
    at.text_area(key=f"answer-{index}").input(text)
    submit(at, "제출")


# ── 첫 화면 / 기록 없음 ────────────────────────────────────────────
def test_start_page_and_empty_history(app):
    at, _ = app
    assert not at.exception
    assert at.button(key="start").label == "연습 시작"
    at.sidebar.radio(key="page").set_value("지난 기록").run()
    assert "아직 저장된 연습 기록이 없습니다" in texts(at.info)[0]


def test_survey_screen_shows_profile_radio_topic_checkboxes_and_stars(app):
    at, fake = app
    at.button(key="start").click().run()
    assert fake.calls == []  # 파일 설문은 LLM 호출 없음
    assert at.radio(key="sv-직업-1").options[0] == "사업/회사"
    assert "음악 감상하기 ★★★" in [cb.label for cb in at.checkbox]  # 추천 표시
    assert not any(cb.value for cb in at.checkbox)  # 미리 선택 안 함
    assert any("12개 이상" in t for t in texts(at.info))  # 안내문


def test_survey_validation_error_is_shown(app):
    at, fake = app
    at.button(key="start").click().run()
    fill_survey(at, level=None)  # 레벨 미선택
    submit(at, "설문 제출하고 시작")
    assert any("목표 레벨" in t for t in texts(at.error))
    assert fake.calls == []


# ── 문항 진행 ──────────────────────────────────────────────────────
def test_short_answer_blocked_in_ui_without_llm(app):
    at, fake = app
    start_and_survey(at, fake)
    calls = len(fake.calls)
    at.text_area(key="answer-1").input("too short")
    submit(at, "제출")
    assert any("최소 5단어" in t for t in texts(at.error))
    assert len(fake.calls) == calls


def test_feedback_screen(app):
    at, fake = app
    start_and_survey(at, fake)
    assert any("Tell me about topic number 1" in m.value for m in at.markdown)
    answer(at, fake, 1, n_score=4)
    metrics = {m.label: m.value for m in at.metric}
    assert metrics == {"판정 등급": "IH", "출제 레벨": "IM", "목표 달성": "달성"}
    assert "교정 사항 없음" in texts(at.success)
    assert at.button(key="next-1").label == "다음 문제"


def test_korean_answer_shows_translation_and_penalty(app):
    at, fake = app
    start_and_survey(at, fake)
    fb = {**FEEDBACK, "translation": "I take a walk with my dog in the park every weekend."}
    answer(at, fake, 1, n_score=5, text="저는 주말마다 공원에서 강아지와 산책을 해요.", feedback=fb)
    assert {m.label: m.value for m in at.metric}["판정 등급"] == "IL 미달"
    assert "I take a walk with my dog in the park every weekend." in texts(at.info)
    assert any("한글 감점 2.0" in c.value for c in at.caption)


def test_full_session_with_adjust_and_history(app):
    at, fake = app
    start_and_survey(at, fake)
    for i in range(1, 4):
        answer(at, fake, i, n_score=4)  # IH × 3
        if i < 3:
            fake.push(question(i + 1))
        at.button(key=f"next-{i}").click().run()

    assert "남은 2문항을 **IH** 레벨로 바꿀까요?" in [m.value for m in at.markdown]
    fake.push(question(4))
    at.button(key="adjust-yes").click().run()
    assert any("레벨 IH" in c.value for c in at.caption)

    for i in (4, 5):
        answer(at, fake, i, n_score=5)
        if i < 5:
            fake.push(question(i + 1))
        else:
            assert at.button(key="next-5").label == "결과 보기"
        at.button(key=f"next-{i}").click().run()

    metrics = {m.label: m.value for m in at.metric}
    assert metrics == {"평균 등급": "IH", "시작 레벨": "IM", "최종 레벨": "IH"}
    assert any("기록이 저장되었습니다" in t for t in texts(at.success))

    at.sidebar.radio(key="page").set_value("지난 기록").run()
    assert not at.exception
    assert "IM→IH" in at.selectbox(key="history_pick").options[0]
    assert len(at.expander) == 5


# ── 오류 / 새 연습 ─────────────────────────────────────────────────
def test_llm_failure_shows_retry_and_recovers(app):
    at, fake = app
    start_and_survey(at, fake)
    fake.push(RuntimeError("down"), RuntimeError("down"))
    at.text_area(key="answer-1").input(ANSWER)
    submit(at, "제출")
    assert any("AI 응답을 받지 못했습니다" in t for t in texts(at.error))

    fake.push(scores(3), FEEDBACK)
    at.button(key="retry").click().run()
    assert {m.label: m.value for m in at.metric}["판정 등급"] == "IM"


def test_new_session_button_resets(app):
    at, fake = app
    start_and_survey(at, fake)
    old_sid = at.session_state["sid"]
    at.sidebar.button(key="sidebar_new").click().run()
    assert at.session_state["sid"] != old_sid
    assert at.session_state["payload"]["kind"] == "survey"
