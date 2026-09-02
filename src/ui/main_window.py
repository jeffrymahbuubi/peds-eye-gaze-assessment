"""Main window hosting the subject canvas and the operator panel."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from .canvas import TaskCanvas
from .operator_panel import OperatorPanel


class MainWindow(QMainWindow):
    def __init__(
        self,
        theme: dict | None = None,
        dwell_threshold_ms: int = 800,
        fullscreen: bool = True,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Pediatric Eye-Gaze Assessment")

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = TaskCanvas(theme=theme)
        self.operator_panel = OperatorPanel(dwell_threshold_ms=dwell_threshold_ms)
        self.operator_panel.setFixedWidth(240)

        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.operator_panel)
        self.setCentralWidget(central)

        if fullscreen:
            self.showFullScreen()
        else:
            self.resize(1280, 800)
