"""Tests for the real device sample-rate tracker (SPEC-ui-setup-task-
selection.md S24.4), distinct from the app's own poll/render-loop FPS."""

from __future__ import annotations

import pytest

from src.engine.sample_rate import SampleRateTracker


def test_rate_is_none_before_first_window_completes():
    tracker = SampleRateTracker()
    tracker.update(sample_t_ns=0, now_ns=100_000_000)
    assert tracker.rate_hz is None


def test_repeated_same_timestamp_does_not_count_as_a_new_sample():
    """A poll loop faster than the device must not inflate the rate just
    because it re-reads the same stale sample many times."""
    tracker = SampleRateTracker()
    now = 0
    for _ in range(201):  # 5ms steps; i=200 crosses the 1s window boundary
        tracker.update(sample_t_ns=0, now_ns=now)
        now += 5_000_000
    assert tracker.rate_hz == 0.0


def test_computes_hz_from_distinct_sample_timestamps_over_one_second():
    tracker = SampleRateTracker()
    step_ns = 17_000_000  # ~58.8 Hz spacing
    n_ticks = 60
    for i in range(n_ticks):
        tracker.update(sample_t_ns=i, now_ns=i * step_ns)
    elapsed_ns = (n_ticks - 1) * step_ns
    expected_hz = (n_ticks - 1) * 1e9 / elapsed_ns
    assert tracker.rate_hz == pytest.approx(expected_hz, rel=1e-9)


def test_window_resets_after_completing():
    tracker = SampleRateTracker()
    step_ns = 17_000_000
    n_ticks = 60
    for i in range(n_ticks):
        tracker.update(sample_t_ns=i, now_ns=i * step_ns)
    first = tracker.rate_hz
    assert first is not None

    # A single further update alone must not complete a new window.
    tracker.update(sample_t_ns=n_ticks, now_ns=(n_ticks - 1) * step_ns + 1_000)
    assert tracker.rate_hz == first
