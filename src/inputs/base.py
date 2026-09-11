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


def outside_distance(x: float, y: float) -> float:
    """How far a normalized position lies outside the 0-1 box, 0.0 if inside.

    Shared by the canvas's off-canvas cursor fade and the dropout diagnostic
    that the fade's threshold is tuned from (SPEC-gaze-cursor-redesign.md
    S4.2/S6), so the number the diagnostic records and the number the renderer
    acts on cannot drift apart.

    Per-axis overshoot combined as the larger of the two rather than a
    Euclidean distance: the question is how far gaze has left the canvas in
    *any* direction, and a corner excursion should not read as ~1.4x worse
    than an equivalent straight-out-the-side one.
    """
    dx = max(0.0, -x, x - 1.0)
    dy = max(0.0, -y, y - 1.0)
    return max(dx, dy)


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
