"""guardrails.py 테스트 (SERVICE §13, Phase 6). 가짜 LLM만 쓰고 Bedrock은 호출하지 않는다."""

import pytest

from opic import guardrails, llm, trace
from opic.agents import feedback, interviewer
from opic.agents.feedback import feedback_schema
from opic.agents.interviewer import question_schema
from opic.config import load_settings
from opic.tools.korean import detect_korean

QSchema = question_schema(["묘사", "습관"])
OK_FEEDBACK = {
    "corrections": [{"original": "I go to park.", "corrected": "I go to the park.", "reason": "특정 장소 앞에는 the가 필요합니다."}],
    "alternatives": ["I often head to the park near my place."],
    "translation": None,
}


def q(question, keywords):
    return QSchema(question=question, question_type="묘사", topic_keywords=keywords)


def fb(needs_translation=False, **overrides):
    return feedback_schema(needs_translation).model_validate({**OK_FEEDBACK, **overrides})


# ── 키워드 매칭 ────────────────────────────────────────────────────
@pytest.mark.parametrize("keyword, question", [
    ("park", "Tell me about the park near your home."),
    ("parks", "Tell me about the park near your home."),
    ("park", "Which parks do you usually visit?"),
    ("movie", "What movies have you seen recently?"),
    ("Movie Theater", "Describe the movie theater you go to."),
    ("cooking", "Do you cook at home? Tell me about your cooking."),
    ("friend's house", "Tell me about your friend's house."),
])
def test_keyword_found(keyword, question):
    assert guardrails.keyword_in_question(keyword, question)


@pytest.mark.parametrize("keyword, question", [
    ("beach", "Tell me about the park near your home."),
    ("movie theater", "Describe the movie you saw."),  # 구의 단어가 모두 있어야 함
    ("experience", "Tell me about a memorable experience."),  # 일반 단어뿐
    ("your favorite", "What is your favorite thing?"),
    ("art", "Tell me about an article you read."),  # 4글자 미만은 앞부분 일치 안 봄
])
def test_keyword_not_found(keyword, question):
    assert not guardrails.keyword_in_question(keyword, question)


# ── interviewer 검사 ───────────────────────────────────────────────
def test_interviewer_on_topic_passes():
    assert guardrails.check_interviewer(q("Tell me about the park you often visit.", ["park"])) == []


def test_interviewer_one_matching_keyword_is_enough():
    assert guardrails.check_interviewer(q("Tell me about the park you often visit.", ["beach", "park"])) == []


def test_interviewer_off_topic_fails():
    [problem] = guardrails.check_interviewer(q("Tell me about your favorite movie.", ["park", "walking"]))
    assert "주제 키워드" in problem


def test_interviewer_generic_keywords_only_fail():
    assert guardrails.check_interviewer(q("Tell me about a memorable experience you had.", ["experience", "memorable"]))


# ── feedback 검사 ──────────────────────────────────────────────────
def test_feedback_ok():
    assert guardrails.check_feedback(fb(), needs_translation=False) == []


def test_feedback_korean_original_is_allowed():
    out = fb(corrections=[{"original": "I like 등산 very much.", "corrected": "I like hiking very much.", "reason": "한글 대신 영어 단어를 씁니다."}])
    assert guardrails.check_feedback(out, needs_translation=False) == []


@pytest.mark.parametrize("overrides, expected", [
    ({"corrections": [{"original": "I go park.", "corrected": "I go 공원.", "reason": "관사가 필요합니다."}]}, "corrected에 한글"),
    ({"corrections": [{"original": "I go park.", "corrected": "I go to the park.", "reason": "You need 'to the'."}]}, "reason이 한국어가 아닙니다"),
    ({"alternatives": ["I love 공원."]}, "대체 문장 1에 한글"),
])
def test_feedback_language_violations(overrides, expected):
    problems = guardrails.check_feedback(fb(**overrides), needs_translation=False)
    assert any(expected in p for p in problems)


def test_feedback_translation_must_not_keep_korean():
    out = fb(needs_translation=True, translation="I go to the 공원 every day.")
    assert any("번역에 한글" in p for p in guardrails.check_feedback(out, needs_translation=True))


def test_feedback_translation_missing_is_caught_even_without_schema():
    out = fb(needs_translation=False)  # 스키마가 막지 못한 경우를 가정
    assert any("번역이 없습니다" in p for p in guardrails.check_feedback(out, needs_translation=True))


def test_feedback_reports_all_problems():
    out = fb(alternatives=["좋아요.", "Nice."], corrections=[{"original": "a", "corrected": "가", "reason": "because"}])
    assert len(guardrails.check_feedback(out, needs_translation=False)) == 3


# ── 근거 확인 (교정 원문이 답변에 있는지) ─────────────────────────
ANSWER = "I go to park every weekends with my dog. It is very fun! 저는 공원이 좋아요."


@pytest.mark.parametrize("original", [
    "I go to park every weekends.",
    "it is very fun",
    "I GO TO PARK, every weekends",
    "I go to park every weekends with my cat.",  # 9단어 중 8개 일치 (80% 이상)
    "저는 공원이 좋아요",
])
def test_grounded(original):
    assert guardrails.grounded_in(original, ANSWER)


