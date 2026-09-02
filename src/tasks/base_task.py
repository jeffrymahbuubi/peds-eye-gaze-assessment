"""BaseTask — per-frame trial state machine (plan section 5.4).

The task is driven one frame at a time by :meth:`update`, so the same logic runs
under the live 60 Hz GUI loop and under the deterministic headless replay
pipeline. All timing is in nanoseconds (``time.time_ns`` domain).

Trial lifecycle::

    SHOW_TARGET -> WAIT_INPUT -> HIT / MISS / TIMEOUT -> FEEDBACK(ITI) -> NEXT

Subclasses provide the target sequence via :meth:`build_targets` and, if the
target moves, override :meth:`target_position`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from ..data.schema import TrialRecord
from ..inputs.base import Pointer, circle_contains, norm_to_px
from ..inputs.eye_input import DwellSelector


class Phase(Enum):
    READY = auto()
    SHOW_TARGET = auto()
    WAIT_INPUT = auto()
    RESULT = auto()
    ITI = auto()
    DONE = auto()


@dataclass(frozen=True, slots=True)
class TargetSpec:
    index: int
    x_norm: float
    y_norm: float
    radius_px: float


@dataclass(frozen=True, slots=True)
class FrameResult:
    phase: Phase
    trial_index: int
    target: TargetSpec | None
    target_xy_norm: tuple[float, float] | None  # live position (may move)
    dwell_progress: float
    pointer: Pointer
    just_finished_trial: bool
    selectable: bool = True  # whether a selection currently counts as a hit


class BaseTask:
    def __init__(
        self,
        config: dict[str, Any],
        screen_width_px: int,
        screen_height_px: int,
        recorder=None,
        feedback=None,
        dwell: DwellSelector | None = None,
        input_mode: str = "eye",
        seed: int = 0,
    ) -> None:
        self.config = config
        self.task_cfg: dict[str, Any] = config.get("task", {})
        self.task_id: str = self.task_cfg.get("task_id", "task")
        self.screen_w = screen_width_px
        self.screen_h = screen_height_px
        self.recorder = recorder
        self.feedback = feedback
        self.dwell = dwell
        self.input_mode = input_mode
        self.rng = random.Random(seed)

        self.timeout_ns = int(self.task_cfg.get("timeout_ms", 8000) * 1e6)
        self.iti_ns = int(self.task_cfg.get("inter_trial_interval_ms", 800) * 1e6)
        self.jitter_px = float(config.get("dwell", {}).get("jitter_tolerance_px", 40))

        self.targets: list[TargetSpec] = self.build_targets()
        self.trials: list[TrialRecord] = []

        self._phase = Phase.READY
        self._trial_index = -1
        self._current: TrialRecord | None = None
        self._trial_start_ns = 0
        self._phase_deadline_ns = 0

    def set_screen_size(self, width_px: int, height_px: int) -> None:
        """Update the pixel-space dimensions used for hit-testing.

        The live GUI calls this every frame with the canvas's actual current
        size, so the hitbox math here always matches what ``TaskCanvas``
        renders (it already paints using its real widget size, not the
        config default). Headless replay has no widget and never calls this,
        so it keeps using the configured ``screen_width_px``/``height_px``
        (see ``default.yaml``'s own comment on that fallback role).

        Ignores non-positive sizes (e.g. a widget queried before it's shown)
        rather than corrupting hit-testing with a degenerate 0x0 hitbox.
        """
        if width_px > 0 and height_px > 0:
            self.screen_w = width_px
            self.screen_h = height_px

    # -- to be provided by subclasses -------------------------------------

    def build_targets(self) -> list[TargetSpec]:
        raise NotImplementedError

    def target_position(self, target: TargetSpec, elapsed_ns: int) -> tuple[float, float]:
        """Live normalized position of the target (static by default)."""
        return target.x_norm, target.y_norm

    def is_selectable(self, target: TargetSpec, elapsed_ns: int) -> bool:
        """Whether a selection this frame counts as a hit (always True by default).

        Overridden by tasks with a timed selection window (e.g. follow_moving),
        where selecting outside the window is a failed attempt rather than a hit.
        """
        return True

    # -- public API --------------------------------------------------------

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def is_done(self) -> bool:
        return self._phase is Phase.DONE

    def update(self, t_ns: int, pointer: Pointer) -> FrameResult:
        just_finished = False

        if self._phase is Phase.READY:
            self._start_trial(t_ns)

        target = self.targets[self._trial_index] if 0 <= self._trial_index < len(self.targets) else None
        tx_norm, ty_norm = (None, None)
        dwell_progress = 0.0
        selectable = True

        if self._phase is Phase.WAIT_INPUT and target is not None and self._current is not None:
            elapsed = t_ns - self._trial_start_ns
            tx_norm, ty_norm = self.target_position(target, elapsed)
            selectable = self.is_selectable(target, elapsed)
            cx_px, cy_px = norm_to_px(tx_norm, ty_norm, self.screen_w, self.screen_h)
            px, py = norm_to_px(pointer.x, pointer.y, self.screen_w, self.screen_h)

            # The effective hitbox includes the jitter tolerance; this is the
            # region the tool treats as "on target" for both dwell and the
            # first-fixation metric, so the two never disagree.
            on_target = pointer.valid and circle_contains(
                cx_px, cy_px, target.radius_px + self.jitter_px, px, py
            )

            if on_target and self._current.t_first_gaze_on_target_ns is None:
                self._current.t_first_gaze_on_target_ns = t_ns

            if self.input_mode == "eye" and self.dwell is not None:
                state = self.dwell.update(t_ns, on_target)
                dwell_progress = state.progress
                if self.feedback is not None and state.progress > 0:
                    self.feedback.on_progress(tx_norm, ty_norm, state.progress)
                clicked = state.triggered  # dwell only triggers while on target
                on_target_at_click = clicked
            else:
                clicked = pointer.clicked
                on_target_at_click = clicked and on_target

            hit = on_target_at_click and selectable

            if clicked and not hit:
                # off-target and/or out-of-window selection: a failed attempt
                self._current.attempts += 1
                self._record_event(
                    "MISS_CLICK", t_ns, x=pointer.x, y=pointer.y, selectable=selectable
                )
            elif hit:
                self._current.attempts += 1
                self._current.t_click_ns = t_ns
                self._current.is_hit = True
                self._finish_trial(t_ns, timed_out=False)
                just_finished = True
            elif elapsed >= self.timeout_ns:
                self._current.is_timeout = True
                self._finish_trial(t_ns, timed_out=True)
                just_finished = True

        elif self._phase is Phase.ITI:
            if t_ns >= self._phase_deadline_ns:
                if self._trial_index + 1 >= len(self.targets):
                    self._phase = Phase.DONE
                else:
                    self._start_trial(t_ns)

        # Recompute the reported target after any phase transition above so the
        # FrameResult's target and trial_index always refer to the same trial.
        target = self.targets[self._trial_index] if 0 <= self._trial_index < len(self.targets) else None

        return FrameResult(
            phase=self._phase,
            trial_index=self._trial_index,
            target=target,
            target_xy_norm=(tx_norm, ty_norm) if tx_norm is not None else None,
            dwell_progress=dwell_progress,
            pointer=pointer,
            just_finished_trial=just_finished,
            selectable=selectable,
        )

    # -- internals ---------------------------------------------------------

    def _start_trial(self, t_ns: int) -> None:
        self._trial_index += 1
        target = self.targets[self._trial_index]
        self._trial_start_ns = t_ns
        self._current = TrialRecord(
            trial_id=self._trial_index,
            task_id=self.task_id,
            target_x=target.x_norm,
            target_y=target.y_norm,
            target_radius_px=target.radius_px,
            t_target_shown_ns=t_ns,
        )
        if self.dwell is not None:
            self.dwell.reset()
        self._phase = Phase.WAIT_INPUT
        if self.feedback is not None:
            self.feedback.on_target_shown(target.x_norm, target.y_norm)
        self._record_event("TARGET_SHOWN", t_ns, trial=self._trial_index,
                           x=target.x_norm, y=target.y_norm)

    def _finish_trial(self, t_ns: int, timed_out: bool) -> None:
        assert self._current is not None
        self._current.t_end_ns = t_ns
        self.trials.append(self._current)
        if self.feedback is not None:
            if self._current.is_hit:
                self.feedback.on_hit(self._current.target_x, self._current.target_y)
            else:
                self.feedback.on_miss(self._current.target_x, self._current.target_y)
        kind = "TIMEOUT" if timed_out else "HIT"
        self._record_event(kind, t_ns, trial=self._trial_index)
        self._current = None
        self._phase = Phase.ITI
        self._phase_deadline_ns = t_ns + self.iti_ns

    def _record_event(self, kind: str, t_ns: int, **payload: Any) -> None:
        if self.recorder is not None:
            self.recorder.record_event(kind, t_ns, **payload)
