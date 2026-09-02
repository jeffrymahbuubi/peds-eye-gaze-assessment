"""Gaze-to-feedback latency measurement (plan risk table / gap F).

Measures the delay between a gaze sample arriving from the tracker (its
capture timestamp, ``GazeSample.t_ns``, stamped when the reader thread parses
the ``<REC>`` line) and this frame's processing (``time.time_ns()`` in
``_tick()``), as a proxy for end-to-end "gaze -> screen feedback" latency.
This is the pipeline latency from socket arrival to the app consuming it; it
does not include the final GPU/compositor time to actually present the
repainted frame, which this app has no way to measure without OS-level
display instrumentation.

Only meaningful for a live tracker connection: a replay source's timestamps
are relative to its own virtual clock, not wall time, so a difference against
``time.time_ns()`` would be meaningless (see ``GazepointClient.is_live``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LatencySummary:
    mean_ms: float
    min_ms: float
    max_ms: float
    n_samples: int


class LatencyTracker:
    """Accumulates per-frame latency samples, flushing a summary every
    ``window_size`` samples so the events log (deliberately low-frequency,
    high-value, and fsync'd on every write -- see ``SessionRecorder.record_event``)
    isn't hit at full frame rate (60/s).
    """

    def __init__(self, window_size: int = 60) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self._window_size = window_size
        self._sum_ms = 0.0
        self._min_ms = float("inf")
        self._max_ms = 0.0
        self._n = 0

    def add_sample(self, sample_t_ns: int, now_ns: int) -> LatencySummary | None:
        """Record one (sample capture time, now) pair.

        Returns a :class:`LatencySummary` once ``window_size`` samples have
        accumulated (and resets for the next window), else ``None``.
        """
        latency_ms = (now_ns - sample_t_ns) / 1e6
        self._sum_ms += latency_ms
        self._min_ms = min(self._min_ms, latency_ms)
        self._max_ms = max(self._max_ms, latency_ms)
        self._n += 1
        if self._n < self._window_size:
            return None

        summary = LatencySummary(
            mean_ms=self._sum_ms / self._n,
            min_ms=self._min_ms,
            max_ms=self._max_ms,
            n_samples=self._n,
        )
        self._sum_ms = 0.0
        self._min_ms = float("inf")
        self._max_ms = 0.0
        self._n = 0
        return summary
