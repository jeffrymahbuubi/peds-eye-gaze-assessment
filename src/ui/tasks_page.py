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
# Public (not module-private) since results_page.py also reads task display
# names off it for the Results tab's page header.
TASK_INFO: dict[str, tuple[str, str]] = {
    "click_static": ("Static Click", "One still target on an empty field — baseline look-and-select."),
    "click_grid": ("Grid Click (3×3)", "One cell of a visible 3x3 board lights up — selection among candidates."),
    "follow_moving": ("Follow & Click", "The target travels; select it while it moves — smooth pursuit."),
    "scanning": ("Scanning Search", "Find the cued shape in a 2D field of distractors — visual search."),
}


class _TaskCard(QFrame):
    runRequested = Signal(str)
    settingsRequested = Signal(str)
    analyzeRequested = Signal(str)
    saveSettingsRequested = Signal(str)

    def __init__(self, task_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task_id = task_id
        self.setObjectName("wtmhCard")
        name, description = TASK_INFO.get(task_id, (task_id, ""))

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

        # Which settings a Run would actually start from (SPEC-live-settings-
        # panel.md S10.7.3 A). Before this, a saved profile was stated in
        # exactly one place -- the OperatorPanel card, which doesn't exist
        # until the run is already underway and the child is already in front
        # of the screen, so there was no way to check beforehand what would be
        # applied. No fixed width (unlike status_label): the text varies with
        # the calibration detail.
        self.settings_label = QLabel("Task defaults")
        self.settings_label.setObjectName("wtmhBadgeNeutral")
        self.settings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.settings_label)
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
        self.analyze_button.setToolTip("Enabled once this task shows Complete — opens the Results tab.")
        self.analyze_button.clicked.connect(lambda: self.analyzeRequested.emit(self.task_id))
        buttons.addWidget(self.analyze_button)

        # SPEC-live-settings-panel.md S10.5.1: the OperatorPanel's own "Save
        # for this subject" is only reachable *during* a run, but the moment a
        # physician actually knows a run's settings were good is after seeing
        # its hit rate and reaction times. This is the same save, available
        # once a run has finished -- it stores that run's ending values, which
        # DashboardWindow already holds.
        self.save_settings_button = QPushButton("Save Settings")
        self.save_settings_button.setObjectName("wtmhGhost")
        self.save_settings_button.setEnabled(False)
        self.save_settings_button.setToolTip(
            "Enabled after a run — saves that run's settings as this subject's "
            "profile for this task."
        )
        self.save_settings_button.clicked.connect(
            lambda: self.saveSettingsRequested.emit(self.task_id)
        )
        buttons.addWidget(self.save_settings_button)
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

    _SETTINGS_BADGES = {
        "defaults": "wtmhBadgeNeutral",
        "profile": "wtmhBadgeSuccess",
        "carried": "wtmhBadgeAccent",
    }

    def set_settings_badge(self, text: str, source: str, tooltip: str = "") -> None:
        self.settings_label.setText(text)
        self.settings_label.setToolTip(tooltip)
        object_name = self._SETTINGS_BADGES.get(source, "wtmhBadgeNeutral")
        self.settings_label.setObjectName(object_name)
        self.settings_label.style().unpolish(self.settings_label)
        self.settings_label.style().polish(self.settings_label)

    def set_run_enabled(self, enabled: bool) -> None:
        self.run_button.setEnabled(enabled)
        self.settings_button.setEnabled(enabled)

    def set_save_settings_enabled(self, enabled: bool) -> None:
        self.save_settings_button.setEnabled(enabled)

    def set_settings_saved(self, filename: str) -> None:
        """Confirm the save on the button itself.

        A silent write is indistinguishable from a button that does nothing,
        and this one has no dialog and no visible side effect anywhere else on
        the page.
        """
        self.save_settings_button.setText("Settings Saved ✓")
        self.save_settings_button.setToolTip(
            f"Saved as this subject's profile for this task ({filename}). "
            "Press Run again to apply it, or save again after another run."
        )


class TasksPage(QWidget):
    runRequested = Signal(str)
    settingsRequested = Signal(str)
    analyzeRequested = Signal(str)
    saveSettingsRequested = Signal(str)
    backToSetupRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: dict[str, _TaskCard] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(24, 20, 24, 20)
        self._outer.setSpacing(16)

        self._title_label = QLabel("2 · Tasks")
        self._title_label.setObjectName("wtmhPageTitle")
        self._outer.addWidget(self._title_label)

        self._back_button = QPushButton("← Back to Setup / recalibrate")
        self._back_button.setObjectName("wtmhGhost")
        self._back_button.clicked.connect(self.backToSetupRequested)
        self._outer.addWidget(self._back_button)

        # S19: single-column card stack, one card per row via plain
        # QVBoxLayout.addWidget() -- reverted from the 2-column QGridLayout
        # (S16-S18) back to the pattern already used on setup_page.py's
        # own card stack (see SetupPage._build_ui: addWidget() per card,
        # then a single trailing addStretch(1) here). S16-S18's grid
        # attempt chased the same "empty space at the bottom" problem
        # through several fixes (a responsive 2/1-column breakpoint, a
        # centered block, spacer rows) without ever fully matching Setup's
        # own look; the user's own second-thought decision was to stop
        # fixing the grid and just reuse Setup's simpler, already-working
        # pattern instead. Live-validated maximized (SPEC-ui-setup-task-
        # selection.md S19): the 4 stacked cards fill roughly 3/4 of the
        # available height with one clean trailing margin below the last
        # card -- Setup's own cards happen to be tall enough (forms) to
        # reach almost to the bottom on content alone, so this is a
        # smaller residual margin than Setup's, not a perfect pixel match
        # -- but there is no large or awkward empty region anywhere, no
        # internal gaps inside any card, and no leftover grid/breakpoint
        # code, which is what this round actually asked for.
        for task_id in TASK_REGISTRY:
            card = _TaskCard(task_id)
            card.runRequested.connect(self.runRequested)
            card.settingsRequested.connect(self.settingsRequested)
            card.analyzeRequested.connect(self.analyzeRequested)
            card.saveSettingsRequested.connect(self.saveSettingsRequested)
            self._cards[task_id] = card
            self._outer.addWidget(card)
        self._outer.addStretch(1)

    def set_task_status(self, task_id: str, status: str) -> None:
        if task_id in self._cards:
            self._cards[task_id].set_status(status)

    def set_task_run_number(self, task_id: str, n: int) -> None:
        if task_id in self._cards:
            self._cards[task_id].set_run_count(n)

    def set_task_settings_badge(
        self, task_id: str, text: str, source: str, tooltip: str = ""
    ) -> None:
        if task_id in self._cards:
            self._cards[task_id].set_settings_badge(text, source, tooltip)

    def set_task_save_settings_enabled(self, task_id: str, enabled: bool) -> None:
        if task_id in self._cards:
            self._cards[task_id].set_save_settings_enabled(enabled)

    def set_task_settings_saved(self, task_id: str, filename: str) -> None:
        if task_id in self._cards:
            self._cards[task_id].set_settings_saved(filename)

    def set_all_runs_enabled(self, enabled: bool) -> None:
        """Disable every card's Run/Settings while one task is embedded and running."""
        for card in self._cards.values():
            card.set_run_enabled(enabled)
