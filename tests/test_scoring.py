"""rules/scoring.py 테스트 (PRD 성공 기준 2·8).

수치 기대값은 테스트 전용 고정 루브릭으로 계산한다. data/rubric.json 값이 조정돼도 이 테스트는 깨지지 않는다.
실제 파일과의 호환은 마지막 테스트에서만 확인한다.
"""

import pytest

from opic.rules import scoring as sc

RUBRIC = {
    "items": [
        {"key": "grammar", "weight": 0.3},
        {"key": "vocabulary", "weight": 0.25},
        {"key": "organization", "weight": 0.2},
        {"key": "task", "weight": 0.25},
    ],
    "scale": {"min": 1, "max": 5},
    "grade_bands": [
        {"grade": "AL", "min": 4.5},
        {"grade": "IH", "min": 3.7},
        {"grade": "IM", "min": 2.8},
        {"grade": "IL", "min": 2.0},
    ],
    "below_lowest": "IL 미달",
    "grade_cap_offset": 1,
    "korean": {"penalty_per_10pct": 0.2, "fail_threshold": 0.8},
    "min_words": 5,
}


def scores(g, v, o, t):
    return {"grammar": g, "vocabulary": v, "organization": o, "task": t}


# ── 가중 합산 ──────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "s, expected",
    [
        (scores(5, 5, 5, 5), 5.0),
        (scores(1, 1, 1, 1), 1.0),
        (scores(4, 3, 4, 4), 3.75),
        (scores(3, 4, 4, 4), 3.7),  # 부동소수 합은 3.6999…
    ],
)
def test_weighted_score(s, expected):
    assert sc.weighted_score(s, RUBRIC) == expected


@pytest.mark.parametrize(
    "bad",
    [
        {"grammar": 3, "vocabulary": 3, "organization": 3},  # 항목 누락
        {**scores(3, 3, 3, 3), "fluency": 3},  # 항목 추가
        scores(0, 3, 3, 3),  # 척도 아래
        scores(6, 3, 3, 3),  # 척도 위
        scores(3.5, 3, 3, 3),  # 정수 아님
        scores(True, 3, 3, 3),  # bool은 정수로 보지 않음
    ],
)
def test_weighted_score_rejects_invalid(bad):
    with pytest.raises(ValueError):
        sc.weighted_score(bad, RUBRIC)


# ── 한글 감점 ──────────────────────────────────────────────────────
@pytest.mark.parametrize("ratio, expected", [(0, 0.0), (0.1, 0.2), (0.25, 0.5), (0.5, 1.0), (1.0, 2.0)])
def test_korean_penalty_is_proportional(ratio, expected):
    assert sc.korean_penalty(ratio, RUBRIC) == expected


@pytest.mark.parametrize("ratio, fail", [(0.79, False), (0.8, True), (1.0, True)])
def test_korean_fail_threshold(ratio, fail):
    assert sc.is_korean_fail(ratio, RUBRIC) is fail


@pytest.mark.parametrize("ratio", [-0.1, 1.1, float("nan")])
def test_korean_ratio_out_of_range(ratio):
    with pytest.raises(ValueError):
        sc.korean_penalty(ratio, RUBRIC)


# ── 등급 구간 ──────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "score, grade",
    [
        (5.0, "AL"), (4.5, "AL"), (4.49, "IH"), (3.7, "IH"), (3.69, "IM"),
        (2.8, "IM"), (2.79, "IL"), (2.0, "IL"), (1.99, "IL 미달"), (-1.0, "IL 미달"),
        (3.6999999999, "IH"),  # 반올림 후 비교
    ],
)
def test_grade_from_score_boundaries(score, grade):
    assert sc.grade_from_score(score, RUBRIC) == grade


# ── 상한 / 달성 ────────────────────────────────────────────────────
@pytest.mark.parametrize("level, cap", [("IL", "IM"), ("IM", "IH"), ("IH", "AL"), ("AL", "AL")])
def test_grade_cap_is_level_plus_one(level, cap):
    assert sc.grade_cap(level, RUBRIC) == cap


