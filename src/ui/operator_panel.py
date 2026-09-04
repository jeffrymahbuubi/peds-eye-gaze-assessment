"""Operator (therapist) control panel (plan section 5.6 / Prompt 4).

Shows live diagnostics -- FPS, gaze validity, current trial index -- and
exposes runtime controls: pause/resume, skip trial, and a live settings
panel built from ``settings_registry.LIVE_SETTINGS`` (SPEC-live-settings-panel.md
section 5.1/5.2). A small "Basic" group (physician-facing: dwell threshold,
visual cursor, progress ring, instant feedback) is always visible; everything
else (jitter tolerance, refractory, smoothing, task timing) lives in a
collapsed-by-default "Advanced" section for debugging/development use.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .settings_registry import LiveSetting, live_settings_for_task


class OperatorPanel(QWidget):
    pause_toggled = Signal(bool)
    skip_requested = Signal()
    # Fired for every live setting the operator changes: (dotted key, new value).
    # Replaces the old one-signal-per-field pattern (a single
    # ``dwell_threshold_changed`` signal) so adding a new live-tunable field
    # is a registry entry, not a new Signal + slot pair.
    setting_changed = Signal(str, object)

    def __init__(
        self,
        task_id: str = "click_static",
        initial_values: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._values = dict(initial_values or {})
        layout = QVBoxLayout(self)

        status_box = QGroupBox("Status")
        status_layout = QVBoxLayout(status_box)
        self.fps_label = QLabel("FPS: --")
        self.validity_label = QLabel("Gaze: --")
        self.trial_label = QLabel("Trial: --")
        for lbl in (self.fps_label, self.validity_label, self.trial_label):
            status_layout.addWidget(lbl)
        layout.addWidget(status_box)

        control_box = QGroupBox("Controls")
        control_layout = QVBoxLayout(control_box)

        self._paused = False
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._on_pause)
        control_layout.addWidget(self.pause_button)

        self.skip_button = QPushButton("Skip trial")
        self.skip_button.clicked.connect(self.skip_requested.emit)
        control_layout.addWidget(self.skip_button)

        layout.addWidget(control_box)

        settings = live_settings_for_task(task_id)
        basic = [s for s in settings if s.group == "basic"]
        advanced = [s for s in settings if s.group == "advanced"]

        basic_box = QGroupBox("Settings")
        basic_layout = QVBoxLayout(basic_box)
        for setting in basic:
            basic_layout.addWidget(self._build_control(setting))
        layout.addWidget(basic_box)

        # Collapsed by default: a checkable QGroupBox whose title checkbox
        # shows/hides its contents -- standard Qt pattern, no extra widget
        # dependency (SPEC section 7, open question 1).
        self.advanced_box = QGroupBox("Advanced")
        self.advanced_box.setCheckable(True)
        self.advanced_box.setChecked(False)
        advanced_layout = QVBoxLayout(self.advanced_box)
        for setting in advanced:
            advanced_layout.addWidget(self._build_control(setting))
        self._advanced_content = advanced_layout
        self._set_advanced_visible(False)
        self.advanced_box.toggled.connect(self._set_advanced_visible)
        layout.addWidget(self.advanced_box)

        layout.addStretch(1)

    # -- control construction ------------------------------------------------

    def _set_advanced_visible(self, visible: bool) -> None:
        for i in range(self._advanced_content.count()):
            item = self._advanced_content.itemAt(i)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setVisible(visible)

    def _build_control(self, setting: LiveSetting) -> QWidget:
        value = self._values.get(setting.key)
        container = QWidget(self)
        row = QVBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)

        if setting.kind == "bool":
            box = QCheckBox(setting.label)
            box.setChecked(bool(value))
            box.toggled.connect(lambda v, k=setting.key: self._emit_change(k, bool(v)))
            row.addWidget(box)
            return container

        row.addWidget(QLabel(setting.label))
        if setting.kind == "int":
            spin = QSpinBox()
            spin.setMinimum(int(setting.min or 0))
            spin.setMaximum(int(setting.max or 100))
            spin.setSingleStep(int(setting.step or 1))
            spin.setValue(int(value if value is not None else setting.min or 0))
            spin.valueChanged.connect(lambda v, k=setting.key: self._emit_change(k, int(v)))
            row.addWidget(spin)
        else:  # float
            spin = QDoubleSpinBox()
            spin.setMinimum(float(setting.min or 0.0))
            spin.setMaximum(float(setting.max or 1.0))
            spin.setSingleStep(float(setting.step or 0.05))
            spin.setDecimals(2)
            spin.setValue(float(value if value is not None else setting.min or 0.0))
            spin.valueChanged.connect(lambda v, k=setting.key: self._emit_change(k, float(v)))
            row.addWidget(spin)
        return container

    def _emit_change(self, key: str, value: Any) -> None:
        self.setting_changed.emit(key, value)

    # -- live updates ------------------------------------------------------

    def update_status(
        self,
        fps: float,
        gaze_valid: bool,
        trial_index: int,
        n_trials: int,
        connected: bool = True,
    ) -> None:
        self.fps_label.setText(f"FPS: {fps:.0f}")
        if not connected:
            status = "DISCONNECTED"
        elif gaze_valid:
            status = "valid"
        else:
            status = "LOST"
        self.validity_label.setText(f"Gaze: {status}")
        self.trial_label.setText(f"Trial: {trial_index + 1}/{n_trials}")

    # -- handlers ----------------------------------------------------------

    def _on_pause(self) -> None:
        self._paused = not self._paused
        self.pause_button.setText("Resume" if self._paused else "Pause")
        self.pause_toggled.emit(self._paused)
