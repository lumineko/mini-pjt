"""공용 fixture (SERVICE §14.1). 실제 LLM은 호출하지 않는다."""

import pytest
from langchain_core.messages import AIMessage

from opic import llm


class FakeLLM:
    """llm.set_model_factory에 끼우는 가짜 모델.

    outcomes를 순서대로 소비한다 (모든 모델 id가 같은 큐를 공유하므로 폴백도 다음 항목을 받는다).
    - dict: 구조화 출력 스키마로 검증해 돌려준다(검증 실패 → invoke_llm이 다음 모델로)
    - str: AIMessage
    - 예외: 그대로 던진다
    호출 기록은 calls에 남는다: {model_id, role, schema, messages, metadata}.
    """

    def __init__(self):
        self.outcomes: list = []
        self.calls: list[dict] = []

    def push(self, *outcomes):
        self.outcomes.extend(outcomes)
        return self

    def factory(self, model_id, role, settings):
        return _FakeRunnable(self, model_id, role)

    def last(self, role=None):
        calls = [c for c in self.calls if role is None or c["role"] == role]
        return calls[-1]

    def system_text(self, role=None):
        return self.last(role)["messages"][0].content

    def user_text(self, role=None):
        return self.last(role)["messages"][1].content


class _FakeRunnable:
    def __init__(self, fake, model_id, role, schema=None):
        self.fake, self.model_id, self.role, self.schema = fake, model_id, role, schema

    def with_structured_output(self, schema):
        return _FakeRunnable(self.fake, self.model_id, self.role, schema)

    def invoke(self, messages, config=None):
        self.fake.calls.append({
            "model_id": self.model_id, "role": self.role, "schema": self.schema,
            "messages": messages, "metadata": (config or {}).get("metadata", {}),
        })
        if not self.fake.outcomes:
            raise AssertionError(f"FakeLLM 응답이 더 없습니다 (role={self.role})")
        outcome = self.fake.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, dict):
            return self.schema.model_validate(outcome) if self.schema else AIMessage(str(outcome))
        return AIMessage(outcome)


@pytest.fixture(autouse=True)
def _restore_llm_hooks():
    """훅 목록은 모듈 전역이라, 테스트(예: app.py가 트레이스를 설치)가 남긴 훅을 되돌린다."""
    saved = [list(h) for h in (llm.before_call_hooks, llm.after_call_hooks, llm.error_call_hooks)]
    yield
    for hooks, original in zip((llm.before_call_hooks, llm.after_call_hooks, llm.error_call_hooks), saved):
        hooks[:] = original


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    llm.set_model_factory(fake.factory)
    monkeypatch.setattr(llm, "_sleep", lambda s: None)
    monkeypatch.setenv("MODEL_PRIMARY", "fake-primary")
    monkeypatch.setenv("MODEL_FALLBACKS", "fake-fallback")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    yield fake
    llm.set_model_factory(None)
