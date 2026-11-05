"""trace.py 테스트 (SERVICE §13, Phase 6). 가짜 모델만 쓰고 Bedrock은 호출하지 않는다."""

from botocore.exceptions import ClientError
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from opic import llm, trace
from opic.config import ROOT_DIR, load_settings

MSGS = [HumanMessage("SECRET ANSWER TEXT")]


class Scores(BaseModel):
    grammar: int = Field(ge=1, le=5)


def settings(tmp_path, **env):
    base = {"MODEL_PRIMARY": "primary", "MODEL_FALLBACKS": "fallback", "LLM_MAX_RETRIES": "1",
            "TRACE_FILE": str(tmp_path / "traces.jsonl")}
    return load_settings({**base, **env})


def factory_for(outcomes):
    outcomes = list(outcomes)

    class Model:
        def __init__(self, schema=None):
            self.schema = schema

        def with_structured_output(self, schema):
            return Model(schema)

        def invoke(self, messages, config=None):
            outcome = outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return self.schema.model_validate(outcome) if self.schema else AIMessage(outcome)

    return lambda model_id, role, s: Model()


def throttle():
    return ClientError({"Error": {"Code": "ThrottlingException"}, "ResponseMetadata": {"HTTPStatusCode": 400}}, "Converse")


META = {"session_id": "s1", "node": "scorer_agent", "item_index": 2, "prompt": "scorer@2"}


# ── 설정 ───────────────────────────────────────────────────────────
def test_trace_file_default_and_off(tmp_path):
    assert load_settings({}).trace_file.name == "traces.jsonl"
    assert load_settings({}).trace_file.parent.name == "logs"
    for off in ("off", "OFF", "none", "false", "0"):
        assert load_settings({"TRACE_FILE": off}).trace_file is None
    assert settings(tmp_path).trace_file == tmp_path / "traces.jsonl"


# ── 설치 ───────────────────────────────────────────────────────────
def test_install_is_idempotent(tmp_path):
    s = settings(tmp_path)
    trace.install(s)
    trace.install(s)
    assert sum(trace._is_recorder_hook(h) for h in llm.after_call_hooks) == 1
    assert sum(trace._is_recorder_hook(h) for h in llm.error_call_hooks) == 1


def test_install_off_registers_nothing(tmp_path):
    trace.install(settings(tmp_path))
    assert trace.install(settings(tmp_path, TRACE_FILE="off")) is None
    assert not any(trace._is_recorder_hook(h) for h in llm.after_call_hooks + llm.error_call_hooks)


def test_uninstall_keeps_other_hooks(tmp_path):
    other = lambda role, output, meta: None  # noqa: E731
    llm.after_call_hooks.append(other)
    trace.install(settings(tmp_path))
    trace.uninstall()
    assert llm.after_call_hooks == [other]


# ── 기록 내용 ──────────────────────────────────────────────────────
def test_success_record_has_metadata_and_output_but_no_input(tmp_path):
    s = settings(tmp_path)
    trace.install(s)
    llm.invoke_llm("scorer", MSGS, schema=Scores, metadata=META, settings=s, factory=factory_for([{"grammar": 4}]))

    [rec] = trace.read_traces(s.trace_file)
    assert rec["status"] == "ok"
    assert rec["output"] == {"grammar": 4}
    assert {k: rec[k] for k in ("session_id", "node", "item_index", "prompt", "role")} == {**META, "role": "scorer"}
    assert rec["model_id"] == "primary" and rec["attempt"] == 1 and rec["fallback"] is False
    assert isinstance(rec["elapsed_ms"], int) and rec["elapsed_ms"] >= 0
    assert rec["ts"]
    assert "SECRET ANSWER TEXT" not in s.trace_file.read_text(encoding="utf-8")


def test_plain_message_output_is_content(tmp_path):
    s = settings(tmp_path)
    trace.install(s)
    llm.invoke_llm("interviewer", MSGS, settings=s, factory=factory_for(["Hello there"]))
    assert trace.read_traces(s.trace_file)[0]["output"] == "Hello there"


