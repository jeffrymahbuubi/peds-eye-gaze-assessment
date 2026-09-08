"""Unit tests for the dashboard's Qt-free helpers (SPEC-ui-setup-task-selection.md)."""

from __future__ import annotations

from src.engine.local_state import load_local_state, save_local_state
from src.engine.session_naming import next_session_id


def test_next_session_id_first_run_has_no_collision(tmp_path):
    session_id = next_session_id(tmp_path, "P001", "click_static", date_str="2026-09-09")
    assert session_id == "2026-09-09_P001_click_static_run1"


def test_next_session_id_increments_past_existing_runs(tmp_path):
    (tmp_path / "2026-09-09_P001_click_static_run1").mkdir()
    (tmp_path / "2026-09-09_P001_click_static_run2").mkdir()
    session_id = next_session_id(tmp_path, "P001", "click_static", date_str="2026-09-09")
    assert session_id == "2026-09-09_P001_click_static_run3"


def test_next_session_id_independent_per_subject_and_task(tmp_path):
    (tmp_path / "2026-09-09_P001_click_static_run1").mkdir()
    assert next_session_id(tmp_path, "P002", "click_static", date_str="2026-09-09") == (
        "2026-09-09_P002_click_static_run1"
    )
    assert next_session_id(tmp_path, "P001", "scanning", date_str="2026-09-09") == (
        "2026-09-09_P001_scanning_run1"
    )


def test_local_state_roundtrip(tmp_path):
    path = tmp_path / "local_state.json"
    assert load_local_state(path) == {}
    save_local_state({"host": "26.113.49.235", "port": 4242}, path)
    assert load_local_state(path) == {"host": "26.113.49.235", "port": 4242}


def test_local_state_merges_rather_than_replaces(tmp_path):
    path = tmp_path / "local_state.json"
    save_local_state({"host": "127.0.0.1"}, path)
    save_local_state({"port": 4242}, path)
    assert load_local_state(path) == {"host": "127.0.0.1", "port": 4242}


def test_local_state_malformed_file_treated_as_empty(tmp_path):
    path = tmp_path / "local_state.json"
    path.write_text("not json", encoding="utf-8")
    assert load_local_state(path) == {}
