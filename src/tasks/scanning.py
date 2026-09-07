"""Scanning selection task (plan section 5.5).

Several icons are arranged on screen; one lights up as the target and the child
selects it. Distractor icons are visual only (rendered by the GUI); the metric
of interest is reaction time and wrong-selection count (tracked as attempts).

**Arrangement + shapes ported from ``resources/diki`` (SPEC-diki-design-audit.md
S3.4).** The original version here only ever laid icons out on a single
horizontal row -- not real visual search, since the child never has to look up
or down. ``layout.arrangement`` now supports ``row`` (kept for compatibility),
``ring``, and ``grid`` (new default): a genuine 2D field the child has to
actually scan. Icons are also now assigned one of 6 distinct *shapes*, not just
positions, rendered by ``TaskCanvas`` -- distinguishing by form (not just
brightness/colour) is what makes this a search task rather than a pop-out task.
"""

from __future__ import annotations

import math

from .base_task import BaseTask, TargetSpec


class ScanningTask(BaseTask):
    def build_targets(self) -> list[TargetSpec]:
        cfg = self.task_cfg
        layout = cfg.get("layout", {})
        n_icons = int(layout.get("n_icons", 4))
        radius = float(layout.get("radius_px", 80))
        arrangement = str(layout.get("arrangement", "grid"))
        margin = float(layout.get("margin_frac", 0.14))
        n_trials = int(cfg.get("trials", 16))

        self.icon_slots = self._layout_slots(n_icons, arrangement, margin)
        self.icon_shapes = [i % 6 for i in range(len(self.icon_slots))]
        # Kept for the fixture-generation tool and the existing GUI
        # dim-outline fallback -- see BaseTask.layout_slots's own docstring.
        # scanning now draws real shapes instead (scene_spec's "icons" mode),
        # but this alias stays so nothing that reads task.layout_slots breaks.
        self.layout_slots = list(self.icon_slots)

        targets: list[TargetSpec] = []
        for i in range(n_trials):
            slot = self.rng.randrange(len(self.icon_slots))
            x, y = self.icon_slots[slot]
            targets.append(
                TargetSpec(index=i, x_norm=x, y_norm=y, radius_px=radius, slot_index=slot)
            )
        return targets

    def _layout_slots(
        self, n_icons: int, arrangement: str, margin: float
    ) -> list[tuple[float, float]]:
        span = 1.0 - 2 * margin
        if arrangement == "row":
            return [(margin + span * (i + 0.5) / n_icons, 0.5) for i in range(n_icons)]
        if arrangement == "ring":
            cx, cy, r = 0.5, 0.5, 0.32
            return [
                (
                    cx + r * math.cos(2 * math.pi * i / n_icons - math.pi / 2),
                    cy + r * math.sin(2 * math.pi * i / n_icons - math.pi / 2),
                )
                for i in range(n_icons)
            ]
        # grid (default): favour more columns than rows, because the screen is
        # wider than it is tall -- round() here would give 6 icons a 2x3
        # layout, leaving large empty margins left and right.
        cols = max(1, math.ceil(n_icons ** 0.5))
        rows = max(1, -(-n_icons // cols))  # ceil division
        slots: list[tuple[float, float]] = []
        for i in range(n_icons):
            r, c = divmod(i, cols)
            slots.append(
                (
                    margin + span * (c + 0.5) / cols,
                    margin + span * (r + 0.5) / rows,
                )
            )
        return slots

    def scene_spec(self) -> dict:
        return {
            "mode": "icons",
            "slots": list(self.icon_slots),
            "shapes": list(self.icon_shapes),
        }
