"""Persistent Setup/Tasks dashboard (SPEC-ui-setup-task-selection.md).

Replaces the old one-task-per-process launch model for interactive clinical
use: the tracker connection and calibration made in the Setup tab persist
across every task run in the Tasks tab, and "Run" embeds the task canvas +
operator sidebar into this same window in place of the Tasks tab content
(S3.1.7) -- no new window, no subprocess, "nothing gets relaunched".

The standalone ``python -m src.main --task X --gui`` launch path
(:func:`src.app.run_gui`) is untouched and still creates its own
``GazepointClient``/``MainWindow`` per run -- this window is an additional,
opt-in entry point (``--dashboard``), not a replacement.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from ..app import AssessmentApp
from ..engine.config import CONFIG_ROOT, load_task_config
from ..engine.calibration import CalibrationFileError
from ..engine.session_naming import next_run_number
from .results_page import ResultsPage
from .setup_page import SetupPage
from .task_settings_dialog import TaskSettingsDialog
from .tasks_page import TasksPage
from .wtmh_theme import STYLESHEET

_LOGO_PATH = CONFIG_ROOT / "assets" / "branding" / "wtmh_logo.png"
_ICON_PATH = CONFIG_ROOT / "assets" / "branding" / "WTMH.ico"

_SETUP_INDEX = 0
_TASKS_INDEX = 1
_RESULTS_INDEX = 2
_RUN_INDEX = 3  # the embedded TaskRunView is inserted/removed here per run


class DashboardWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pediatric Eye-Gaze Assessment")
        if _ICON_PATH.exists():
            from PySide6.QtGui import QIcon

            self.setWindowIcon(QIcon(str(_ICON_PATH)))

        self._active_assessment: AssessmentApp | None = None
        self._active_task_id: str | None = None
        # Most recent session directory per task_id, populated whenever a run
        # finishes (SPEC-result-logic.md §8.2: the Results tab always shows
        # the most-recent run only, no run-picker yet -- re-runs still get
        # their own on-disk _run<N> folder, but only the latest is tracked
        # here for Analyze/Results purposes).
        self._task_session_dirs: dict[str, Path] = {}
        # Structural overrides configured via each task's own "Settings"
        # button (tasks.md's separate Settings/Run buttons -- Settings
        # edits+stores them, Run applies whatever was last saved without
        # popping the dialog again every time; an un-configured task simply
        # uses its YAML defaults).
        self._task_overrides: dict[str, dict] = {}

        central = QWidget(self)
        central.setObjectName("wtmhDashboard")
        central.setStyleSheet(STYLESHEET)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_title_bar())

        self.stack = QStackedWidget()
        self.setup_page = SetupPage()
        self.tasks_page = TasksPage()
        self.results_page = ResultsPage()
        self.stack.addWidget(self.setup_page)  # index 0
        self.stack.addWidget(self.tasks_page)  # index 1
        self.stack.addWidget(self.results_page)  # index 2
        outer.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)
        self.resize(1024, 800)

        self.setup_page.continueRequested.connect(self._on_continue_to_tasks)
        self.tasks_page.runRequested.connect(self._on_run_requested)
        self.tasks_page.settingsRequested.connect(self._on_settings_requested)
        self.tasks_page.analyzeRequested.connect(self._on_analyze_requested)
        self.tasks_page.backToSetupRequested.connect(lambda: self.stack.setCurrentIndex(_SETUP_INDEX))
        self.results_page.backRequested.connect(lambda: self._go_to_tab(_TASKS_INDEX))

        self._set_active_nav(_SETUP_INDEX)

    # -- title bar ------------------------------------------------------

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("wtmhTitleBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        if _LOGO_PATH.exists():
            from PySide6.QtGui import QPixmap

            logo_label = QLabel()
            logo_label.setPixmap(QPixmap(str(_LOGO_PATH)).scaledToHeight(28))
            layout.addWidget(logo_label)

        title_label = QLabel("Pediatric Eye-Gaze Assessment")
        title_label.setObjectName("wtmhBrandTitle")
        layout.addWidget(title_label)
        layout.addStretch(1)

        self.setup_nav_button = QPushButton("Setup")
        self.setup_nav_button.setObjectName("wtmhNavButton")
        self.setup_nav_button.clicked.connect(lambda: self._go_to_tab(_SETUP_INDEX))
        layout.addWidget(self.setup_nav_button)

        self.tasks_nav_button = QPushButton("Tasks")
        self.tasks_nav_button.setObjectName("wtmhNavButton")
        self.tasks_nav_button.clicked.connect(lambda: self._go_to_tab(_TASKS_INDEX))
        layout.addWidget(self.tasks_nav_button)

        self.results_nav_button = QPushButton("Results")
        self.results_nav_button.setObjectName("wtmhNavButton")
        self.results_nav_button.clicked.connect(lambda: self._go_to_tab(_RESULTS_INDEX))
        layout.addWidget(self.results_nav_button)

        return bar

    def _go_to_tab(self, index: int) -> None:
        if self._active_assessment is not None:
            return  # a task is embedded and running
        self.stack.setCurrentIndex(index)
        self._set_active_nav(index)

    def _set_active_nav(self, index: int) -> None:
        self.setup_nav_button.setProperty("active", index == _SETUP_INDEX)
        self.tasks_nav_button.setProperty("active", index == _TASKS_INDEX)
        self.results_nav_button.setProperty("active", index == _RESULTS_INDEX)
        for button in (self.setup_nav_button, self.tasks_nav_button, self.results_nav_button):
            button.style().unpolish(button)
            button.style().polish(button)

    # -- Setup -> Tasks ---------------------------------------------------

    def _on_continue_to_tasks(self) -> None:
        if not self.setup_page.can_continue():
            return
        self.stack.setCurrentIndex(_TASKS_INDEX)
        self._set_active_nav(_TASKS_INDEX)

    # -- task settings ------------------------------------------------------

    def _on_settings_requested(self, task_id: str) -> None:
        config = load_task_config(task_id)
        if task_id in self._task_overrides:
            from ..engine.config import deep_merge

            config["task"] = deep_merge(config["task"], self._task_overrides[task_id])
        dialog = TaskSettingsDialog(task_id, config, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._task_overrides[task_id] = dialog.overrides()

    # -- embed-in-place task run --------------------------------------------

    def _on_run_requested(self, task_id: str) -> None:
        if self._active_assessment is not None:
            return  # one task at a time
        if not self.setup_page.can_continue():
            return  # tracker/calibration dropped since Setup; nothing to run against

        structural_overrides = self._task_overrides.get(task_id)

        # Predict the run index the about-to-start AssessmentApp/
        # SessionRecorder will independently compute via the same
        # next_session_id() scan (S11.5) -- safe to compute twice since
        # nothing else can create a session directory between these two
        # calls in this single-threaded UI flow.
        subject_id = self.setup_page.subject_id()
        output_root = load_task_config(task_id).get("recording", {}).get("output_root", "sessions")
        run_number = next_run_number(output_root, subject_id, task_id)

        try:
            assessment = AssessmentApp(
                task_id=task_id,
                replay_path=None,
                subject_id=self.setup_page.subject_id(),
                structural_overrides=structural_overrides,
                client=self.setup_page.client,
                preset_calibration_result=self.setup_page.calibration_result,
                embedded=True,
                on_finished=self._on_task_finished,
                assessment_date=self.setup_page.assessment_date(),
                sex=self.setup_page.sex(),
                notes=self.setup_page.notes(),
            )
        except CalibrationFileError as exc:  # pragma: no cover - unreachable (no --calibration-file here)
            self.tasks_page.set_task_status(task_id, "Pending")
            print(f"Could not start task: {exc}")
            return

        self._active_assessment = assessment
        self._active_task_id = task_id
        self.tasks_page.set_task_status(task_id, "Running")
        self.tasks_page.set_task_run_number(task_id, run_number)
        self.tasks_page.set_all_runs_enabled(False)
        self.setup_nav_button.setEnabled(False)

        self.stack.addWidget(assessment.view)  # index _RUN_INDEX
        self.stack.setCurrentWidget(assessment.view)
        assessment.view.canvas.setFocus()

    def _on_task_finished(self) -> None:
        task_id = self._active_task_id
        assessment = self._active_assessment
        self._active_assessment = None
        self._active_task_id = None

        # Captured before the view is torn down, per src.app.AssessmentApp's
        # own contract: _active_assessment/_active_task_id are the only
        # handles to this run's data once _on_task_finished starts.
        session_dir = assessment.recorder.session_dir if assessment is not None else None
        if assessment is not None:
            self.stack.removeWidget(assessment.view)
            assessment.view.deleteLater()

        # SPEC-result-logic.md §8.2: a run returns directly to Tasks --
        # Results is a persistent tab reached on request (nav button or
        # this task's own "Analyze" button), not auto-shown after every run
        # like the earlier (§3, now superseded) design.
        if session_dir is not None and task_id is not None:
            self._task_session_dirs[task_id] = session_dir

        self.stack.setCurrentIndex(_TASKS_INDEX)
        if task_id is not None:
            self.tasks_page.set_task_status(task_id, "Complete")
        self.tasks_page.set_all_runs_enabled(True)
        self.setup_nav_button.setEnabled(True)
        self._set_active_nav(_TASKS_INDEX)

    def _on_analyze_requested(self, task_id: str) -> None:
        session_dir = self._task_session_dirs.get(task_id)
        if session_dir is None:  # pragma: no cover - defensive; Analyze is disabled until a run exists
            return
        self.results_page.populate(session_dir, task_id, subject_id=self.setup_page.subject_id())
        self._go_to_tab(_RESULTS_INDEX)


def run_dashboard() -> int:
    existing = QApplication.instance()
    app = existing or QApplication([])
    if existing is None:
        # Windows' native "windowsvista" QStyle (the platform default, and
        # this app never set one before) largely ignores QSS-declared
        # custom arrow/indicator subcontrols -- it paints its own tiny
        # native glyph inside whatever box our stylesheet reserves,
        # regardless of the border-triangle CSS we declare (confirmed via
        # a zoomed qt-mcp screenshot, SPEC-ui-setup-task-selection.md
        # S12). Fusion is the standard, reliable fix: it fully honors
        # custom subcontrol QSS, which this app leans on heavily
        # (wtmh_theme.py, operator_panel.py).
        style = QStyleFactory.create("Fusion")
        app.setStyle(style)
        # S13: switching style alone isn't enough -- on a machine with
        # Windows dark mode on, Qt6 auto-adopts a DARK default QPalette
        # (confirmed: Window #1e1e1e, Button #3c3c3c) regardless of which
        # QStyle is active. Anything our QSS doesn't explicitly cover
        # (e.g. QCalendarWidget's weekday header, which QSS itself can't
        # reach for this widget -- see setup_page.py's
        # _theme_calendar_popup) silently falls back to that dark palette
        # instead of a neutral light one, which is almost certainly the
        # real explanation behind most of this app's "looks
        # dark/unthemed" reports so far, not just the calendar header.
        # Fusion's own standardPalette() is a real light default,
        # independent of OS dark-mode inheritance -- applying it here
        # gives every not-yet-explicitly-styled corner a sane light
        # fallback instead of near-black.
        app.setPalette(style.standardPalette())
    window = DashboardWindow()
    window.show()
    return app.exec()
