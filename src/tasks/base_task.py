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
    # Which element of the task's static layout this target is (e.g. a
    # scanning icon slot); -1 for tasks with no fixed multi-item layout.
    # Lets the canvas draw the *active* slot in full colour/shape while the
    # rest render as distractors, via FrameResult.target.slot_index.
    slot_index: int = -1


@dataclass(frozen=True, slots=True)
class FrameResult:
    phase: Phase
    trial_index: int
    target: TargetSpec | None
    target_xy_norm: tuple[float, float] | None  # live position (may move)
    dwell_progress: float
    pointer: Pointer
    just_finished_trial: bool
    # Where the pointer actually is in *canvas-normalized* coordinates, i.e.
    # the same space target_xy_norm is expressed in and the canvas renders in
    # (SPEC-gui-audit-2026-09-10.md S6). Distinct from ``pointer.x/y``, which
    # for a live tracker are normalized against the whole tracked monitor.
    # The renderer must use this, not pointer.x/y, or the drawn cursor and the
    # position hit-testing checks are two different points. May fall outside
    # [0,1] when real gaze is off the canvas -- clamping is the renderer's
    # decision, not this layer's, so hit-testing stays exact.
    cursor_xy_norm: tuple[float, float] = (0.5, 0.5)
    selectable: bool = True  # whether a selection currently counts as a hit
    # Instant (not dwell-gated) acknowledgment that gaze is on the target right
    # now (SPEC-2026-09-02.md item 2) -- distinct from dwell_progress, which
    # only becomes visible after threshold_ms of accumulated on-target time.
    on_target: bool = False


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

        # Real tracked-screen geometry for converting the *pointer* only
        # (SPEC-gui-audit-2026-09-10.md item 5) -- None until set_gaze_geometry
        # is called, in which case the pointer falls back to screen_w/screen_h
        # with a zero offset, i.e. today's exact (canvas-relative) behavior.
        # Kept separate from screen_w/screen_h, which stay canvas-relative and
        # keep driving target-position conversion (target coordinates are
        # authored normalized-to-canvas, not normalized-to-monitor).
        self._gaze_geometry: tuple[float, float, float, float] | None = None

        # Populated by subclasses (in build_targets) that lay out multiple
        # candidate positions on screen at once — e.g. click_grid's cells or
        # scanning's icon row. The GUI draws these as dim, unlit markers so
        # the multi-item layout is actually visible (SPEC-2026-09-02.md #3).
        # Stays None for single-target tasks (click_static, follow_moving).
        self.layout_slots: list[tuple[float, float]] | None = None
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

    def set_gaze_geometry(
        self, screen_width_px: float, screen_height_px: float, offset_x_px: float, offset_y_px: float
    ) -> None:
        """Tell hit-testing how to convert the *pointer* to canvas pixels
        when the canvas does not fill the tracked screen (SPEC-gui-audit-
        2026-09-10.md item 5).

        Gazepoint's ``BPOGX``/``BPOGY`` are normalized against the tracked
        screen Gazepoint Control reports via ``SCREEN_SIZE`` -- the full
        physical monitor, not this app's window. Whenever the canvas is
        smaller than that (a non-fullscreen window, a sidebar next to the
        canvas, ...), converting the pointer with the canvas's own width/
        height instead undershoots real gaze position, worse the further a
        target sits from center -- the confirmed root cause of "hard to
        reach the right side" reported in the SPEC.

        ``screen_width_px``/``screen_height_px`` is the tracked screen's real
        size; ``offset_x_px``/``offset_y_px`` is the canvas's on-screen
        position relative to that same tracked screen's origin (so the
        converted point lands in canvas-local pixels, matching
        ``screen_w``/``screen_h``'s own coordinate space used for targets).
        Non-positive width/height is ignored (mirrors ``set_screen_size``)
        rather than corrupting hit-testing with a degenerate conversion.
        Never called -> pointer conversion falls back to ``screen_w``/
        ``screen_h`` with a zero offset, i.e. today's exact behavior
        (headless replay and any caller that hasn't been updated yet).
        """
        if screen_width_px > 0 and screen_height_px > 0:
            self._gaze_geometry = (screen_width_px, screen_height_px, offset_x_px, offset_y_px)

    def pointer_to_canvas_px(self, pointer: Pointer) -> tuple[float, float]:
        """Convert a pointer to canvas-local pixels, applying the tracked-screen
        geometry from :meth:`set_gaze_geometry` when it's known.

        The single place this conversion happens, so hit-testing (below) and
        whatever the GUI draws can never drift apart -- they did before
        (SPEC-gui-audit-2026-09-10.md S6: item 5 corrected hit-testing only,
        while the canvas kept converting the raw pointer with its own widget
        size, so the drawn cursor left the widget's rect and Qt silently
        clipped it away).
        """
        if self._gaze_geometry is not None:
            gaze_w, gaze_h, offset_x, offset_y = self._gaze_geometry
            px, py = norm_to_px(pointer.x, pointer.y, gaze_w, gaze_h)
            return px - offset_x, py - offset_y
        return norm_to_px(pointer.x, pointer.y, self.screen_w, self.screen_h)

    def pointer_to_canvas_norm(self, pointer: Pointer) -> tuple[float, float]:
        """Same conversion as :meth:`pointer_to_canvas_px`, re-normalized to the
        canvas's own 0-1 space so the renderer can use it directly.

        Not clamped to [0,1]: a value outside that range is the truthful
        statement "real gaze is off the canvas", which the renderer needs to
        know about in order to decide what to show for it.
        """
        px, py = self.pointer_to_canvas_px(pointer)
        w = self.screen_w or 1
        h = self.screen_h or 1
        return px / w, py / h

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

    def scene_spec(self) -> dict[str, Any]:
        """Describe the task's persistent on-screen layout for the renderer.

        Fetched once when a task starts (see ``AssessmentApp.__init__``), not
        per frame. Default ``{"mode": "single"}`` matches today's rendering
        (one target on an empty field, plus the generic dim ``layout_slots``
        outlines for tasks that set them) so every task not yet ported to a
        dedicated mode is unaffected. ``scanning`` is the first task to
        override this (mode ``"icons"`` — see ``ScanningTask.scene_spec``);
        porting the rest (``"grid"`` for click_grid, ``"moving"`` for
        follow_moving) is future work, not done here.
        """
        return {"mode": "single"}

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
        on_target = False

        if self._phase is Phase.WAIT_INPUT and target is not None and self._current is not None:
            elapsed = t_ns - self._trial_start_ns
            tx_norm, ty_norm = self.target_position(target, elapsed)
            selectable = self.is_selectable(target, elapsed)
            cx_px, cy_px = norm_to_px(tx_norm, ty_norm, self.screen_w, self.screen_h)
            px, py = self.pointer_to_canvas_px(pointer)

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
            # Computed every frame, not just during WAIT_INPUT -- the cursor is
            # drawn continuously (including between trials), so it can't depend
            # on the hit-testing branch above having run.
            cursor_xy_norm=self.pointer_to_canvas_norm(pointer),
            selectable=selectable,
            on_target=on_target,
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
