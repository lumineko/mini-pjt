"""storage.py 테스트 (PRD F-08, F-09, 성공 기준 5). 실제 data/history 대신 tmp_path를 쓴다."""

import json

import pytest

from fixtures.sessions import completed_state
from opic.storage import SCHEMA_VERSION, StorageError, build_record, list_sessions, load_session, save_session


def test_save_and_load_round_trip(tmp_path):
    state = completed_state()
    path = save_session(state, tmp_path)
    assert path == tmp_path / "s-001.json"

    record = load_session("s-001", tmp_path)
    assert record["items"] == state["items"]
    assert record["summary"] == state["summary"]
    assert record["schema_version"] == SCHEMA_VERSION and record["saved_at"]


def test_record_excludes_progress_fields():
    record = build_record(completed_state(), saved_at="x")
    assert "current_question" not in record and "pending" not in record
    assert {"level_history", "survey_answers", "initial_level"} <= set(record)


def test_korean_is_saved_readably(tmp_path):
    path = save_session(completed_state(), tmp_path)
    assert "조깅" in path.read_text(encoding="utf-8")


def test_creates_history_dir(tmp_path):
    target = tmp_path / "nested" / "history"
    save_session(completed_state(), target)
    assert (target / "s-001.json").exists()


@pytest.mark.parametrize("n_items", [0, 3, 4])
def test_incomplete_session_is_not_saved(tmp_path, n_items):
    state = completed_state()
    state["items"] = state["items"][:n_items]
    with pytest.raises(StorageError):
        save_session(state, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_session_without_summary_is_not_saved(tmp_path):
    state = completed_state()
    state["summary"] = None
    with pytest.raises(StorageError):
        save_session(state, tmp_path)


@pytest.mark.parametrize("bad_id", ["../evil", "a/b", "a\\b", "", "x" * 65, "세션"])
def test_unsafe_session_id_rejected(tmp_path, bad_id):
    state = completed_state()
    state["session_id"] = bad_id
    with pytest.raises(StorageError):
        save_session(state, tmp_path)
    with pytest.raises(StorageError):
        load_session(bad_id, tmp_path)


def test_load_missing_session(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_session("nope", tmp_path)


def test_overwrite_same_session(tmp_path):
    save_session(completed_state(avg="IM"), tmp_path)
    save_session(completed_state(avg="IH"), tmp_path)
    assert load_session("s-001", tmp_path)["summary"]["average_grade"] == "IH"
    assert [p.name for p in tmp_path.iterdir()] == ["s-001.json"]  # 임시 파일 안 남음


def test_list_sessions_newest_first(tmp_path):
    save_session(completed_state("old", "2026-11-01T09:00:00+09:00"), tmp_path)
    save_session(completed_state("new", "2026-11-05T09:00:00+09:00", initial="IM", final="IH", avg="IH"), tmp_path)
    assert list_sessions(tmp_path) == [
        {"session_id": "new", "date": "2026-11-05T09:00:00+09:00", "initial_level": "IM", "final_level": "IH", "avg_grade": "IH"},
        {"session_id": "old", "date": "2026-11-01T09:00:00+09:00", "initial_level": "IM", "final_level": "IM", "avg_grade": "IM"},
    ]


def test_list_skips_broken_and_temp_files(tmp_path):
    save_session(completed_state(), tmp_path)
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "partial.json").write_text(json.dumps({"session_id": "p"}), encoding="utf-8")
    (tmp_path / ".tmp-abc.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    assert [e["session_id"] for e in list_sessions(tmp_path)] == ["s-001"]


def test_list_missing_dir(tmp_path):
    assert list_sessions(tmp_path / "none") == []
