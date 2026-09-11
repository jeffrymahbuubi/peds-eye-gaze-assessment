"""Fullscreen subject-facing canvas (PySide6).

Renders the active target, the gaze cursor, the dwell progress ring, and simple
hit particle feedback. Imports PySide6 at module load, so it is only imported by
the GUI path (:mod:`src.app`), never by the headless pipeline or tests.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from ..inputs.base import norm_to_px, outside_distance

# Distractor glyphs for the scanning field (ported from resources/diki, see
# SPEC-diki-design-audit.md S3.4/S4). Distinct shapes -- not just distinct
# colours -- mean the child discriminates form, which is what a scanning/
# visual-search assessment is for.
_SHAPE_CIRCLE, _SHAPE_SQUARE, _SHAPE_TRIANGLE, _SHAPE_DIAMOND, _SHAPE_HEX, _SHAPE_STAR = range(6)

# The gaze cursor is a small hollow ring, modelled on Gazepoint Control's own
# marker (SPEC-gaze-cursor-redesign.md S4.3, reference screenshots at
# resources/images/gaze-cursor-from-calib/). Hollow and small on purpose: it no
# longer occludes the target underneath it, which matters most at exactly the
# moment the child is on target and the dwell ring is filling. It must stay
# visually distinct from that dwell arc (8px stroke, target-sized radius) so it
# never reads as a second, smaller progress indicator.
_CURSOR_RADIUS_PX = 5.0
_CURSOR_STROKE_PX = 2.0

# The ring is drawn twice: a wider halo underneath, then the core stroke on
# top, leaving a contrasting fringe on both sides of the core line. This is
# what makes one small marker legible on *any* backdrop without per-theme
# tuning (SPEC-gaze-cursor-redesign.md S10) -- a single-colour ring cannot be,
# and the first attempt proved it: a dark-green core on the forest theme's
# light-green background, among dark-green grid outlines drawn in the same
# `cursor_color`, was reported as blending in and hard to notice.
#
# Copying Gazepoint Control's *colour* was the error there. Their saturated
# green works because their backdrop is near-black; the transferable principle
# is maximum contrast against the background, not the hue itself.
# The dark fringe is the load-bearing half, and it was chosen by measurement,
# not taste: rendered against the real forest scene, a white halo round a
# theme-coloured core scored 32205 against the plain ring's 30832 -- a 4%
# improvement, because white fringe on a near-white background adds almost no
# ink. Dark fringe with a white core scored 53363, +73%. The core then carries
# legibility on dark themes, where the fringe is what disappears. Both values
# are deliberately theme-independent: per-theme accent colours are exactly what
# produced the blending complaint.
_CURSOR_HALO_STROKE_PX = 5.0
_CURSOR_HALO_COLOR = "#102010"
_CURSOR_CORE_COLOR = "#ffffff"

# A ring lays down far less ink than the filled disc it replaces, so it needs
# more alpha than the old 200/70 pair to stay as legible.
_CURSOR_ALPHA = 235
_CURSOR_ALPHA_DIM = 110


def _clamp_to_canvas(x: float, y: float, w: int, h: int) -> tuple[float, float, bool]:
    """Pull a cursor position inside the canvas, reporting whether it had to.

    Off-canvas gaze no longer reaches here -- the cursor freezes at its last
    on-canvas position instead (see :meth:`TaskCanvas._cursor_draw_position`),
    so this is now a safety net rather than the main mechanism: it keeps a ring
    sitting exactly on the boundary drawn whole instead of half-clipped by the
    widget edge, and guards against rounding at 0.0/1.0.

    Inset by the cursor's own radius *plus half its stroke* so the clamped ring
    is drawn whole, not half-clipped by the boundary -- a stroke straddles the
    path it is drawn on, so radius alone would leave the outer half of the line
    outside the widget. The returned flag is what lets the caller show a
    clamped cursor differently from a real in-canvas one -- without it, "gaze
    at the very edge" and "gaze left the canvas" would be identical.
    """
    r = _CURSOR_RADIUS_PX + max(_CURSOR_STROKE_PX, _CURSOR_HALO_STROKE_PX) / 2.0
    cx = min(max(x, r), max(float(w) - r, r))
    cy = min(max(y, r), max(float(h) - r, r))
    return cx, cy, (cx != x or cy != y)


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
        self.layout_slots: list[tuple[float, float]] = []
        self.cursor_xy_norm: tuple[float, float] = (0.5, 0.5)
        self.cursor_valid: bool = False
        # Last position gaze was actually inside the canvas, which off-canvas
        # gaze freezes at (see _cursor_draw_position).
        self._last_on_canvas_xy: tuple[float, float] | None = None
        self.dwell_progress: float = 0.0
        self.selectable: bool = True
        self.show_cursor: bool = True
        self.show_progress_ring: bool = True
        self.show_instant_feedback: bool = True
        self.on_target: bool = False
        self._particles: list[tuple[float, float, float]] = []  # x_norm, y_norm, age

        # Scene (task-level layout description, ported from resources/diki --
        # see SPEC-diki-design-audit.md S3.1). Set once per task run via
        # AssessmentApp; default "single" matches pre-existing rendering
        # (just the active target + any generic layout_slots outlines) so
        # tasks not yet ported to a dedicated mode are unaffected.
        self.scene: dict = {"mode": "single"}
        self.active_slot: int = -1
        self._trail: list[tuple[float, float]] = []  # "moving" mode only

    # -- state updates from the app loop ----------------------------------

    def set_frame(
        self,
        target_xy_norm: tuple[float, float] | None,
        target_radius_px: float,
        cursor_xy_norm: tuple[float, float],
        cursor_valid: bool,
        dwell_progress: float,
        selectable: bool = True,
        layout_slots: list[tuple[float, float]] | None = None,
        on_target: bool = False,
        scene: dict | None = None,
        active_slot: int = -1,
    ) -> None:
        self.target_xy_norm = target_xy_norm
        self.target_radius_px = target_radius_px
        self.cursor_xy_norm = cursor_xy_norm
        self.cursor_valid = cursor_valid
        self.dwell_progress = dwell_progress
        self.selectable = selectable
        self.layout_slots = layout_slots or []
        self.on_target = on_target
        if scene is not None:
            self.scene = scene
        self.active_slot = active_slot

        # Fading motion-trail history for "moving" mode (ported from
        # resources/diki, SPEC-diki-design-audit.md S3.5/S4). Cleared
        # whenever the target isn't shown (e.g. between trials during ITI)
        # so the trail never bridges a teleport to the next trial's start.
        if self.scene.get("mode") == "moving" and target_xy_norm is not None:
            self._trail.append(target_xy_norm)
            # ~1.5s of history at 60Hz -- long enough to read as a path, short
            # enough not to overlap the target's own next lap on a small orbit.
            if len(self._trail) > 90:
                self._trail.pop(0)
        elif target_xy_norm is None and self._trail:
            self._trail.clear()

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

        mode = self.scene.get("mode", "single")
        if mode == "icons":
            self._draw_icon_scene(painter, w, h)
        elif mode == "grid":
            self._draw_grid_scene(painter, w, h)
        elif mode == "moving":
            self._draw_trail(painter, w, h)
        elif self.layout_slots:
            self._draw_layout_slots(painter, w, h)

        if self.target_xy_norm is not None:
            tx, ty = norm_to_px(*self.target_xy_norm, w, h)
            self._draw_target(painter, tx, ty)
            if self.show_instant_feedback and self.on_target:
                self._draw_instant_feedback(painter, tx, ty)
            if self.show_progress_ring and self.dwell_progress > 0:
                self._draw_progress_ring(painter, tx, ty)

        self._draw_particles(painter, w, h)

        if self.show_cursor:
            placed = self._cursor_draw_position()
            if placed is not None:
                (xn, yn), frozen = placed
                cx, cy = norm_to_px(xn, yn, w, h)
                ccx, ccy, _ = _clamp_to_canvas(cx, cy, w, h)
                self._draw_cursor(painter, ccx, ccy, dim=frozen or not self.cursor_valid)

        painter.end()

    def _draw_layout_slots(self, painter: QPainter, w: int, h: int) -> None:
        """Draw the unlit candidate positions of a multi-item task.

        click_grid's 3x3 cells and scanning's icon row are otherwise invisible
        between trials — only the single active target is ever painted — which
        made the two tasks (and click_static) look identical to an observer.
        This paints every other slot as a dim outline so the layout itself is
        visible, while the active target (painted afterwards) stays the only
        filled, bright shape.
        """
        r = self.target_radius_px
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setOpacity(0.25)
        for xn, yn in self.layout_slots:
            if self.target_xy_norm is not None and math.isclose(xn, self.target_xy_norm[0], abs_tol=1e-6) and math.isclose(
                yn, self.target_xy_norm[1], abs_tol=1e-6
            ):
                continue  # the active slot is drawn as the real target instead
            sx, sy = norm_to_px(xn, yn, w, h)
            painter.drawEllipse(QPointF(sx, sy), r, r)
        painter.setOpacity(1.0)

    def _draw_grid_scene(self, painter: QPainter, w: int, h: int) -> None:
        """Draw every grid cell as a real rounded-rect, not a dim circle.

        Ported from resources/diki (SPEC-diki-design-audit.md S3.3/S4) --
        click_grid mimics a communication board, so the whole board should be
        visible, not just the lit cell. The active cell is drawn afterwards
        by _draw_target on top; this only paints the (n-1) inactive cells.
        """
        cells = self.scene.get("cells") or []
        cw = float(self.scene.get("cell_w", 0.0)) * w
        ch = float(self.scene.get("cell_h", 0.0)) * h
        if not cells or cw <= 0 or ch <= 0:
            return

        pad = 0.06 * min(cw, ch)
        idle = QColor(self.theme.get("cursor_color", "#ffffff"))
        idle.setAlpha(38)
        for i, (xn, yn) in enumerate(cells):
            if i == self.active_slot:
                continue  # the active cell is drawn as the real target instead
            cx, cy = norm_to_px(xn, yn, w, h)
            rect = QRectF(cx - cw / 2 + pad, cy - ch / 2 + pad, cw - 2 * pad, ch - 2 * pad)
            painter.setPen(QPen(idle, 2))
            painter.setBrush(QColor(255, 255, 255, 16))
            painter.drawRoundedRect(rect, 14, 14)

    def _draw_trail(self, painter: QPainter, w: int, h: int) -> None:
        """Fading trail behind a moving target, so pursuit is visible.

        Ported from resources/diki (SPEC-diki-design-audit.md S3.5/S4) --
        distinguishes "tracked it" from "waited where it would arrive."
        History is accumulated in set_frame, not here.
        """
        if len(self._trail) < 2:
            return
        color = QColor(self.target_color)
        n = len(self._trail)
        painter.setPen(Qt.PenStyle.NoPen)
        for i, (xn, yn) in enumerate(self._trail[:-1]):
            frac = (i + 1) / n
            color.setAlpha(int(120 * frac))
            painter.setBrush(color)
            px, py = norm_to_px(xn, yn, w, h)
            radius = self.target_radius_px * 0.34 * frac
            painter.drawEllipse(QPointF(px, py), radius, radius)

    def _draw_icon_scene(self, painter: QPainter, w: int, h: int) -> None:
        """Draw the distractor field; the cued slot is drawn by _draw_target.

        Ported from resources/diki (SPEC-diki-design-audit.md S3.4/S4).
        """
        slots = self.scene.get("slots") or []
        shapes = self.scene.get("shapes") or []
        if not slots:
            return

        r = self.target_radius_px * 0.78
        distractor = QColor(self.theme.get("cursor_color", "#ffffff"))
        distractor.setAlpha(64)
        for i, (xn, yn) in enumerate(slots):
            if i == self.active_slot:
                continue  # the target itself is drawn on top, in colour
            cx, cy = norm_to_px(xn, yn, w, h)
            shape = shapes[i] if i < len(shapes) else _SHAPE_CIRCLE
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(distractor)
            painter.drawPath(self._shape_path(cx, cy, r, shape))

    def _shape_path(self, cx: float, cy: float, r: float, shape: int) -> QPainterPath:
        path = QPainterPath()
        if shape == _SHAPE_SQUARE:
            path.addRoundedRect(QRectF(cx - r, cy - r, 2 * r, 2 * r), r * 0.2, r * 0.2)
            return path
        if shape == _SHAPE_TRIANGLE:
            pts = [(0, -r), (r * 0.92, r * 0.7), (-r * 0.92, r * 0.7)]
        elif shape == _SHAPE_DIAMOND:
            pts = [(0, -r), (r, 0), (0, r), (-r, 0)]
        elif shape == _SHAPE_HEX:
            pts = [
                (r * math.cos(math.tau * k / 6), r * math.sin(math.tau * k / 6))
                for k in range(6)
            ]
        elif shape == _SHAPE_STAR:
            pts = []
            for k in range(10):
                rad = r if k % 2 == 0 else r * 0.45
                ang = math.tau * k / 10 - math.pi / 2
                pts.append((rad * math.cos(ang), rad * math.sin(ang)))
        else:  # circle
            path.addEllipse(QPointF(cx, cy), r, r)
            return path

        path.moveTo(cx + pts[0][0], cy + pts[0][1])
        for dx, dy in pts[1:]:
            path.lineTo(cx + dx, cy + dy)
        path.closeSubpath()
        return path

    def _draw_target(self, painter: QPainter, x: float, y: float) -> None:
        r = self.target_radius_px
        color = self.target_color if self.selectable else self.target_color.darker(180)
        grad = QRadialGradient(QPointF(x, y), r)
        grad.setColorAt(0.0, color.lighter(130))
        grad.setColorAt(1.0, color)
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)

        mode = self.scene.get("mode", "single")
        if mode == "icons" and self.active_slot >= 0:
            # Keep the target's silhouette so the child matches shape, not
            # just brightness/colour -- a plain circle would turn a search
            # task into pop-out. Ported from resources/diki.
            shapes = self.scene.get("shapes") or []
            shape = shapes[self.active_slot] if self.active_slot < len(shapes) else _SHAPE_CIRCLE
            painter.drawPath(self._shape_path(x, y, r * 0.78, shape))
        else:
            painter.drawEllipse(QPointF(x, y), r, r)

        if self.selectable:
            # bright "catch me now" outline during the selectable window.
            # Must be a freshly-constructed QPen, not painter.pen() mutated in
            # place -- the painter's current pen is NoPen (just used for the
            # gradient fill above), and changing a NoPen pen's color/width
            # does not change its style, so the outline silently never drew.
            painter.setPen(QPen(QColor("#ffffff"), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(x, y), r + 4, r + 4)

    def _draw_instant_feedback(self, painter: QPainter, x: float, y: float) -> None:
        """Immediate acknowledgment that gaze is on the target right now.

        SPEC-2026-09-02.md item 2: the only prior on-target feedback was the
        dwell progress ring, which needs threshold_ms (800ms default) of
        accumulated dwell before it's visibly obvious -- so "gaze lands on
        target" and "nothing happens for the better part of a second" looked
        identical. This is a full-brightness ring drawn the instant on_target
        is true, not gated by dwell progress at all.
        """
        r = self.target_radius_px + 10
        painter.setPen(QPen(QColor(self.theme.get("cursor_color", "#ffffff")), 5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(x, y), r, r)

    def _draw_progress_ring(self, painter: QPainter, x: float, y: float) -> None:
        r = self.target_radius_px + 16
        # Same NoPen-carryover fix as _draw_instant_feedback/_draw_target: a
        # fresh QPen, not painter.pen() mutated in place -- this arc was
        # silently never drawn before, which is very likely the real cause
        # behind SPEC-2026-09-02.md item 1's "toggling dwell.progress_ring
        # produced no visible change" observation.
        painter.setPen(QPen(QColor(self.theme.get("cursor_color", "#ffffff")), 8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        span = int(-360 * 16 * max(0.0, min(1.0, self.dwell_progress)))
        painter.drawArc(int(x - r), int(y - r), int(2 * r), int(2 * r), 90 * 16, span)

    def _cursor_draw_position(self) -> tuple[tuple[float, float], bool] | None:
        """Where to draw the gaze marker, and whether that position is frozen.

        Returns ``None`` when there is nothing to draw at all -- only before
        the very first on-canvas reading of a run, when no position has ever
        been established to freeze at.

        **Off-canvas gaze freezes the cursor in place** rather than tracking it
        to the nearest edge (SPEC-gaze-cursor-redesign.md S10, revising S4.2).
        The earlier design clamped to the edge and faded by distance; the user
        asked for parity with Gazepoint Control instead, where looking away
        simply stops the marker. That makes "looking away" and "tracking lost"
        visually identical, which is a deliberate, accepted consequence --
        Gazepoint Control does not distinguish them either, and it removes the
        distance threshold this otherwise needed.

        Hit-testing is untouched by any of this. ``BaseTask`` still sees the
        true, unfrozen, possibly out-of-range position, so freezing can never
        cause a selection the child did not actually make -- freezing is the
        renderer's decision alone (the same separation S6 of
        SPEC-gui-audit-2026-09-10.md established for the clamp).
        """
        xy = self.cursor_xy_norm
        if outside_distance(*xy) > 0.0:
            if self._last_on_canvas_xy is None:
                return None
            return self._last_on_canvas_xy, True
        self._last_on_canvas_xy = xy
        return xy, False

    def _draw_cursor(self, painter: QPainter, x: float, y: float, dim: bool = False) -> None:
        """Draw the gaze marker: a small hollow ring with a contrasting fringe.

        Two states, deliberately only two (S10): a live on-canvas reading at
        full strength, and a *frozen* one -- dimmed -- covering both tracking
        loss and gaze that has left the canvas.

        Drawn as two concentric strokes at the same radius, wider first: the
        halo's extra width survives on both sides of the narrower core, so the
        marker carries its own contrast onto any backdrop instead of depending
        on the theme it happens to be drawn over.
        """
        alpha = _CURSOR_ALPHA_DIM if (dim or not self.cursor_valid) else _CURSOR_ALPHA
        centre = QPointF(x, y)
        # Hollow: stroke only, no fill, so the target underneath stays visible.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        halo = QColor(_CURSOR_HALO_COLOR)
        halo.setAlpha(alpha)
        painter.setPen(QPen(halo, _CURSOR_HALO_STROKE_PX))
        painter.drawEllipse(centre, _CURSOR_RADIUS_PX, _CURSOR_RADIUS_PX)
        core = QColor(_CURSOR_CORE_COLOR)
        core.setAlpha(alpha)
        painter.setPen(QPen(core, _CURSOR_STROKE_PX))
        painter.drawEllipse(centre, _CURSOR_RADIUS_PX, _CURSOR_RADIUS_PX)

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
