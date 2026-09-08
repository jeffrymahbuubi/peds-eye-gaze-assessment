"""Setup tab: subject info, tracker connection, calibration (SPEC-ui-setup-
task-selection.md S5 / S3.1).

Connect and Do Calibration both block on real device I/O (a 5s socket
timeout on a bad host; several seconds of point-by-point polling for a real
calibration) -- both run on a background ``QThread`` so the dashboard stays
responsive, matching the concurrency budget already spent elsewhere in this
app (``GazepointClient``'s own reader thread).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..engine.calibration import Calibration, CalibrationFileError, CalibrationResult, load_calibration_result
from ..engine.config import load_default
from ..engine.local_state import load_local_state, save_local_state
from ..inputs.gazepoint_client import GazepointClient
from .wtmh_theme import BORDER, PANEL_BG

_SEX_OPTIONS = ["Select", "Female", "Male", "Other / Prefer not to say"]


class _ConnectThread(QThread):
    """Connects (or probes) a GazepointClient off the UI thread.

    ``keep=False`` (Test Connection) closes the client again immediately on
    success -- it only reports reachability, it must not replace the page's
    real connection.
    """

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, host: str, port: int, keep: bool, parent=None) -> None:
        super().__init__(parent)
        self._host = host
        self._port = port
        self._keep = keep

    def run(self) -> None:
        client = GazepointClient()
        try:
            client.connect(host=self._host, port=self._port)
        except OSError as exc:
            self.failed.emit(str(exc))
            return
        if not self._keep:
            client.stop()
            self.succeeded.emit(None)
        else:
            self.succeeded.emit(client)


class _CalibrationThread(QThread):
    finished_ok = Signal(object)

    def __init__(self, client: GazepointClient, n_points: int, show: bool, parent=None) -> None:
        super().__init__(parent)
        self._client = client
        self._n_points = n_points
        self._show = show

    def run(self) -> None:
        calibration = Calibration(self._client, n_points=self._n_points, enabled=True, show=self._show)
        self.finished_ok.emit(calibration.run())


class SetupPage(QWidget):
    stateChanged = Signal()
    continueRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client: GazepointClient | None = None
        self._calibration_result: CalibrationResult | None = None
        self._connect_thread: _ConnectThread | None = None
        self._calibration_thread: _CalibrationThread | None = None
        self._defaults = load_default()
        self._build_ui()

    # -- accessors used by DashboardWindow ---------------------------------

    @property
    def client(self) -> GazepointClient | None:
        return self._client

    @property
    def calibration_result(self) -> CalibrationResult | None:
        return self._calibration_result

    def subject_id(self) -> str:
        return self.subject_id_edit.text().strip()

    def assessment_date(self) -> str:
        return self.date_edit.date().toString("yyyy-MM-dd")

    def sex(self) -> str:
        idx = self.sex_combo.currentIndex()
        return self.sex_combo.currentText() if idx > 0 else ""

    def notes(self) -> str:
        return self.notes_edit.toPlainText()

    def can_continue(self) -> bool:
        return (
            self._client is not None
            and self._client.is_connected()
            and self._calibration_result is not None
            and bool(self.subject_id())
            and bool(self.assessment_date())
            and bool(self.sex())
        )

    # -- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        title = QLabel("1 · Setup")
        title.setObjectName("wtmhPageTitle")
        outer.addWidget(title)

        outer.addWidget(self._build_subject_card())
        outer.addWidget(self._build_tracker_card())
        outer.addWidget(self._build_calibration_card())
        outer.addWidget(self._build_device_notice_card())

        self.continue_button = QPushButton("Continue to Tasks →")
        self.continue_button.setObjectName("wtmhPrimary")
        self.continue_button.setEnabled(False)
        self.continue_button.clicked.connect(self.continueRequested)
        outer.addWidget(self.continue_button)
        outer.addStretch(1)

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("wtmhCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        return card, layout

    @staticmethod
    def _card_title(text: str) -> QLabel:
        title = QLabel(text)
        title.setObjectName("wtmhSectionTitle")
        return title

    def _build_subject_card(self) -> QFrame:
        card, layout = self._card()
        layout.addWidget(self._card_title("Subject & Session Info"))

        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.subject_id_edit = QLineEdit()
        self.subject_id_edit.textChanged.connect(self._on_state_changed)
        form.addRow("Subject ID", self.subject_id_edit)

        # No calendar popup (SPEC-ui-setup-task-selection.md S13, user
        # feedback): a physician recording an assessment isn't "booking" a
        # future date from a browsable calendar, so a plain auto-populated,
        # still-correctable date field (segments editable via keyboard,
        # today's date by default) fits the actual data-entry need better
        # than a booking-style date picker -- and sidesteps entirely a
        # QCalendarWidget theming problem this session hit real, confirmed
        # Qt/Fusion limits on (a QHeaderView's background ignoring both
        # ancestor-scoped and directly-applied QSS, needing a QPalette
        # workaround that still didn't match the app's exact background).
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_state_changed)
        # S14: QDateEdit is a QAbstractSpinBox subclass, so even with the
        # calendar popup removed it still paints its own native up/down
        # step buttons on the right edge -- wtmh_theme.py's QSS never
        # targeted QDateEdit's ::up-button/::down-button (only QSpinBox/
        # QDoubleSpinBox get themed steppers), so those native buttons
        # rendered unstyled as a bare vertical sliver. Disabling them
        # outright (rather than theming them like the spin boxes) is the
        # correct fix here: the field is meant to read as a plain,
        # keyboard-editable text box matching Subject ID above it, not a
        # steppable control.
        self.date_edit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        form.addRow("Assessment Date", self.date_edit)

        self.sex_combo = QComboBox()
        self.sex_combo.addItems(_SEX_OPTIONS)
        self.sex_combo.currentIndexChanged.connect(self._on_state_changed)
        # S13 removed the popup's inner QAbstractItemView's own frame so
        # wtmh_theme.py's QSS border/radius would be the only one visible.
        # S14 found that incomplete -- the view sits inside a second, outer
        # QFrame (Qt's undocumented QComboBoxPrivateContainer, the popup's
        # actual top-level window) which draws its own default frame
        # independently of the inner view's frame shape and is unreachable
        # by QSS at all.
        #
        # S15: S14's first attempt at fixing that outer frame (WA_
        # TranslucentBackground + a "background: transparent" stylesheet,
        # relying on the desktop compositor to blend it) rendered as SOLID
        # BLACK on real Windows on-screen compositing -- a known Qt/Windows
        # quirk where an alpha-enabled Qt::Popup window without proper DWM
        # composited support paints black instead of transparent. This
        # wasn't caught by qt-mcp's own screenshot tool because
        # `qt_screenshot` uses `QWidget.grab()`, which paints the widget
        # tree directly into a pixmap and bypasses real window compositing
        # entirely -- it cannot see a translucency/compositing bug at all,
        # so it falsely showed a clean white popup while the real
        # on-screen render was black. Fixed by giving the container an
        # ordinary OPAQUE background instead of relying on transparency --
        # no compositor dependency, so nothing to fail under either
        # verification method.
        self.sex_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        # S16: a QSS-only attempt (outline: 0 + an explicit transparent
        # border on ::item:focus) did NOT clear the bare focus-rectangle
        # outline Fusion draws around the current item on a fresh popup
        # open -- confirmed live, still present with only that change.
        # This is Qt's own QStyle::PE_FrameFocusRect primitive, painted
        # independently of the item delegate's stylesheet-driven paint,
        # so no QSS property on ::item:focus can suppress it. Disabling
        # the view's own focus policy stops it from ever reporting
        # State_HasFocus in the first place, which is what the primitive
        # keys off -- verified live to remove the outline while the combo
        # box itself still drives arrow-key navigation/selection (that is
        # handled by QComboBox's own key forwarding, independent of the
        # popup view's focus policy).
        self.sex_combo.view().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        popup_container = self.sex_combo.view().parentWidget()
        if popup_container is not None:
            # S16: no top border on the container -- the closed field
            # already draws its own bottom border directly above this
            # popup, so a second, separate top border here doubled up
            # into a faint seam. Leaving only the field's own border
            # visible at that boundary makes it one deliberate divider
            # instead of two borders sitting flush.
            popup_container.setStyleSheet(
                f"background: {PANEL_BG}; border: 1px solid {BORDER}; "
                f"border-top: none; border-radius: 8px;"
            )
        form.addRow("Sex", self.sex_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(60)
        form.addRow("Notes", self.notes_edit)

        layout.addLayout(form)
        return card

    def _build_tracker_card(self) -> QFrame:
        card, layout = self._card()
        layout.addWidget(self._card_title("Tracker Connection"))

        local_state = load_local_state()
        gp_defaults = self._defaults.get("gazepoint", {})

        row = QHBoxLayout()
        addr_col = QVBoxLayout()
        addr_col.addWidget(QLabel("Control Address"))
        self.address_edit = QLineEdit(str(local_state.get("host", "127.0.0.1")))
        addr_col.addWidget(self.address_edit)
        row.addLayout(addr_col, stretch=2)

        port_col = QVBoxLayout()
        port_col.addWidget(QLabel("Control Port"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(int(local_state.get("port", gp_defaults.get("port", 4242))))
        port_col.addWidget(self.port_spin)
        row.addLayout(port_col, stretch=1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("wtmhPrimary")
        self.connect_button.clicked.connect(self._on_connect_clicked)
        buttons.addWidget(self.connect_button)

        self.test_connection_button = QPushButton("Test Connection")
        self.test_connection_button.setObjectName("wtmhGhost")
        self.test_connection_button.clicked.connect(self._on_test_connection_clicked)
        buttons.addWidget(self.test_connection_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.tracker_status_label = QLabel("Not connected.")
        self.tracker_status_label.setObjectName("wtmhMuted")
        layout.addWidget(self.tracker_status_label)
        return card

    def _build_calibration_card(self) -> QFrame:
        card, layout = self._card()
        layout.addWidget(self._card_title("Calibration"))

        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.point_count_spin = QSpinBox()
        self.point_count_spin.setRange(1, 9)
        cal_defaults = self._defaults.get("calibration", {})
        self.point_count_spin.setValue(int(cal_defaults.get("points", 5)))
        form.addRow("Point Count (1–9)", self.point_count_spin)
        layout.addLayout(form)

        self.show_calibration_checkbox = QCheckBox("Show calibration window to the subject")
        self.show_calibration_checkbox.setChecked(bool(cal_defaults.get("show", True)))
        layout.addWidget(self.show_calibration_checkbox)

        buttons = QHBoxLayout()
        self.do_calibration_button = QPushButton("Do Calibration")
        self.do_calibration_button.setObjectName("wtmhPrimary")
        self.do_calibration_button.setEnabled(False)  # needs a connected tracker first
        self.do_calibration_button.clicked.connect(self._on_do_calibration_clicked)
        buttons.addWidget(self.do_calibration_button)

        self.load_calibration_button = QPushButton("Load Calibration File")
        self.load_calibration_button.setObjectName("wtmhGhost")
        self.load_calibration_button.clicked.connect(self._on_load_calibration_clicked)
        buttons.addWidget(self.load_calibration_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.calibration_alert = QFrame()
        self.calibration_alert.setObjectName("wtmhAlertWarning")
        alert_layout = QVBoxLayout(self.calibration_alert)
        self.calibration_alert_label = QLabel(
            "No calibration yet for this subject — run Do Calibration or "
            "Load Calibration File before continuing."
        )
        self.calibration_alert_label.setWordWrap(True)
        alert_layout.addWidget(self.calibration_alert_label)
        layout.addWidget(self.calibration_alert)
        return card

    def _build_device_notice_card(self) -> QFrame:
        card, layout = self._card()
        layout.addWidget(self._card_title("Before You Start"))
        alert = QFrame()
        alert.setObjectName("wtmhAlertInfo")
        alert_layout = QVBoxLayout(alert)
        label = QLabel(
            "Confirm in Gazepoint Control that Lens Focusing and Automatic "
            "Gain Sweep are enabled. (Read-only reminder — neither setting "
            "can be checked or changed from this app; it does not gate "
            "Continue.)"
        )
        label.setWordWrap(True)
        alert_layout.addWidget(label)
        layout.addWidget(alert)
        return card

    # -- tracker connection ---------------------------------------------

    def _on_connect_clicked(self) -> None:
        if self._connect_thread is not None:
            return
        self.connect_button.setEnabled(False)
        self.tracker_status_label.setText("Connecting…")
        self._connect_thread = _ConnectThread(
            self.address_edit.text().strip() or "127.0.0.1", self.port_spin.value(), keep=True, parent=self
        )
        self._connect_thread.succeeded.connect(self._on_connect_succeeded)
        self._connect_thread.failed.connect(self._on_connect_failed)
        self._connect_thread.finished.connect(self._connect_thread.deleteLater)
        self._connect_thread.start()

    def _on_connect_succeeded(self, client: GazepointClient) -> None:
        self._connect_thread = None
        self._client = client
        self.connect_button.setEnabled(True)
        self.tracker_status_label.setText("Connected.")
        self.do_calibration_button.setEnabled(True)
        save_local_state({"host": self.address_edit.text().strip(), "port": self.port_spin.value()})
        self._on_state_changed()

    def _on_connect_failed(self, message: str) -> None:
        self._connect_thread = None
        self.connect_button.setEnabled(True)
        self.tracker_status_label.setText(f"Connection failed: {message}")

    def _on_test_connection_clicked(self) -> None:
        if self._connect_thread is not None:
            return
        self.test_connection_button.setEnabled(False)
        self.tracker_status_label.setText("Testing connection…")
        thread = _ConnectThread(
            self.address_edit.text().strip() or "127.0.0.1", self.port_spin.value(), keep=False, parent=self
        )
        self._connect_thread = thread

        def on_ok(_client: object) -> None:
            self._connect_thread = None
            self.test_connection_button.setEnabled(True)
            self.tracker_status_label.setText("Reachable.")

        def on_fail(message: str) -> None:
            self._connect_thread = None
            self.test_connection_button.setEnabled(True)
            self.tracker_status_label.setText(f"Unreachable: {message}")

        thread.succeeded.connect(on_ok)
        thread.failed.connect(on_fail)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    # -- calibration ------------------------------------------------------

    def _on_do_calibration_clicked(self) -> None:
        if self._client is None or self._calibration_thread is not None:
            return
        self.do_calibration_button.setEnabled(False)
        self._set_calibration_alert("info", "Calibrating…")
        thread = _CalibrationThread(
            self._client, self.point_count_spin.value(), self.show_calibration_checkbox.isChecked(), parent=self
        )
        self._calibration_thread = thread
        thread.finished_ok.connect(self._on_calibration_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_calibration_finished(self, result: CalibrationResult) -> None:
        self._calibration_thread = None
        self.do_calibration_button.setEnabled(True)
        self._calibration_result = result
        if result.valid:
            error_txt = f"{result.mean_error_px:.0f}px" if result.mean_error_px is not None else "n/a"
            self._set_calibration_alert(
                "success",
                f"Calibration measured — {result.n_points} points, mean error {error_txt}, valid.",
            )
        else:
            self._calibration_result = None
            self._set_calibration_alert(
                "error", "Calibration did not produce a valid result. Try again or adjust point count."
            )
        self._on_state_changed()

    def _on_load_calibration_clicked(self) -> None:
        output_root = self._defaults.get("recording", {}).get("output_root", "sessions")
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Calibration File", str(Path(output_root)), "Calibration files (*.json)"
        )
        if not path:
            return
        subject_id = self.subject_id() or "UNKNOWN"
        try:
            saved = load_calibration_result(path)
            if saved.subject_id != subject_id:
                raise CalibrationFileError(
                    f"Calibration file subject_id {saved.subject_id!r} does not match "
                    f"Subject ID {subject_id!r}"
                )
        except CalibrationFileError as exc:
            self._calibration_result = None
            self._set_calibration_alert("error", str(exc))
            self._on_state_changed()
            return
        self._calibration_result = saved.result
        error_txt = f"{saved.result.mean_error_px:.0f}px" if saved.result.mean_error_px is not None else "n/a"
        self._set_calibration_alert(
            "success", f"Calibration loaded — {saved.result.n_points} points, mean error {error_txt}, valid."
        )
        self._on_state_changed()

    def _set_calibration_alert(self, kind: str, text: str) -> None:
        object_names = {
            "info": "wtmhAlertInfo",
            "warning": "wtmhAlertWarning",
            "success": "wtmhAlertSuccess",
            "error": "wtmhAlertError",
        }
        self.calibration_alert.setObjectName(object_names[kind])
        self.calibration_alert.style().unpolish(self.calibration_alert)
        self.calibration_alert.style().polish(self.calibration_alert)
        self.calibration_alert_label.setText(text)

    # -- gating -------------------------------------------------------------

    def _missing_requirements(self) -> list[str]:
        """Human-readable list of unmet Continue-to-Tasks gate conditions.

        SPEC-ui-setup-task-selection.md S13: a real user loaded a
        calibration file, then couldn't tell why "Continue to Tasks"
        stayed disabled -- the gate (S5.6) has always also required a
        connected tracker, independently of where the calibration came
        from, but nothing in the UI ever said so. This isn't a code bug
        (verified: `can_continue()` correctly flips True once the tracker
        is also connected), just a missing explanation -- surfaced as a
        tooltip on the disabled button instead of silence.
        """
        missing = []
        if self._client is None or not self._client.is_connected():
            missing.append("connect to the tracker")
        if self._calibration_result is None:
            missing.append("run or load a calibration")
        if not self.subject_id():
            missing.append("enter a Subject ID")
        if not self.sex():
            missing.append("select Sex")
        return missing

    def _on_state_changed(self, *_args: object) -> None:
        missing = self._missing_requirements()
        self.continue_button.setEnabled(not missing)
        self.continue_button.setToolTip(
            "Still needed: " + "; ".join(missing) + "." if missing else ""
        )
        self.stateChanged.emit()
