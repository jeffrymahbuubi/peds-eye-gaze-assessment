"""Fullscreen subject-facing canvas (PySide6).

Renders the active target, the gaze cursor, the dwell progress ring, and simple
hit particle feedback. Imports PySide6 at module load, so it is only imported by
the GUI path (:mod:`src.app`), never by the headless pipeline or tests.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from ..inputs.base import norm_to_px


class TaskCanvas(QWidget):
    def __init__(self, theme: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme or {}
        self.setMouseTracking(True)
        self._bg = QColor(self.theme.get("background", "#101418"))

        # Render state, updated by the app loop each frame.
        self.target_xy_norm: tuple[float, float] | None = None
        self.target_radius_px: float = 90.0
        self.target_color = QColor(self.theme.get("target_default", "#ff5252"))
        self.cursor_xy_norm: tuple[float, float] = (0.5, 0.5)
        self.cursor_valid: bool = False
        self.dwell_progress: float = 0.0
        self.selectable: bool = True
        self.show_cursor: bool = True
        self.show_progress_ring: bool = True
        self._particles: list[tuple[float, float, float]] = []  # x_norm, y_norm, age

    # -- state updates from the app loop ----------------------------------

    def set_frame(
        self,
        target_xy_norm: tuple[float, float] | None,
        target_radius_px: float,
        cursor_xy_norm: tuple[float, float],
        cursor_valid: bool,
        dwell_progress: float,
        selectable: bool = True,
    ) -> None:
        self.target_xy_norm = target_xy_norm
        self.target_radius_px = target_radius_px
        self.cursor_xy_norm = cursor_xy_norm
        self.cursor_valid = cursor_valid
        self.dwell_progress = dwell_progress
        self.selectable = selectable
        self.update()

    def burst(self, x_norm: float, y_norm: float) -> None:
        """Trigger a hit particle burst at a normalized position."""
        self._particles.append((x_norm, y_norm, 0.0))

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        w, h = self.width(), self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self._bg)

        if self.target_xy_norm is not None:
            tx, ty = norm_to_px(*self.target_xy_norm, w, h)
            self._draw_target(painter, tx, ty)
            if self.show_progress_ring and self.dwell_progress > 0:
                self._draw_progress_ring(painter, tx, ty)

        self._draw_particles(painter, w, h)

        if self.show_cursor:
            cx, cy = norm_to_px(*self.cursor_xy_norm, w, h)
            self._draw_cursor(painter, cx, cy)

        painter.end()

    def _draw_target(self, painter: QPainter, x: float, y: float) -> None:
        r = self.target_radius_px
        color = self.target_color if self.selectable else self.target_color.darker(180)
        grad = QRadialGradient(QPointF(x, y), r)
        grad.setColorAt(0.0, color.lighter(130))
        grad.setColorAt(1.0, color)
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(x, y), r, r)
        if self.selectable:
            # bright "catch me now" outline during the selectable window
            pen = painter.pen()
            pen.setColor(QColor("#ffffff"))
            pen.setWidth(4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(x, y), r + 4, r + 4)

    def _draw_progress_ring(self, painter: QPainter, x: float, y: float) -> None:
        r = self.target_radius_px + 16
        pen = painter.pen()
        pen.setColor(QColor(self.theme.get("cursor_color", "#ffffff")))
        pen.setWidth(8)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        span = int(-360 * 16 * max(0.0, min(1.0, self.dwell_progress)))
        painter.drawArc(int(x - r), int(y - r), int(2 * r), int(2 * r), 90 * 16, span)

    def _draw_cursor(self, painter: QPainter, x: float, y: float) -> None:
        color = QColor(self.theme.get("cursor_color", "#ffffff"))
        color.setAlpha(200 if self.cursor_valid else 70)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(x, y), 14, 14)

    def _draw_particles(self, painter: QPainter, w: int, h: int) -> None:
        if not self._particles:
            return
        color = QColor(self.theme.get("particle_color", "#ffd54f"))
        alive: list[tuple[float, float, float]] = []
        for (xn, yn, age) in self._particles:
            age += 1.0
            if age > 20:
                continue
            cx, cy = norm_to_px(xn, yn, w, h)
            for k in range(8):
                ang = math.tau * k / 8
                rad = age * 6
                color.setAlpha(max(0, int(255 * (1 - age / 20))))
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(
                    QPointF(cx + rad * math.cos(ang), cy + rad * math.sin(ang)), 6, 6
                )
            alive.append((xn, yn, age))
        self._particles = alive
