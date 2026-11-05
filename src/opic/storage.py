"""세션 기록 저장·목록·조회 (PRD F-08, F-09 / SERVICE §4, §5).

- 5문항을 마치고 요약까지 만든 세션만 저장한다. 미완료 세션은 거부한다(F-09).
- 파일: `{history_dir}/{session_id}.json` (UTF-8, 한글 그대로). 임시 파일에 쓴 뒤 바꿔 넣어 쓰다 만 파일이 남지 않게 한다.
- session_id는 영문·숫자·`-`·`_`만 허용한다(경로 조작 방지).
- 목록은 시작 시각 최신순. 깨진 파일은 건너뛰고 로그만 남긴다.
"""

import json
import logging
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from opic.state import SESSION_ITEMS, Grade, Level

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# State에서 기록으로 옮기는 필드 (진행용 임시 필드 pending, current_* 등은 제외)
RECORD_FIELDS = (
    "session_id", "started_at", "survey_source", "survey_answers",
    "initial_level", "current_level", "level_history", "items", "summary",
)


class SessionListEntry(TypedDict):
    session_id: str
    date: str
    initial_level: Level
    final_level: Level
    avg_grade: Grade


class StorageError(ValueError):
    pass


def _check_id(session_id: str) -> str:
    if not isinstance(session_id, str) or not _SESSION_ID.match(session_id):
        raise StorageError(f"올바르지 않은 session_id: {session_id!r}")
    return session_id


def _path(history_dir: Path, session_id: str) -> Path:
    return Path(history_dir) / f"{_check_id(session_id)}.json"


def build_record(state: Mapping[str, Any], saved_at: str | None = None) -> dict[str, Any]:
    """State에서 저장할 기록을 만든다. 미완료면 StorageError."""
    items = state.get("items") or []
    if len(items) != SESSION_ITEMS or not state.get("summary"):
        raise StorageError(f"완료된 세션만 저장합니다 (문항 {len(items)}/{SESSION_ITEMS}, 요약 {'있음' if state.get('summary') else '없음'})")
    record = {field: state.get(field) for field in RECORD_FIELDS}
    record["schema_version"] = SCHEMA_VERSION
    record["saved_at"] = saved_at or datetime.now().astimezone().isoformat(timespec="seconds")
    return record


def save_session(state: Mapping[str, Any], history_dir: Path) -> Path:
    record = build_record(state)
    target = _path(history_dir, record["session_id"])
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    logger.info("세션 저장: %s", target.name)
    return target


def load_session(session_id: str, history_dir: Path) -> dict[str, Any]:
    path = _path(history_dir, session_id)
    if not path.exists():
        raise FileNotFoundError(f"세션 기록이 없습니다: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_sessions(history_dir: Path) -> list[SessionListEntry]:
    history_dir = Path(history_dir)
    if not history_dir.is_dir():
        return []

    entries: list[SessionListEntry] = []
    for path in history_dir.glob("*.json"):
        if path.name.startswith(".tmp-"):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            summary = record["summary"]
            entries.append(
                SessionListEntry(
                    session_id=record["session_id"],
                    date=record["started_at"],
                    initial_level=summary["initial_level"],
                    final_level=summary["final_level"],
                    avg_grade=summary["average_grade"],
                )
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("세션 기록을 읽지 못해 건너뜀: %s (%s)", path.name, exc)
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries
