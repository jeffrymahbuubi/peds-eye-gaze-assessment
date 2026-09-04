"""Dwell-selection logic for gaze input (plan section 5.2).

The dwell rule is deliberately isolated from any tracker or GUI so it can be
unit-tested against synthetic timelines:

1. While the pointer stays on the active target's hitbox, accumulate dwell time.
2. When accumulated time >= ``threshold_ms`` -> emit a click.
3. After a click, enter a ``refractory_ms`` window during which no dwell
   accumulates (prevents double-triggering).

A short *hold grace* tolerates momentary drop-outs (a single invalid gaze frame
or brief saccade off the hitbox) without resetting progress; this matters a lot
for children whose gaze is noisier than adults'.

SPEC-2026-09-02.md items 1/2: raw point-of-gaze is inherently noisy, and that
noise -- not a hitbox/timing bug -- was the root cause of both the reported
"jittery cursor" (item 1) and "gaze on target does nothing" (item 2): jitter
pushes the pointer in and out of the hitbox faster than ``hold_grace_ms``
tolerates, so dwell progress kept resetting before it became visible.
:class:`GazeSmoother` filters the pointer used for cursor rendering and
on-target hit-testing to address both from one fix.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..data.schema import GazeSample
from .base import Pointer


@dataclass(frozen=True, slots=True)
class DwellConfig:
    threshold_ms: float = 800.0
    refractory_ms: float = 500.0
    hold_grace_ms: float = 120.0  # tolerated off-target gap before progress resets


@dataclass(frozen=True, slots=True)
class SmoothingConfig:
    enabled: bool = True
    # Exponential-moving-average weight given to each new raw sample: lower
    # = smoother but more lag behind real gaze movement, higher = more
    # responsive but closer to raw jitter. 0.35 was chosen as a middle
    # ground -- responsive enough for follow_moving's tracked target, smooth
    # enough to stop click_static-style dwell from resetting on noise.
    alpha: float = 0.35


class GazeSmoother:
    """Exponential moving average over the raw (x, y) point of gaze.

    Deliberately applied only to the pointer used for cursor rendering and
    on-target hit-testing (see :meth:`EyeInput.poll`) -- never to the raw
    :class:`GazeSample` handed to the session recorder, so
    ``gaze_stream.csv`` and the fixation/saccade metrics derived from it
    (``CLINICAL_DATA_REFERENCE.md``) stay untouched by this UI-facing filter.
    """

    def __init__(self, config: SmoothingConfig | None = None) -> None:
        self.config = config or SmoothingConfig()
        self._x: float | None = None
        self._y: float | None = None

    def reset(self) -> None:
        """Drop the running average (e.g. after a gaze drop-out) so the next
        sample starts fresh instead of blending with a stale position."""
        self._x = None
        self._y = None

    def update(self, x: float, y: float) -> tuple[float, float]:
        if not self.config.enabled or self._x is None:
            self._x, self._y = x, y
            return x, y
        a = self.config.alpha
        self._x = a * x + (1 - a) * self._x
        self._y = a * y + (1 - a) * self._y
        return self._x, self._y


@dataclass(frozen=True, slots=True)
class DwellState:
    progress: float          # 0-1 fill toward threshold
    triggered: bool          # rising-edge click this frame
    in_refractory: bool


class DwellSelector:
    """Temporal dwell accumulator. Target hit-testing is done by the caller."""

    def __init__(self, config: DwellConfig | None = None) -> None:
        self.config = config or DwellConfig()
        self._dwell_start_ns: int | None = None
        self._last_on_target_ns: int | None = None
        self._refractory_until_ns: int | None = None

    def reset(self) -> None:
        """Reset accumulation and refractory (e.g. between trials)."""
        self._dwell_start_ns = None
        self._last_on_target_ns = None
        self._refractory_until_ns = None

    def update(self, t_ns: int, on_target: bool) -> DwellState:
        threshold_ns = int(self.config.threshold_ms * 1e6)
        refractory_ns = int(self.config.refractory_ms * 1e6)
        grace_ns = int(self.config.hold_grace_ms * 1e6)

        # Refractory window: no accumulation, report clearly.
        if self._refractory_until_ns is not None:
            if t_ns < self._refractory_until_ns:
                return DwellState(progress=0.0, triggered=False, in_refractory=True)
            self._refractory_until_ns = None

        if not on_target:
            # Off target: preserve progress only within the hold-grace window,
            # but never *complete* a dwell while the gaze is away — the grace
            # bridges brief drop-outs, it does not select in absentia.
            within_grace = (
                self._dwell_start_ns is not None
                and self._last_on_target_ns is not None
                and (t_ns - self._last_on_target_ns) <= grace_ns
            )
            if not within_grace:
                self._dwell_start_ns = None
                self._last_on_target_ns = None
                return DwellState(progress=0.0, triggered=False, in_refractory=False)
            elapsed = t_ns - self._dwell_start_ns
            progress = 0.0 if threshold_ns <= 0 else min(1.0, elapsed / threshold_ns)
            return DwellState(progress=progress, triggered=False, in_refractory=False)

        # On target: accumulate and allow completion.
        if self._dwell_start_ns is None:
            self._dwell_start_ns = t_ns
        self._last_on_target_ns = t_ns

        elapsed = t_ns - self._dwell_start_ns
        if elapsed >= threshold_ns:
            self._dwell_start_ns = None
            self._last_on_target_ns = None
            self._refractory_until_ns = t_ns + refractory_ns
            return DwellState(progress=1.0, triggered=True, in_refractory=False)

        progress = 0.0 if threshold_ns <= 0 else min(1.0, elapsed / threshold_ns)
        return DwellState(progress=progress, triggered=False, in_refractory=False)


class EyeInput:
    """Gaze pointer provider backed by a gaze source.

    The gaze source is any object exposing ``latest() -> GazeSample | None``
    (the live :class:`GazepointClient`) or, for deterministic playback, a
    callable set via :meth:`from_callable`. Click decisions are NOT made here —
    they depend on the active target and are computed by the task engine using
    a :class:`DwellSelector`.
    """

    def __init__(
        self,
        gaze_source,
        dwell_config: DwellConfig | None = None,
        smoothing_config: SmoothingConfig | None = None,
    ) -> None:
        self._source = gaze_source
        self.dwell = DwellSelector(dwell_config)
        self.smoother = GazeSmoother(smoothing_config)
        self._last_valid: GazeSample | None = None

    def latest_sample(self) -> GazeSample | None:
        """Return the raw, unsmoothed sample -- used for recording, never for
        the pointer (see :meth:`poll`)."""
        sample = self._source.latest()
        if sample is not None and sample.valid:
            self._last_valid = sample
        return sample

    def poll(self, t_ns: int) -> Pointer:
        """Return the smoothed gaze pointer (clicked is always False; dwell is
        separate).

        If the underlying source exposes ``is_connected()`` and reports the
        link as down, the pointer is forced invalid at the neutral center —
        without this, a dropped connection would otherwise look identical to
        a live, motionless gaze (the last cached sample stays "valid" forever).
        """
        is_connected = getattr(self._source, "is_connected", None)
        if is_connected is not None and not is_connected():
            self.smoother.reset()
            return Pointer(x=0.5, y=0.5, valid=False, clicked=False)
        sample = self.latest_sample()
        if sample is None:
            if self._last_valid is None:
                return Pointer(x=0.5, y=0.5, valid=False, clicked=False)
            sample = self._last_valid
        if not sample.valid:
            # Don't let an invalid/stale point smear the running average --
            # the next valid sample should start a fresh average rather than
            # blend toward wherever gaze happened to be lost.
            self.smoother.reset()
            return Pointer(x=sample.x, y=sample.y, valid=False, clicked=False)
        sx, sy = self.smoother.update(sample.x, sample.y)
        return Pointer(x=sx, y=sy, valid=True, clicked=False)

    def close(self) -> None:  # pragma: no cover - passthrough
        close = getattr(self._source, "stop", None) or getattr(self._source, "close", None)
        if callable(close):
            close()
