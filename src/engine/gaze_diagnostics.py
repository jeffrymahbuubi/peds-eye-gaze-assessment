"""Gaze dropout / off-canvas excursion diagnostic (SPEC-gaze-cursor-redesign.md S6).

Built to answer questions the source alone cannot: how often the tracker
actually drops out during a real task, how long a dropout lasts, and how far
off the canvas real gaze travels. The off-canvas fade threshold (S4.2) is meant
to be set from this data rather than guessed -- the precedent is
``SPEC-gui-audit-2026-09-10.md`` S9, where a constant was guessed, implemented,
live-tested and still wrong, and only measurement produced the right value.

Deliberately mirrors ``src/engine/calibration.py``'s timing diagnostic: one
shared append-only JSONL under ``sessions/_diagnostics/``, across every run and
subject, with every filesystem error swallowed. A diagnostic must never be able
to break a session a child is sitting through.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..inputs.base import outside_distance


def gaze_dropout_log_path(output_root: str | Path) -> Path:
    """Where dropout records accumulate. Shared across runs and subjects, for
    the same reason the calibration timing log is: the questions it answers
    ("how often, how long, how far") are only answerable in aggregate."""
    return Path(output_root) / "_diagnostics" / "gaze_dropouts.jsonl"


def _append_record(path: str | Path, record: dict[str, Any]) -> None:
    """Append one JSONL record, never raising.

    Losing a diagnostic line is always preferable to interrupting a task, so
    every filesystem error is swallowed by design.
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


class GazeDropoutLog:
    """Per-frame observer that records dropout and off-canvas *runs*.

    A record is written when a run ends, not per frame -- a 150 Hz tracker
    would otherwise produce tens of thousands of lines per session and bury the
    signal. Nothing is written for a session with no dropouts.
    """

    def __init__(
        self,
        path: str | Path,
        raw_probe: Callable[[], dict[str, str] | None] | None = None,
        task_id: str | None = None,
    ) -> None:
        self._path = Path(path)
        self._raw_probe = raw_probe
        self._task_id = task_id

        self._drop_start_ns: int | None = None
        self._drop_frames = 0
        self._drop_raw: dict[str, str] | None = None
        self._drop_from_xy: tuple[float, float] | None = None

        self._off_start_ns: int | None = None
        self._off_frames = 0
        self._off_max_distance = 0.0

        self._last_valid_xy: tuple[float, float] | None = None

    # -- per-frame entry point --------------------------------------------

    def observe(self, t_ns: int, valid: bool, cursor_xy_norm: tuple[float, float]) -> None:
        """Feed one frame's pointer state. Cheap enough for the render loop."""
        if valid:
            self._end_dropout(t_ns)
            self._observe_off_canvas(t_ns, cursor_xy_norm)
            self._last_valid_xy = cursor_xy_norm
        else:
            # An off-canvas run cannot continue to be measured through a
            # dropout -- the position is frozen, not observed (S4.5) -- so
            # close it out before starting/continuing the dropout.
            self._end_off_canvas(t_ns)
            self._observe_dropout(t_ns)

    def close(self, t_ns: int) -> None:
        """Flush any run still open at end of task, so a dropout that never
        recovered is still recorded rather than silently dropped."""
        self._end_dropout(t_ns, truncated=True)
        self._end_off_canvas(t_ns, truncated=True)

    # -- dropout runs ------------------------------------------------------

    def _observe_dropout(self, t_ns: int) -> None:
        if self._drop_start_ns is None:
            self._drop_start_ns = t_ns
            self._drop_frames = 0
            self._drop_from_xy = self._last_valid_xy
            # Snapshot the raw REC that accompanied the dropout's first frame.
            # This is what distinguishes "the device sent literal zeros" from
            # "our own None -> 0.0 fallback manufactured them" (S6).
            self._drop_raw = self._raw_probe() if self._raw_probe is not None else None
        self._drop_frames += 1

    def _end_dropout(self, t_ns: int, truncated: bool = False) -> None:
        if self._drop_start_ns is None:
            return
        duration_s = max(0.0, (t_ns - self._drop_start_ns) / 1e9)
        _append_record(
            self._path,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": "dropout",
                "task_id": self._task_id,
                "duration_s": round(duration_s, 4),
                "frames": self._drop_frames,
                "truncated": truncated,
                "raw_pog_at_start": self._drop_raw,
                "frozen_at_xy_norm": (
                    [round(v, 4) for v in self._drop_from_xy] if self._drop_from_xy else None
                ),
            },
        )
        self._drop_start_ns = None
        self._drop_frames = 0
        self._drop_raw = None
        self._drop_from_xy = None

    # -- off-canvas runs ---------------------------------------------------

    def _observe_off_canvas(self, t_ns: int, cursor_xy_norm: tuple[float, float]) -> None:
        distance = outside_distance(*cursor_xy_norm)
        if distance <= 0.0:
            self._end_off_canvas(t_ns)
            return
        if self._off_start_ns is None:
            self._off_start_ns = t_ns
            self._off_frames = 0
            self._off_max_distance = 0.0
        self._off_frames += 1
        self._off_max_distance = max(self._off_max_distance, distance)

    def _end_off_canvas(self, t_ns: int, truncated: bool = False) -> None:
        if self._off_start_ns is None:
            return
        duration_s = max(0.0, (t_ns - self._off_start_ns) / 1e9)
        _append_record(
            self._path,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": "off_canvas",
                "task_id": self._task_id,
                "duration_s": round(duration_s, 4),
                "frames": self._off_frames,
                "truncated": truncated,
                # The number S4.2's fade threshold should be set from.
                "max_distance_norm": round(self._off_max_distance, 4),
            },
        )
        self._off_start_ns = None
        self._off_frames = 0
        self._off_max_distance = 0.0
