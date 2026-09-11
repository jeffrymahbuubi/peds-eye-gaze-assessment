"""Operator (therapist) control panel (plan section 5.6 / Prompt 4).

Shows live diagnostics -- FPS, gaze validity, a diki-style live trial
counter/hit-timeout tally/progress bar (SPEC-diki-design-audit.md S8) -- and
exposes runtime controls: pause/resume, skip trial, end task early, and a
live settings panel built from ``settings_registry.LIVE_SETTINGS``
(SPEC-live-settings-panel.md section 9). Two always-visible groups, split by
field origin: "Settings" (every ``dwell.*`` field -- configs/default.yaml's
global dwell block) and "Pacing" (everything else -- each task's own YAML
config: trial timeout, inter-trial interval, follow_moving's target speed).

Unlike diki's own live panel, this one stays visible for the whole task run
rather than hiding while idle -- SPEC-diki-design-audit.md S8.2 flagged that
diki's idle state (browsing a persistent multi-task list, no task started
yet) has no equivalent in this app's one-task-per-window launch model, so
the hide-while-idle behavior was deliberately dropped rather than forced.

Restyled into a HUD-style floating-card look (SPEC-diki-design-audit.md
S8.10): still lives in ``MainWindow``'s own side column, not a canvas
overlay -- that approach was built and then explicitly rejected in S8.9, and
S8.10 deliberately did not re-open it. Instead the column's own background is
matched to the forest theme's canvas background (``configs/themes/
forest.yaml``, all four tasks unified to it per SPEC-scanning-task-design-
port.md S6) so the inset margin around the cards blends into the canvas
rather than reading as a second panel, and the five original ``QGroupBox``
cards are grouped into three semi-transparent dark-slate ``QFrame`` cards
(rounded corners, drop shadow, small-caps subheadings instead of pill
titles), sized to their content and stacked at the top of the column rather
than stretched to the window's full height.

The stylesheet is scoped to this widget's own subtree only (``setObjectName``
+ a Qt stylesheet set on ``self``), so it cannot leak into ``TaskCanvas`` or
any other window -- Qt stylesheets apply to the widget they're set on plus
its descendants, never to siblings or parents.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .settings_registry import LiveSetting, format_calibration, live_settings_for_task
from .slider_spin import SliderSpinRow

# HUD palette (SPEC-diki-design-audit.md S8.10). _TEXT/_MUTED/_ACCENT/_OK are
# diki's own TaskHud tokens, unchanged from S8.9 (ui/dashboard.py:328-391).
# _CANVAS_BG is the forest theme's canvas background (configs/themes/
# forest.yaml) -- all four tasks are unified to forest (SPEC-scanning-task-
# design-port.md S6), so hardcoding it here is a disclosed assumption tied to
# that fact, not a guess; it would need revisiting if a task is ever switched
# to a different theme. _CARD_BG is a new ~90%-opacity slate with no direct
# diki source -- diki's own TaskHud is a fully opaque overlay meant to sit on
# a dark canvas, not a translucent one meant to blend with a light one.
_TEXT = "#e7edf2"
_MUTED = "#b7c0cb"
_CANVAS_BG = "#e8f5e9"
_CARD_BG = "rgba(43, 51, 64, 230)"
_ACCENT = "#4dd0e1"
_ACCENT_SOFT = "rgba(77, 208, 225, 40)"
_OK = "#7fd992"
_BAD = "#e5484d"

_STYLESHEET = f"""
QWidget#operatorPanel {{ background: {_CANVAS_BG}; }}
/* The scroll area and its viewport must not paint over the panel's own
   canvas-matched background -- see the autoFillBackground note in __init__,
   which this rule alone cannot fix. */
