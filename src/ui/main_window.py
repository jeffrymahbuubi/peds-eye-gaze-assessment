"""Views hosting the subject canvas and the operator sidebar.

:class:`TaskRunView` is the actual canvas+sidebar content, as a plain
``QWidget`` -- extracted so it can be embedded into another window (the
Setup/Task-selection dashboard's ``QStackedWidget``, SPEC-ui-setup-
task-selection.md S3.1.7) instead of only ever living inside its own
top-level window. :class:`MainWindow` is now a thin wrapper around it for
the standalone ``--task X --gui`` CLI launch (:mod:`src.app`), unchanged in
behavior and public attributes (``.canvas``/``.operator_panel``) from
before this split.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from .canvas import TaskCanvas
from .operator_panel import OperatorPanel


class TaskRunView(QWidget):
    def __init__(
        self,
        theme: dict | None = None,
        task_id: str = "click_static",
        initial_settings: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Qt's default inter-widget spacing otherwise leaves a gap between
        # canvas and sidebar where this unstyled central widget's raw (black)
        # background shows through (SPEC-diki-design-audit.md S8.7).
        layout.setSpacing(0)

        self.canvas = TaskCanvas(theme=theme)
        self.operator_panel = OperatorPanel(task_id=task_id, initial_values=initial_settings)
        self.operator_panel.setFixedWidth(280)

        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.operator_panel)


class MainWindow(QMainWindow):
    def __init__(
        self,
        theme: dict | None = None,
        task_id: str = "click_static",
        initial_settings: dict[str, Any] | None = None,
        fullscreen: bool = True,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Pediatric Eye-Gaze Assessment")

        self.view = TaskRunView(theme=theme, task_id=task_id, initial_settings=initial_settings)
        self.canvas = self.view.canvas
        self.operator_panel = self.view.operator_panel
        self.setCentralWidget(self.view)

        if fullscreen:
            self.showFullScreen()
        else:
            self.resize(1280, 800)
