"""Abstract pointer source and geometry helpers.

A *pointer source* produces a screen position (normalized 0-1) plus a boolean
"click" edge each frame. Both gaze+dwell and switch inputs implement this so the
Task Engine can treat them uniformly (plan section 4, ``PointerSource``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Pointer:
    """Pointer state for one frame.

    x, y are normalized (0-1). ``valid`` is False when the underlying signal is
    unreliable (e.g. gaze lost). ``clicked`` is a one-frame rising edge.
    """

    x: float
    y: float
    valid: bool
    clicked: bool


@dataclass(frozen=True, slots=True)
class Rect:
    """Axis-aligned rectangle in pixel space (used for hitboxes)."""

    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h


def norm_to_px(x: float, y: float, width_px: int, height_px: int) -> tuple[float, float]:
    """Convert normalized (0-1) coordinates to pixels."""
    return x * width_px, y * height_px


def circle_contains(cx_px: float, cy_px: float, radius_px: float, px: float, py: float) -> bool:
    """Whether pixel point (px, py) is within ``radius_px`` of (cx, cy)."""
    dx = px - cx_px
    dy = py - cy_px
    return (dx * dx + dy * dy) <= (radius_px * radius_px)


class PointerSource(ABC):
    """Something that yields a :class:`Pointer` each frame."""

    @abstractmethod
    def poll(self, t_ns: int) -> Pointer:
        """Return the current pointer state at time ``t_ns`` (nanoseconds)."""

    def close(self) -> None:  # noqa: B027 - intentional optional no-op hook
        """Release any resources. Override if needed (no-op by default)."""
        return None
