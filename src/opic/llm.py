"""모든 LLM 호출의 단일 진입점 (PRD F-10 / SERVICE §6, §7, §11, §13).

다른 모듈은 Bedrock(ChatBedrockConverse, boto3)을 직접 부르지 않고 `invoke_llm()`만 쓴다.

호출 순서:
  모델 목록(Settings.models: 기본 → 폴백) 순서대로
    ├ 재시도 가능 오류(스로틀링, 5xx, 일시 장애, 네트워크) → 지수 백오프(1s, 2s …)로 같은 모델 재시도 (모델당 LLM_MAX_RETRIES회)
    ├ 구조화 출력 파싱·검증 실패, after_call 가드레일 위반 → 재시도 없이 다음 모델
    └ 그 밖의 오류(권한, 잘못된 요청 등) → 재시도 없이 다음 모델
  모두 실패 → LLMError (UI는 '다시 시도'로 체크포인트부터 재실행, SERVICE §7)

botocore 자체 재시도는 끈다(total_max_attempts=1). 재시도는 여기서만 한다.

확장 지점 (SERVICE §13, Phase 6 트레이스·출력 가드레일이 사용):
- 호출 메타데이터: RunnableConfig metadata/tags에 role, model_id, attempt, session_id, node, item_index, prompt(id@version)
- 훅: before_call_hooks / after_call_hooks / error_call_hooks (기본은 비어 있음, 트레이스는 trace.install()로 등록)
"""

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ValidationError

from opic.config import Settings, load_settings

logger = logging.getLogger(__name__)


# ── 용도별 설정 ────────────────────────────────────────────────────
@dataclass(frozen=True)
class RoleConfig:
    temperature: float
    max_tokens: int


# temperature: scorer는 일관성(PRD §6)을 위해 0. 생성 용도는 다양성을 위해 높게. (초안, 조정 가능)
ROLE_CONFIG: dict[str, RoleConfig] = {
    "survey": RoleConfig(temperature=0.7, max_tokens=1024),
    "interviewer": RoleConfig(temperature=0.7, max_tokens=512),
    "scorer": RoleConfig(temperature=0.0, max_tokens=512),
    "feedback": RoleConfig(temperature=0.3, max_tokens=2048),
}

# 같은 모델로 다시 시도할 만한 Bedrock 오류 코드
RETRYABLE_CODES = frozenset({
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "InternalServerException",
    "ModelNotReadyException",
    "ModelTimeoutException",
})


# ── 오류 ───────────────────────────────────────────────────────────
class GuardrailViolation(Exception):
    """after_call 훅이 출력을 거부할 때 던진다 → 다음 모델로 넘어간다."""


class StructuredOutputError(Exception):
    """구조화 출력이 비었거나 검증에 실패했다."""


@dataclass
class Attempt:
    model_id: str
    attempt: int
    error: str


class LLMError(RuntimeError):
    """모든 모델이 실패했다."""

    def __init__(self, role: str, attempts: list[Attempt]):
        self.role = role
        self.attempts = attempts
        tried = ", ".join(f"{a.model_id}#{a.attempt}: {a.error}" for a in attempts)
        super().__init__(f"[{role}] 모든 모델 호출 실패 ({tried})")


def is_retryable(exc: BaseException) -> bool:
    """스로틀링·5xx·일시 장애·네트워크 오류면 True."""
    try:
        from botocore.exceptions import ClientError, ConnectionError as BotoConnectionError, ReadTimeoutError
    except ImportError:  # pragma: no cover
        return False
    if isinstance(exc, (BotoConnectionError, ReadTimeoutError)):
        return True
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return error.get("Code") in RETRYABLE_CODES or 500 <= int(status or 0) < 600
    return False


def _is_structured_failure(exc: BaseException) -> bool:
    if isinstance(exc, (ValidationError, StructuredOutputError)):
        return True
    try:
        from langchain_core.exceptions import OutputParserException
    except ImportError:  # pragma: no cover
        return False
    return isinstance(exc, OutputParserException)


# ── 모델 생성 ──────────────────────────────────────────────────────
ModelFactory = Callable[[str, str, Settings], Any]


@lru_cache(maxsize=16)
def _bedrock_model(model_id: str, region: str, profile: str | None, temperature: float, max_tokens: int):
    from botocore.config import Config
    from langchain_aws import ChatBedrockConverse

    return ChatBedrockConverse(
        model=model_id,
        region_name=region,
        credentials_profile_name=profile,
        temperature=temperature,
        max_tokens=max_tokens,
        # total_max_attempts=1: 첫 호출만 (botocore의 max_attempts=1은 '재시도 1회'라 총 2번이 된다)
        config=Config(retries={"total_max_attempts": 1, "mode": "standard"}, connect_timeout=10, read_timeout=120),
    )


def bedrock_model_factory(model_id: str, role: str, settings: Settings):
    """실제 Bedrock 모델 (자격 증명은 .env의 키 또는 AWS_PROFILE, 호출 시점에 확인됨)."""
    cfg = ROLE_CONFIG[role]
    return _bedrock_model(model_id, settings.aws_region, settings.aws_profile, cfg.temperature, cfg.max_tokens)


