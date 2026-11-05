"""LangGraph 고정 순서 워크플로 조립과 UI용 API (SERVICE §1, §3, §4).

- 노드 순서는 고정 엣지로, 분기 4곳은 routing.py 파이썬 함수로 정한다(슈퍼바이저 없음).
- HITL 노드는 `interrupt(payload)`로 멈추고 `Command(resume=값)`으로 이어 간다.
  LangGraph는 재개할 때 노드를 처음부터 다시 실행하므로, HITL 노드는 interrupt 전에 부작용이 없고
  입력 처리는 순수 함수(`apply_*`)로 분리한다.
- 체크포인터는 MemorySaver(thread_id = session_id). 5문항을 마친 세션만 JSON으로 저장한다(F-09).
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from opic import routing as r
from opic.agents import feedback, interviewer, scorer, survey
from opic.config import load_settings
from opic.rules.difficulty import CHECK_AFTER_ITEMS, apply_adjustment, propose_adjustment
from opic.rules.scoring import average_grade, grade_answer, load_rubric
from opic.rules.summary import summarize
from opic.rules.topic import assign_topics
from opic.rules.validation import validate_answer, validate_level, validate_survey_answers
from opic.state import LEVELS, SESSION_ITEMS, ItemResult, Pending, SessionState, new_session_state
from opic.storage import save_session
from opic.tools.korean import detect_korean

logger = logging.getLogger(__name__)


# ── 입력 처리 (순수 함수, HITL 노드에서 사용) ──────────────────────
def apply_survey_submission(state, value: Any) -> dict:
    """설문·레벨 제출값 {answers: {id: [보기]}, level} 검증 → State 변경분."""
    value = value if isinstance(value, dict) else {}
    answers = value.get("answers")
    level = value.get("level")
    if not isinstance(answers, dict):
        return {"survey_error": "설문 응답 형식이 올바르지 않습니다."}
    error = validate_survey_answers(state["survey_items"], answers) or validate_level(level)
    if error:
        return {"survey_error": error}
    answers = {k: list(v) for k, v in answers.items()}
    return {
        "survey_answers": answers,
        "initial_level": level,
        "current_level": level,
        "topic_plan": assign_topics(state["survey_items"], answers, SESSION_ITEMS),
        "survey_error": None,
    }


def apply_answer_submission(state, text: Any, min_words: int) -> dict:
    """답변 제출 → 검증 통과 시 current_answer와 pending(한글 비율, 유일한 출처) 생성."""
    text = text if isinstance(text, str) else None
    error = validate_answer(text, min_words)
    if error:
        return {"answer_error": error}
    text = text.strip()
    korean = detect_korean(text)
    return {
        "current_answer": text,
        "pending": Pending(korean_ratio=korean["ratio"], korean_spans=korean["spans"]),
        "answer_error": None,
    }


def build_item(state) -> ItemResult:
    pending = state["pending"]
    grading = pending["grading"]
    fb = pending["feedback"]
    return ItemResult(
        question=state["current_question"],
        question_type=state["current_question_type"],
        topic=state["topic_plan"][len(state["items"])],
        level=state["current_level"],
        answer=state["current_answer"],
        korean_ratio=pending["korean_ratio"],
        rubric_scores=pending["rubric_scores"],
        weighted_score=grading["weighted_score"],
        penalty=grading["penalty"],
        final_score=grading["final_score"],
        raw_grade=grading["raw_grade"],
        grade=grading["grade"],
        achieved=grading["achieved"],
        corrections=fb["corrections"],
        alternatives=fb["alternatives"],
        translation=fb["translation"],
    )


# ── HITL 노드 ──────────────────────────────────────────────────────
def ask_survey_and_level(state: SessionState) -> dict:
    value = interrupt({
        "kind": "survey",
        "notice": state["survey_notice"],
        "source": state["survey_source"],
        "items": state["survey_items"],
        "levels": list(LEVELS),
        "error": state["survey_error"],
    })
    return apply_survey_submission(state, value)


def await_answer(state: SessionState) -> dict:
    min_words = load_rubric()["min_words"]
    text = interrupt({
        "kind": "answer",
        "item_index": len(state["items"]) + 1,
        "total": SESSION_ITEMS,
        "level": state["current_level"],
        "question": state["current_question"],
        "question_type": state["current_question_type"],
        "min_words": min_words,
        "error": state["answer_error"],
    })
    return apply_answer_submission(state, text, min_words)


def show_feedback(state: SessionState) -> dict:
    n = len(state["items"])
    interrupt({
        "kind": "feedback",
        "item_index": n,
        "total": SESSION_ITEMS,
        "item": state["items"][-1],
        "is_last": n >= SESSION_ITEMS,
    })
    return {}


def confirm_adjust(state: SessionState) -> dict:
    accepted = interrupt({
        "kind": "adjust",
        "average_grade": average_grade([i["grade"] for i in state["items"][:CHECK_AFTER_ITEMS]]),
        "current_level": state["current_level"],
        "proposal": state["adjust_proposal"],
    })
    return {"adjust_response": accepted is True}


# ── 파이썬 노드 ────────────────────────────────────────────────────
def score_and_grade(state: SessionState) -> dict:
    pending = state["pending"]
    grading = grade_answer(pending["rubric_scores"], pending["korean_ratio"], state["current_level"], load_rubric())
    return {"pending": {**pending, "grading": grading}}


def record_item(state: SessionState) -> dict:
    return {
        "items": [*state["items"], build_item(state)],
        "pending": None,
        "current_question": None,
        "current_question_type": None,
        "current_answer": None,
    }


def check_difficulty(state: SessionState) -> dict:
    grades = [i["grade"] for i in state["items"][:CHECK_AFTER_ITEMS]]
    proposal = propose_adjustment(grades, state["current_level"])
    logger.info("난이도 점검: 평균 %s, 목표 %s, 제안 %s", average_grade(grades), state["current_level"], proposal)
    return {"difficulty_checked": True, "adjust_proposal": proposal}


def apply_level(state: SessionState) -> dict:
    new_level, change = apply_adjustment(state["current_level"], state["adjust_proposal"], len(state["items"]))
    logger.info("난이도 조정: %s → %s (%d문항 후)", change["from"], change["to"], change["after_item"])
    return {"current_level": new_level, "level_history": [*state["level_history"], change], "adjust_applied": True}


def summarize_node(state: SessionState) -> dict:
    return {"summary": summarize(state["items"], state["initial_level"], state["level_history"])}


def save_session_node(state: SessionState) -> dict:
    save_session(state, load_settings().history_dir)
    return {"done": True}


# ── 그래프 조립 ────────────────────────────────────────────────────
NODES = {
    r.SURVEY_AGENT: survey.run,
    r.ASK_SURVEY_AND_LEVEL: ask_survey_and_level,
    r.INTERVIEWER_AGENT: interviewer.run,
    r.AWAIT_ANSWER: await_answer,
    r.SCORER_AGENT: scorer.run,
    r.SCORE_AND_GRADE: score_and_grade,
    r.FEEDBACK_AGENT: feedback.run,
    r.RECORD_ITEM: record_item,
    r.SHOW_FEEDBACK: show_feedback,
    r.CHECK_DIFFICULTY: check_difficulty,
    r.CONFIRM_ADJUST: confirm_adjust,
    r.APPLY_LEVEL: apply_level,
    r.SUMMARIZE: summarize_node,
    r.SAVE_SESSION: save_session_node,
}

FIXED_EDGES = [
    (START, r.SURVEY_AGENT),
    (r.SURVEY_AGENT, r.ASK_SURVEY_AND_LEVEL),
    (r.INTERVIEWER_AGENT, r.AWAIT_ANSWER),
    (r.SCORER_AGENT, r.SCORE_AND_GRADE),
    (r.SCORE_AND_GRADE, r.FEEDBACK_AGENT),
    (r.FEEDBACK_AGENT, r.RECORD_ITEM),
    (r.RECORD_ITEM, r.SHOW_FEEDBACK),
    (r.APPLY_LEVEL, r.INTERVIEWER_AGENT),
    (r.SUMMARIZE, r.SAVE_SESSION),
    (r.SAVE_SESSION, END),
]


def build_graph(checkpointer=None):
    builder = StateGraph(SessionState)
    for name, fn in NODES.items():
        builder.add_node(name, fn)
    for src, dst in FIXED_EDGES:
        builder.add_edge(src, dst)
    for src, (fn, targets) in r.CONDITIONAL_EDGES.items():
        builder.add_conditional_edges(src, fn, targets)
    return builder.compile(checkpointer=checkpointer or MemorySaver())


# ── UI용 API (SERVICE §4) ──────────────────────────────────────────
_default_graph = None


def get_graph():
    """프로세스당 그래프 1개 (Streamlit은 @st.cache_resource로 감싼다)."""
    global _default_graph
    if _default_graph is None:
        _default_graph = build_graph()
    return _default_graph


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _payload(graph, session_id: str, result: dict) -> dict:
    interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
    if interrupts:
        return interrupts[0].value
    state = graph.get_state(_config(session_id)).values
    return {"kind": "done", "session_id": session_id, "summary": state.get("summary")}


def new_session_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def start_session(graph=None, session_id: str | None = None) -> tuple[str, dict]:
    """새 세션을 시작해 첫 interrupt(설문)까지 진행한다."""
    graph = graph or get_graph()
    session_id = session_id or new_session_id()
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    logger.info("세션 시작: %s", session_id)
    result = graph.invoke(new_session_state(session_id, started_at), _config(session_id))
    return session_id, _payload(graph, session_id, result)


def resume(session_id: str, value: Any, graph=None) -> dict:
    """interrupt에 값을 넘겨 다음 interrupt 또는 종료까지 진행한다."""
    graph = graph or get_graph()
    result = graph.invoke(Command(resume=value), _config(session_id))
    return _payload(graph, session_id, result)


def retry(session_id: str, graph=None) -> dict:
    """오류(LLMError 등) 뒤 마지막 체크포인트부터 다시 실행한다."""
    graph = graph or get_graph()
    result = graph.invoke(None, _config(session_id))
    return _payload(graph, session_id, result)


def get_state(session_id: str, graph=None) -> dict:
    graph = graph or get_graph()
    return graph.get_state(_config(session_id)).values


def current_payload(session_id: str, graph=None) -> dict | None:
    """화면을 다시 그릴 때 지금 기다리는 interrupt 값 (없으면 None)."""
    graph = graph or get_graph()
    snapshot = graph.get_state(_config(session_id))
    for task in snapshot.tasks:
        if task.interrupts:
            return task.interrupts[0].value
    return None
