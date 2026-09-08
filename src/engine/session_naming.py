"""Session-directory naming with a collision-proof run index.

SPEC-ui-setup-task-selection.md S3.1.8: the dashboard's embed-in-place task
hosting explicitly wants to support re-running the same task for the same
subject on the same day (diki's own "run in any order, re-run freely"
model). The pre-existing ``<date>_<subject_id>_<task_id>`` naming
(:mod:`src.app`) has no run/time component, so a same-day re-run would
silently reuse -- and overwrite -- the prior run's session directory
(``SessionRecorder`` creates its directory with ``exist_ok=True``). Kept
Qt-free so it can be unit tested without importing PySide6.
"""

from __future__ import annotations

import time
from pathlib import Path


def next_run_number(
    output_root: str | Path, subject_id: str, task_id: str, date_str: str | None = None
) -> int:
    """Return the next free run index ``N`` for this subject/task/day.

    Extracted out of :func:`next_session_id` (SPEC-ui-setup-task-selection.md
    S11.5) so the dashboard UI can show "this will be run N" the moment Run
    is clicked, without duplicating the directory-scan logic or waiting for
    ``AssessmentApp``/``SessionRecorder`` to create the directory first.
    """
    date_str = date_str or time.strftime("%Y-%m-%d")
    base = f"{date_str}_{subject_id}_{task_id}"
    root = Path(output_root)
    n = 1
    while (root / f"{base}_run{n}").exists():
        n += 1
    return n


def next_session_id(
    output_root: str | Path, subject_id: str, task_id: str, date_str: str | None = None
) -> str:
    """Return ``<date>_<subject_id>_<task_id>_run<N>`` for the next free ``N``.

    ``N`` starts at 1 and is chosen by checking which ``_run<N>`` directories
    already exist under ``output_root`` -- so a re-run never overwrites a
    prior attempt, and a from-scratch subject/task/day always gets ``_run1``.
    """
    date_str = date_str or time.strftime("%Y-%m-%d")
    n = next_run_number(output_root, subject_id, task_id, date_str=date_str)
    return f"{date_str}_{subject_id}_{task_id}_run{n}"
