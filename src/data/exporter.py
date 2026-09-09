"""Read a recorded session back into analysis-friendly structures.

Kept separate from :mod:`recorder` so analysis notebooks can depend on it
without pulling in write-side logic. ``pandas`` is imported lazily so the module
imports cleanly in environments where it is not installed.
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path
from typing import Any


def load_metadata(session_dir: str | Path) -> dict[str, Any]:
    path = Path(session_dir) / "metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_events(session_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(session_dir) / "events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def load_trials_rows(session_dir: str | Path) -> list[dict[str, str]]:
    """Load ``trials.csv`` as a list of dict rows (no pandas dependency)."""
    path = Path(session_dir) / "trials.csv"
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_trials_df(session_dir: str | Path):
    """Load ``trials.csv`` as a pandas DataFrame (requires pandas)."""
    import pandas as pd  # local import: optional dependency

    return pd.read_csv(Path(session_dir) / "trials.csv")


def load_gaze_df(session_dir: str | Path):
    """Load ``gaze_stream.csv`` as a pandas DataFrame (requires pandas)."""
    import pandas as pd

    return pd.read_csv(Path(session_dir) / "gaze_stream.csv")


def load_gaze_rows(session_dir: str | Path) -> list[dict[str, str]]:
    """Load ``gaze_stream.csv`` as a list of dict rows (no pandas dependency)."""
    path = Path(session_dir) / "gaze_stream.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


_EMPTY_FIXATION_METRICS: dict[str, Any] = {
    "n_samples": 0,
    "valid_ratio": None,
    "on_screen_ratio": None,
    "effective_rate_hz": None,
    "longest_gap_s": None,
    "n_fixations": 0,
    "mean_fixation_duration_s": None,
    "median_fixation_duration_s": None,
    "max_fixation_duration_s": None,
    "fixation_rate_per_min": None,
    "n_saccades": 0,
    "saccade_rate_per_min": None,
    "mean_pupil_left_mm": None,
    "mean_pupil_right_mm": None,
}


def compute_fixation_saccade_metrics(session_dir: str | Path) -> dict[str, Any]:
    """Session-level fixation/saccade/pupil features from ``gaze_stream.csv``.

    These map onto the oculomotor features used in the CP/CVI eye-tracking
    classification literature cited in ``SPEC-2026-09-02.md`` item 6 (fixation
    duration/frequency, saccade rate, tracked/"off-screen" proportion, pupil
    diameter). All inputs are already recorded per-sample; this just
    aggregates them — no new tracker data is required.
    """
    rows = load_gaze_rows(session_dir)
    if not rows:
        return dict(_EMPTY_FIXATION_METRICS)

    n_samples = len(rows)
    valid_rows = [r for r in rows if r.get("valid") == "1"]
    valid_ratio = len(valid_rows) / n_samples

    # On-screen: of the valid samples, the fraction whose normalized (x, y)
    # actually falls within the visible [0, 1] bounds -- a raw BPOG/FPOG
    # reading can be valid (tracker confidence) yet still land off the
    # physical screen (head turn, glasses glare deflecting the estimate).
    on_screen_rows = [
        r for r in valid_rows if 0.0 <= float(r["x"]) <= 1.0 and 0.0 <= float(r["y"]) <= 1.0
    ]
    on_screen_ratio = (len(on_screen_rows) / len(valid_rows)) if valid_rows else None

    t_values = [int(r["t_ns"]) for r in rows]
    t0, t1 = t_values[0], t_values[-1]
    duration_s = max((t1 - t0) / 1e9, 1e-9)
    duration_min = duration_s / 60.0
    effective_rate_hz = n_samples / duration_s if n_samples > 1 else None
    longest_gap_s = (max(b - a for a, b in zip(t_values, t_values[1:])) / 1e9) if n_samples > 1 else None

    # FPOGD (fix_duration_s) is cumulative for the life of a fixation, so the
    # last sample carrying a given fixation_id holds that fixation's total
    # duration; the count of distinct ids in arrival order gives fixation
    # count, and consecutive-id transitions approximate saccade count.
    last_duration_by_fixation: dict[str, float] = {}
    fixation_sequence: list[str] = []
    for r in valid_rows:
        fid = r.get("fixation_id")
        if not fid:
            continue
        if not fixation_sequence or fixation_sequence[-1] != fid:
            fixation_sequence.append(fid)
        dur = r.get("fix_duration_s")
        if dur:
            last_duration_by_fixation[fid] = float(dur)

    durations = list(last_duration_by_fixation.values())
    n_fixations = len(durations)
    n_saccades = max(len(fixation_sequence) - 1, 0)

    pupil_l = [float(r["pupil_left"]) for r in valid_rows if r.get("pupil_left")]
    pupil_r = [float(r["pupil_right"]) for r in valid_rows if r.get("pupil_right")]

    return {
        "n_samples": n_samples,
        "valid_ratio": round(valid_ratio, 4),
        "on_screen_ratio": round(on_screen_ratio, 4) if on_screen_ratio is not None else None,
        "effective_rate_hz": round(effective_rate_hz, 2) if effective_rate_hz is not None else None,
        "longest_gap_s": round(longest_gap_s, 3) if longest_gap_s is not None else None,
        "n_fixations": n_fixations,
        "mean_fixation_duration_s": round(statistics.mean(durations), 4) if durations else None,
        "median_fixation_duration_s": round(statistics.median(durations), 4) if durations else None,
        "max_fixation_duration_s": round(max(durations), 4) if durations else None,
        "fixation_rate_per_min": round(n_fixations / duration_min, 2) if n_fixations else None,
        "n_saccades": n_saccades,
        "saccade_rate_per_min": round(n_saccades / duration_min, 2) if n_saccades else None,
        "mean_pupil_left_mm": round(statistics.mean(pupil_l), 3) if pupil_l else None,
        "mean_pupil_right_mm": round(statistics.mean(pupil_r), 3) if pupil_r else None,
    }


def compute_trial_fixation_counts(session_dir: str | Path) -> dict[int, int]:
    """Distinct fixation count within each trial's [target-shown, end] window.

    A visual-search/spatial-selection task (``scanning``, ``click_grid``) is
    expected to show multiple fixations per trial as gaze searches among
    candidates; a pure fixation task (``click_static``) should show close to
    one. This distinguishes single-target fixation from target-target
    fixation shift per ``SPEC-2026-09-02.md`` item 6.
    """
    trial_rows = load_trials_rows(session_dir)
    gaze_rows = load_gaze_rows(session_dir)
    counts: dict[int, int] = {}
    for trial in trial_rows:
        t_start = int(trial["t_target_shown_ns"])
        t_end_raw = trial.get("t_end_ns")
        t_end = int(t_end_raw) if t_end_raw else t_start
        fixation_ids = {
            r["fixation_id"]
            for r in gaze_rows
            if r.get("valid") == "1" and r.get("fixation_id") and t_start <= int(r["t_ns"]) <= t_end
        }
        counts[int(trial["trial_id"])] = len(fixation_ids)
    return counts


def summarize(session_dir: str | Path) -> dict[str, Any]:
    """Compute a small headline summary from ``trials.csv`` without pandas."""
    rows = load_trials_rows(session_dir)
    n = len(rows)
    hits = sum(1 for r in rows if r.get("is_hit") == "1")
    timeouts = sum(1 for r in rows if r.get("is_timeout") == "1")
    rts = [float(r["reaction_time_ms"]) for r in rows if r.get("reaction_time_ms")]
    mean_rt = sum(rts) / len(rts) if rts else None
    median_rt = statistics.median(rts) if rts else None
    attempts = [int(r["attempts"]) for r in rows if r.get("attempts")]
    mean_attempts = statistics.mean(attempts) if attempts else None
    n_needing_reattempt = sum(1 for a in attempts if a > 1)
    ttff = [float(r["time_to_first_fixation_ms"]) for r in rows if r.get("time_to_first_fixation_ms")]
    mean_ttff = statistics.mean(ttff) if ttff else None
    return {
        "n_trials": n,
        "n_hits": hits,
        "n_timeouts": timeouts,
        "hit_rate": (hits / n) if n else None,
        "mean_reaction_time_ms": round(mean_rt, 2) if mean_rt is not None else None,
        "median_reaction_time_ms": round(median_rt, 2) if median_rt is not None else None,
        "mean_attempts": round(mean_attempts, 2) if mean_attempts is not None else None,
        "n_trials_needing_reattempt": n_needing_reattempt,
        "mean_time_to_first_fixation_ms": round(mean_ttff, 2) if mean_ttff is not None else None,
    }


def write_session_metrics(session_dir: str | Path) -> Path:
    """Compute and persist the rolled-up per-session result (Result logic).

    Combines :func:`summarize`, :func:`compute_fixation_saccade_metrics` and
    :func:`compute_trial_fixation_counts` into ``session_metrics.json`` next to
    ``trials.csv``/``gaze_stream.csv`` in ``session_dir``. Called automatically
    at the end of every run (live GUI and headless replay alike) so a rolled-up
    result always exists on disk without a separate manual
    ``analysis/analyze_session.py`` invocation.
    """
    payload = {
        "summary": summarize(session_dir),
        "fixation_saccade": compute_fixation_saccade_metrics(session_dir),
        "fixations_per_trial": compute_trial_fixation_counts(session_dir),
    }
    path = Path(session_dir) / "session_metrics.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
