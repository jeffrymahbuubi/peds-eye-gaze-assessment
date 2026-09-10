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
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..engine.calibration import (
    Calibration,
    CalibrationFileError,
    CalibrationResult,
    calibration_timing_log_path,
    load_calibration_result,
    per_point_errors_px,
    save_calibration_result,
)
from ..engine.config import load_default
from ..engine.local_state import load_local_state, save_local_state
from ..inputs.gazepoint_client import DeviceInfo, GazepointClient
from .wtmh_theme import BORDER, PANEL_BG

_SEX_OPTIONS = ["Select", "Female", "Male", "Other / Prefer not to say"]


def _format_device_info(info: DeviceInfo | None) -> str:
    """Build the post-connect device-info text (SPEC-ui-setup-task-
    selection.md S23) -- up to two lines, each field independently optional
    since it was queried independently and may not have answered in time.
    Returns "" (hide the label) if nothing came back at all.
    """
    if info is None:
        return ""

    identity_parts = []
    if info.model:
        identity_parts.append(info.model)
    if info.rate_hz:
        identity_parts.append(f"{info.rate_hz} Hz")
    if info.bus:
        identity_parts.append(info.bus)
    if info.serial:
        identity_parts.append(f"SN {info.serial}")

    detail_parts = []
    if info.camera_width and info.camera_height:
        detail_parts.append(f"{info.camera_width}×{info.camera_height}")
    if info.api_version:
        detail_parts.append(f"API v{info.api_version}")

    lines = []
    if identity_parts:
        lines.append("Device: " + " · ".join(identity_parts))
    if detail_parts:
        lines.append("Camera: " + " · ".join(detail_parts))
    return "\n".join(lines)


def _format_rate_warning(info: DeviceInfo | None) -> str:
    """Build the USB2/60 Hz warning text (SPEC-ui-setup-task-selection.md
    S24.3). Sourced from ``rate_hz`` alone -- a rate genuinely below 150 is
    never a false alarm, regardless of exact model. Returns "" (hide the
    banner) when the rate is unknown or already at full HD rate.
    """
    if info is None or info.rate_hz is None or info.rate_hz >= 150:
        return ""
    bus_text = f" over {info.bus}" if info.bus else ""
    return (
        f"Tracker is running at {info.rate_hz} Hz{bus_text}. The GP3 HD only "
        "reaches 150 Hz on a USB 3.0 connection — move the data cable to a "
        "USB 3.0 port and reconnect for full-rate data."
    )


def _subject_calibration_dir(output_root: str | Path, subject_id: str) -> Path:
    """Canonical per-subject saved-calibration folder (SPEC-gui-audit-
    2026-09-10.md item 2b). Distinct from a run's own auto-saved
    ``calibration.json`` (``src/app.py``, one per session folder) -- this is
    a single, explicitly-saved record per subject that "Save Calibration"
    writes to and "Load Calibration File" defaults its file picker to, so a
    calibration can be reused across sessions without hunting through dated
    run folders. Doesn't create the directory -- callers create it on save,
    or just check existence before using it as a browse-to default.
    """
    return Path(output_root) / "_calibrations" / subject_id


def _subject_calibration_path(output_root: str | Path, subject_id: str, n_points: int) -> Path:
    """One saved calibration file per point count per subject (SPEC-gui-audit-
    2026-09-10.md S8).

    The point count is in the filename so it's readable without opening the
    file. Because it's part of the name rather than a fixed ``calibration.json``,
    saving a 9-point calibration no longer overwrites the same subject's
    5-point one -- both stay available to load.
    """
    return _subject_calibration_dir(output_root, subject_id) / f"calibration_{int(n_points)}pt.json"


def _latest_subject_calibration(output_root: str | Path, subject_id: str) -> Path | None:
    """The subject's most recently saved calibration, or None if they have none.

    With one file per point count (S8), a subject can have several. The most
    recently written one is what a single canonical ``calibration.json`` would
    always have held anyway, so defaulting the file picker to it keeps the
    established behaviour while still listing the others alongside it.

    ``calibration.json`` (the pre-S8 name) is included in the search so
    calibrations saved before this change are still offered.
    """
    directory = _subject_calibration_dir(output_root, subject_id)
    if not directory.is_dir():
        return None
    candidates = [p for p in directory.glob("calibration_*pt.json") if p.is_file()]
    legacy = directory / "calibration.json"
    if legacy.is_file():
        candidates.append(legacy)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


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


class _DeviceInfoRefreshThread(QThread):
    """Re-queries device info over an already-open connection (SPEC-ui-
    setup-task-selection.md S24.2), off the UI thread since it's still a
    blocking socket round trip even though it's usually fast.
    """

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, client: GazepointClient, parent=None) -> None:
        super().__init__(parent)
        self._client = client

    def run(self) -> None:
        try:
            info = self._client.refresh_device_info()
        except (RuntimeError, OSError) as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(info)


