"""tools/survey.py 테스트 (PRD F-01, 성공 기준 9)."""

import random

import pytest

from opic.config import ROOT_DIR
from opic.tools.survey import load_default_topics, load_survey_file, parse_survey, pick_default_topic

DEFAULT_TOPICS = ["직업", "거주지", "여가활동", "취미/관심사", "운동", "휴가/출장"]


# ── 실제 opic_survey.md ────────────────────────────────────────────
@pytest.fixture(scope="module")
def real():
    parsed = load_survey_file(ROOT_DIR / "opic_survey.md")
    assert parsed is not None
    return parsed


def test_real_file_structure(real):
    summary = [(i["id"], i["kind"], len(i["options"])) for i in real["items"]]
    assert summary == [
        ("직업-1", "profile", 4), ("직업-2", "profile", 2), ("직업-3", "profile", 4),
        ("거주지-1", "profile", 5),
        ("여가활동-1", "topic", 8), ("취미/관심사-1", "topic", 10),
        ("운동-1", "topic", 32), ("휴가/출장-1", "topic", 5),
    ]


def test_real_file_notice_and_comment_removed(real):
    assert real["notice"].startswith("실제 시험에서는")
    assert all("출처" not in i["question"] for i in real["items"])


def test_real_file_stars(real):
    hobby = next(i for i in real["items"] if i["topic"] == "취미/관심사")
    stars = {o["label"]: o["recommend"] for o in hobby["options"]}
    assert stars["음악 감상하기"] == 3 and stars["독서"] == 2 and stars["그림 그리기"] == 0
    assert all("★" not in o["label"] for i in real["items"] for o in i["options"])


def test_real_file_question_split_on_first_colon(real):
    assert real["items"][0]["question"] == "현재 종사 분야는 무엇인가요?"


# ── 파싱 규칙 ──────────────────────────────────────────────────────
SAMPLE = """\
# 제목은 무시
<!-- 여러 줄
     주석 - 무시: a | b -->
> 첫 안내
> 둘째 안내

- 제목 전 문항: a | b

## [프로필]  거주지
- 어디 사나요?: 혼자★ | 가족

## 여가
- 무엇을 하나요?: 영화★★★★ | 공연 | | 영화 | 카페★
- 보기 없음:
- 콜론 없는 줄 영화 | 공연
- 시간: 10:30 같은 보기 | 저녁
### 하위 제목 무시
- 두 번째 문항: 산책
"""


def test_sample_parsing():
    parsed = parse_survey(SAMPLE)
    assert parsed["notice"] == "첫 안내\n둘째 안내"
    assert [(i["id"], i["topic"], i["kind"], i["question"]) for i in parsed["items"]] == [
        ("거주지-1", "거주지", "profile", "어디 사나요?"),
        ("여가-1", "여가", "topic", "무엇을 하나요?"),
        ("여가-2", "여가", "topic", "시간"),
        ("여가-3", "여가", "topic", "두 번째 문항"),
    ]


def test_options_stars_empty_and_duplicates():
    item = parse_survey(SAMPLE)["items"][1]
    assert item["options"] == [
        {"label": "영화", "recommend": 3},  # ★ 4개 → 최대 3, 중복 "영화"는 첫 번째만
        {"label": "공연", "recommend": 0},
        {"label": "카페", "recommend": 1},
    ]


def test_only_first_colon_splits():
    item = parse_survey(SAMPLE)["items"][2]
    assert [o["label"] for o in item["options"]] == ["10:30 같은 보기", "저녁"]


def test_profile_prefix_is_removed_from_topic():
    assert parse_survey(SAMPLE)["items"][0]["topic"] == "거주지"


def test_no_notice():
    assert parse_survey("## 운동\n- 무엇?: 조깅")["notice"] is None


# ── fallback 조건 ──────────────────────────────────────────────────
def test_missing_file_falls_back(tmp_path):
    assert load_survey_file(tmp_path / "none.md") is None


@pytest.mark.parametrize(
    "content",
    [
        "",
        "   \n\n",
        "# 제목만\n> 안내만\n",
        "## [프로필] 직업\n- 무엇?: 학생 | 회사원\n",  # profile만 있고 topic 0개
        "## 운동\n- 형식 틀림\n- 보기 없음:\n",
    ],
)
def test_no_topic_items_falls_back(tmp_path, content):
    path = tmp_path / "survey.md"
    path.write_text(content, encoding="utf-8")
    assert load_survey_file(path) is None


def test_bom_file_is_read(tmp_path):
    path = tmp_path / "survey.md"
    path.write_text("## 운동\n- 무엇?: 조깅", encoding="utf-8-sig")
    assert load_survey_file(path)["items"][0]["id"] == "운동-1"


def test_undecodable_file_falls_back(tmp_path):
    path = tmp_path / "survey.md"
    path.write_bytes(b"\xff\xfe\x00\xd8 broken")
    assert load_survey_file(path) is None


# ── 기본 주제 ──────────────────────────────────────────────────────
def test_default_topics_file():
    assert load_default_topics() == DEFAULT_TOPICS


def test_pick_default_topic_is_from_six_and_reproducible_with_seed():
    picks = {pick_default_topic(random.Random(seed)) for seed in range(200)}
    assert picks == set(DEFAULT_TOPICS)
    assert pick_default_topic(random.Random(7)) == pick_default_topic(random.Random(7))


def test_pick_default_topic_custom_list():
    assert pick_default_topic(random.Random(0), ["운동"]) == "운동"