_model_factory: ModelFactory = bedrock_model_factory


def set_model_factory(factory: ModelFactory | None) -> None:
    """테스트·평가용으로 모델 생성 함수를 바꾼다. None이면 Bedrock으로 되돌린다."""
    global _model_factory
    _model_factory = factory or bedrock_model_factory


# ── 훅 (SERVICE §13, 기본 비어 있음) ───────────────────────────────
BeforeHook = Callable[[str, Sequence[Any], dict[str, Any]], None]
AfterHook = Callable[[str, Any, dict[str, Any]], None]
ErrorHook = Callable[[str, BaseException, dict[str, Any]], None]
before_call_hooks: list[BeforeHook] = []
# 출력 검사(GuardrailViolation을 던질 수 있음)를 앞에, 트레이스 기록기를 맨 끝에 둔다.
after_call_hooks: list[AfterHook] = []
# 시도 하나가 실패할 때마다 불린다(기록 전용). 여기서 난 예외는 로그만 남기고 무시한다.
error_call_hooks: list[ErrorHook] = []


def _run_error_hooks(role: str, exc: BaseException, meta: dict[str, Any]) -> None:
    for hook in error_call_hooks:
        try:
            hook(role, exc, meta)
        except Exception:  # noqa: BLE001 - 기록 실패가 호출 흐름을 바꾸면 안 된다
            logger.exception("error_call 훅 실패: %r", hook)


# ── 호출 ───────────────────────────────────────────────────────────
_sleep: Callable[[float], None] = time.sleep


def backoff_delay(retry_index: int) -> float:
    """0 → 1s, 1 → 2s, 2 → 4s …"""
    return float(2**retry_index)


def invoke_llm(
    role: str,
    messages: Sequence[Any],
    *,
    schema: type[BaseModel] | None = None,
    metadata: Mapping[str, Any] | None = None,
    settings: Settings | None = None,
    factory: ModelFactory | None = None,
    sleep: Callable[[float], None] | None = None,
) -> Any:
    """role 용도로 LLM을 호출한다. schema를 주면 그 Pydantic 인스턴스를, 없으면 AIMessage를 돌려준다.

    metadata: session_id, node, item_index, prompt(= "id@version") 등. 트레이스용으로 그대로 전달된다.
    """
    if role not in ROLE_CONFIG:
        raise ValueError(f"알 수 없는 role: {role!r} (허용: {sorted(ROLE_CONFIG)})")
    settings = settings or load_settings()
    factory = factory or _model_factory
    sleep = sleep or _sleep
    base_meta = {"role": role, **(metadata or {})}
    tags = [f"role:{role}"] + ([f"prompt:{base_meta['prompt']}"] if base_meta.get("prompt") else [])

    attempts: list[Attempt] = []
    models = settings.models
    for model_index, model_id in enumerate(models):
        runnable = factory(model_id, role, settings)
        if schema is not None:
            runnable = runnable.with_structured_output(schema)

        for retry in range(settings.llm_max_retries + 1):
            meta = {**base_meta, "model_id": model_id, "attempt": len(attempts) + 1, "fallback": model_index > 0}
            started = time.perf_counter()
            try:
                for hook in before_call_hooks:
                    hook(role, messages, meta)
                output = runnable.invoke(list(messages), config={"metadata": meta, "tags": tags, "run_name": role})
                if schema is not None and not isinstance(output, schema):
                    raise StructuredOutputError(f"{schema.__name__} 형식이 아닌 출력: {type(output).__name__}")
                hook_meta = {**meta, "elapsed_ms": round((time.perf_counter() - started) * 1000)}
                for hook in after_call_hooks:
                    hook(role, output, hook_meta)
            except Exception as exc:  # noqa: BLE001 - 오류 종류별로 아래에서 분기
                elapsed = time.perf_counter() - started
                _run_error_hooks(role, exc, {**meta, "elapsed_ms": round(elapsed * 1000)})
                attempts.append(Attempt(model_id, retry + 1, f"{type(exc).__name__}: {exc}"[:300]))
                retryable = is_retryable(exc)
                logger.warning(
                    "LLM 실패 role=%s model=%s fallback=%s retry=%d elapsed=%.2fs error=%s",
                    role, model_id, model_index > 0, retry, elapsed, type(exc).__name__,
                )
                if retryable and retry < settings.llm_max_retries:
                    sleep(backoff_delay(retry))
                    continue
                if not (retryable or _is_structured_failure(exc) or isinstance(exc, GuardrailViolation)):
                    logger.info("재시도 대상 아님 → 다음 모델: %s", type(exc).__name__)
                break  # 다음 모델
            else:
                logger.info(
                    "LLM 성공 role=%s model=%s fallback=%s retries=%d elapsed=%.2fs",
                    role, model_id, model_index > 0, retry, time.perf_counter() - started,
                )
                return output

    raise LLMError(role, attempts)