class _CalibrationThread(QThread):
    finished_ok = Signal(object)

    def __init__(
        self, client: GazepointClient, n_points: int, show: bool, output_root: str | Path, parent=None
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._n_points = n_points
        self._show = show
        self._output_root = output_root

    def run(self) -> None:
        calibration = Calibration(
            self._client,
            n_points=self._n_points,
            enabled=True,
            show=self._show,
            timing_log_path=calibration_timing_log_path(self._output_root),
        )
        self.finished_ok.emit(calibration.run())


class SetupPage(QWidget):
    stateChanged = Signal()
    continueRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client: GazepointClient | None = None
        self._calibration_result: CalibrationResult | None = None
        self._connect_thread: _ConnectThread | None = None
        self._recheck_thread: _DeviceInfoRefreshThread | None = None
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

        # Expanding the calibration-details table (below) can push the card
        # stack taller than the window -- scrolling the cards (rather than
        # the whole page) keeps "Continue to Tasks" pinned as a fixed footer
        # outside the scroll area, so it's always reachable regardless of
        # scroll position or how much detail is showing.
        scroll = QScrollArea()
        scroll.setObjectName("wtmhSetupScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)
        scroll_layout.addWidget(self._build_subject_card())
        scroll_layout.addWidget(self._build_tracker_card())
        scroll_layout.addWidget(self._build_calibration_card())
        scroll_layout.addWidget(self._build_device_notice_card())
        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        # QScrollArea.setWidget() turns on autoFillBackground for both the
        # viewport and the content widget, painting them with the inherited
        # QPalette::Window color (black in this app's Fusion palette) --
        # invisible under the cards themselves but exposed as black bands in
        # the spacing gaps between them. The QSS transparent rule below only
        # reaches the viewport (a direct QScrollArea child), not this content
        # widget (a grandchild via the viewport), so both need autofill
        # disabled explicitly here.
        scroll.viewport().setAutoFillBackground(False)
        scroll_content.setAutoFillBackground(False)
        outer.addWidget(scroll, stretch=1)

        self.continue_button = QPushButton("Continue to Tasks →")
        self.continue_button.setObjectName("wtmhPrimary")
        self.continue_button.setEnabled(False)
        self.continue_button.clicked.connect(self.continueRequested)
        outer.addWidget(self.continue_button)

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

        # Populated from GazepointClient.device_info on a successful
        # connect; hidden whenever there's nothing to show (SPEC S23).
        # "Re-check" (S24.2) re-queries it without a full reconnect -- only
        # safe before any task has streamed this session (see
        # GazepointClient.refresh_device_info's own docstring), so a click
        # after that point fails gracefully via device_info_status_label
        # rather than racing the reader thread.
        device_info_row = QHBoxLayout()
        self.device_info_label = QLabel("")
        self.device_info_label.setObjectName("wtmhMuted")
        self.device_info_label.setVisible(False)
        device_info_row.addWidget(self.device_info_label, stretch=1)

        self.recheck_device_info_button = QPushButton("Re-check")
        self.recheck_device_info_button.setObjectName("wtmhGhost")
        self.recheck_device_info_button.setVisible(False)
        self.recheck_device_info_button.clicked.connect(self._on_recheck_device_info_clicked)
        device_info_row.addWidget(self.recheck_device_info_button)
        layout.addLayout(device_info_row)

        self.device_info_status_label = QLabel("")
        self.device_info_status_label.setObjectName("wtmhMuted")
        self.device_info_status_label.setWordWrap(True)
        self.device_info_status_label.setVisible(False)
        layout.addWidget(self.device_info_status_label)

        # S24.3: shown whenever a connected device reports a rate below
        # 150 Hz -- the same visual pattern as calibration_alert below.
        self.rate_warning_alert = QFrame()
        self.rate_warning_alert.setObjectName("wtmhAlertWarning")
        self.rate_warning_alert.setVisible(False)
        rate_alert_layout = QVBoxLayout(self.rate_warning_alert)
        self.rate_warning_label = QLabel("")
        self.rate_warning_label.setWordWrap(True)
        rate_alert_layout.addWidget(self.rate_warning_label)
        layout.addWidget(self.rate_warning_alert)
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

        # SPEC-gui-audit-2026-09-10.md item 2b: an explicit save action,
        # decoupled from Do Calibration's own silent per-run auto-save
        # (src/app.py), so a calibration measured for a subject in one
        # sitting can be deliberately promoted to that subject's canonical
        # reusable record -- disabled until there's a result to save, same
        # gating as View Calibration Details below.
        self.save_calibration_button = QPushButton("Save Calibration")
        self.save_calibration_button.setObjectName("wtmhGhost")
        self.save_calibration_button.setEnabled(False)
        self.save_calibration_button.clicked.connect(self._on_save_calibration_clicked)
        buttons.addWidget(self.save_calibration_button)

        # SPEC-result-logic.md §8.1: disabled until a calibration result
        # exists, same gating as Continue to Tasks -- toggles the inline
        # per-point breakdown below, not a modal (a modal would block the
        # qt-mcp automation probe, see setup.md's own design note).
        self.view_details_button = QPushButton("View Calibration Details")
        self.view_details_button.setObjectName("wtmhGhost")
        self.view_details_button.setEnabled(False)
        self.view_details_button.clicked.connect(self._on_toggle_details_clicked)
        buttons.addWidget(self.view_details_button)
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

        layout.addWidget(self._build_calibration_details_section())
        return card

    def _build_calibration_details_section(self) -> QWidget:
        self.calibration_details_section = QWidget()
        self.calibration_details_section.setVisible(False)
        details_layout = QVBoxLayout(self.calibration_details_section)
        details_layout.setContentsMargins(0, 4, 0, 0)
        details_layout.setSpacing(6)

        details_layout.addWidget(self._card_title("Per-point breakdown"))

        self.calibration_details_table = QTableWidget(0, 7)
        self.calibration_details_table.setObjectName("wtmhTable")
        self.calibration_details_table.setHorizontalHeaderLabels(
            ["Point", "Target (X, Y)", "Left eye (X, Y)", "Left valid", "Right eye (X, Y)", "Right valid", "Error (px)"]
        )
        self.calibration_details_table.verticalHeader().setVisible(False)
        self.calibration_details_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.calibration_details_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.calibration_details_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        details_layout.addWidget(self.calibration_details_table)

        self.calibration_details_empty_label = QLabel(
            "Per-point breakdown not available for this calibration."
        )
        self.calibration_details_empty_label.setObjectName("wtmhMuted")
        self.calibration_details_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.calibration_details_empty_label.setVisible(False)
        details_layout.addWidget(self.calibration_details_empty_label)

        return self.calibration_details_section

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

    def _apply_device_info(self, info: DeviceInfo | None) -> None:
        """Render device_info_label + rate_warning_alert from a DeviceInfo
        -- shared by both a fresh connect and a S24.2 re-check, so the two
        paths can never drift apart in how they display the same data.
        """
        device_info_text = _format_device_info(info)
        self.device_info_label.setText(device_info_text)
        self.device_info_label.setVisible(bool(device_info_text))
        self.recheck_device_info_button.setVisible(True)

        rate_warning_text = _format_rate_warning(info)
        self.rate_warning_label.setText(rate_warning_text)
        self.rate_warning_alert.setVisible(bool(rate_warning_text))

    def _on_connect_clicked(self) -> None:
        if self._connect_thread is not None:
            return
        self.connect_button.setEnabled(False)
        self.tracker_status_label.setText("Connecting…")
        self.device_info_label.setVisible(False)
        self.recheck_device_info_button.setVisible(False)
        self.device_info_status_label.setVisible(False)
        self.rate_warning_alert.setVisible(False)
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
        self.device_info_status_label.setVisible(False)
        self._apply_device_info(client.device_info)
        self.do_calibration_button.setEnabled(True)
        save_local_state({"host": self.address_edit.text().strip(), "port": self.port_spin.value()})
        self._on_state_changed()

    def _on_connect_failed(self, message: str) -> None:
        self._connect_thread = None
        self.connect_button.setEnabled(True)
        self.tracker_status_label.setText(f"Connection failed: {message}")
        self.device_info_label.setVisible(False)
        self.recheck_device_info_button.setVisible(False)
        self.device_info_status_label.setVisible(False)
        self.rate_warning_alert.setVisible(False)

    def _on_recheck_device_info_clicked(self) -> None:
        if self._recheck_thread is not None or self._client is None:
            return
        self.recheck_device_info_button.setEnabled(False)
        self.device_info_status_label.setText("Re-checking…")
        self.device_info_status_label.setVisible(True)
        self._recheck_thread = _DeviceInfoRefreshThread(self._client, parent=self)
        self._recheck_thread.succeeded.connect(self._on_recheck_succeeded)
        self._recheck_thread.failed.connect(self._on_recheck_failed)
        self._recheck_thread.finished.connect(self._recheck_thread.deleteLater)
        self._recheck_thread.start()

    def _on_recheck_succeeded(self, info: DeviceInfo) -> None:
        self._recheck_thread = None
        self.recheck_device_info_button.setEnabled(True)
        self.device_info_status_label.setVisible(False)
        self._apply_device_info(info)

    def _on_recheck_failed(self, message: str) -> None:
        self._recheck_thread = None
        self.recheck_device_info_button.setEnabled(True)
        # Last-known-good device_info_label/rate_warning_alert are left
        # exactly as they were -- a failed re-check (most commonly: a task
        # has already streamed this session, see refresh_device_info's own
        # docstring) doesn't mean the device info shown is now wrong.
        self.device_info_status_label.setText(f"Re-check unavailable: {message}")
        self.device_info_status_label.setVisible(True)

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
            self._client,
            self.point_count_spin.value(),
            self.show_calibration_checkbox.isChecked(),
            self._defaults.get("recording", {}).get("output_root", "sessions"),
            parent=self,
        )
        self._calibration_thread = thread
        thread.finished_ok.connect(self._on_calibration_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_calibration_finished(self, result: CalibrationResult) -> None:
        self._calibration_thread = None
        self.do_calibration_button.setEnabled(True)
        self._calibration_result = result
        self.calibration_details_section.setVisible(False)  # collapse any stale prior breakdown
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

    def _on_save_calibration_clicked(self) -> None:
        if self._calibration_result is None:
            return
        subject_id = self.subject_id()
        if not subject_id:
            return  # button is disabled in this state; guard against a stray signal anyway
        output_root = self._defaults.get("recording", {}).get("output_root", "sessions")
        n_points = self._calibration_result.n_points
        target_path = _subject_calibration_path(output_root, subject_id, n_points)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        save_calibration_result(target_path, subject_id, self._calibration_result)
        self._set_calibration_alert(
            "success",
            f"Calibration saved for {subject_id} as {target_path.name} — "
            "Load Calibration File will offer it next time.",
        )

    def _on_load_calibration_clicked(self) -> None:
        output_root = self._defaults.get("recording", {}).get("output_root", "sessions")
        # Default to this subject's own saved calibration (SPEC-gui-audit-
        # 2026-09-10.md item 2b) when one exists, instead of always starting
        # the browse at output_root -- QFileDialog pre-selects the file
        # itself when given a full path, not just a directory. With one file
        # per point count (S8) a subject can have several; the most recently
        # saved one is pre-selected and the rest are listed beside it.
        default_path = Path(output_root)
        subject_id = self.subject_id()
        if subject_id:
            candidate = _latest_subject_calibration(output_root, subject_id)
            if candidate is not None:
                default_path = candidate
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Calibration File", str(default_path), "Calibration files (*.json)"
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
        self.calibration_details_section.setVisible(False)  # collapse any stale prior breakdown
        error_txt = f"{saved.result.mean_error_px:.0f}px" if saved.result.mean_error_px is not None else "n/a"
        self._set_calibration_alert(
            "success", f"Calibration loaded — {saved.result.n_points} points, mean error {error_txt}, valid."
        )
        self._on_state_changed()

    def _on_toggle_details_clicked(self) -> None:
        showing = not self.calibration_details_section.isVisible()
        if showing:
            self._populate_calibration_details()
        self.calibration_details_section.setVisible(showing)

    def _populate_calibration_details(self) -> None:
        per_point = self._calibration_result.per_point if self._calibration_result else None
        table = self.calibration_details_table
        table.setRowCount(0)
        if not per_point:
            table.setVisible(False)
            self.calibration_details_empty_label.setVisible(True)
            return
        table.setVisible(True)
        self.calibration_details_empty_label.setVisible(False)

        app_defaults = self._defaults.get("app", {})
        screen_w = int(app_defaults.get("screen_width_px", 1920))
        screen_h = int(app_defaults.get("screen_height_px", 1080))
        rows = per_point_errors_px(per_point, screen_w, screen_h)

        def _eye_cell(eye: dict | None) -> tuple[str, str]:
            if eye is None:
                return "—", "—"
            return f"{eye['x']:.3f}, {eye['y']:.3f}", "Yes" if eye["valid"] else "No"

        def _error_cell(left_err: float | None, right_err: float | None) -> str:
            errs = [e for e in (left_err, right_err) if e is not None]
            return f"{sum(errs) / len(errs):.1f}" if errs else "—"

        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            left_pos, left_valid = _eye_cell(row["left"])
            right_pos, right_valid = _eye_cell(row["right"])
            values = [
                str(row["point"]),
                f"{row['target_x']:.3f}, {row['target_y']:.3f}",
                left_pos,
                left_valid,
                right_pos,
                right_valid,
                _error_cell(row["left_error_px"], row["right_error_px"]),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(i, col, item)

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
        self.view_details_button.setEnabled(self._calibration_result is not None)
        self.save_calibration_button.setEnabled(
            self._calibration_result is not None and bool(self.subject_id())
        )
        if self._calibration_result is None:
            self.calibration_details_section.setVisible(False)
        self.stateChanged.emit()
