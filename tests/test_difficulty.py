"""rules/difficulty.py 테스트 (PRD F-12, 성공 기준 7)."""

import pytest

from opic.rules.difficulty import CHECK_AFTER_ITEMS, apply_adjustment, propose_adjustment


def up(level):
    return {"direction": "up", "suggested_level": level}


def down(level):
    return {"direction": "down", "suggested_level": level}


# ── 제안 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "grades, level, expected",
    [
        # 같으면 제안 없음
        (["IM", "IM", "IM"], "IM", None),
        (["IL", "IM", "IH"], "IM", None),  # 평균 2.0
        (["IM", "IM", "IH"], "IM", None),  # 2.33 → IM
        # 높으면 up (한 단계)
        (["IH", "IH", "IM"], "IM", up("IH")),  # 2.67 → IH
        (["IM", "IM", "IM"], "IL", up("IM")),
        (["AL", "AL", "AL"], "IL", up("IM")),  # 세 단계 차이여도 한 단계만
        # 낮으면 down (한 단계)
        (["IL", "IL", "IM"], "IM", down("IL")),  # 1.33 → IL
        (["IL", "IL", "IL"], "AL", down("IH")),  # 세 단계 차이여도 한 단계만
        (["IL 미달", "IL 미달", "IL 미달"], "IM", down("IL")),  # IL 미달도 down
        (["IL 미달", "IL", "IL"], "IH", down("IM")),
    ],
)
def test_propose_adjustment(grades, level, expected):
    assert propose_adjustment(grades, level) == expected


@pytest.mark.parametrize(
    "grades, level",
    [
        (["AL", "AL", "AL"], "AL"),  # AL에서 up 없음
        (["IL 미달", "IL 미달", "IL 미달"], "IL"),  # IL에서 down 없음
        (["IL 미달", "IL", "IL 미달"], "IL"),
    ],
)
def test_no_proposal_at_boundaries(grades, level):
    assert propose_adjustment(grades, level) is None


def test_al_level_with_lower_grades_proposes_down():
    assert propose_adjustment(["IH", "IH", "IM"], "AL") == down("IH")


def test_il_level_with_higher_grades_proposes_up():
    # IL 문항 상한은 IM이라 최대 IM까지 나온다
    assert propose_adjustment(["IM", "IM", "IL"], "IL") == up("IM")


@pytest.mark.parametrize("n", [0, 2, 4, 5])
def test_requires_exactly_three_grades(n):
    assert CHECK_AFTER_ITEMS == 3
    with pytest.raises(ValueError):
        propose_adjustment(["IM"] * n, "IM")


def test_proposal_is_deterministic():
    args = (["IH", "IM", "IH"], "IM")
    assert all(propose_adjustment(*args) == propose_adjustment(*args) for _ in range(10))


# ── 적용 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "level, proposal, new_level",
    [("IM", up("IH"), "IH"), ("IM", down("IL"), "IL"), ("IH", up("AL"), "AL"), ("IH", down("IM"), "IM")],
)
def test_apply_adjustment(level, proposal, new_level):
    result, change = apply_adjustment(level, proposal, after_item=3)
    assert result == new_level
    assert change == {"after_item": 3, "from": level, "to": new_level}


@pytest.mark.parametrize(
    "level, proposal",
    [
        ("AL", up("AL")),  # AL 초과
        ("IL", down("IL")),  # IL 미만
        ("IM", up("AL")),  # 두 단계
        ("IM", down("IH")),  # 방향과 레벨 불일치
    ],
)
def test_apply_rejects_invalid_proposal(level, proposal):
    with pytest.raises(ValueError):
        apply_adjustment(level, proposal, after_item=3)


def test_propose_then_apply_round_trip():
    proposal = propose_adjustment(["IL 미달", "IL", "IL"], "IH")
    level, change = apply_adjustment("IH", proposal, after_item=3)
    assert level == "IM" and change["from"] == "IH"
