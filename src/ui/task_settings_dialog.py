"""Pre-launch dialog for structural/layout task parameters
(SPEC-live-settings-panel.md section 5.3).

Grid size, target radius, icon count, trial count, and follow_moving's
selection window are baked once into a task's trial list at
``build_targets()`` time -- they are not safe to change mid-task without a
trial-rebuild mechanism this design deliberately avoids (see the SPEC's
section 4 classification table). Instead, they're collected here, before
``AssessmentApp`` is constructed, and merged over the task's own config via
the same ``deep_merge`` an ``overrides:`` YAML block already goes through.

Shown modally by :func:`src.app.run_gui`. "Start task" accepts current
values (defaults if untouched); "Cancel" aborts the launch.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout

from .settings_registry import (
    StructuralSetting,
    initial_structural_values,
    set_nested,
    structural_settings_for_task,
)
from .slider_spin import SliderSpinRow


class TaskSettingsDialog(QDialog):
    def __init__(self, task_id: str, config: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Task settings — {task_id}")
        self._settings = structural_settings_for_task(task_id)
        values = initial_structural_values(task_id, config)

        outer = QVBoxLayout(self)
        form = QFormLayout()
        self._controls: dict[str, SliderSpinRow] = {}

        for setting in self._settings:
            control = self._build_control(setting, values.get(setting.key))
            self._controls[setting.key] = control
            form.addRow(setting.label, control)

        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start task")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    @staticmethod
    def _build_control(setting: StructuralSetting, value: Any) -> SliderSpinRow:
        initial = value if value is not None else setting.min
        return SliderSpinRow(setting.kind, setting.min, setting.max, setting.step, initial)

    def overrides(self) -> dict[str, Any]:
        """Return a nested dict (dotted keys expanded) suitable for
        ``deep_merge``-ing over ``config["task"]``."""
        result: dict[str, Any] = {}
        for setting in self._settings:
            control = self._controls[setting.key]
            value = control.value()
            set_nested(result, setting.key, int(value) if setting.kind == "int" else float(value))
        return result
