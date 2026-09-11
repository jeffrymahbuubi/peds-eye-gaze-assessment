"""Tests for the gaze dropout / off-canvas diagnostic (SPEC-gaze-cursor-redesign.md S6).

Pure-logic tests: the module deliberately has no Qt or device dependency, so
unlike the canvas rendering it can be covered directly.
"""

from __future__ import annotations

import json

import pytest

from src.engine.gaze_diagnostics import GazeDropoutLog, gaze_dropout_log_path
from src.inputs.base import outside_distance

MS = 1_000_000


def _records(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def testoutside_distance_is_zero_inside_and_grows_outside():
    assert outside_distance(0.5, 0.5) == 0.0
    assert outside_distance(0.0, 1.0) == 0.0  # exactly on the edge is inside
    assert outside_distance(1.2, 0.5) == pytest.approx(0.2)
    assert outside_distance(0.5, -0.3) == pytest.approx(0.3)
    # A corner excursion reports the larger overshoot, not a Euclidean
    # combination -- otherwise the same real distance off-canvas would read as
    # ~1.4x worse diagonally than straight out the side.
    assert outside_distance(1.2, 1.2) == pytest.approx(0.2)


def test_dropout_run_is_recorded_once_when_it_ends_not_per_frame(tmp_path):
    path = tmp_path / "gaze_dropouts.jsonl"
    log = GazeDropoutLog(path, raw_probe=lambda: {"BPOGV": "0", "FPOGV": "0"})
    log.observe(0, True, (0.4, 0.4))
    for i in range(1, 6):  # five consecutive dropout frames
        log.observe(i * 10 * MS, False, (0.4, 0.4))
    log.observe(60 * MS, True, (0.45, 0.45))

    records = _records(path)
    assert len(records) == 1, "a run must produce one record, not one per frame"
    rec = records[0]
    assert rec["kind"] == "dropout"
    assert rec["frames"] == 5
    assert rec["duration_s"] == 0.05
    assert rec["truncated"] is False
    assert rec["raw_pog_at_start"] == {"BPOGV": "0", "FPOGV": "0"}
    # The position the cursor froze at is the last valid one, which is what
    # S4.1 says stays on screen for the duration of the dropout.
    assert rec["frozen_at_xy_norm"] == [0.4, 0.4]


def test_no_record_is_written_for_a_clean_session(tmp_path):
    path = tmp_path / "gaze_dropouts.jsonl"
    log = GazeDropoutLog(path)
    for i in range(10):
        log.observe(i * 10 * MS, True, (0.5, 0.5))
    log.close(100 * MS)
    assert _records(path) == []


def test_off_canvas_run_records_its_maximum_distance(tmp_path):
    """That maximum is the number S4.2's fade threshold is meant to be set
    from, so it must survive the run rather than only the final frame's."""
    path = tmp_path / "gaze_dropouts.jsonl"
    log = GazeDropoutLog(path)
    log.observe(0, True, (0.5, 0.5))
    log.observe(10 * MS, True, (1.1, 0.5))
    log.observe(20 * MS, True, (1.4, 0.5))  # furthest point of the excursion
    log.observe(30 * MS, True, (1.05, 0.5))
    log.observe(40 * MS, True, (0.9, 0.5))  # back inside, run ends

    records = _records(path)
    assert len(records) == 1
    assert records[0]["kind"] == "off_canvas"
    assert records[0]["max_distance_norm"] == pytest.approx(0.4)
    assert records[0]["frames"] == 3


def test_dropout_closes_an_open_off_canvas_run(tmp_path):
    """S4.5: through a dropout the position is frozen, not observed, so an
    off-canvas excursion cannot keep being measured across one."""
    path = tmp_path / "gaze_dropouts.jsonl"
    log = GazeDropoutLog(path)
    log.observe(0, True, (1.2, 0.5))  # off-canvas run opens
    log.observe(10 * MS, False, (1.2, 0.5))  # tracking lost
    log.observe(20 * MS, True, (0.5, 0.5))  # recovered, on-canvas

    kinds = [r["kind"] for r in _records(path)]
    assert kinds == ["off_canvas", "dropout"]


def test_close_flushes_a_dropout_that_never_recovered(tmp_path):
    path = tmp_path / "gaze_dropouts.jsonl"
    log = GazeDropoutLog(path)
    log.observe(0, True, (0.3, 0.7))
    log.observe(10 * MS, False, (0.3, 0.7))
    log.close(50 * MS)

    records = _records(path)
    assert len(records) == 1
    assert records[0]["truncated"] is True
    assert records[0]["frozen_at_xy_norm"] == [0.3, 0.7]


def test_a_dropout_before_any_valid_sample_has_no_frozen_position(tmp_path):
    path = tmp_path / "gaze_dropouts.jsonl"
    log = GazeDropoutLog(path)
    log.observe(0, False, (0.5, 0.5))
    log.close(10 * MS)
    assert _records(path)[0]["frozen_at_xy_norm"] is None


def test_writing_never_raises_when_the_path_is_unusable(tmp_path):
    """A diagnostic must not be able to break a task a child is sitting
    through, so filesystem errors are swallowed by design."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    log = GazeDropoutLog(blocker / "nested" / "gaze_dropouts.jsonl")
    log.observe(0, True, (0.5, 0.5))
    log.observe(10 * MS, False, (0.5, 0.5))
    log.close(20 * MS)  # must not raise


def test_log_path_is_shared_across_runs_and_subjects():
    a = gaze_dropout_log_path("sessions")
    assert a.name == "gaze_dropouts.jsonl"
    assert a.parent.name == "_diagnostics"
    assert gaze_dropout_log_path("sessions") == a