def test_every_attempt_recorded_through_retry_and_fallback(tmp_path):
    s = settings(tmp_path)
    trace.install(s)
    outcomes = [throttle(), throttle(), {"grammar": 9}, {"grammar": 3}]  # 기본 2번 스로틀 → 폴백 검증 실패 → ...
    # 기본: 스로틀(재시도) → 스로틀(재시도 끝) / 폴백: 검증 실패 → 모두 실패가 아니라 마지막 성공이 되도록 재시도 1회 허용
    outcomes = [throttle(), throttle(), {"grammar": 3}]
    llm.invoke_llm("scorer", MSGS, schema=Scores, metadata=META, settings=s, factory=factory_for(outcomes),
                   sleep=lambda _: None)

    recs = trace.read_traces(s.trace_file)
    assert [r["status"] for r in recs] == ["error", "error", "ok"]
    assert [r["attempt"] for r in recs] == [1, 2, 3]
    assert [r["fallback"] for r in recs] == [False, False, True]
    assert [r["model_id"] for r in recs] == ["primary", "primary", "fallback"]
    assert recs[0]["error"]["type"] == "ClientError"
    assert "ThrottlingException" in recs[0]["error"]["message"]


def test_structured_failure_recorded_as_error(tmp_path):
    s = settings(tmp_path)
    trace.install(s)
    llm.invoke_llm("scorer", MSGS, schema=Scores, settings=s, factory=factory_for([{"grammar": 9}, {"grammar": 2}]))
    recs = trace.read_traces(s.trace_file)
    assert [r["status"] for r in recs] == ["error", "ok"]
    assert recs[0]["error"]["type"] == "ValidationError"


def test_guardrail_before_trace_records_error_not_ok(tmp_path):
    def reject_first(role, output, meta):
        if meta["attempt"] == 1:
            raise llm.GuardrailViolation("bad output")

    llm.after_call_hooks.append(reject_first)
    s = settings(tmp_path)
    trace.install(s)  # 기록기는 맨 끝
    llm.invoke_llm("interviewer", MSGS, settings=s, factory=factory_for(["first", "second"]))
    recs = trace.read_traces(s.trace_file)
    assert [r["status"] for r in recs] == ["error", "ok"]
    assert recs[0]["error"] == {"type": "GuardrailViolation", "message": "bad output"}
    assert recs[1]["output"] == "second"


def test_write_failure_does_not_break_call(tmp_path, caplog):
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not a dir")
    s = settings(tmp_path, TRACE_FILE=str(blocker / "traces.jsonl"))
    trace.install(s)
    out = llm.invoke_llm("interviewer", MSGS, settings=s, factory=factory_for(["ok"]))
    assert out.content == "ok"
    assert "트레이스 기록 실패" in caplog.text


def test_error_hook_exception_is_swallowed(tmp_path):
    def boom(role, exc, meta):
        raise RuntimeError("hook broke")

    llm.error_call_hooks.append(boom)
    s = settings(tmp_path)
    out = llm.invoke_llm("scorer", MSGS, schema=Scores, settings=s, factory=factory_for([{"grammar": 9}, {"grammar": 2}]))
    assert out.grammar == 2


def test_read_traces_skips_broken_lines(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text('{"a": 1}\nnot json\n{"b": 2}\n', encoding="utf-8")
    assert trace.read_traces(path) == [{"a": 1}, {"b": 2}]
    assert trace.read_traces(tmp_path / "missing.jsonl") == []


# ── 그래프 연동 (에이전트 메타데이터가 기록에 남는지) ─────────────
def test_graph_session_writes_traces_with_node_metadata(fake_llm, tmp_path, monkeypatch):
    from opic import graph as g

    monkeypatch.setenv("HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("SURVEY_FILE", str(ROOT_DIR / "opic_survey.md"))
    s = settings(tmp_path)
    trace.install(s)
    fake_llm.push({"question": "Tell me about your favorite park in detail.", "question_type": "묘사"})
    graph = g.build_graph()
    sid, payload = g.start_session(graph)
    answers = {item["id"]: [item["options"][0]["label"]] for item in payload["items"]}
    g.resume(sid, {"answers": answers, "level": "IM"}, graph)

    [rec] = [r for r in trace.read_traces(s.trace_file) if r["session_id"] == sid]
    assert rec["node"] == "interviewer_agent"
    assert rec["item_index"] == 1
    assert rec["prompt"].startswith("interviewer@")
    assert rec["output"].get("question_type") == "묘사"
