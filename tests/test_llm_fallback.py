"""llm.py 테스트 (PRD F-10, 성공 기준 4). 가짜 모델만 쓰고 Bedrock은 호출하지 않는다."""

import logging

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from opic import llm
from opic.config import load_settings

SETTINGS = load_settings({"MODEL_PRIMARY": "primary", "MODEL_FALLBACKS": "fallback", "LLM_MAX_RETRIES": "2"})
MSGS = [HumanMessage("hello")]


def client_error(code, status=400):
    return ClientError({"Error": {"Code": code, "Message": code}, "ResponseMetadata": {"HTTPStatusCode": status}}, "Converse")


class Scores(BaseModel):
    grammar: int = Field(ge=1, le=5)


class FakeModel:
    """정해진 순서대로 결과를 내거나 예외를 던지는 가짜 모델. 호출 기록을 남긴다."""

    def __init__(self, model_id, outcomes, log):
        self.model_id, self.outcomes, self.log = model_id, list(outcomes), log
        self.structured = None

    def with_structured_output(self, schema):
        self.structured = schema
        return self

    def invoke(self, messages, config=None):
        self.log.append({"model": self.model_id, "config": config, "messages": messages})
        outcome = self.outcomes.pop(0) if self.outcomes else AIMessage("default")
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return outcome()
        return outcome


def make(outcomes_by_model):
    log, sleeps = [], []
    models = {mid: FakeModel(mid, outs, log) for mid, outs in outcomes_by_model.items()}

    def factory(model_id, role, settings):
        return models[model_id]

    def call(role="interviewer", **kw):
        return llm.invoke_llm(role, MSGS, settings=kw.pop("settings", SETTINGS), factory=factory, sleep=sleeps.append, **kw)

    return call, log, sleeps


# ── 성공 / 재시도 ──────────────────────────────────────────────────
def test_success_on_primary():
    call, log, sleeps = make({"primary": [AIMessage("hi")]})
    assert call().content == "hi"
    assert [e["model"] for e in log] == ["primary"] and sleeps == []


def test_throttling_retries_with_backoff_then_succeeds():
    call, log, sleeps = make({"primary": [client_error("ThrottlingException"), client_error("ThrottlingException"), AIMessage("ok")]})
    assert call().content == "ok"
    assert [e["model"] for e in log] == ["primary"] * 3
    assert sleeps == [1.0, 2.0]


def test_throttling_exhausts_retries_then_falls_back():
    call, log, sleeps = make({"primary": [client_error("ThrottlingException")] * 3, "fallback": [AIMessage("fb")]})
    assert call().content == "fb"
    assert [e["model"] for e in log] == ["primary"] * 3 + ["fallback"]
    assert sleeps == [1.0, 2.0]


@pytest.mark.parametrize(
    "exc",
    [
        client_error("InternalServerException", 500),
        client_error("SomethingElse", 503),  # 코드와 상관없이 5xx
        client_error("ServiceUnavailableException", 503),
        ReadTimeoutError(endpoint_url="https://bedrock"),
    ],
)
def test_transient_errors_are_retried(exc):
    call, log, sleeps = make({"primary": [exc, AIMessage("ok")]})
    assert call().content == "ok" and sleeps == [1.0]


@pytest.mark.parametrize(
    "exc",
    [client_error("AccessDeniedException", 403), client_error("ValidationException", 400), RuntimeError("boom")],
)
def test_non_retryable_errors_fall_back_immediately(exc):
    call, log, sleeps = make({"primary": [exc], "fallback": [AIMessage("fb")]})
    assert call().content == "fb"
    assert [e["model"] for e in log] == ["primary", "fallback"] and sleeps == []


def test_zero_retries_setting():
    settings = load_settings({"MODEL_PRIMARY": "primary", "MODEL_FALLBACKS": "fallback", "LLM_MAX_RETRIES": "0"})
    call, log, sleeps = make({"primary": [client_error("ThrottlingException")], "fallback": [AIMessage("fb")]})
    assert call(settings=settings).content == "fb" and sleeps == []


def test_all_models_fail_raises_llm_error():
    call, log, sleeps = make({"primary": [client_error("ThrottlingException")] * 3, "fallback": [RuntimeError("down")]})
    with pytest.raises(llm.LLMError) as info:
        call()
    assert [(a.model_id, a.attempt) for a in info.value.attempts] == [
        ("primary", 1), ("primary", 2), ("primary", 3), ("fallback", 1)
    ]
    assert "down" in str(info.value)


