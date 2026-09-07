"""Grid click task (Compass-style comparison, plan section 5.5).

Cells of an R x C grid light up one at a time in randomized order; the child
selects the lit cell.

**Real grid rendering ported from ``resources/diki``** (SPEC-diki-design-audit.md
S3.3/S4). Previously the GUI only ever drew every cell as a dim, generic
outline circle (the same fallback ``TaskCanvas._draw_layout_slots`` uses for
any multi-item task); the board is the whole point of this task -- it mimics
a communication board -- so cells are now drawn as real rounded-rect grid
cells via ``scene_spec()``'s new ``"grid"`` mode.
"""

from __future__ import annotations

from .base_task import BaseTask, TargetSpec


class ClickGridTask(BaseTask):
    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        grid = cfg.get("grid", {})
        rows = int(grid.get("rows", 3))
        cols = int(grid.get("cols", 3))
        margin = float(grid.get("margin_frac", 0.12))
        radius = float(cfg.get("target", {}).get("radius_px", 80))
        n_trials = int(cfg.get("trials", rows * cols))

        cells: list[tuple[float, float]] = []
        span = 1.0 - 2 * margin
        for r in range(rows):
            for c in range(cols):
                x = margin + (span * (c + 0.5) / cols)
                y = margin + (span * (r + 0.5) / rows)
                cells.append((x, y))

        # Kept so the canvas can draw the whole grid (scene_spec's "grid"
        # mode) and for tools/make_replay_fixture.py + the existing
        # layout_slots pytest coverage.
        self.rows = rows
        self.cols = cols
        self.cells = cells
        self.cell_w = span / cols
        self.cell_h = span / rows
        self.layout_slots = cells

        # Randomized order, cycling through all cells if n_trials > len(cells).
        order: list[int] = []
        while len(order) < n_trials:
            shuffled = list(range(len(cells)))
            self.rng.shuffle(shuffled)
            order.extend(shuffled)
        order = order[:n_trials]

        return [
            TargetSpec(
                index=i,
                x_norm=cells[slot][0],
                y_norm=cells[slot][1],
                radius_px=radius,
                slot_index=slot,
            )
            for i, slot in enumerate(order)
        ]

    def scene_spec(self) -> dict:
        return {
            "mode": "grid",
            "rows": self.rows,
            "cols": self.cols,
            "cells": list(self.cells),
            "cell_w": self.cell_w,
            "cell_h": self.cell_h,
        }