@pytest.mark.parametrize(
    "grade, level, capped",
    [("AL", "IL", "IM"), ("AL", "IM", "IH"), ("IH", "IM", "IH"), ("IL", "AL", "IL"), ("IL 미달", "IL", "IL 미달")],
)
def test_apply_cap(grade, level, capped):
    assert sc.apply_cap(grade, level, RUBRIC) == capped


@pytest.mark.parametrize(
    "grade, target, achieved",
    [("IM", "IM", True), ("IH", "IM", True), ("IL", "IM", False), ("IL 미달", "IL", False), ("AL", "AL", True)],
)
def test_is_achieved(grade, target, achieved):
    assert sc.is_achieved(grade, target) is achieved


# ── 전체 판정 ──────────────────────────────────────────────────────
def test_grade_answer_without_korean():
    g = sc.grade_answer(scores(4, 3, 4, 4), 0.0, "IM", RUBRIC)
    assert g == {
        "weighted_score": 3.75, "penalty": 0.0, "final_score": 3.75,
        "raw_grade": "IH", "grade": "IH", "achieved": True,
    }


def test_grade_answer_cap_applies():
    g = sc.grade_answer(scores(5, 5, 5, 5), 0.0, "IL", RUBRIC)
    assert g["raw_grade"] == "AL" and g["grade"] == "IM" and g["achieved"] is True


def test_grade_answer_korean_penalty_lowers_grade():
    g = sc.grade_answer(scores(4, 3, 4, 4), 0.3, "IH", RUBRIC)
    assert g["penalty"] == 0.6 and g["final_score"] == 3.15
    assert g["raw_grade"] == "IM" and g["achieved"] is False


def test_grade_answer_korean_fail_forces_below_lowest():
    g = sc.grade_answer(scores(5, 5, 5, 5), 0.8, "IM", RUBRIC)
    assert g["final_score"] == 3.4  # 점수는 계산하지만
    assert g["raw_grade"] == "IL 미달" and g["grade"] == "IL 미달" and g["achieved"] is False


def test_grade_answer_is_deterministic():
    args = (scores(3, 4, 2, 5), 0.15, "IH", RUBRIC)
    assert all(sc.grade_answer(*args) == sc.grade_answer(*args) for _ in range(20))


# ── 순서값 / 평균 ──────────────────────────────────────────────────
def test_ordinals():
    assert [sc.grade_ordinal(g) for g in ["IL 미달", "IL", "IM", "IH", "AL"]] == [0, 1, 2, 3, 4]
    assert [sc.level_ordinal(lv) for lv in ["IL", "IM", "IH", "AL"]] == [1, 2, 3, 4]
    with pytest.raises(ValueError):
        sc.grade_ordinal("NH")


@pytest.mark.parametrize(
    "grades, avg",
    [
        (["IM", "IM", "IM"], "IM"),
        (["IM", "IH", "IH"], "IH"),  # 2.67 → 3
        (["IM", "IM", "IH"], "IM"),  # 2.33 → 2
        (["IL 미달", "IL 미달", "IL"], "IL 미달"),  # 0.33 → 0
        (["IM", "IH"], "IH"),  # 2.5 → 3 (.5 올림)
        (["IL", "IM", "IH", "AL", "AL"], "IH"),  # 2.8 → 3
    ],
)
def test_average_grade(grades, avg):
    assert sc.average_grade(grades) == avg


def test_average_grade_empty():
    with pytest.raises(ValueError):
        sc.average_grade([])


def test_works_with_real_rubric_file():
    rubric = sc.load_rubric()
    g = sc.grade_answer({i["key"]: 3 for i in rubric["items"]}, 0.0, "IM", rubric)
    assert g["grade"] in ("IL 미달", "IL", "IM", "IH")