QScrollArea#operatorPanelScroll {{ background: transparent; border: none; }}
QScrollArea#operatorPanelScroll > QWidget > QWidget {{ background: transparent; }}
/* Scrollbar themed here rather than relying on wtmh_theme.py's app-wide rule:
   this panel sets its own stylesheet and also runs under the standalone
   MainWindow, which never installs the app-wide sheet at all. Matches the HUD
   palette (translucent accent thumb, no native arrow buttons). */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {_ACCENT_SOFT};
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {_ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QFrame#hudCard {{
    background: {_CARD_BG};
    border-radius: 9px;
}}
QWidget#operatorPanel QLabel {{ color: {_TEXT}; background: transparent; font-size: 11px; }}
QWidget#operatorPanel QCheckBox {{ color: {_TEXT}; font-size: 11px; }}
QLabel#hudMuted {{ color: {_MUTED}; font-size: 10px; }}
QLabel[hudSubheading="true"] {{
    color: {_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QPushButton {{
    background: rgba(255, 255, 255, 18);
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    color: {_TEXT};
    font-size: 11px;
}}
QPushButton:hover {{ background: {_ACCENT_SOFT}; }}
QPushButton:disabled {{ color: #5a6472; background: rgba(255, 255, 255, 6); }}
QPushButton#danger {{ color: {_BAD}; }}
QSlider::groove:horizontal {{ height: 3px; background: rgba(255, 255, 255, 30); border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {_ACCENT}; width: 13px; height: 13px; margin: -5px 0; border-radius: 7px;
}}
QProgressBar {{
    border: none;
    border-radius: 3px;
    background: rgba(255, 255, 255, 20);
    text-align: center;
}}
QProgressBar::chunk {{ background: {_ACCENT}; border-radius: 3px; }}
QSpinBox, QDoubleSpinBox {{
    background: rgba(255, 255, 255, 18);
    border: none;
    border-radius: 5px;
    padding: 1px 4px;
    color: {_TEXT};
    font-size: 11px;
}}
QCheckBox::indicator {{
    width: 13px; height: 13px; border-radius: 3px;
    background: rgba(255, 255, 255, 18); border: 1px solid rgba(255, 255, 255, 40);
}}
QCheckBox::indicator:checked {{ background: {_ACCENT}; border: 1px solid {_ACCENT}; }}
"""


class OperatorPanel(QWidget):
    pause_toggled = Signal(bool)
    skip_requested = Signal()
    end_requested = Signal()
    # Fired for every live setting the operator changes: (dotted key, new value).
    # Replaces the old one-signal-per-field pattern (a single
    # ``dwell_threshold_changed`` signal) so adding a new live-tunable field
    # is a registry entry, not a new Signal + slot pair.
    setting_changed = Signal(str, object)
    # Explicit "keep these settings for this subject" (SPEC-live-settings-panel.md
    # S10.3). Deliberately an action, not an auto-save at run end: an
    # exploratory run must not be able to overwrite a profile that was working.
    save_profile_requested = Signal()
    reset_settings_requested = Signal()

    def __init__(
        self,
        task_id: str = "click_static",
        initial_values: dict[str, Any] | None = None,
        settings_source: str = "defaults",
        settings_saved_at: str = "",
        settings_calibration: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("operatorPanel")
        # Plain QWidget ignores a stylesheet "background" unless this is set
        # -- a real Qt gotcha, not optional.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_STYLESHEET)
        self._values = dict(initial_values or {})
        # key -> the widget driving it, so "Reset to defaults" can put values
        # back into the controls rather than only into the engine.
        self._controls: dict[str, Any] = {}

        # The cards are built into a scrolled content widget, not into the
        # panel directly (SPEC-live-settings-panel.md S10.10). The card stack
        # needs 989 px (1038 for follow_moving) and cannot compress, which is
        # more than a maximized window can offer on a 1920x1080 screen -- put
        # directly on the panel it forced the whole DashboardWindow to grow
        # past the screen edge and silently cut its own bottom card off. The
        # scroll area lives inside the panel rather than around it so both
        # embedders get it: DashboardWindow's TaskRunView and the standalone
        # ``--task X --gui`` MainWindow (S10.8.4's second occurrence).
        content = QWidget()
        content.setObjectName("operatorPanelContent")
        layout = QVBoxLayout(content)
        # ~16-20px inset from the window's top/right edges (SPEC-diki-design-
        # audit.md S8.10); uniform on all sides so the cards read as floating
        # within the column rather than flush against any edge of it.
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # -- Status + Live card --------------------------------------------
        status_card, status_layout = self._make_card()
        self._add_subheading(status_layout, "Status")
        self.fps_label = QLabel("FPS: --")
        # Distinct from fps_label: this is the tracker's real measured
        # incoming-sample rate (SampleRateTracker, keyed off each sample's
        # own capture timestamp), not the app's own poll/render-loop rate
        # -- see SPEC-ui-setup-task-selection.md S24.4 for why the two can
        # read very differently (e.g. polling at 150 while a GP3 HD capped
        # at 60 Hz over USB 2.0 delivers new samples much more slowly).
        self.device_rate_label = QLabel("Device: -- Hz")
        self.validity_label = QLabel("Gaze: --")
        status_layout.addWidget(self.fps_label)
        status_layout.addWidget(self.device_rate_label)
        status_layout.addWidget(self.validity_label)

        # "Live" section -- ported from diki's LiveCounterPanel (SPEC-diki-
        # design-audit.md S4.2/S5/S8): a large trial counter, running
        # hit/timeout tally, and a progress bar.
        status_layout.addSpacing(8)
        self._add_subheading(status_layout, "Live")
        self.trial_label = QLabel("Trial: --")
        # 22pt bold, accent-coloured -- diki's TaskHud counter size (SPEC-
        # diki-design-audit.md S4.1/S8.5 table), not DashboardWindow's larger
        # 34pt -- this restyle targets the HUD look, not the light-card one.
        trial_font = QFont()
        trial_font.setPointSize(22)
        trial_font.setBold(True)
        self.trial_label.setFont(trial_font)
        self.trial_label.setStyleSheet(f"color: {_ACCENT};")
        status_layout.addWidget(self.trial_label)

        stats_row = QHBoxLayout()
        self.hit_label = QLabel("0 hit")
        self.hit_label.setStyleSheet(f"color: {_OK}; font-weight: 600; font-size: 11px;")
        self.timeout_label = QLabel("0 timeout")
        self.timeout_label.setStyleSheet(f"color: {_MUTED}; font-weight: 600; font-size: 11px;")
        stats_row.addWidget(self.hit_label)
        stats_row.addWidget(self.timeout_label)
        stats_row.addStretch(1)
        status_layout.addLayout(stats_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        status_layout.addWidget(self.progress_bar)
        layout.addWidget(status_card)

        # -- Controls card ---------------------------------------------------
        controls_card, controls_layout = self._make_card()
        self._add_subheading(controls_layout, "Controls")

        self._paused = False
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._on_pause)
        controls_layout.addWidget(self.pause_button)

        self.skip_button = QPushButton("Skip trial")
        self.skip_button.clicked.connect(self.skip_requested.emit)
        controls_layout.addWidget(self.skip_button)

        # Ported from diki's "Live controls" box (SPEC-diki-design-audit.md
        # S5/S8), which has Pause/Skip/End.
        self.end_button = QPushButton("End task")
        self.end_button.setObjectName("danger")  # diki's stop_button (ui/dashboard.py:787)
        self.end_button.clicked.connect(self.end_requested.emit)
        controls_layout.addWidget(self.end_button)
        layout.addWidget(controls_card)

        # -- Settings + Pacing card -------------------------------------------
        settings = live_settings_for_task(task_id)
        dwell_settings = [s for s in settings if s.group == "settings"]
        pacing_settings = [s for s in settings if s.group == "pacing"]

        tuning_card, tuning_layout = self._make_card()
        self._add_subheading(tuning_layout, "Settings")
        for setting in dwell_settings:
            tuning_layout.addWidget(self._build_control(setting))
        tuning_layout.addSpacing(8)
        self._add_subheading(tuning_layout, "Pacing")
        for setting in pacing_settings:
            tuning_layout.addWidget(self._build_control(setting))
        layout.addWidget(tuning_card)

        # -- Profile card ------------------------------------------------------
        # The visible half of S10.3's "auto-apply, clearly shown" decision.
        # Auto-applying a profile from another day WITHOUT saying so would be
        # silent protocol drift, so the indicator is not decoration -- it is
        # the other half of the decision.
        profile_card, profile_layout = self._make_card()
        self._add_subheading(profile_layout, "Settings profile")
        self.settings_source_label = QLabel()
        self.settings_source_label.setObjectName("hudMuted")
        self.settings_source_label.setWordWrap(True)
        profile_layout.addWidget(self.settings_source_label)
        self.set_settings_source(settings_source, settings_saved_at, settings_calibration)

        self.save_profile_button = QPushButton("Save for this subject")
        self.save_profile_button.clicked.connect(self.save_profile_requested.emit)
        profile_layout.addWidget(self.save_profile_button)

        self.reset_settings_button = QPushButton("Reset to defaults")
        self.reset_settings_button.clicked.connect(self.reset_settings_requested.emit)
        profile_layout.addWidget(self.reset_settings_button)
        layout.addWidget(profile_card)

        # Cards hug the top of the column; the rest of the column shows the
        # canvas-matched background instead of stretching a card to fill it.
        layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setObjectName("operatorPanelScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Width is fixed at 280 by the embedder, so a horizontal bar would only
        # ever be a rendering artifact.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        # setWidget() turns on autoFillBackground for BOTH the viewport and the
        # content widget, which paints them with the inherited QPalette::Window
        # colour -- near-black under this app's Fusion palette, and visible in
        # the gaps between the HUD cards. The QSS rule below only reaches the
        # viewport (a direct QScrollArea child), never the content widget (a
        # grandchild via the viewport), so both need it cleared explicitly.
        # Same gotcha as SPEC-ui-setup-task-selection.md S22.5.
        scroll.viewport().setAutoFillBackground(False)
        content.setAutoFillBackground(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

    # -- HUD card construction -----------------------------------------------

    def _make_card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(self)
        card.setObjectName("hudCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Soft drop shadow to lift the card off the canvas-matched
        # background (SPEC-diki-design-audit.md S8.10) -- QSS has no
        # box-shadow property, so this needs a real graphics effect. Each
        # card gets its own QGraphicsDropShadowEffect instance -- Qt effects
        # cannot be shared across widgets.
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 64))
        card.setGraphicsEffect(shadow)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(6)
        return card, card_layout

    def _add_subheading(self, layout: QVBoxLayout, text: str) -> None:
        # Small-caps-style muted subheading in place of the old QGroupBox
        # pill title -- Qt stylesheets have no text-transform, so the text
        # itself is upper-cased.
        label = QLabel(text.upper())
        label.setProperty("hudSubheading", True)
        layout.addWidget(label)

    # -- control construction ------------------------------------------------

    def _build_control(self, setting: LiveSetting) -> QWidget:
        value = self._values.get(setting.key)
        container = QWidget(self)
        row = QVBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)

        if setting.kind == "bool":
            box = QCheckBox(setting.label)
            box.setChecked(bool(value))
            if setting.tooltip:
                box.setToolTip(setting.tooltip)
            box.toggled.connect(lambda v, k=setting.key: self._emit_change(k, bool(v)))
            self._controls[setting.key] = box
            row.addWidget(box)
            return container

        label = QLabel(setting.label)
        if setting.tooltip:
            label.setToolTip(setting.tooltip)
        row.addWidget(label)
        if setting.kind == "int":
            minimum = setting.min if setting.min is not None else 0
            maximum = setting.max if setting.max is not None else 100
            step = setting.step if setting.step is not None else 1
            initial = int(value if value is not None else setting.min or 0)
        else:  # float
            minimum = setting.min if setting.min is not None else 0.0
            maximum = setting.max if setting.max is not None else 1.0
            step = setting.step if setting.step is not None else 0.05
            initial = float(value if value is not None else setting.min or 0.0)
        control = SliderSpinRow(setting.kind, minimum, maximum, step, initial)
        if setting.tooltip:
            control.setToolTip(setting.tooltip)
        control.valueChanged.connect(lambda v, k=setting.key: self._emit_change(k, v))
        self._controls[setting.key] = control
        row.addWidget(control)
        return container

    def _emit_change(self, key: str, value: Any) -> None:
        self._values[key] = value
        self.setting_changed.emit(key, value)

    # -- settings profile --------------------------------------------------

    def current_values(self) -> dict[str, Any]:
        """The live values currently shown, i.e. what a save would store."""
        return dict(self._values)

    def set_settings_source(
        self, source: str, saved_at: str = "", calibration: dict[str, Any] | None = None
    ) -> None:
        """Say where this run's settings came from, in plain language.

        For a loaded profile this also names the calibration it was tuned
        under (S10.5.5) -- settings tuned under a poor calibration may be
        compensating for bad tracking rather than suiting the child, and that
        is worth seeing at the moment they are applied, not only in the file.
        """
        if source == "profile":
            when = f" (saved {saved_at[:10]})" if saved_at else ""
            text = f"Loaded from this subject's saved profile{when}."
            cal = format_calibration(calibration)
            if cal:
                text += f" Tuned under {cal}."
        elif source == "carried":
            text = "Carried over from the previous run in this session."
        else:
            text = "Using task defaults."
        self.settings_source_label.setText(text)

    def apply_values(self, values: dict[str, Any]) -> None:
        """Push values into the controls, emitting a change for each.

        Used by "Reset to defaults". Each control is updated with its signals
        blocked and the change re-emitted explicitly, so the engine is updated
        exactly once per key and a SETTING_CHANGED event is still logged --
        a reset is a real settings change and must appear in the record like
        any other.
        """
        for key, value in values.items():
            control = self._controls.get(key)
            if control is None:
                continue
            blocked = control.blockSignals(True)
            try:
                if isinstance(control, QCheckBox):
                    control.setChecked(bool(value))
                else:
                    control.setValue(value)
            finally:
                control.blockSignals(blocked)
            self._emit_change(key, value)

    # -- live updates ------------------------------------------------------

    def update_status(
        self,
        fps: float,
        gaze_valid: bool,
        trial_index: int,
        n_trials: int,
        connected: bool = True,
        hits: int = 0,
        timeouts: int = 0,
        device_rate_hz: float | None = None,
    ) -> None:
        self.fps_label.setText(f"FPS: {fps:.0f}")
        self.device_rate_label.setText(
            "Device: -- Hz" if device_rate_hz is None else f"Device: {device_rate_hz:.0f} Hz"
        )
        if not connected:
            status = "DISCONNECTED"
        elif gaze_valid:
            status = "valid"
        else:
            status = "LOST"
        self.validity_label.setText(f"Gaze: {status}")
        self.trial_label.setText(f"Trial: {trial_index + 1}/{n_trials}")
        self.hit_label.setText(f"{hits} hit")
        self.timeout_label.setText(f"{timeouts} timeout")
        self.progress_bar.setRange(0, max(n_trials, 1))
        self.progress_bar.setValue(min(trial_index + 1, n_trials) if n_trials else 0)

    # -- handlers ----------------------------------------------------------

    def _on_pause(self) -> None:
        self._paused = not self._paused
        self.pause_button.setText("Resume" if self._paused else "Pause")
        self.pause_toggled.emit(self._paused)
