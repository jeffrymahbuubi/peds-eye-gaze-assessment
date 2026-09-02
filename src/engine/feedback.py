"""Feedback bus (plan section 5.6).

Feedback (sound, particle animation, progress ring) is abstracted behind a small
interface so the task logic stays GUI-free and testable. The GUI supplies a
PySide6-backed implementation; the headless pipeline and tests use
:class:`NullFeedback`, which just records the events it was asked to play.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class FeedbackBus(ABC):
    """Sink for feedback effects triggered by tasks."""

    @abstractmethod
    def on_target_shown(self, x: float, y: float) -> None: ...

    @abstractmethod
    def on_hit(self, x: float, y: float) -> None: ...

    @abstractmethod
    def on_miss(self, x: float, y: float) -> None: ...

    @abstractmethod
    def on_progress(self, x: float, y: float, progress: float) -> None: ...


@dataclass
class NullFeedback(FeedbackBus):
    """No-op feedback that records calls for inspection/testing."""

    events: list[tuple[str, float, float]] = field(default_factory=list)

    def on_target_shown(self, x: float, y: float) -> None:
        self.events.append(("target_shown", x, y))

    def on_hit(self, x: float, y: float) -> None:
        self.events.append(("hit", x, y))

    def on_miss(self, x: float, y: float) -> None:
        self.events.append(("miss", x, y))

    def on_progress(self, x: float, y: float, progress: float) -> None:
        # progress is high-frequency; only the latest is usually of interest.
        self.events.append(("progress", x, y))
