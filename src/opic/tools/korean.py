"""한글 감지 (PRD F-13, F-04 / SERVICE §3 await_answer).

정의 (2026-11-05 확정):
- **단어**: 공백으로 나눈 덩어리 중 글자(한글·영문 등 문자)가 하나 이상 있는 것. 숫자·문장부호만 있는 덩어리는 세지 않는다.
- **한글 단어**: 한글 글자가 하나라도 들어간 단어 (예: "떡볶이를", "Kimchi찌개").
- **한글 비율** = 한글 단어 수 / 전체 단어 수 (단어가 없으면 0).
- **최소 단어 수 검증**(rules.validation)도 같은 단어 정의를 쓴다. 한글 단어도 센다.
- **번역 구간(spans)**: 연속된 한글 글자 묶음. 사이에 영문 글자 없이 공백·문장부호·숫자만 있으면 한 구간으로 합친다.

한글 비율은 await_answer에서 이 함수로 **한 번만** 계산한다(유일한 출처).
"""

import re
from typing import TypedDict

from opic.state import KoreanSpan

# 한글 자모(1100–11FF), 호환 자모(3130–318F, 예: ㅋㅋ), 자모 확장 A/B, 완성형 음절(AC00–D7A3)
_HANGUL = "ᄀ-ᇿ㄰-㆏ꥠ-꥿가-힣ힰ-퟿"
_HANGUL_CHAR = re.compile(f"[{_HANGUL}]")
_HANGUL_RUN = re.compile(f"[{_HANGUL}]+")
_LETTER = re.compile(r"[^\W\d_]")  # 유니코드 문자(숫자·밑줄 제외)
_TOKEN = re.compile(r"\S+")


class KoreanDetection(TypedDict):
    ratio: float
    spans: list[KoreanSpan]
    korean_words: int
    total_words: int


def split_words(text: str) -> list[str]:
    """글자가 하나 이상 들어간 공백 단위 덩어리 목록."""
    return [tok for tok in _TOKEN.findall(text) if _LETTER.search(tok)]


def count_words(text: str) -> int:
    return len(split_words(text))


def _is_non_hangul_letter(ch: str) -> bool:
    return bool(_LETTER.match(ch)) and not _HANGUL_CHAR.match(ch)


def find_korean_spans(text: str) -> list[KoreanSpan]:
    spans: list[KoreanSpan] = []
    for m in _HANGUL_RUN.finditer(text):
        start, end = m.start(), m.end()
        if spans:
            gap = text[spans[-1]["end"]:start]
            if not any(_is_non_hangul_letter(ch) for ch in gap):
                spans[-1]["end"] = end
                spans[-1]["text"] = text[spans[-1]["start"]:end]
                continue
        spans.append(KoreanSpan(start=start, end=end, text=text[start:end]))
    return spans


def detect_korean(text: str) -> KoreanDetection:
    words = split_words(text)
    korean = sum(1 for w in words if _HANGUL_CHAR.search(w))
    return KoreanDetection(
        ratio=korean / len(words) if words else 0.0,
        spans=find_korean_spans(text),
        korean_words=korean,
        total_words=len(words),
    )
