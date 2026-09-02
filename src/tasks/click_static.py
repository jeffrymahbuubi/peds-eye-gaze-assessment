"""Static single-target click task (plan section 5.5).

A single target appears at one of a set of candidate positions; the child
selects it by dwell (or switch). Reaction time and hit rate are the primary
metrics.
"""

from __future__ import annotations

from .base_task import BaseTask, TargetSpec


class ClickStaticTask(BaseTask):
    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        n_trials = int(cfg.get("trials", 32))
        target_cfg = cfg.get("target", {})
        radius = float(target_cfg.get("radius_px", 90))
        positions = target_cfg.get("positions") or [[0.5, 0.5]]

        targets: list[TargetSpec] = []
        for i in range(n_trials):
            pos = self.rng.choice(positions)
            targets.append(
                TargetSpec(index=i, x_norm=float(pos[0]), y_norm=float(pos[1]), radius_px=radius)
            )
        return targets
