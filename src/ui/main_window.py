"""Main window hosting the subject canvas and the operator panel."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from .canvas import TaskCanvas
from .operator_panel import OperatorPanel


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

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = TaskCanvas(theme=theme)
        self.operator_panel = OperatorPanel(task_id=task_id, initial_values=initial_settings)
        self.operator_panel.setFixedWidth(280)

        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.operator_panel)
        self.setCentralWidget(central)

        if fullscreen:
            self.showFullScreen()
        else:
            self.resize(1280, 800)
