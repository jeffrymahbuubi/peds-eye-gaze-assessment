"""Structured data records for the eye-gaze assessment.

All records are plain dataclasses so they can be serialised to CSV/JSON without
any GUI dependency. Coordinates are stored in **normalized** screen space
(0.0-1.0, origin top-left) unless a field name explicitly ends in ``_px``.

The ``SCHEMA_VERSION`` constant is written into every ``metadata.json`` so that
downstream loaders can tolerate future schema changes (see risk table in the
project plan, section 8).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

SCHEMA_VERSION = 1


@dataclass(slots=True)
class GazeSample:
    """One normalized gaze sample.

    Attributes
    ----------
    t_ns:
        Monotonic-ish capture timestamp in nanoseconds (``time.time_ns``).
    x, y:
        Normalized best point-of-gaze, 0-1. May be outside [0, 1] briefly.
    valid:
        Whether the tracker reported this sample as valid (FPOGV/BPOGV).
    fixation_id:
        Fixation identifier (FPOGID); ``None`` if not fixating.
    fix_duration_s:
        Fixation duration so far, seconds (FPOGD).
    pupil_left, pupil_right:
        Pupil diameters if available (v2 analysis); ``None`` otherwise.
    """

    t_ns: int
    x: float
    y: float
    valid: bool
    fixation_id: int | None = None
    fix_duration_s: float | None = None
    pupil_left: float | None = None
    pupil_right: float | None = None

    def as_row(self) -> dict[str, Any]:
        return {
            "t_ns": self.t_ns,
            "x": self.x,
            "y": self.y,
            "valid": int(self.valid),
            "fixation_id": self.fixation_id if self.fixation_id is not None else "",
            "fix_duration_s": self.fix_duration_s if self.fix_duration_s is not None else "",
            "pupil_left": self.pupil_left if self.pupil_left is not None else "",
            "pupil_right": self.pupil_right if self.pupil_right is not None else "",
        }


@dataclass(slots=True)
class TrialRecord:
    """One completed trial (one row of ``trials.csv``)."""

    trial_id: int
    task_id: str
    target_x: float
    target_y: float
    target_radius_px: float
    t_target_shown_ns: int
    t_first_gaze_on_target_ns: int | None = None
    t_click_ns: int | None = None
    t_end_ns: int | None = None
    is_hit: bool = False
    is_timeout: bool = False
    attempts: int = 0
    # First moment this trial's target could actually be selected. Equal to
    # t_target_shown_ns for every task except follow_moving, the only one that
    # overrides BaseTask.is_selectable(); None if the window never opened.
    t_selectable_start_ns: int | None = None

    @property
    def reaction_time_ms(self) -> float | None:
        """Time from the target appearing to the selection.

        Kept unchanged, and comparable across tasks. Note for follow_moving
        specifically: its selection window opens at a random offset, so this
        figure is dominated by that offset rather than by the child --
        :attr:`reaction_time_from_selectable_ms` is the meaningful one there
        (SPEC-follow-moving-selection.md S4.2).
        """
        if self.t_click_ns is None:
            return None
        return (self.t_click_ns - self.t_target_shown_ns) / 1e6

    @property
    def reaction_time_from_selectable_ms(self) -> float | None:
        """Time from the target becoming selectable to the selection.

        For a task with no selection window this equals
        :attr:`reaction_time_ms`. For follow_moving it is the reaction time
        with the random window offset removed. Can be ~0 by design: a child
        already tracking has their held dwell fire the instant the window
        opens (S5.2).
        """
        if self.t_click_ns is None or self.t_selectable_start_ns is None:
            return None
        return (self.t_click_ns - self.t_selectable_start_ns) / 1e6

    @property
    def time_to_first_fixation_ms(self) -> float | None:
        if self.t_first_gaze_on_target_ns is None:
            return None
        return (self.t_first_gaze_on_target_ns - self.t_target_shown_ns) / 1e6

    def as_row(self) -> dict[str, Any]:
        row = {
            "trial_id": self.trial_id,
            "task_id": self.task_id,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "target_radius_px": self.target_radius_px,
            "t_target_shown_ns": self.t_target_shown_ns,
            "t_first_gaze_on_target_ns": _blank(self.t_first_gaze_on_target_ns),
            "t_click_ns": _blank(self.t_click_ns),
            "t_end_ns": _blank(self.t_end_ns),
            "is_hit": int(self.is_hit),
            "is_timeout": int(self.is_timeout),
            "attempts": self.attempts,
            "t_selectable_start_ns": _blank(self.t_selectable_start_ns),
            "reaction_time_ms": _blank(_round(self.reaction_time_ms)),
            "reaction_time_from_selectable_ms": _blank(
                _round(self.reaction_time_from_selectable_ms)
            ),
            "time_to_first_fixation_ms": _blank(_round(self.time_to_first_fixation_ms)),
        }
        return row

    @staticmethod
    def csv_header() -> list[str]:
        return [
            "trial_id",
            "task_id",
            "target_x",
            "target_y",
            "target_radius_px",
            "t_target_shown_ns",
            "t_first_gaze_on_target_ns",
            "t_click_ns",
            "t_end_ns",
            "is_hit",
            "is_timeout",
            "attempts",
            "t_selectable_start_ns",
            "reaction_time_ms",
            "reaction_time_from_selectable_ms",
            "time_to_first_fixation_ms",
        ]


@dataclass(slots=True)
class SessionMetadata:
    """Session-level metadata written to ``metadata.json``."""

    subject_id: str
    session_id: str
    started_ns: int
    schema_version: int = SCHEMA_VERSION
    gazepoint_model: str = "GP3HD"
    input_mode: str = "eye"
    calibration_error_px: float | None = None
    calibration_points: int | None = None
    tasks: list[str] = field(default_factory=list)
    notes: str = ""
    assessment_date: str = ""
    sex: str = ""
    # The settings this run actually used, and where they came from
    # (SPEC-live-settings-panel.md S10.4). Additive, so `schema_version` is
    # deliberately NOT bumped: every existing reader takes named keys and is
    # unaffected, and older sessions simply lack the block.
    settings: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def _round(value: float | None, ndigits: int = 2) -> float | None:
    return None if value is None else round(value, ndigits)


def _blank(value: Any) -> Any:
    return "" if value is None else value
