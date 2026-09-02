"""Tests for EyeInput's handling of a disconnected gaze source (gap D)."""

from __future__ import annotations

from src.data.schema import GazeSample
from src.inputs.eye_input import EyeInput


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
