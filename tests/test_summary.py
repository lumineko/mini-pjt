"""rules/summary.py 테스트 (PRD F-11, 성공 기준 6)."""

import pytest

from opic.rules.summary import summarize


def item(grade, level="IM"):
    """요약에 필요한 필드만 채운 최소 ItemResult."""
    return {"grade": grade, "level": level}


def change(after, frm, to):
    return {"after_item": after, "from": frm, "to": to}


def test_summary_without_level_change():
    items = [item(g) for g in ["IM", "IH", "IM", "IM", "IL"]]
    s = summarize(items, "IM")
    assert s == {
        "item_grades": ["IM", "IH", "IM", "IM", "IL"],
        "average_grade": "IM",  # (2+3+2+2+1)/5 = 2.0
        "initial_level": "IM",
        "final_level": "IM",
        "level_changed": False,
    }


def test_summary_with_level_change():
    items = [item("IH"), item("IH"), item("AL"), item("IH", "IH"), item("AL", "IH")]
    s = summarize(items, "IM", [change(3, "IM", "IH")])
    assert s["average_grade"] == "IH"  # (3+3+4+3+4)/5 = 3.4
    assert s["final_level"] == "IH" and s["level_changed"] is True


def test_average_uses_capped_grade_and_below_lowest():
    items = [item(g) for g in ["IL 미달", "IL 미달", "IL", "IL 미달", "IL"]]
    assert summarize(items, "IL")["average_grade"] == "IL 미달"  # 0.4 → 0


def test_average_rounds_up_from_point_six():
    items = [item(g) for g in ["IM", "IH", "IH", "IM", "IH"]]
    assert summarize(items, "IM")["average_grade"] == "IH"  # 2.6 → 3


@pytest.mark.parametrize("n", [0, 3, 4, 6])
def test_requires_five_items(n):
    with pytest.raises(ValueError):
        summarize([item("IM")] * n, "IM")


def test_rejects_broken_level_history():
    with pytest.raises(ValueError):
        summarize([item("IM")] * 5, "IM", [change(3, "IH", "AL")])


def test_summary_is_deterministic():
    items = [item(g) for g in ["IL", "IM", "IH", "AL", "IM"]]
    assert all(summarize(items, "IM") == summarize(items, "IM") for _ in range(10))
