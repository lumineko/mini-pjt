"""그래프 조건 분기 (SERVICE §3 엣지/분기 조건). 슈퍼바이저 없이 파이썬 함수만 다음 노드를 정한다.

- 분기 함수는 LLM 출력을 보지 않고, State의 파이썬 계산값(문항 수, 검증 결과, 조정 제안·응답)만 본다.
- 위에서부터 평가하고 처음 맞는 조건이 이긴다.
- 방어 처리: 검증 오류가 없어도 필요한 값이 비어 있으면 같은 입력 노드로 되돌린다.
"""

import logging
from collections.abc import Mapping
from typing import Any, Literal

from opic.rules.difficulty import CHECK_AFTER_ITEMS
from opic.state import SESSION_ITEMS

logger = logging.getLogger(__name__)

# 노드 이름 (graph.py와 공유)
SURVEY_AGENT = "survey_agent"
ASK_SURVEY_AND_LEVEL = "ask_survey_and_level"
INTERVIEWER_AGENT = "interviewer_agent"
AWAIT_ANSWER = "await_answer"
SCORER_AGENT = "scorer_agent"
SCORE_AND_GRADE = "score_and_grade"
FEEDBACK_AGENT = "feedback_agent"
RECORD_ITEM = "record_item"
SHOW_FEEDBACK = "show_feedback"
CHECK_DIFFICULTY = "check_difficulty"
CONFIRM_ADJUST = "confirm_adjust"
APPLY_LEVEL = "apply_level"
SUMMARIZE = "summarize"
SAVE_SESSION = "save_session"

State = Mapping[str, Any]


def _log(name: str, target: str) -> str:
    logger.info("라우팅 %s → %s", name, target)
    return target


def route_after_survey(state: State) -> Literal["ask_survey_and_level", "interviewer_agent"]:
    if state.get("survey_error") or not state.get("survey_answers") or not state.get("current_level") or not state.get("topic_plan"):
        return _log("route_after_survey", ASK_SURVEY_AND_LEVEL)
    return _log("route_after_survey", INTERVIEWER_AGENT)


def route_after_answer(state: State) -> Literal["await_answer", "scorer_agent"]:
    if state.get("answer_error") or not state.get("current_answer") or not state.get("pending"):
        return _log("route_after_answer", AWAIT_ANSWER)
    return _log("route_after_answer", SCORER_AGENT)


def route_after_feedback(state: State) -> Literal["summarize", "check_difficulty", "interviewer_agent"]:
    done = len(state.get("items") or [])
    if done >= SESSION_ITEMS:
        return _log("route_after_feedback", SUMMARIZE)
    if done == CHECK_AFTER_ITEMS and not state.get("difficulty_checked"):
        return _log("route_after_feedback", CHECK_DIFFICULTY)
    return _log("route_after_feedback", INTERVIEWER_AGENT)


def route_after_check(state: State) -> Literal["confirm_adjust", "interviewer_agent"]:
    if state.get("adjust_proposal"):
        return _log("route_after_check", CONFIRM_ADJUST)
    return _log("route_after_check", INTERVIEWER_AGENT)


def route_after_confirm(state: State) -> Literal["apply_level", "interviewer_agent"]:
    if state.get("adjust_response") is True and state.get("adjust_proposal") and not state.get("adjust_applied"):
        return _log("route_after_confirm", APPLY_LEVEL)
    return _log("route_after_confirm", INTERVIEWER_AGENT)


# graph.add_conditional_edges(출발 노드, 함수, path_map)에 그대로 쓴다
CONDITIONAL_EDGES = {
    ASK_SURVEY_AND_LEVEL: (route_after_survey, [ASK_SURVEY_AND_LEVEL, INTERVIEWER_AGENT]),
    AWAIT_ANSWER: (route_after_answer, [AWAIT_ANSWER, SCORER_AGENT]),
    SHOW_FEEDBACK: (route_after_feedback, [SUMMARIZE, CHECK_DIFFICULTY, INTERVIEWER_AGENT]),
    CHECK_DIFFICULTY: (route_after_check, [CONFIRM_ADJUST, INTERVIEWER_AGENT]),
    CONFIRM_ADJUST: (route_after_confirm, [APPLY_LEVEL, INTERVIEWER_AGENT]),
}
