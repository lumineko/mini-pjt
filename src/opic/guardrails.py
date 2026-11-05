"""출력 가드레일 — LLM 출력 검사 after 훅 (SERVICE §13, TASK Phase 6).

검사는 모두 파이썬 규칙이다(추가 LLM 호출 없음). 위반하면 `GuardrailViolation`을 던져
`invoke_llm`이 다음 모델로 넘어간다(사용자 결정). 모든 모델이 위반하면 LLMError → 화면의 '다시 시도'.

- interviewer: 주제 이탈. LLM이 함께 낸 `topic_keywords`(영어 1~3개) 중 일반 단어가 아닌 것 하나 이상이
  질문에 실제로 들어 있어야 한다(키워드 자기검증, 사용자 결정). 질문 영어 여부는 Pydantic 스키마가 본다.
- feedback: 언어 규칙, 번역 누락, 근거 확인.
  - `corrected`, `alternatives`는 영어(한글 단어 없음). `original`은 학습자 문장이라 한글이 있을 수 있어 보지 않는다.
  - `reason`은 한국어(한글 단어 1개 이상).
  - 한글 구간이 있으면(`metadata.needs_translation`) 번역이 비지 않고, 번역에 한글이 남지 않는다.
  - 근거: 교정의 `original`이 실제 답변(`metadata.guard_answer`, 개인정보 가린 답변)에 있는 문장이어야 한다.
    단어(대소문자·문장부호 무시)의 80% 이상이 답변에 같은 순서로 있으면 인정한다.

`install()`은 after 훅 맨 앞에 붙인다. 트레이스 기록기(trace.install)는 맨 끝이라, 위반한 출력은 error로 기록된다.
"""

import difflib
import logging
import re
from typing import Any

from opic import llm
from opic.tools.korean import detect_korean

logger = logging.getLogger(__name__)

# 어떤 주제의 질문에도 들어갈 수 있어 주제를 보여 주지 못하는 단어
GENERIC_WORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "for", "with", "about",
    "i", "me", "my", "you", "your", "yours", "we", "our",
    "what", "how", "why", "when", "where", "which", "who", "do", "did", "does",
    "tell", "describe", "talk", "explain", "like", "likes", "favorite", "favourite",
    "experience", "experiences", "time", "times", "thing", "things", "something",
    "kind", "type", "story", "memorable", "recent", "recently", "usually", "often",
})
_WORD_RE = re.compile(r"[a-z]+")
MIN_PREFIX = 4
_TOKEN_RE = re.compile(r"\w+")
GROUNDING_MIN_RATIO = 0.8


def has_korean(text: str | None) -> bool:
    return bool(text) and detect_korean(text)["korean_words"] > 0


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower().replace("'s", ""))


def _same_word(a: str, b: str) -> bool:
    """같은 단어이거나, 짧은 쪽(4글자 이상)이 긴 쪽의 앞부분이면 같은 단어로 본다 (park/parks/parking, movie/movies)."""
    short, long_ = sorted((a, b), key=len)
    return short == long_ or (len(short) >= MIN_PREFIX and long_.startswith(short))


def keyword_in_question(keyword: str, question: str) -> bool:
    """키워드(단어 또는 짧은 구)의 일반 단어가 아닌 단어가 모두 질문에 있으면 True. 일반 단어뿐이면 False."""
    words = [w for w in _words(keyword) if w not in GENERIC_WORDS]
    if not words:
        return False
    question_words = _words(question)
    return all(any(_same_word(w, q) for q in question_words) for w in words)


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def grounded_in(original: str, answer: str, min_ratio: float = GROUNDING_MIN_RATIO) -> bool:
    """original 단어의 min_ratio 이상이 answer에 같은 순서로 있으면 True (지어낸 문장 감지)."""
    orig = _tokens(original)
    if not orig:
        return False
    matcher = difflib.SequenceMatcher(None, orig, _tokens(answer), autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(orig) >= min_ratio


# ── 검사 (위반 사유 목록, 없으면 빈 목록) ─────────────────────────
def check_interviewer(output: Any) -> list[str]:
    keywords = list(getattr(output, "topic_keywords", None) or [])
    if not keywords:
        return ["주제 키워드가 없습니다"]
    if not any(keyword_in_question(k, output.question) for k in keywords):
        return [f"질문에 주제 키워드가 없습니다 (keywords={keywords})"]
    return []


def check_feedback(output: Any, needs_translation: bool, answer: str | None = None) -> list[str]:
    problems = []
    for i, c in enumerate(output.corrections, 1):
        if answer is not None and not grounded_in(c.original, answer):
            problems.append(f"교정 {i}의 original이 답변에 없습니다")
        if has_korean(c.corrected):
            problems.append(f"교정 {i}의 corrected에 한글이 있습니다")
        if not has_korean(c.reason):
            problems.append(f"교정 {i}의 reason이 한국어가 아닙니다")
    for i, alt in enumerate(output.alternatives, 1):
        if has_korean(alt):
            problems.append(f"대체 문장 {i}에 한글이 있습니다")
    translation = (output.translation or "").strip()
    if needs_translation and not translation:
        problems.append("한글 구간이 있는데 번역이 없습니다")
    if has_korean(translation):
        problems.append("번역에 한글이 남아 있습니다")
    return problems


def output_guard(role: str, output: Any, meta: dict[str, Any]) -> None:
    """after_call 훅. 위반 시 GuardrailViolation → 다음 모델."""
    if role == "interviewer":
        problems = check_interviewer(output)
    elif role == "feedback":
        problems = check_feedback(output, bool(meta.get("needs_translation")), meta.get("guard_answer"))
    else:
        return
    if problems:
        logger.warning(
            "출력 가드레일 위반 role=%s model=%s node=%s: %s",
            role, meta.get("model_id"), meta.get("node"), "; ".join(problems),
        )
        raise llm.GuardrailViolation("; ".join(problems))


# ── 등록 ───────────────────────────────────────────────────────────
def uninstall() -> None:
    llm.after_call_hooks[:] = [h for h in llm.after_call_hooks if h is not output_guard]


def install() -> None:
    """after 훅 맨 앞에 단다. 여러 번 불러도 하나만 남는다."""
    uninstall()
    llm.after_call_hooks.insert(0, output_guard)