# ── 구조화 출력 ────────────────────────────────────────────────────
def test_structured_output_returns_model_instance():
    call, log, _ = make({"primary": [Scores(grammar=4)]})
    out = call(role="scorer", schema=Scores)
    assert out == Scores(grammar=4)


@pytest.mark.parametrize(
    "bad",
    [None, {"grammar": 4}, lambda: Scores(grammar=9)],  # 빈 출력, 다른 형식, 검증 실패(ValidationError)
)
def test_structured_failure_goes_to_next_model_without_retry(bad):
    call, log, sleeps = make({"primary": [bad], "fallback": [Scores(grammar=3)]})
    assert call(role="scorer", schema=Scores) == Scores(grammar=3)
    assert [e["model"] for e in log] == ["primary", "fallback"] and sleeps == []


# ── 메타데이터 / 훅 ────────────────────────────────────────────────
def test_metadata_and_tags_are_passed():
    call, log, _ = make({"primary": [client_error("ThrottlingException")], "fallback": []})
    call(metadata={"session_id": "s1", "node": "interviewer_agent", "item_index": 2, "prompt": "interviewer@1"})
    first, second = log[0]["config"], log[1]["config"]
    assert first["metadata"] == {
        "role": "interviewer", "session_id": "s1", "node": "interviewer_agent", "item_index": 2,
        "prompt": "interviewer@1", "model_id": "primary", "attempt": 1, "fallback": False,
    }
    assert second["metadata"]["attempt"] == 2
    assert first["tags"] == ["role:interviewer", "prompt:interviewer@1"]


def test_hooks_called_and_guardrail_violation_falls_back(monkeypatch):
    seen = []

    def before(role, messages, meta):
        seen.append(("before", role, meta["model_id"]))

    def after(role, output, meta):
        seen.append(("after", meta["model_id"], output.content))
        if output.content == "bad":
            raise llm.GuardrailViolation("언어 규칙 위반")

    monkeypatch.setattr(llm, "before_call_hooks", [before])
    monkeypatch.setattr(llm, "after_call_hooks", [after])
    call, log, sleeps = make({"primary": [AIMessage("bad")], "fallback": [AIMessage("good")]})
    assert call().content == "good"
    assert seen == [("before", "interviewer", "primary"), ("after", "primary", "bad"),
                    ("before", "interviewer", "fallback"), ("after", "fallback", "good")]
    assert sleeps == []


def test_hooks_are_empty_by_default():
    assert llm.before_call_hooks == [] and llm.after_call_hooks == []


def test_logs_fallback(caplog):
    call, _, _ = make({"primary": [RuntimeError("x")], "fallback": [AIMessage("ok")]})
    with caplog.at_level(logging.INFO, logger="opic.llm"):
        call()
    text = caplog.text
    assert "model=primary" in text and "model=fallback fallback=True" in text


# ── 기타 ───────────────────────────────────────────────────────────
def test_unknown_role():
    with pytest.raises(ValueError):
        llm.invoke_llm("supervisor", MSGS, settings=SETTINGS, factory=lambda *a: None)


def test_backoff_delay():
    assert [llm.backoff_delay(i) for i in range(3)] == [1.0, 2.0, 4.0]


def test_role_config_scorer_temperature_zero():
    assert set(llm.ROLE_CONFIG) == {"survey", "interviewer", "scorer", "feedback"}
    assert llm.ROLE_CONFIG["scorer"].temperature == 0.0


def test_set_model_factory_and_reset():
    call_log = []

    def factory(model_id, role, settings):
        call_log.append(model_id)
        return FakeModel(model_id, [AIMessage("x")], [])

    llm.set_model_factory(factory)
    try:
        assert llm.invoke_llm("feedback", MSGS, settings=SETTINGS).content == "x"
    finally:
        llm.set_model_factory(None)
    assert call_log == ["primary"] and llm._model_factory is llm.bedrock_model_factory


def test_bedrock_factory_builds_without_network():
    settings = load_settings({"AWS_REGION": "us-east-1"})
    model = llm.bedrock_model_factory(settings.model_primary, "scorer", settings)
    assert model.model_id == "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    assert model.temperature == 0.0 and model.max_tokens == 512
    assert model.client.meta.config.retries["total_max_attempts"] == 1  # botocore 자체 재시도 끔
