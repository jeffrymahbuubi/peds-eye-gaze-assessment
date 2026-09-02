"""Scanning selection task (plan section 5.5).

Several icons are arranged on screen; one lights up as the target and the child
selects it. Distractor icons are visual only (rendered by the GUI); the metric
of interest is reaction time and wrong-selection count (tracked as attempts).
"""

from __future__ import annotations

from .base_task import BaseTask, TargetSpec


class ScanningTask(BaseTask):
    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        layout = cfg.get("layout", {})
        n_icons = int(layout.get("n_icons", 4))
        radius = float(layout.get("radius_px", 80))
        n_trials = int(cfg.get("trials", 16))

        # Evenly spaced icon slots on a horizontal row.
        slots = [
            ((i + 0.5) / n_icons, 0.5) for i in range(n_icons)
        ]
        self.icon_slots = slots  # exposed for the GUI to draw distractors

        targets: list[TargetSpec] = []
        for i in range(n_trials):
            x, y = self.rng.choice(slots)
            targets.append(TargetSpec(index=i, x_norm=x, y_norm=y, radius_px=radius))
        return targets
