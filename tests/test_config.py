"""config.py 테스트: 실제 .env나 자격 증명 없이 env 딕셔너리로 확인한다."""

import logging

import pytest

from opic import config
from opic.config import ConfigError, load_settings, setup_logging


def test_defaults_without_any_env():
    s = load_settings({})
    assert s.aws_region == "ap-northeast-2"
    assert s.aws_profile is None
    assert s.has_credentials is False
    assert s.model_primary == "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    assert s.model_fallbacks == ("global.anthropic.claude-haiku-4-5-20251001-v1:0",)
    assert s.llm_max_retries == 2
    assert s.survey_file == config.ROOT_DIR / "opic_survey.md"
    assert s.history_dir == config.ROOT_DIR / "data" / "history"
    assert s.log_level == "INFO"


def test_blank_values_fall_back_to_defaults():
    s = load_settings({"MODEL_PRIMARY": "  ", "AWS_PROFILE": "", "LLM_MAX_RETRIES": ""})
    assert s.model_primary == config.DEFAULT_MODEL_PRIMARY
    assert s.aws_profile is None
    assert s.llm_max_retries == 2


def test_overrides_and_fallback_list_parsing():
    s = load_settings(
        {
            "AWS_REGION": "ap-northeast-2",
            "MODEL_PRIMARY": "model-a",
            "MODEL_FALLBACKS": " model-b , ,model-c ",
            "LLM_MAX_RETRIES": "0",
            "LOG_LEVEL": "debug",
        }
    )
    assert s.aws_region == "ap-northeast-2"
    assert s.model_fallbacks == ("model-b", "model-c")
    assert s.models == ("model-a", "model-b", "model-c")
    assert s.llm_max_retries == 0
    assert s.log_level == "DEBUG"


def test_models_removes_duplicate_of_primary():
    s = load_settings({"MODEL_PRIMARY": "m1", "MODEL_FALLBACKS": "m1,m2"})
    assert s.models == ("m1", "m2")


@pytest.mark.parametrize(
    "env",
    [
        {"AWS_ACCESS_KEY_ID": "id", "AWS_SECRET_ACCESS_KEY": "secret"},
        {"AWS_PROFILE": "dev"},
    ],
)
def test_credentials_by_key_or_profile(env):
    assert load_settings(env).has_credentials is True


def test_access_key_without_secret_is_not_credentials():
    assert load_settings({"AWS_ACCESS_KEY_ID": "id"}).has_credentials is False


def test_relative_and_absolute_paths(tmp_path):
    s = load_settings({"SURVEY_FILE": "x/survey.md", "HISTORY_DIR": str(tmp_path)})
    assert s.survey_file == config.ROOT_DIR / "x" / "survey.md"
    assert s.history_dir == tmp_path


@pytest.mark.parametrize("value", ["abc", "-1"])
def test_invalid_retries(value):
    with pytest.raises(ConfigError):
        load_settings({"LLM_MAX_RETRIES": value})


def test_invalid_log_level():
    with pytest.raises(ConfigError):
        load_settings({"LOG_LEVEL": "LOUD"})


def test_env_var_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("MODEL_PRIMARY=from-dotenv\nLOG_LEVEL=WARNING\n", encoding="utf-8")
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    monkeypatch.setenv("MODEL_PRIMARY", "from-env")
    # setenv로 원래 상태를 기록한 뒤 지워야, load_dotenv가 채운 값이 테스트 후 원상 복구된다.
    monkeypatch.setenv("LOG_LEVEL", "")
    monkeypatch.delenv("LOG_LEVEL")
    s = load_settings()
    assert s.model_primary == "from-env"
    assert s.log_level == "WARNING"


def test_drop_blank_aws_vars():
    environ = {"AWS_PROFILE": "", "AWS_SESSION_TOKEN": "  ", "AWS_ACCESS_KEY_ID": "id", "OTHER": ""}
    assert sorted(config.drop_blank_aws_vars(environ)) == ["AWS_PROFILE", "AWS_SESSION_TOKEN"]
    assert environ == {"AWS_ACCESS_KEY_ID": "id", "OTHER": ""}


def test_blank_aws_vars_from_dotenv_are_removed(tmp_path, monkeypatch):
    # .env.example을 그대로 복사한 상황: 빈 AWS_PROFILE이 boto3를 깨뜨리면 안 된다
    (tmp_path / ".env").write_text("AWS_PROFILE=\nAWS_SESSION_TOKEN=\n", encoding="utf-8")
    monkeypatch.setattr(config, "ROOT_DIR", tmp_path)
    for name in ("AWS_PROFILE", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(name, "")  # 원래 상태 기록용
        monkeypatch.delenv(name)
    s = load_settings()
    import os
    assert "AWS_PROFILE" not in os.environ and "AWS_SESSION_TOKEN" not in os.environ
    assert s.aws_profile is None


def test_setup_logging_writes_file_and_no_duplicate_handlers(tmp_path):
    s = load_settings({"LOG_LEVEL": "INFO"})
    setup_logging(s, log_dir=tmp_path)
    logger = setup_logging(s, log_dir=tmp_path)
    marked = [h for h in logger.handlers if getattr(h, "_opic_handler", False)]
    assert len(marked) == 2

    logging.getLogger("opic.test").info("hello")
    for h in marked:
        h.flush()
    assert "hello" in (tmp_path / "app.log").read_text(encoding="utf-8")

    for h in marked:
        logger.removeHandler(h)
        h.close()
