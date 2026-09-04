"""Tests for GazeSmoother (SPEC-2026-09-02.md item 1: raw gaze jitter)."""

from __future__ import annotations

import statistics

from src.inputs.eye_input import GazeSmoother, SmoothingConfig


def test_first_sample_passes_through_unchanged():
    smoother = GazeSmoother(SmoothingConfig(enabled=True, alpha=0.35))
    x, y = smoother.update(0.42, 0.58)
    assert (x, y) == (0.42, 0.58)


def test_disabled_smoothing_always_passes_through_raw_values():
    smoother = GazeSmoother(SmoothingConfig(enabled=False))
    smoother.update(0.5, 0.5)
    x, y = smoother.update(0.9, 0.1)
    assert (x, y) == (0.9, 0.1)


def test_smoothing_pulls_output_toward_running_average_not_latest_sample():
    smoother = GazeSmoother(SmoothingConfig(enabled=True, alpha=0.35))
    smoother.update(0.5, 0.5)
    x, y = smoother.update(1.0, 1.0)
    # EMA output must sit strictly between the previous and new raw sample --
    # neither frozen at the old value nor jumping straight to the new one.
    assert 0.5 < x < 1.0
    assert 0.5 < y < 1.0
    assert x == 0.5 + 0.35 * (1.0 - 0.5)


def test_smoothing_reduces_variance_of_noisy_signal():
    """The whole point of item 1's fix: feed a signal that jitters around a
    fixed center and confirm the smoothed output varies less than the raw
    input, without drifting away from that center."""
    import random

    rng = random.Random(0)
    center = 0.5
    raw_xs = [center + rng.uniform(-0.05, 0.05) for _ in range(200)]

    smoother = GazeSmoother(SmoothingConfig(enabled=True, alpha=0.35))
    smoothed_xs = [smoother.update(x, x)[0] for x in raw_xs]

    # Ignore the initial transient where the average is still converging.
    raw_tail = raw_xs[50:]
    smoothed_tail = smoothed_xs[50:]

    assert statistics.pstdev(smoothed_tail) < statistics.pstdev(raw_tail)
    # And it must still track the true center, not drift off toward one side.
    assert abs(statistics.mean(smoothed_tail) - center) < 0.01


def test_reset_clears_running_average():
    smoother = GazeSmoother(SmoothingConfig(enabled=True, alpha=0.35))
    smoother.update(0.1, 0.1)
    smoother.update(0.1, 0.1)
    smoother.reset()
    # After reset, the next sample should pass through unchanged again,
    # exactly like the very first call -- no blending toward the old average.
    x, y = smoother.update(0.9, 0.9)
    assert (x, y) == (0.9, 0.9)
