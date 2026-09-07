"""Shared slider + numeric-readout widget for int/float task settings
(SPEC-live-settings-panel.md section 8).

Both OperatorPanel's live settings and TaskSettingsDialog's structural
settings need the same slider+exact-value pairing, kept in sync both ways.
This widget owns that sync so neither call site duplicates it.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QSlider, QSpinBox, QWidget


class SliderSpinRow(QWidget):
    """A QSlider paired with a QSpinBox/QDoubleSpinBox readout, kept in sync.

    ``kind`` selects the readout type (``"int"`` -> ``QSpinBox``, ``"float"``
    -> ``QDoubleSpinBox``). The slider always moves over integer *positions*
    (section 8.2's mapping: ``position = round((value - min) / step)``,
    ``value = min + position * step``), so one widget covers both kinds
    without a separate float-slider implementation.
    """

    valueChanged = Signal(object)  # emits int or float, matching `kind`

    def __init__(
        self,
        kind: str,
        minimum: float,
        maximum: float,
        step: float,
        value: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._min = minimum
        self._step = step
        n_steps = round((maximum - minimum) / step)

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setMinimum(0)
        self._slider.setMaximum(int(n_steps))

        self._spin: QSpinBox | QDoubleSpinBox
        if kind == "int":
            self._spin = QSpinBox(self)
            self._spin.setMinimum(int(minimum))
            self._spin.setMaximum(int(maximum))
            self._spin.setSingleStep(int(step))
        else:
            self._spin = QDoubleSpinBox(self)
            self._spin.setMinimum(float(minimum))
            self._spin.setMaximum(float(maximum))
            self._spin.setSingleStep(float(step))
            self._spin.setDecimals(2)

        # Set initial values before wiring the sync signals below, so
        # construction never emits a spurious valueChanged.
        self._slider.setValue(self._position_for(value))
        self._spin.setValue(value if kind == "float" else int(value))

        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spin.valueChanged.connect(self._on_spin_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._slider, stretch=1)
        layout.addWidget(self._spin)

    def _position_for(self, value: float) -> int:
        return round((value - self._min) / self._step)

    def _value_for(self, position: int) -> float:
        value = self._min + position * self._step
        return value if self._kind == "float" else int(round(value))

    def _on_slider_changed(self, position: int) -> None:
        value = self._value_for(position)
        self._spin.blockSignals(True)
        self._spin.setValue(value)
        self._spin.blockSignals(False)
        self.valueChanged.emit(value)

    def _on_spin_changed(self, value: float) -> None:
        typed_value = value if self._kind == "float" else int(value)
        position = self._position_for(typed_value)
        self._slider.blockSignals(True)
        self._slider.setValue(position)
        self._slider.blockSignals(False)
        self.valueChanged.emit(typed_value)

    def value(self) -> float:
        return self._spin.value() if self._kind == "float" else int(self._spin.value())

    def setValue(self, value: float) -> None:  # noqa: N802 (Qt naming)
        self._spin.setValue(value if self._kind == "float" else int(value))
