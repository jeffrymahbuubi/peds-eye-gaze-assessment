"""Operator (therapist) control panel (plan section 5.6 / Prompt 4).

Shows live diagnostics — FPS, gaze validity, current trial index — and exposes
runtime controls: pause/resume, skip trial, and a dwell-threshold slider so the
therapist can adapt to a child without restarting (plan risk table).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class OperatorPanel(QWidget):
    pause_toggled = Signal(bool)
    skip_requested = Signal()
    dwell_threshold_changed = Signal(int)  # milliseconds

    def __init__(self, dwell_threshold_ms: int = 800, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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

        control_layout.addWidget(QLabel("Dwell threshold (ms)"))
        self.dwell_slider = QSlider(Qt.Orientation.Horizontal)
        self.dwell_slider.setMinimum(300)
        self.dwell_slider.setMaximum(2000)
        self.dwell_slider.setSingleStep(50)
        self.dwell_slider.setValue(dwell_threshold_ms)
        self.dwell_value = QLabel(f"{dwell_threshold_ms} ms")
        self.dwell_slider.valueChanged.connect(self._on_dwell_changed)
        control_layout.addWidget(self.dwell_slider)
        control_layout.addWidget(self.dwell_value)

        layout.addWidget(control_box)
        layout.addStretch(1)

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

    def _on_dwell_changed(self, value: int) -> None:
        self.dwell_value.setText(f"{value} ms")
        self.dwell_threshold_changed.emit(value)
