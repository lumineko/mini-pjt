"""입력 가드레일 — 학습자 답변 검사 (SERVICE §13, TASK Phase 6). LLM 없는 순수 함수.

Bedrock Guardrails를 쓸 수 없어 로컬 파이썬 규칙으로 대신한다.

- `mask_pii(text)`: 개인정보(주민등록번호·카드번호·전화번호·계좌번호·이메일)를 `[PHONE]` 같은 표시로 바꾼다.
  가린 답변이 LLM에 보내지고 기록에도 저장된다(사용자 결정). 원문은 어디에도 남기지 않는다.
- `detect_injection(text)`: 프롬프트 인젝션으로 보이는 문구를 찾는다. **표시만** 한다(사용자 결정).
  막지 않고 채점은 그대로 진행한다(답변 격리 + 채점 지시로 무시, SERVICE §3 보안). 결과는 기록·로그·트레이스에 남는다.
"""

import re
from typing import TypedDict

# ── 개인정보 ───────────────────────────────────────────────────────
# 순서가 중요하다: 긴·구체적인 형식(주민번호, 카드)을 먼저 바꿔야 전화·계좌 규칙이 일부만 먹지 않는다.
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")),
    ("rrn", re.compile(r"(?<!\d)\d{6}\s?-\s?[1-8]\d{6}(?!\d)")),  # 주민등록번호·외국인등록번호
    ("card", re.compile(r"(?<!\d)\d{4}(?:[ -]?\d{4}){3}(?!\d)")),
    ("phone", re.compile(
        r"(?<![\d-])(?:\+82[ -]?1[016789]|01[016789]|0(?:2|[3-6][1-5]))[ -]?\d{3,4}[ -]?\d{4}(?![\d-])"
    )),
    # 계좌번호: 하이픈으로 나뉜 숫자 3~4묶음, 숫자 합계 10자리 이상 (날짜 2024-05-01 같은 8자리는 제외)
    ("account", re.compile(r"(?<![\d-])\d{2,6}(?:-\d{2,7}){2,3}(?![\d-])")),
]
PII_LABELS = {"email": "[EMAIL]", "rrn": "[ID_NUMBER]", "card": "[CARD]", "phone": "[PHONE]", "account": "[ACCOUNT]"}
PII_NAMES_KO = {"email": "이메일", "rrn": "주민등록번호", "card": "카드번호", "phone": "전화번호", "account": "계좌번호"}
_ACCOUNT_MIN_DIGITS = 10


class MaskResult(TypedDict):
    text: str
    pii_types: list[str]  # 가린 종류 (중복 없음, 처음 나온 순서)


def mask_pii(text: str) -> MaskResult:
    found: list[str] = []

    for name, pattern in _PII_PATTERNS:
        def _replace(match: re.Match, name=name) -> str:
            if name == "account" and sum(c.isdigit() for c in match.group()) < _ACCOUNT_MIN_DIGITS:
                return match.group()
            if name not in found:
                found.append(name)
            return PII_LABELS[name]

        text = pattern.sub(_replace, text)
    return MaskResult(text=text, pii_types=found)


# ── 인젝션 ─────────────────────────────────────────────────────────
# 일상 답변에 흔한 표현(forget the rules, you are now ...)은 넣지 않는다. 골든 세트 일반 답변 33건에서 오탐 0건.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ignore_instructions", re.compile(
        r"\b(?:ignore|disregard)\b.{0,30}\b(?:instructions?|prompts?|rubric|directions?)\b", re.I)),
    ("role_marker", re.compile(r"\[\s*(?:system|assistant|developer|admin)\s*\]|^\s*(?:system|assistant)\s*:", re.I | re.M)),
    ("grader_address", re.compile(
        r"\b(?:note|message|instructions?)\s+(?:to|for)\s+(?:the\s+)?(?:grader|scorer|evaluator|examiner|ai|model)\b", re.I)),
    ("score_request", re.compile(
        r"\b(?:give|grade|score|rate|mark|assign)\b.{0,30}"
        r"\b(?:\d|five|full|max(?:imum)?|perfect|highest|lowest|minimum|zero)\s*(?:points?|scores?|marks?)\b", re.I)),
    ("level_request", re.compile(
        r"\b(?:give|grade|rate|score)\s+(?:me|it|this(?:\s+answer)?|my\s+answer)\s+(?:an?\s+)?(?:AL|IH|advanced\s+low)\b", re.I)),
    ("score_demand", re.compile(
        r"\b(?:must|should)\s+(?:receive|get|be\s+given)\b.{0,20}\b(?:score|grade|points?|marks?)\b", re.I)),
    ("rubric_update", re.compile(r"\b(?:rubric|grading|scoring)\b.{0,20}\b(?:updated|changed|replaced)\b", re.I)),
    ("system_prompt", re.compile(r"\bsystem\s+prompt\b", re.I)),
    # 한국어
    ("ignore_instructions_ko", re.compile(r"(?:지시|지침|명령|프롬프트)\S{0,3}\s*(?:을|를)?\s*(?:무시|잊어)")),
    ("score_request_ko", re.compile(r"(?:점수|등급|만점|최고점|5점|AL)\S{0,2}\s*(?:을|를|로|으로)?\s*(?:줘|주세요|달라|주십시오|매겨|해\s?줘)")),
    ("system_prompt_ko", re.compile(r"시스템\s*프롬프트|역할\S{0,2}\s*(?:을|를)?\s*(?:바꿔|변경)")),
]


def detect_injection(text: str) -> list[str]:
    """찾은 인젝션 규칙 이름 목록(없으면 빈 목록)."""
    return [name for name, pattern in _INJECTION_PATTERNS if pattern.search(text)]
