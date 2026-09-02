"""Follow-and-click task (plan section 5.5).

The target travels along a path; the child tracks it and selects it. Reaction
time and gaze-to-target distance are the metrics of interest. The target's live
position is computed per frame via :meth:`target_position`.
"""

from __future__ import annotations

import math

from .base_task import BaseTask, TargetSpec


class FollowMovingTask(BaseTask):
    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        n_trials = int(cfg.get("trials", 12))
        radius = float(cfg.get("target", {}).get("radius_px", 80))
        motion = cfg.get("motion", {})
        self.path = str(motion.get("path", "horizontal"))
        self.speed = float(motion.get("speed_frac_per_s", 0.20))
        self.select_window_ns = int(float(motion.get("select_window_ms", 2500)) * 1e6)

        # Per-trial selection window: the target is only selectable (and
        # highlighted) for select_window_ms starting at a randomized offset, so
        # the child must actively track and catch it rather than park on it.
        latest_start = max(0, self.timeout_ns - self.select_window_ns)
        self.select_windows: list[tuple[int, int]] = []

        targets: list[TargetSpec] = []
        for i in range(n_trials):
            y = self.rng.uniform(0.25, 0.75)
            start = self.rng.randint(int(0.15 * self.timeout_ns), latest_start) if latest_start > 0 else 0
            self.select_windows.append((start, start + self.select_window_ns))
            targets.append(TargetSpec(index=i, x_norm=0.1, y_norm=y, radius_px=radius))
        return targets

    def is_selectable(self, target: TargetSpec, elapsed_ns: int) -> bool:
        start, end = self.select_windows[target.index]
        return start <= elapsed_ns <= end

    def target_position(self, target: TargetSpec, elapsed_ns: int) -> tuple[float, float]:
        elapsed_s = elapsed_ns / 1e9
        if self.path == "circular":
            cx, cy, r = 0.5, 0.5, 0.3
            omega = 2 * math.pi * self.speed
            return (
                cx + r * math.cos(omega * elapsed_s),
                cy + r * math.sin(omega * elapsed_s),
            )
        # horizontal: bounce between 0.1 and 0.9
        span = 0.8
        raw = 0.1 + (self.speed * elapsed_s) % (2 * span)
        x = raw if raw <= 0.9 else (1.8 - raw)  # triangle wave
        return x, target.y_norm
