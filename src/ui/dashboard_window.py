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
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..app import AssessmentApp
from ..engine.config import CONFIG_ROOT, load_task_config
from ..engine.calibration import CalibrationFileError
from ..engine.session_naming import next_run_number
from .results_page import ResultsPage
from .setup_page import SetupPage
from .task_settings_dialog import TaskSettingsDialog
from ..engine.settings_profile import (
    list_settings_profiles,
    load_settings_profile,
    load_settings_profile_file,
    resolve_settings_precedence,
    settings_profile_dir,
)
from ..engine.task_runner import TASK_REGISTRY
from .settings_registry import format_calibration, format_saved_at
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
        self.setWindowTitle(f"Pediatric Eye-Gaze Assessment v{__version__}")
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
        # Live (OperatorPanel) values carried from the previous run of each
        # task in this sitting -- SPEC-live-settings-panel.md S10.3's
        # "run 1 tunes, run 2 collects" requirement. Populated from the
        # finished AssessmentApp's own resolved values, so what carries is
        # exactly what was in effect, not a re-derivation. In-memory only;
        # the saved profile is what survives the app closing.
        self._task_live_overrides: dict[str, dict] = {}
        # The saved version the operator explicitly chose via Load Settings
        # (S10.12), per task, for the next run only -- cleared when that run
        # finishes, because its ending values then become the carried entry
        # above, which wins next per S10.3. Absent = the newest version.
        self._task_selected_profile: dict[str, Path] = {}

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
        # Which profile applies depends entirely on the Subject ID, so a stale
        # badge after an edit would be actively misleading (S10.7.3 A).
        self.setup_page.subjectIdChanged.connect(self._on_subject_id_changed)
        self.tasks_page.runRequested.connect(self._on_run_requested)
        self.tasks_page.settingsRequested.connect(self._on_settings_requested)
        self.tasks_page.analyzeRequested.connect(self._on_analyze_requested)
        self.tasks_page.loadSettingsRequested.connect(self._on_load_settings_requested)
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
        if index == _TASKS_INDEX:
            self._refresh_settings_badges()
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
        self._refresh_settings_badges()
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

    def _on_load_settings_requested(self, task_id: str) -> None:
        """Let the operator choose which saved version the next run starts from.

        SPEC-live-settings-panel.md S10.12: every save is kept, so a subject
        can have a 09/17 and a 09/18 profile for the same task and the
        operator picks between them here -- via the native file dialog,
        opened on that subject+task's own folder (decision 2). The chosen
        file must be a profile for **this** task (other tasks carry different
        keys, e.g. ``motion.*``) and **this** subject (S10.1's reason for
        per-subject keying: one child's tuning must not become another's by
        a browse-up-one-level mistake); anything else is refused with the
        reason on the button.

        On success the carried entry is dropped (S10.11.3, unchanged): the
        explicit choice is now the most recent deliberate act, so the shared
        :meth:`_resolve_settings` path -- the badge refresh right below, and
        the next Run -- applies the chosen version on its own.
        """
        subject_id = self.setup_page.subject_id()
        output_root = load_task_config(task_id).get("recording", {}).get("output_root", "sessions")
        directory = settings_profile_dir(output_root, subject_id, task_id)
        directory.mkdir(parents=True, exist_ok=True)  # so the dialog has somewhere to open
        chosen, _filter = QFileDialog.getOpenFileName(
            self,
            f"Load Settings — {subject_id} / {task_id}",
            str(directory),
            "Settings profile (*.json)",
        )
        if not chosen:
            return
        profile = load_settings_profile_file(chosen)
        if profile is None:
            self.tasks_page.set_task_load_settings_refused(
                task_id, f"{Path(chosen).name} is not a readable settings profile."
            )
            return
        if profile["task_id"] and profile["task_id"] != task_id:
            self.tasks_page.set_task_load_settings_refused(
                task_id,
                f"{Path(chosen).name} is a profile for {profile['task_id']}, not {task_id}.",
            )
            return
        if profile["subject_id"] and profile["subject_id"] != subject_id:
            self.tasks_page.set_task_load_settings_refused(
                task_id,
                f"{Path(chosen).name} belongs to subject {profile['subject_id']}, "
                f"not {subject_id}.",
            )
            return
        self._task_selected_profile[task_id] = Path(chosen)
        self._task_live_overrides.pop(task_id, None)
        self._refresh_settings_badges()

    def _resolve_settings(self, task_id: str) -> dict:
        """Work out which settings a run of this task would start from.

        Settings precedence (S10.3): values carried from an earlier run in this
        sitting win, because they are the most recent deliberate act. Failing
        that, the saved version the operator explicitly chose (S10.12) if any,
        else the subject's **newest** saved version -- with the panel saying
        so, which is the other half of that decision.

        Shared by :meth:`_on_run_requested` and the Tasks-page badge rather
        than duplicated, so the badge cannot promise one thing while the run
        applies another (S10.7.3 A). Reading a profile here is a small JSON
        read that already tolerates every failure as "no profile", so calling
        it to paint a badge is safe.
        """
        output_root = load_task_config(task_id).get("recording", {}).get("output_root", "sessions")
        carried = self._task_live_overrides.get(task_id)
        # Skip the disk read entirely when something was carried -- it would
        # lose to it anyway.
        profile = None
        if not carried:
            selected = self._task_selected_profile.get(task_id)
            if selected is not None:
                profile = load_settings_profile_file(selected)
            if profile is None:
                # No explicit choice, or the chosen file has since gone: the
                # newest version, exactly as a fresh sitting would.
                profile = load_settings_profile(output_root, self.setup_page.subject_id(), task_id)
        resolved = resolve_settings_precedence(
            carried, profile, self._task_overrides.get(task_id)
        )
        resolved["output_root"] = output_root
        resolved["profile_path"] = (
            profile["path"] if profile is not None and resolved["source"] == "profile" else ""
        )
        return resolved

    def _on_subject_id_changed(self, _text: str) -> None:
        # Which profile applies depends entirely on the Subject ID, so a stale
        # badge after an edit would be actively misleading (S10.7.3 A) -- and
        # a version chosen for one subject must not follow the operator to
        # the next (S10.12).
        self._task_selected_profile.clear()
        self._refresh_settings_badges()

    def _refresh_settings_badges(self) -> None:
        """Restate on every card what a Run would apply right now.

        Driven by :meth:`_resolve_settings`, so this reports **precedence**
        rather than mere file existence: a card whose values carried over from
        an earlier run this sitting says so, because that is what will win even
        though a saved profile also exists. A badge naming the profile in that
        case would be worse than no badge at all.
        """
        subject_id = self.setup_page.subject_id()
        for task_id in TASK_REGISTRY:
            resolved = self._resolve_settings(task_id)
            source = resolved["source"]
            when = format_saved_at(resolved["saved_at"], with_time=False)
            if source == "carried":
                text = "Carried from last run"
                tooltip = (
                    "This task was tuned earlier in this sitting; those values win over "
                    "any saved profile. Save from the running task's own panel to keep them, "
                    "or Load Settings to go back to a saved version."
                )
            elif source == "profile":
                detail = format_calibration(resolved["calibration"])
                text = f"Profile {when}" if when else "Profile saved"
                if detail:
                    text += f" · {detail}"
                full_when = format_saved_at(resolved["saved_at"])
                tooltip = (
                    "This subject's saved settings for this task will be applied"
                    + (f" (saved {full_when})" if full_when else "")
                    + (f": {Path(resolved['profile_path']).name}" if resolved["profile_path"] else "")
                    + "."
                )
            else:
                text = "Task defaults"
                tooltip = (
                    "No saved profile for this subject and task — the run starts from "
                    "the task's configured defaults. Check the Subject ID if you expected one."
                )
            self.tasks_page.set_task_settings_badge(task_id, text, source, tooltip)

            # Load Settings (S10.12): live whenever there is anything to choose
            # from -- including when the newest version has already been
            # auto-applied, since the point is being able to pick an *older*
            # one. Its label confirms an explicit choice for as long as that
            # choice is what the next Run will use.
            versions = list_settings_profiles(resolved["output_root"], subject_id, task_id)
            selected = self._task_selected_profile.get(task_id)
            if selected is not None and source == "profile":
                label = format_saved_at(resolved["saved_at"])
                button_text = f"Loaded {label} ✓" if label else "Loaded ✓"
                button_tip = f"The next run starts from {selected.name}. Click to choose another."
            else:
                button_text = "Load Settings"
                button_tip = (
                    f"Choose which of this subject's {len(versions)} saved version(s) the "
                    "next run starts from."
                    if versions
                    else "Enabled once this subject has a saved settings profile for this task."
                )
            self.tasks_page.set_task_load_settings_state(
                task_id, bool(versions), button_text, button_tip
            )

    def _on_run_requested(self, task_id: str) -> None:
        if self._active_assessment is not None:
            return  # one task at a time
        if not self.setup_page.can_continue():
            return  # tracker/calibration dropped since Setup; nothing to run against

        subject_id = self.setup_page.subject_id()
        resolved = self._resolve_settings(task_id)
        output_root = resolved["output_root"]
        structural_overrides = resolved["structural_overrides"]
        live_overrides = resolved["live_overrides"]
        settings_source = resolved["source"]
        settings_saved_at = resolved["saved_at"]
        settings_calibration = resolved["calibration"]

        # Predict the run index the about-to-start AssessmentApp/
        # SessionRecorder will independently compute via the same
        # next_session_id() scan (S11.5) -- safe to compute twice since
        # nothing else can create a session directory between these two
        # calls in this single-threaded UI flow.
        run_number = next_run_number(output_root, subject_id, task_id)

        try:
            assessment = AssessmentApp(
                task_id=task_id,
                replay_path=None,
                subject_id=subject_id,
                structural_overrides=structural_overrides,
                live_overrides=live_overrides,
                settings_source=settings_source,
                settings_saved_at=settings_saved_at,
                settings_calibration=settings_calibration,
                settings_profile_file=(
                    Path(resolved["profile_path"]).name if resolved["profile_path"] else ""
                ),
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
        if assessment is not None and task_id is not None:
            # Carry this run's ending live values into the next run of the
            # same task (S10.3). Taken from the AssessmentApp's own resolved
            # dict, so what carries is exactly what was in effect. Must happen
            # before the view is torn down, like session_dir above.
            self._task_live_overrides[task_id] = dict(assessment._live_values)
            # The version chosen for this run has been used; its ending values
            # are now the carried entry above, which wins next (S10.12.4).
            self._task_selected_profile.pop(task_id, None)
        if assessment is not None:
            self.stack.removeWidget(assessment.view)
            assessment.view.deleteLater()

        # SPEC-result-logic.md §8.2: a run returns directly to Tasks --
        # Results is a persistent tab reached on request (nav button or
        # this task's own "Analyze" button), not auto-shown after every run
        # like the earlier (§3, now superseded) design.
        if session_dir is not None and task_id is not None:
            self._task_session_dirs[task_id] = session_dir

        # This run's ending values are now carried for this task, which changes
        # what the badge should say (profile -> carried).
        self._refresh_settings_badges()
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
    # showMaximized(), not show() (SPEC-live-settings-panel.md S10.8). The
    # OperatorPanel column needs 891 px (935 for follow_moving) and its
    # minimumSizeHint equals its sizeHint, so it cannot compress by a pixel;
    # with no scroll area, whatever doesn't fit is silently clipped. Opening
    # at resize(1024, 800) leaves only ~713 px, so the column was clipped at
    # startup -- and maximizing afterwards doesn't rebuild the already-clipped
    # layout, which is why minimize/restore/maximize "fixed" it. Starting
    # maximized never enters that path (~976 px on a 1920x1080 display).
    # The resize() above stays as the restore-down geometry.
    window.showMaximized()
    return app.exec()
