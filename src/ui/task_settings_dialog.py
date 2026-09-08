"""Pre-launch dialog for structural/layout task parameters
(SPEC-live-settings-panel.md section 5.3).

Grid size, target radius, icon count, trial count, and follow_moving's
selection window are baked once into a task's trial list at
``build_targets()`` time -- they are not safe to change mid-task without a
trial-rebuild mechanism this design deliberately avoids (see the SPEC's
section 4 classification table). Instead, they're collected here, before
``AssessmentApp`` is constructed, and merged over the task's own config via
the same ``deep_merge`` an ``overrides:`` YAML block already goes through.

Shown modally by :func:`src.app.run_gui` and by ``DashboardWindow``'s Tasks
tab. "Start task" accepts current values (defaults if untouched); "Cancel"
aborts the launch.

Themed to match the WTMH dashboard (SPEC-ui-setup-task-selection.md S11.1
critique point 1 -- previously fell back entirely to native OS dialog
styling). Reuses ``wtmh_theme.STYLESHEET`` directly rather than duplicating
any button/form-control CSS: giving this dialog the same ``wtmhDashboard``
object name is enough for every ancestor-scoped rule in that stylesheet
(form controls, button tiers, sliders) to apply here too, exactly as it does
in ``DashboardWindow``. The dialog keeps its native OS title bar (this app
never goes frameless anywhere, not even ``DashboardWindow`` itself, which
only adds its own styled bar *below* the OS chrome) -- the in-card title
label below plays that same role here.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
)

from .settings_registry import (
    StructuralSetting,
    initial_structural_values,
    set_nested,
    structural_settings_for_task,
)
from .slider_spin import SliderSpinRow
from .wtmh_theme import STYLESHEET


class TaskSettingsDialog(QDialog):
    def __init__(self, task_id: str, config: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Task settings — {task_id}")
        self.setObjectName("wtmhDashboard")
        self.setStyleSheet(STYLESHEET)
        self._settings = structural_settings_for_task(task_id)
        values = initial_structural_values(task_id, config)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        card = QFrame(self)
        card.setObjectName("wtmhCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Soft drop shadow to lift the card off the page-background dialog
        # behind it -- same QGraphicsDropShadowEffect pattern already used
        # for OperatorPanel's HUD cards (SPEC-diki-design-audit.md S8.10);
        # QSS has no box-shadow property, so this needs a real graphics
        # effect, not CSS.
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 60))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(12)

        title = QLabel(f"Task settings — {task_id}")
        title.setObjectName("wtmhSectionTitle")
        card_layout.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        self._controls: dict[str, SliderSpinRow] = {}

        for setting in self._settings:
            control = self._build_control(setting, values.get(setting.key))
            self._controls[setting.key] = control
            form.addRow(setting.label, control)

        card_layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Start task")
        ok_button.setObjectName("wtmhPrimary")
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("wtmhGhost")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        card_layout.addWidget(buttons)

        outer.addWidget(card)

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
