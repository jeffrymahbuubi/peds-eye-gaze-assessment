"""Tests for the gaze-to-feedback latency tracker (gap F)."""

from __future__ import annotations

import pytest

from src.engine.latency import LatencySummary, LatencyTracker


def test_add_sample_returns_none_until_window_fills():
    tracker = LatencyTracker(window_size=3)
    assert tracker.add_sample(sample_t_ns=0, now_ns=1_000_000) is None
    assert tracker.add_sample(sample_t_ns=0, now_ns=2_000_000) is None


def test_add_sample_returns_summary_when_window_fills():
    tracker = LatencyTracker(window_size=3)
    # Latencies (ms): 1, 2, 3
    tracker.add_sample(sample_t_ns=0, now_ns=1_000_000)
    tracker.add_sample(sample_t_ns=0, now_ns=2_000_000)
    summary = tracker.add_sample(sample_t_ns=0, now_ns=3_000_000)

    assert summary == LatencySummary(mean_ms=2.0, min_ms=1.0, max_ms=3.0, n_samples=3)


def test_tracker_resets_after_emitting_a_summary():
    tracker = LatencyTracker(window_size=2)
    tracker.add_sample(sample_t_ns=0, now_ns=1_000_000)
    first = tracker.add_sample(sample_t_ns=0, now_ns=1_000_000)
    assert first is not None

    # A fresh window: only one sample so far, must not carry over old state.
    assert tracker.add_sample(sample_t_ns=0, now_ns=9_000_000) is None
    second = tracker.add_sample(sample_t_ns=0, now_ns=9_000_000)
    assert second == LatencySummary(mean_ms=9.0, min_ms=9.0, max_ms=9.0, n_samples=2)


def test_window_size_of_one_emits_every_sample():
    tracker = LatencyTracker(window_size=1)
    summary = tracker.add_sample(sample_t_ns=1_000_000, now_ns=6_000_000)
    assert summary == LatencySummary(mean_ms=5.0, min_ms=5.0, max_ms=5.0, n_samples=1)


def test_rejects_non_positive_window_size():
    with pytest.raises(ValueError):
        LatencyTracker(window_size=0)
