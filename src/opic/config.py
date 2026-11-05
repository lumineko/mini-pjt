"""설정 로더 (SERVICE.md §8, §11).

- `.env`(프로젝트 루트)를 읽어 `Settings`로 만든다. 이미 설정된 환경변수가 `.env`보다 우선한다.
- 자격 증명이 없어도 로드는 실패하지 않는다. 키 확인은 실제 Bedrock 호출 시점(llm.py)에서 한다.
- 상대 경로는 프로젝트 루트 기준으로 바꾼다.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

DEFAULT_MODEL_PRIMARY = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_MODEL_FALLBACKS = ("global.anthropic.claude-haiku-4-5-20251001-v1:0",)
DEFAULT_REGION = "us-east-1"
DEFAULT_MAX_RETRIES = 2
DEFAULT_SURVEY_FILE = "opic_survey.md"
DEFAULT_HISTORY_DIR = "data/history"
DEFAULT_LOG_LEVEL = "INFO"
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
# boto3가 os.environ에서 직접 읽는 인증 변수. 빈 값이 남아 있으면 boto3가 실패한다
# (예: AWS_PROFILE="" → "The config profile () could not be found").
AWS_CREDENTIAL_VARS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE")


class ConfigError(ValueError):
    """설정값이 잘못되었을 때."""


@dataclass(frozen=True)
class Settings:
    aws_region: str
    aws_profile: str | None
    has_access_key: bool
    model_primary: str
    model_fallbacks: tuple[str, ...]
    llm_max_retries: int
    survey_file: Path
    history_dir: Path
    log_level: str

    @property
    def models(self) -> tuple[str, ...]:
        """시도 순서대로 정렬한 모델 목록 (기본 → 폴백, 중복 제거)."""
        return tuple(dict.fromkeys((self.model_primary, *self.model_fallbacks)))

    @property
    def has_credentials(self) -> bool:
        """액세스 키 또는 프로필 중 하나가 설정되었는지 (실제 유효성은 확인하지 않음)."""
        return self.has_access_key or self.aws_profile is not None


def _get(env: Mapping[str, str], key: str) -> str | None:
    """값을 읽고 공백을 지운다. 빈 문자열은 미설정(None)으로 본다."""
    value = env.get(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def _parse_retries(value: str | None) -> int:
    if value is None:
        return DEFAULT_MAX_RETRIES
    try:
        retries = int(value)
    except ValueError as exc:
        raise ConfigError(f"LLM_MAX_RETRIES는 정수여야 합니다: {value!r}") from exc
    if retries < 0:
        raise ConfigError(f"LLM_MAX_RETRIES는 0 이상이어야 합니다: {retries}")
    return retries


def _parse_fallbacks(value: str | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_MODEL_FALLBACKS
    return tuple(m.strip() for m in value.split(",") if m.strip())


def _parse_log_level(value: str | None) -> str:
    level = (value or DEFAULT_LOG_LEVEL).upper()
    if level not in _LOG_LEVELS:
        raise ConfigError(f"LOG_LEVEL이 올바르지 않습니다: {value!r} (허용: {sorted(_LOG_LEVELS)})")
    return level


def drop_blank_aws_vars(environ: "os._Environ[str] | dict[str, str]") -> list[str]:
    """빈 AWS 인증 변수를 지운다(.env.example을 그대로 복사한 경우 대비). 지운 이름 목록을 돌려준다."""
    removed = [name for name in AWS_CREDENTIAL_VARS if name in environ and not environ[name].strip()]
    for name in removed:
        del environ[name]
    return removed


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """설정을 읽는다.

    env를 주면 그 값만 쓴다(테스트용, `.env` 파일을 읽지 않음).
    env가 없으면 루트의 `.env`를 os.environ에 채운 뒤(기존 값은 덮어쓰지 않음) os.environ을 읽는다.
    """
    if env is None:
        load_dotenv(ROOT_DIR / ".env", override=False)
        drop_blank_aws_vars(os.environ)
        env = os.environ

    return Settings(
        aws_region=_get(env, "AWS_REGION") or DEFAULT_REGION,
        aws_profile=_get(env, "AWS_PROFILE"),
        has_access_key=bool(_get(env, "AWS_ACCESS_KEY_ID") and _get(env, "AWS_SECRET_ACCESS_KEY")),
        model_primary=_get(env, "MODEL_PRIMARY") or DEFAULT_MODEL_PRIMARY,
        model_fallbacks=_parse_fallbacks(_get(env, "MODEL_FALLBACKS")),
        llm_max_retries=_parse_retries(_get(env, "LLM_MAX_RETRIES")),
        survey_file=_resolve_path(_get(env, "SURVEY_FILE") or DEFAULT_SURVEY_FILE),
        history_dir=_resolve_path(_get(env, "HISTORY_DIR") or DEFAULT_HISTORY_DIR),
        log_level=_parse_log_level(_get(env, "LOG_LEVEL")),
    )


_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_HANDLER_MARK = "_opic_handler"


def setup_logging(settings: Settings, log_dir: Path = LOGS_DIR) -> logging.Logger:
    """`opic` 로거에 콘솔 + `logs/app.log` 핸들러를 단다 (SERVICE §11).

    여러 번 불러도(Streamlit 재실행) 핸들러가 중복되지 않는다.
    """
    logger = logging.getLogger("opic")
    logger.setLevel(settings.log_level)
    logger.propagate = False

    for handler in [h for h in logger.handlers if getattr(h, _HANDLER_MARK, False)]:
        logger.removeHandler(handler)
        handler.close()

    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_LOG_FORMAT)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
    ]
    for handler in handlers:
        handler.setFormatter(formatter)
        setattr(handler, _HANDLER_MARK, True)
        logger.addHandler(handler)
    return logger
