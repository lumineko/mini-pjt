"""LLM 호출 트레이스 — 로컬 JSONL (SERVICE §13, TASK Phase 6).

- 저장: `Settings.trace_file`(기본 `logs/traces.jsonl`)에 시도 1번 = 한 줄로 이어 쓴다. 새 라이브러리 없음.
- 범위: 메타데이터(세션·노드·문항·프롬프트 버전·모델·시도·폴백·소요 시간·성공/오류) + LLM 출력.
  입력 메시지(답변 원문 포함)는 넣지 않는다. 답변은 완료 세션 JSON(data/history)에 이미 있다.
- 보존: 자동 삭제 없음(필요하면 파일을 직접 지운다).
- 연결: `install(settings)`가 `llm.after_call_hooks` 맨 끝과 `llm.error_call_hooks`에 기록기를 단다.
  after 훅 앞쪽의 출력 검사가 거부하면 성공 기록 대신 오류(GuardrailViolation) 기록이 남는다.
- 기록 실패(디스크 오류 등)는 경고 로그만 남기고 삼킨다. 트레이스 때문에 LLM 호출이 폴백되면 안 된다.
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from opic import llm
from opic.config import Settings

logger = logging.getLogger(__name__)

# 메타데이터 중 기록할 키 (순서 = 파일에 보이는 순서)
META_KEYS = ("session_id", "node", "item_index", "role", "prompt", "model_id", "attempt", "fallback", "elapsed_ms", "injection_flags")
ERROR_MESSAGE_LIMIT = 500


def serialize_output(output: Any) -> Any:
    """구조화 출력은 dict, AIMessage는 content, 그 밖은 문자열."""
    if isinstance(output, BaseMessage):
        return output.content
    if isinstance(output, BaseModel):
        return output.model_dump(mode="json")
    return str(output)


def build_record(meta: dict[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    record = {"ts": datetime.now().astimezone().isoformat(timespec="milliseconds")}
    record.update({key: meta.get(key) for key in META_KEYS})
    record["status"] = status
    record.update(extra)
    return record


class TraceRecorder:
    """JSONL 트레이스 기록기. 여러 Streamlit 세션(스레드)이 함께 써도 줄이 섞이지 않게 잠근다."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def after_call(self, role: str, output: Any, meta: dict[str, Any]) -> None:
        self.write(build_record(meta, "ok", output=serialize_output(output)))

    def on_error(self, role: str, exc: BaseException, meta: dict[str, Any]) -> None:
        self.write(build_record(
            meta, "error",
            error={"type": type(exc).__name__, "message": str(exc)[:ERROR_MESSAGE_LIMIT]},
        ))

    def write(self, record: dict[str, Any]) -> None:
        try:
            line = json.dumps(record, ensure_ascii=False, default=str)
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as exc:  # noqa: BLE001 - 기록 실패는 호출 흐름에 영향 주지 않음
            logger.warning("트레이스 기록 실패 (%s): %s", self.path, exc)


def _is_recorder_hook(hook: Any) -> bool:
    return isinstance(getattr(hook, "__self__", None), TraceRecorder)


def uninstall() -> None:
    """등록된 트레이스 기록기를 모두 뗀다."""
    llm.after_call_hooks[:] = [h for h in llm.after_call_hooks if not _is_recorder_hook(h)]
    llm.error_call_hooks[:] = [h for h in llm.error_call_hooks if not _is_recorder_hook(h)]


def install(settings: Settings) -> TraceRecorder | None:
    """기록기를 훅에 단다. 여러 번 불러도(Streamlit 재실행) 하나만 남는다. 꺼져 있으면 None."""
    uninstall()
    if settings.trace_file is None:
        logger.info("트레이스 꺼짐 (TRACE_FILE=off)")
        return None
    recorder = TraceRecorder(settings.trace_file)
    llm.after_call_hooks.append(recorder.after_call)
    llm.error_call_hooks.append(recorder.on_error)
    logger.info("트레이스 기록: %s", recorder.path)
    return recorder


def read_traces(path: Path) -> list[dict[str, Any]]:
    """트레이스 파일을 읽는다(분석·테스트용). 깨진 줄은 건너뛴다."""
    path = Path(path)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
