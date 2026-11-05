"""공용 샘플 세션 State (저장·그래프 테스트에서 재사용)."""

from opic.state import new_session_state


def make_item(i, grade="IM", level="IM", topic="조깅", question_type="묘사"):
    return {
        "question": f"Question {i}?",
        "question_type": question_type,
        "topic": topic,
        "level": level,
        "answer": f"My answer number {i} is here.",
        "korean_ratio": 0.0,
        "rubric_scores": {"grammar": 3, "vocabulary": 3, "organization": 3, "task": 3},
        "weighted_score": 3.0,
        "penalty": 0.0,
        "final_score": 3.0,
        "raw_grade": grade,
        "grade": grade,
        "achieved": True,
        "corrections": [],
        "alternatives": ["An alternative sentence."],
        "translation": None,
    }


def completed_state(session_id="s-001", started_at="2026-11-05T10:00:00+09:00", initial="IM", final="IM", avg="IM"):
    state = new_session_state(session_id, started_at)
    history = [] if initial == final else [{"after_item": 3, "from": initial, "to": final}]
    state.update(
        survey_source="file",
        survey_answers={"운동-1": ["조깅"]},
        initial_level=initial,
        current_level=final,
        level_history=history,
        items=[make_item(i) for i in range(1, 6)],
        difficulty_checked=True,
        summary={
            "item_grades": ["IM"] * 5,
            "average_grade": avg,
            "initial_level": initial,
            "final_level": final,
            "level_changed": initial != final,
        },
        # 저장에서 빠져야 하는 진행용 필드
        current_question="leftover?",
        pending=None,
    )
    return state
