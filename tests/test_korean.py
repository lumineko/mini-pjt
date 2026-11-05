"""tools/korean.py 테스트 (PRD F-13, 성공 기준 8)."""

import pytest

from opic.tools.korean import count_words, detect_korean, find_korean_spans, split_words


# ── 단어 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "text, words",
    [
        ("I like 떡볶이 very much", ["I", "like", "떡볶이", "very", "much"]),
        ("  Hello,   world!  ", ["Hello,", "world!"]),
        ("I have 2 dogs - 3 cats ...", ["I", "have", "dogs", "cats"]),  # 숫자·문장부호만 있는 덩어리 제외
        ("I'm 25years old", ["I'm", "25years", "old"]),
        ("", []),
        ("   \n\t ", []),
        ("!!! 123 ...", []),
    ],
)
def test_split_words(text, words):
    assert split_words(text) == words
    assert count_words(text) == len(words)


def test_korean_words_are_counted_for_min_length():
    assert count_words("나는 어제 친구와 영화를 봤다") == 5


# ── 비율 (단어 기준) ───────────────────────────────────────────────
@pytest.mark.parametrize(
    "text, korean, total, ratio",
    [
        ("I like 떡볶이 very much", 1, 5, 0.2),
        ("나는 학교에 갔다 because I was late", 3, 7, 3 / 7),
        ("I usually go jogging in the park", 0, 7, 0.0),
        ("나는 주말에 보통 공원에서 산책을 한다", 6, 6, 1.0),
        ("I ate Kimchi찌개 for lunch", 1, 5, 0.2),  # 섞인 단어는 한글 단어
        ("ㅋㅋ that was so funny", 1, 5, 0.2),  # 호환 자모
        ("", 0, 0, 0.0),
    ],
)
def test_ratio_is_korean_words_over_total_words(text, korean, total, ratio):
    d = detect_korean(text)
    assert (d["korean_words"], d["total_words"]) == (korean, total)
    assert d["ratio"] == pytest.approx(ratio)


def test_ratio_80_percent_boundary_is_exact():
    # 4/5 = 0.8 → rubric fail_threshold(0.8)와 같은 값으로 비교되어야 한다
    assert detect_korean("나는 학교에 정말 갔다 yesterday")["ratio"] == 0.8


def test_punctuation_and_numbers_do_not_change_ratio():
    a = detect_korean("I like 떡볶이 very much")["ratio"]
    b = detect_korean("I like 떡볶이 very much!!! 100% ... :)")["ratio"]
    assert a == b


def test_detect_is_deterministic():
    text = "I went to 제주도 last summer, 정말 좋았어요."
    assert all(detect_korean(text) == detect_korean(text) for _ in range(10))


# ── 번역 구간 ──────────────────────────────────────────────────────
def test_spans_merge_across_spaces_and_punctuation():
    text = "나는 학교에, 갔다 because I was late"
    spans = find_korean_spans(text)
    assert [s["text"] for s in spans] == ["나는 학교에, 갔다"]
    assert text[spans[0]["start"]:spans[0]["end"]] == spans[0]["text"]


def test_spans_split_by_english_words():
    text = "I went to 제주도 last summer, 정말 좋았어요."
    assert [s["text"] for s in find_korean_spans(text)] == ["제주도", "정말 좋았어요"]


def test_spans_inside_mixed_word():
    assert [s["text"] for s in find_korean_spans("I ate Kimchi찌개 today")] == ["찌개"]


def test_spans_merge_across_numbers():
    assert [s["text"] for s in find_korean_spans("오늘 3시에 만나요")] == ["오늘 3시에 만나요"]


def test_no_spans_for_english_only():
    assert find_korean_spans("I usually go jogging.") == []
    assert detect_korean("I usually go jogging.")["spans"] == []


def test_span_offsets_match_text():
    text = "Hello 안녕하세요 world 반가워요!"
    for s in detect_korean(text)["spans"]:
        assert text[s["start"]:s["end"]] == s["text"]
