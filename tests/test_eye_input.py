"""Tests for EyeInput's handling of a disconnected gaze source (gap D) and,
below, its gaze-smoothing behavior (SPEC-2026-09-02.md items 1 & 2)."""

from __future__ import annotations

from src.data.schema import GazeSample
from src.inputs.base import circle_contains, norm_to_px
from src.inputs.eye_input import DwellConfig, EyeInput, SmoothingConfig


class _StubSource:
    """A gaze source whose connection state and last sample are set by hand."""

    def __init__(self, connected: bool, sample: GazeSample | None) -> None:
        self._connected = connected
        self._sample = sample

    def is_connected(self) -> bool:
        return self._connected

    def latest(self) -> GazeSample | None:
        return self._sample


def _sample(valid: bool = True) -> GazeSample:
    return GazeSample(t_ns=0, x=0.9, y=0.9, valid=valid, fixation_id=None, fix_duration_s=None)


def test_poll_returns_valid_pointer_when_connected():
    source = _StubSource(connected=True, sample=_sample())
    pointer = EyeInput(source).poll(t_ns=0)
    assert pointer.valid is True
    assert pointer.x == 0.9


def test_poll_forces_invalid_when_disconnected_even_with_cached_valid_sample():
    """Without this, a dropped connection looks identical to a live, frozen
    gaze cursor -- the exact HANDOVER_GAZEPOINT.md gap D symptom."""
    source = _StubSource(connected=False, sample=_sample(valid=True))
    pointer = EyeInput(source).poll(t_ns=0)
    assert pointer.valid is False
    assert (pointer.x, pointer.y) == (0.5, 0.5)


def test_poll_ignores_connection_state_when_source_lacks_is_connected():
    """Sources without is_connected() (e.g. a bare replay source) behave as
    before -- connection tracking is opt-in, not required."""

    class _NoConnState:
        def latest(self) -> GazeSample | None:
            return _sample(valid=True)

    pointer = EyeInput(_NoConnState()).poll(t_ns=0)
    assert pointer.valid is True


# -- gaze smoothing (SPEC-2026-09-02.md items 1 & 2) ------------------------


class _SequenceSource:
    """Replays a fixed sequence of samples, one per ``latest()`` call (holding
    the last one once exhausted) -- a minimal stand-in for a noisy tracker."""

    def __init__(self, samples: list[GazeSample]) -> None:
        self._samples = samples
        self._i = -1

    def latest(self) -> GazeSample | None:
        self._i = min(self._i + 1, len(self._samples) - 1)
        return self._samples[self._i]


def test_poll_smooths_successive_samples_instead_of_passing_raw_value():
    samples = [
        GazeSample(t_ns=0, x=0.5, y=0.5, valid=True),
        GazeSample(t_ns=1, x=0.9, y=0.5, valid=True),
    ]
    eye = EyeInput(_SequenceSource(samples), smoothing_config=SmoothingConfig(enabled=True, alpha=0.35))
    eye.poll(t_ns=0)
    pointer = eye.poll(t_ns=1)
    # Smoothed toward, but not equal to, the raw second sample.
    assert 0.5 < pointer.x < 0.9


def test_poll_does_not_smooth_when_smoothing_disabled():
    samples = [
        GazeSample(t_ns=0, x=0.5, y=0.5, valid=True),
        GazeSample(t_ns=1, x=0.9, y=0.5, valid=True),
    ]
    eye = EyeInput(_SequenceSource(samples), smoothing_config=SmoothingConfig(enabled=False))
    eye.poll(t_ns=0)
    pointer = eye.poll(t_ns=1)
    assert pointer.x == 0.9


def test_invalid_sample_resets_running_average_instead_of_blending():
    samples = [
        GazeSample(t_ns=0, x=0.1, y=0.1, valid=True),
        GazeSample(t_ns=1, x=0.1, y=0.1, valid=False),  # gaze lost briefly
        GazeSample(t_ns=2, x=0.9, y=0.9, valid=True),  # reacquired elsewhere
    ]
    eye = EyeInput(_SequenceSource(samples), smoothing_config=SmoothingConfig(enabled=True, alpha=0.35))
    eye.poll(t_ns=0)
    eye.poll(t_ns=1)
    pointer = eye.poll(t_ns=2)
    # Must land exactly on the fresh sample, not blended toward the stale 0.1
    # average from before the drop-out.
    assert (pointer.x, pointer.y) == (0.9, 0.9)


