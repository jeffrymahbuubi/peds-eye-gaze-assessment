"""Tests for the session recorder and exporter."""

from __future__ import annotations

from pathlib import Path

from src.data.exporter import (
    compute_fixation_saccade_metrics,
    compute_trial_fixation_counts,
    load_metadata,
    load_trials_rows,
    summarize,
)
from src.data.recorder import SessionRecorder
from src.data.schema import GazeSample, SessionMetadata, TrialRecord


def make_metadata() -> SessionMetadata:
    return SessionMetadata(
        subject_id="P001",
        session_id="2026-07-15_P001_S1",
        started_ns=1000,
        input_mode="eye",
        tasks=["click_static"],
    )


def test_recorder_writes_all_artifacts(tmp_path: Path):
    meta = make_metadata()
    with SessionRecorder(meta, output_root=tmp_path) as rec:
        rec.record_gaze(GazeSample(t_ns=0, x=0.5, y=0.5, valid=True, fixation_id=1))
        rec.record_event("TARGET_SHOWN", t_ns=0, trial=0, x=0.5, y=0.5)
        rec.log("started")
        trials = [
            TrialRecord(
                trial_id=0,
                task_id="click_static",
                target_x=0.5,
                target_y=0.5,
                target_radius_px=90,
                t_target_shown_ns=0,
                t_click_ns=850_000_000,
                is_hit=True,
                attempts=1,
            )
        ]
        rec.write_trials(trials)

    session_dir = tmp_path / meta.session_id
    for name in ("metadata.json", "gaze_stream.csv", "trials.csv", "events.jsonl", "session.log"):
        assert (session_dir / name).exists(), name


def test_trial_reaction_time_computation():
    trial = TrialRecord(
        trial_id=0,
        task_id="t",
        target_x=0.0,
        target_y=0.0,
        target_radius_px=90,
        t_target_shown_ns=0,
        t_first_gaze_on_target_ns=300_000_000,
        t_click_ns=850_000_000,
        is_hit=True,
    )
    assert trial.reaction_time_ms == 850.0
    assert trial.time_to_first_fixation_ms == 300.0
    row = trial.as_row()
    assert row["reaction_time_ms"] == 850.0
    assert row["is_hit"] == 1


def test_exporter_roundtrip_and_summary(tmp_path: Path):
    meta = make_metadata()
    trials = [
        TrialRecord(0, "t", 0.5, 0.5, 90, 0, t_click_ns=800_000_000, is_hit=True, attempts=1),
        TrialRecord(1, "t", 0.5, 0.5, 90, 0, is_timeout=True),
    ]
    with SessionRecorder(meta, output_root=tmp_path) as rec:
        rec.write_trials(trials)

    session_dir = tmp_path / meta.session_id
    rows = load_trials_rows(session_dir)
    assert len(rows) == 2
    assert load_metadata(session_dir)["schema_version"] == 1

    summary = summarize(session_dir)
    assert summary["n_trials"] == 2
    assert summary["n_hits"] == 1
    assert summary["n_timeouts"] == 1
    assert summary["hit_rate"] == 0.5
    assert summary["mean_reaction_time_ms"] == 800.0


def test_recorder_raises_if_not_open(tmp_path: Path):
    rec = SessionRecorder(make_metadata(), output_root=tmp_path)
    try:
        import pytest

        with pytest.raises(RuntimeError):
            rec.record_gaze(GazeSample(t_ns=0, x=0.0, y=0.0, valid=True))
    finally:
        rec.close()


def _make_two_fixation_session(tmp_path: Path) -> Path:
    """One trial spanning two fixations (0-0.4s, 0.5-0.9s) with pupil data."""
    meta = make_metadata()
    with SessionRecorder(meta, output_root=tmp_path) as rec:
        for i in range(5):
            rec.record_gaze(
                GazeSample(
                    t_ns=i * 100_000_000,
                    x=0.5,
                    y=0.5,
                    valid=True,
                    fixation_id=1,
                    fix_duration_s=(i + 1) * 0.1,
                    pupil_left=3.5,
                    pupil_right=3.6,
                )
            )
        for i in range(5):
            rec.record_gaze(
                GazeSample(
                    t_ns=500_000_000 + i * 100_000_000,
                    x=0.6,
                    y=0.6,
                    valid=True,
                    fixation_id=2,
                    fix_duration_s=(i + 1) * 0.1,
                    pupil_left=3.5,
                    pupil_right=3.6,
                )
            )
        rec.write_trials(
            [
                TrialRecord(
                    trial_id=0,
                    task_id="scanning",
                    target_x=0.5,
                    target_y=0.5,
                    target_radius_px=80,
                    t_target_shown_ns=0,
                    t_end_ns=900_000_000,
                    is_hit=True,
                    attempts=1,
                )
            ]
        )
    return tmp_path / meta.session_id


def test_compute_fixation_saccade_metrics(tmp_path: Path):
    session_dir = _make_two_fixation_session(tmp_path)
    fix = compute_fixation_saccade_metrics(session_dir)
    assert fix["n_samples"] == 10
    assert fix["valid_ratio"] == 1.0
    assert fix["n_fixations"] == 2
    assert fix["n_saccades"] == 1
    assert fix["mean_fixation_duration_s"] == 0.5
    assert fix["max_fixation_duration_s"] == 0.5
    assert fix["mean_pupil_left_mm"] == 3.5
    assert fix["mean_pupil_right_mm"] == 3.6


def test_compute_fixation_saccade_metrics_empty_session(tmp_path: Path):
    meta = make_metadata()
    with SessionRecorder(meta, output_root=tmp_path):
        pass
    fix = compute_fixation_saccade_metrics(tmp_path / meta.session_id)
    assert fix["n_samples"] == 0
    assert fix["n_fixations"] == 0
    assert fix["mean_fixation_duration_s"] is None


def test_compute_trial_fixation_counts(tmp_path: Path):
    session_dir = _make_two_fixation_session(tmp_path)
    counts = compute_trial_fixation_counts(session_dir)
    assert counts == {0: 2}
