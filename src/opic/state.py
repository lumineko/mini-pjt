"""그래프 State와 하위 타입 정의 (SERVICE.md §3 State, §4 interrupt kind).

- LangGraph State는 TypedDict로 정의한다. 노드는 바뀐 필드만 담은 dict를 반환한다.
- LLM 구조화 출력용 Pydantic 모델은 각 에이전트 모듈에 둔다(여기에는 State 타입만).
- 계산 로직은 넣지 않는다(rules/). 상수와 초기 State 생성만 둔다.
- `from __future__ import annotations`를 쓰지 않는다: TypedDict의 NotRequired 판정이 런타임에 동작해야 한다.
"""

from typing import Literal, NotRequired, TypedDict

# ── 레벨·등급 ──────────────────────────────────────────────────────
Level = Literal["IL", "IM", "IH", "AL"]
Grade = Literal["IL 미달", "IL", "IM", "IH", "AL"]

LEVELS: tuple[Level, ...] = ("IL", "IM", "IH", "AL")
BELOW_LOWEST: Grade = "IL 미달"
# 낮은 순서. 순서값 = 인덱스 (IL 미달=0 … AL=4, PRD F-11)
GRADES: tuple[Grade, ...] = (BELOW_LOWEST, *LEVELS)

SESSION_ITEMS = 5  # 한 세션 문항 수 (PRD F-11)

SurveySource = Literal["file", "fallback"]
SurveyKind = Literal["profile", "topic"]
Direction = Literal["up", "down"]
InterruptKind = Literal["survey", "answer", "feedback", "adjust"]


# ── 설문 ───────────────────────────────────────────────────────────
class SurveyOption(TypedDict):
    label: str  # ★를 뗀 보기 이름
    recommend: int  # ★ 개수 0~3 (표시만, 미리 선택하지 않음)


class SurveyItem(TypedDict):
    id: str
    topic: str
    kind: SurveyKind  # profile: 단일 선택·주제 배정 제외 / topic: 1개 이상 선택
    question: str
    options: list[SurveyOption]


# ── 레벨 변경 ──────────────────────────────────────────────────────
# "from"이 예약어라 함수형 문법으로 정의한다.
LevelChange = TypedDict("LevelChange", {"after_item": int, "from": Level, "to": Level})


class AdjustProposal(TypedDict):
    direction: Direction
    suggested_level: Level


# ── 문항 처리 ──────────────────────────────────────────────────────
class KoreanSpan(TypedDict):
    start: int  # 답변 문자열 기준 시작 인덱스
    end: int  # 끝 인덱스 (미포함)
    text: str


class Grading(TypedDict):
    """score_and_grade(Python) 결과."""

    weighted_score: float
    penalty: float
    final_score: float
    raw_grade: Grade  # 상한 적용 전
    grade: Grade  # 출제 레벨 +1 상한 적용 후
    achieved: bool  # grade >= 현재 목표 레벨


class Correction(TypedDict):
    original: str  # 오류 문장 (영어)
    corrected: str  # 교정 문장 (영어)
    reason: str  # 교정 이유 (한국어)


class Feedback(TypedDict):
    """feedback_agent(LLM) 결과."""

    corrections: list[Correction]  # 빈 목록이면 UI에 "교정 사항 없음"
    alternatives: list[str]  # 1개 이상 (영어)
    translation: str | None  # 한글 구간이 있을 때만 (영어)


class Pending(TypedDict):
    """처리 중인 문항. await_answer가 만들고 record_item이 비운다."""

    korean_ratio: float  # 유일한 출처 (await_answer에서 한 번만 계산)
    korean_spans: list[KoreanSpan]
    pii_types: NotRequired[list[str]]  # 가린 개인정보 종류 (rules.input_guard.mask_pii)
    injection_flags: NotRequired[list[str]]  # 인젝션 의심 규칙 이름 (표시만, rules.input_guard.detect_injection)
    rubric_scores: NotRequired[dict[str, int]]  # scorer_agent
    grading: NotRequired[Grading]  # score_and_grade
    feedback: NotRequired[Feedback]  # feedback_agent


class ItemResult(TypedDict):
    """완료 문항 (record_item이 만들어 items에 추가)."""

    question: str
    question_type: str
    topic: str
    level: Level  # 출제 레벨
    answer: str  # 개인정보를 가린 답변
    korean_ratio: float
    pii_types: list[str]
    injection_flags: list[str]
    rubric_scores: dict[str, int]
    weighted_score: float
    penalty: float
    final_score: float
    raw_grade: Grade
    grade: Grade
    achieved: bool
    corrections: list[Correction]
    alternatives: list[str]
    translation: str | None


class SessionSummary(TypedDict):
    item_grades: list[Grade]
    average_grade: Grade  # 순서값 평균 반올림 (PRD F-11)
    initial_level: Level
    final_level: Level
    level_changed: bool


# ── 세션 State ─────────────────────────────────────────────────────
class SessionState(TypedDict):
    session_id: str  # = checkpointer thread_id
    started_at: str  # ISO 시각
    survey_source: SurveySource | None
    survey_notice: str | None
    survey_items: list[SurveyItem]
    survey_answers: dict[str, list[str]]
    survey_error: str | None
    topic_plan: list[str]
    initial_level: Level | None
    current_level: Level | None
    level_history: list[LevelChange]
    current_question: str | None
    current_question_type: str | None
    current_answer: str | None
    answer_error: str | None
    pending: Pending | None
    items: list[ItemResult]
    difficulty_checked: bool
    adjust_proposal: AdjustProposal | None
    adjust_response: bool | None
    adjust_applied: bool
    summary: SessionSummary | None
    done: bool


def new_session_state(session_id: str, started_at: str) -> SessionState:
    """모든 필드를 채운 초기 State (설문·레벨 선택 전)."""
    return SessionState(
        session_id=session_id,
        started_at=started_at,
        survey_source=None,
        survey_notice=None,
        survey_items=[],
        survey_answers={},
        survey_error=None,
        topic_plan=[],
        initial_level=None,
        current_level=None,
        level_history=[],
        current_question=None,
        current_question_type=None,
        current_answer=None,
        answer_error=None,
        pending=None,
        items=[],
        difficulty_checked=False,
        adjust_proposal=None,
        adjust_response=None,
        adjust_applied=False,
        summary=None,
        done=False,
    )
