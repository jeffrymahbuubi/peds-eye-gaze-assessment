"""Tasks tab: one card per task, embed-in-place Run (SPEC-ui-setup-task-
selection.md S6).

This widget only presents the task list and asks for a run/settings/back
action via signals -- it does not itself own the ``GazepointClient``,
calibration result, or the embedded ``AssessmentApp``; that lives in
``DashboardWindow``, which is also what actually swaps this page out for the
running task's view and back again.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..engine.task_runner import TASK_REGISTRY

# (display name, one-line description) -- text lifted from docs/wireframes/tasks.md
# so the real UI matches the reviewed mockup, not re-worded independently.
_TASK_INFO: dict[str, tuple[str, str]] = {
    "click_static": ("Static Click", "One still target on an empty field — baseline look-and-select."),
    "click_grid": ("Grid Click (3×3)", "One cell of a visible 3x3 board lights up — selection among candidates."),
    "follow_moving": ("Follow & Click", "The target travels; select it while it moves — smooth pursuit."),
    "scanning": ("Scanning Search", "Find the cued shape in a 2D field of distractors — visual search."),
}


class _TaskCard(QFrame):
    runRequested = Signal(str)
    settingsRequested = Signal(str)

    def __init__(self, task_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task_id = task_id
        self.setObjectName("wtmhCard")
        name, description = _TASK_INFO.get(task_id, (task_id, ""))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)  # matches setup_page.py's card rhythm exactly

        title = QLabel(name)
        title.setObjectName("wtmhSectionTitle")
        layout.addWidget(title)

        desc = QLabel(description)
        desc.setObjectName("wtmhMuted")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Pending")
        self.status_label.setObjectName("wtmhBadgeNeutral")
        self.status_label.setFixedWidth(70)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.status_label)

        # Run-number indicator (SPEC-ui-setup-task-selection.md S11.2 finding
        # B) -- surfaces the same run index session_naming.py's next_run_
        # number() already computes for the on-disk session directory, which
        # was previously never shown anywhere in the UI.
        self.run_label = QLabel("No runs yet")
        self.run_label.setObjectName("wtmhMuted")
        status_row.addWidget(self.run_label)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("wtmhPrimary")
        self.run_button.clicked.connect(lambda: self.runRequested.emit(self.task_id))
        buttons.addWidget(self.run_button)

        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("wtmhGhost")
        self.settings_button.clicked.connect(lambda: self.settingsRequested.emit(self.task_id))
        buttons.addWidget(self.settings_button)

        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.setObjectName("wtmhGhost")
        self.analyze_button.setEnabled(False)
        self.analyze_button.setToolTip("Coming soon — deferred per SPEC-ui-setup-task-selection.md S6.2")
        buttons.addWidget(self.analyze_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    # Full pill set per SPEC-ui-setup-task-selection.md S11.1 critique point
    # 6 -- "Error" has no real trigger yet (S11.4 decision 2: styled and
    # reserved this round, not wired to an actual failure path).
    _STATUS_BADGES = {
        "Pending": "wtmhBadgeNeutral",
        "Running": "wtmhBadgeAccent",
        "Complete": "wtmhBadgeSuccess",
        "Error": "wtmhBadgeDanger",
    }

    def set_status(self, status: str) -> None:
        self.status_label.setText(status)
        object_name = self._STATUS_BADGES.get(status, "wtmhBadgeNeutral")
        self.status_label.setObjectName(object_name)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.analyze_button.setEnabled(status == "Complete")

    def set_run_count(self, n: int) -> None:
        self.run_label.setText(f"Run {n}")

    def set_run_enabled(self, enabled: bool) -> None:
        self.run_button.setEnabled(enabled)
        self.settings_button.setEnabled(enabled)


class TasksPage(QWidget):
    runRequested = Signal(str)
    settingsRequested = Signal(str)
    backToSetupRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: dict[str, _TaskCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("2 · Tasks")
        title.setObjectName("wtmhSectionTitle")
        outer.addWidget(title)

        back_button = QPushButton("← Back to Setup / recalibrate")
        back_button.setObjectName("wtmhGhost")
        back_button.clicked.connect(self.backToSetupRequested)
        outer.addWidget(back_button)

        for task_id in TASK_REGISTRY:
            card = _TaskCard(task_id)
            card.runRequested.connect(self.runRequested)
            card.settingsRequested.connect(self.settingsRequested)
            self._cards[task_id] = card
            outer.addWidget(card)
        outer.addStretch(1)

    def set_task_status(self, task_id: str, status: str) -> None:
        if task_id in self._cards:
            self._cards[task_id].set_status(status)

    def set_task_run_number(self, task_id: str, n: int) -> None:
        if task_id in self._cards:
            self._cards[task_id].set_run_count(n)

    def set_all_runs_enabled(self, enabled: bool) -> None:
        """Disable every card's Run/Settings while one task is embedded and running."""
        for card in self._cards.values():
            card.set_run_enabled(enabled)
