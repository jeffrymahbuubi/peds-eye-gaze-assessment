"""Operator (therapist) control panel (plan section 5.6 / Prompt 4).

Shows live diagnostics -- FPS, gaze validity, current trial index -- and
exposes runtime controls: pause/resume, skip trial, and a live settings
panel built from ``settings_registry.LIVE_SETTINGS`` (SPEC-live-settings-panel.md
section 9). Two always-visible groups, split by field origin: "Settings"
(every ``dwell.*`` field -- configs/default.yaml's global dwell block) and
"Pacing" (everything else -- each task's own YAML config: trial timeout,
inter-trial interval, follow_moving's target speed).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .settings_registry import LiveSetting, live_settings_for_task
from .slider_spin import SliderSpinRow


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
        dwell_settings = [s for s in settings if s.group == "settings"]
        pacing_settings = [s for s in settings if s.group == "pacing"]

        settings_box = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_box)
        for setting in dwell_settings:
            settings_layout.addWidget(self._build_control(setting))
        layout.addWidget(settings_box)

        pacing_box = QGroupBox("Pacing")
        pacing_layout = QVBoxLayout(pacing_box)
        for setting in pacing_settings:
            pacing_layout.addWidget(self._build_control(setting))
        layout.addWidget(pacing_box)

        layout.addStretch(1)

    # -- control construction ------------------------------------------------

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
        control.valueChanged.connect(lambda v, k=setting.key: self._emit_change(k, v))
        row.addWidget(control)
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