def test_smoothing_lets_dwell_complete_despite_jitter_that_defeats_raw_pointer():
    """Regression for SPEC-2026-09-02.md items 1 & 2: the physician's "cursor
    is jittery" and "gaze on target does nothing" reports share one root
    cause -- a hitbox-crossing raw gaze wobble that keeps exceeding the 120ms
    dwell hold-grace, resetting progress before it becomes visible.

    Drives a target-centered square-wave wobble (period and amplitude chosen
    to just clear the hitbox on each swing, deterministically, no RNG)
    through both a raw and a smoothed EyeInput and confirms: raw dwell never
    completes in 5s of that wobble, smoothed dwell does.
    """
    screen_w, screen_h = 1920, 1080
    cx_px, cy_px = 0.5 * screen_w, 0.5 * screen_h
    radius_px, jitter_tolerance_px = 90.0, 40.0
    hitbox_r_px = radius_px + jitter_tolerance_px

    frame_ns = int(1e9 / 60)
    half_period_frames = 9  # 150ms -- comfortably above the 120ms hold-grace
    excess_px = 15.0  # swings just past the hitbox edge on each half-period
    amplitude_px = hitbox_r_px + excess_px
    n_frames = 300  # 5s -- generous headroom past the 800ms dwell threshold

    samples = []
    for i in range(n_frames):
        sign = 1 if (i // half_period_frames) % 2 == 0 else -1
        x = (cx_px + sign * amplitude_px) / screen_w
        y = cy_px / screen_h
        samples.append(GazeSample(t_ns=i * frame_ns, x=x, y=y, valid=True))

    def dwell_completes(smoothing_enabled: bool) -> bool:
        eye = EyeInput(
            _SequenceSource(samples),
            DwellConfig(threshold_ms=800.0, refractory_ms=500.0, hold_grace_ms=120.0),
            SmoothingConfig(enabled=smoothing_enabled, alpha=0.35),
        )
        for i in range(n_frames):
            t_ns = i * frame_ns
            pointer = eye.poll(t_ns)
            px, py = norm_to_px(pointer.x, pointer.y, screen_w, screen_h)
            on_target = pointer.valid and circle_contains(cx_px, cy_px, hitbox_r_px, px, py)
            if eye.dwell.update(t_ns, on_target).triggered:
                return True
        return False

    assert dwell_completes(smoothing_enabled=False) is False
    assert dwell_completes(smoothing_enabled=True) is True


# -- dropout freeze (SPEC-gaze-cursor-redesign.md S4.1 / S5.1) --------------


def test_invalid_sample_freezes_pointer_instead_of_reporting_its_own_coordinates():
    """The reported "cursor jumps to the left corner" bug, reproduced exactly.

    ``rec_to_sample`` substitutes ``0.0`` for a coordinate the device did not
    supply, so a dropout sample carries ``(0.0, 0.0)`` -- not a position, a
    placeholder. Rendering it puts the cursor in the canvas's top-left corner
    (SPEC-gaze-cursor-redesign.md S2). Before the fix this asserted position
    was ``(0.0, 0.0)``; it must now hold wherever gaze actually was.
    """
    samples = [
        GazeSample(t_ns=0, x=0.8, y=0.3, valid=True),
        GazeSample(t_ns=1, x=0.0, y=0.0, valid=False),  # tracking lost
    ]
    eye = EyeInput(_SequenceSource(samples), smoothing_config=SmoothingConfig(enabled=False))
    eye.poll(t_ns=0)
    pointer = eye.poll(t_ns=1)
    assert pointer.valid is False
    assert (pointer.x, pointer.y) == (0.8, 0.3)


def test_frozen_position_is_the_smoothed_one_the_renderer_last_drew():
    """S4.5: "freeze" means freeze what was on screen. The raw last sample and
    the smoothed pointer differ, so freezing the raw one would twitch the
    cursor at the exact moment tracking is lost."""
    samples = [
        GazeSample(t_ns=0, x=0.2, y=0.2, valid=True),
        GazeSample(t_ns=1, x=0.8, y=0.8, valid=True),
        GazeSample(t_ns=2, x=0.0, y=0.0, valid=False),  # tracking lost
    ]
    eye = EyeInput(_SequenceSource(samples), smoothing_config=SmoothingConfig(enabled=True, alpha=0.35))
    eye.poll(t_ns=0)
    smoothed = eye.poll(t_ns=1)
    assert smoothed.x != 0.8  # precondition: smoothing really did lag the raw sample
    frozen = eye.poll(t_ns=2)
    assert (frozen.x, frozen.y) == (smoothed.x, smoothed.y)


def test_invalid_sample_before_any_valid_one_falls_back_to_neutral_center():
    """With nothing valid ever seen there is no position to hold, so the
    cursor must start at the neutral center the sibling branches use -- not in
    a corner."""
    source = _StubSource(connected=True, sample=_sample(valid=False))
    pointer = EyeInput(source).poll(t_ns=0)
    assert pointer.valid is False
    assert (pointer.x, pointer.y) == (0.5, 0.5)


def test_disconnect_clears_the_frozen_position():
    """Across a link drop the held position is stale for the same reason the
    running average is, so it must not survive into the reconnected session."""
    sample = GazeSample(t_ns=0, x=0.8, y=0.3, valid=True)
    source = _StubSource(connected=True, sample=sample)
    eye = EyeInput(source, smoothing_config=SmoothingConfig(enabled=False))
    assert eye.poll(t_ns=0).x == 0.8

    source._connected = False
    assert (eye.poll(t_ns=1).x, eye.poll(t_ns=1).y) == (0.5, 0.5)

    # Reconnected, but the first sample back is an invalid one: fall back to
    # the neutral center rather than resurrecting the pre-disconnect position.
    source._connected = True
    source._sample = GazeSample(t_ns=2, x=0.0, y=0.0, valid=False)
    pointer = eye.poll(t_ns=2)
    assert (pointer.x, pointer.y) == (0.5, 0.5)
