"""Grid click task (Compass-style comparison, plan section 5.5).

Cells of an R x C grid light up one at a time in randomized order; the child
selects the lit cell.
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

        self.layout_slots = cells  # exposed for the GUI to draw the unlit grid cells

        # Randomized order, cycling through all cells if n_trials > len(cells).
        order: list[tuple[float, float]] = []
        while len(order) < n_trials:
            shuffled = cells[:]
            self.rng.shuffle(shuffled)
            order.extend(shuffled)
        order = order[:n_trials]

        return [
            TargetSpec(index=i, x_norm=x, y_norm=y, radius_px=radius)
            for i, (x, y) in enumerate(order)
        ]
