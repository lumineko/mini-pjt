"""evals/scorer/golden.jsonl 형식·규칙 일관성 검사 (SERVICE §14.2). LLM 호출 없음.

기대 등급의 '정답성'은 사용자 검수 대상이고, 여기서는 파이썬 규칙과 모순되지 않는지만 본다.
"""

import json
from collections import Counter

import pytest

from opic.config import ROOT_DIR
from opic.rules.scoring import grade_cap, grade_ordinal, is_korean_fail, load_rubric
from opic.rules.validation import validate_answer
from opic.state import GRADES, LEVELS
from opic.tools.korean import detect_korean

GOLDEN = ROOT_DIR / "evals" / "scorer" / "golden.jsonl"
TAGS = {"korean_mixed", "korean_full", "injection", "off_topic", "short", "cap"}
REQUIRED = {"id", "question", "level", "answer", "expected_grade", "tags", "note", "reviewed"}


@pytest.fixture(scope="module")
def records():
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def rubric():
    return load_rubric()


def test_size_and_unique_ids(records):
    assert 30 <= len(records) <= 50
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids))


def test_fields_and_values(records):
    for r in records:
        assert REQUIRED <= set(r), r["id"]
        assert r["level"] in LEVELS, r["id"]
        assert r["expected_grade"] in GRADES, r["id"]
        assert set(r["tags"]) <= TAGS, r["id"]
        assert isinstance(r["reviewed"], bool)


def test_distribution(records):
    grades = Counter(r["expected_grade"] for r in records)
    assert all(grades[g] >= 3 for g in GRADES), grades
    tags = Counter(t for r in records for t in r["tags"])
    assert all(tags[t] >= 2 for t in TAGS), tags


def test_every_answer_passes_min_words(records, rubric):
    for r in records:
        assert validate_answer(r["answer"], rubric["min_words"]) is None, r["id"]


def test_expected_grade_within_cap(records, rubric):
    for r in records:
        assert grade_ordinal(r["expected_grade"]) <= grade_ordinal(grade_cap(r["level"], rubric)), r["id"]


def test_cap_cases_expect_exactly_the_cap(records, rubric):
    for r in records:
        if "cap" in r["tags"]:
            assert r["expected_grade"] == grade_cap(r["level"], rubric), r["id"]


def test_korean_threshold_matches_expected(records, rubric):
    for r in records:
        fail = is_korean_fail(detect_korean(r["answer"])["ratio"], rubric)
        if fail:
            assert r["expected_grade"] == "IL 미달", r["id"]
        if "korean_full" in r["tags"]:
            assert fail, r["id"]
        if "korean_mixed" in r["tags"] or "korean_full" in r["tags"]:
            assert detect_korean(r["answer"])["korean_words"] > 0, r["id"]


def test_injection_cases_have_clean_answer(records):
    for r in records:
        if "injection" in r["tags"]:
            assert r["clean_answer"] and r["clean_answer"] != r["answer"], r["id"]
            assert r["answer"].startswith(r["clean_answer"]), r["id"]
        else:
            assert "clean_answer" not in r, r["id"]