@pytest.mark.parametrize("original", [
    "I went to the beach yesterday.",
    "I go to the park every weekend.",  # 고친 문장을 original로 낸 경우
    "",
    "...",
])
def test_not_grounded(original):
    assert not guardrails.grounded_in(original, ANSWER)


def test_feedback_ungrounded_correction_fails():
    out = fb(corrections=[{"original": "I visited Paris last year.", "corrected": "I visited Paris last year.", "reason": "예시입니다."}])
    problems = guardrails.check_feedback(out, needs_translation=False, answer="I go to park. It is fun.")
    assert any("original이 답변에 없습니다" in p for p in problems)


def test_feedback_grounding_skipped_without_answer():
    out = fb(corrections=[{"original": "I visited Paris.", "corrected": "I visited Paris.", "reason": "예시입니다."}])
    assert guardrails.check_feedback(out, needs_translation=False) == []


def test_feedback_agent_passes_answer_for_grounding(fake_llm):
    guardrails.install()
    bad = {**OK_FEEDBACK, "corrections": [{"original": "I visited Paris.", "corrected": "I visited Paris.", "reason": "예시."}]}
    fake_llm.push(bad, OK_FEEDBACK)
    feedback.generate_feedback("Do you go to the park?", "IM", "I go to park. It is fun.", "IM", True, [])
    assert fake_llm.calls[0]["metadata"]["guard_answer"] == "I go to park. It is fun."
    assert len(fake_llm.calls) == 2


# ── 훅 동작 ────────────────────────────────────────────────────────
def test_output_guard_raises_guardrail_violation():
    with pytest.raises(llm.GuardrailViolation, match="주제 키워드"):
        guardrails.output_guard("interviewer", q("Tell me about your favorite movie.", ["park"]), {})


def test_output_guard_ignores_other_roles():
    guardrails.output_guard("scorer", object(), {})
    guardrails.output_guard("survey", object(), {})


def test_install_is_idempotent_and_first(tmp_path):
    trace.install(load_settings({"TRACE_FILE": str(tmp_path / "t.jsonl")}))
    guardrails.install()
    guardrails.install()
    assert llm.after_call_hooks[0] is guardrails.output_guard
    assert llm.after_call_hooks.count(guardrails.output_guard) == 1
    assert trace._is_recorder_hook(llm.after_call_hooks[-1])
    guardrails.uninstall()
    assert guardrails.output_guard not in llm.after_call_hooks


# ── 에이전트 연동: 위반 → 다음 모델 ────────────────────────────────
def test_off_topic_question_falls_back_to_next_model(fake_llm):
    guardrails.install()
    fake_llm.push(
        {"question": "Tell me about your favorite movie.", "question_type": "묘사", "topic_keywords": ["park"]},
        {"question": "Tell me about the park you visit often.", "question_type": "묘사", "topic_keywords": ["park"]},
    )
    question, _ = interviewer.generate_question("공원 가기", "IM", [])
    assert question == "Tell me about the park you visit often."
    assert [c["model_id"] for c in fake_llm.calls] == ["fake-primary", "fake-fallback"]


def test_untranslated_feedback_falls_back_and_uses_needs_translation_meta(fake_llm):
    guardrails.install()
    answer = "I go to park. I go to 공원 every day."
    spans = detect_korean(answer)["spans"]
    fake_llm.push(
        {**OK_FEEDBACK, "translation": "I go to park. I go to 공원 every day."},
        {**OK_FEEDBACK, "translation": "I go to park. I go to the park every day."},
    )
    out = feedback.generate_feedback("Do you go to the park?", "IM", answer, "IM", True, spans)
    assert out["translation"] == "I go to park. I go to the park every day."
    assert fake_llm.calls[0]["metadata"]["needs_translation"] is True
    assert len(fake_llm.calls) == 2


def test_all_models_violate_raises_llm_error(fake_llm):
    guardrails.install()
    bad = {"question": "Tell me about your favorite movie.", "question_type": "묘사", "topic_keywords": ["park"]}
    fake_llm.push(bad, bad)
    with pytest.raises(llm.LLMError, match="GuardrailViolation"):
        interviewer.generate_question("공원 가기", "IM", [])


def test_violation_is_traced_as_error(fake_llm, tmp_path):
    guardrails.install()
    settings = load_settings({"TRACE_FILE": str(tmp_path / "t.jsonl")})
    trace.install(settings)
    fake_llm.push(
        {"question": "Tell me about your favorite movie.", "question_type": "묘사", "topic_keywords": ["park"]},
        {"question": "Tell me about the park you visit often.", "question_type": "묘사", "topic_keywords": ["park"]},
    )
    interviewer.generate_question("공원 가기", "IM", [])
    recs = trace.read_traces(settings.trace_file)
    assert [r["status"] for r in recs] == ["error", "ok"]
    assert recs[0]["error"]["type"] == "GuardrailViolation"
    assert recs[1]["output"]["topic_keywords"] == ["park"]
