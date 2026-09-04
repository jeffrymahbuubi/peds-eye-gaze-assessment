"""Declarative registries for the live settings panel and pre-launch task
settings dialog (SPEC-live-settings-panel.md section 5.1).

Kept dependency-light (no PySide6 import) so it can be unit-tested headlessly,
matching this project's existing convention of not testing Qt widgets
directly (see tests/test_theme_sounds.py).

Two registries, matching the SPEC's two buckets:

- ``LIVE_SETTINGS``: cheap, per-frame-read fields that are safe to change
  while a task is running (dwell/feedback toggles, smoothing, task timing).
- ``STRUCTURAL_SETTINGS``: fields baked once into a task's trial list at
  ``build_targets()`` time (grid size, radius, trial count, ...) -- these are
  only offered in the pre-launch dialog, never mid-task.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LiveSetting:
    key: str  # dotted key identifying this field (matches AssessmentApp's dispatch table)
    label: str
    group: str  # "basic" | "advanced"
    kind: str  # "bool" | "int" | "float"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    applies_to: tuple[str, ...] = ()  # empty = every task

    def applies(self, task_id: str) -> bool:
        return not self.applies_to or task_id in self.applies_to


@dataclass(frozen=True, slots=True)
class StructuralSetting:
    key: str  # dotted path within the task config's "task" block, e.g. "target.radius_px"
    label: str
    kind: str  # "int" | "float"
    min: float
    max: float
    step: float
    applies_to: tuple[str, ...] = ()

    def applies(self, task_id: str) -> bool:
        return not self.applies_to or task_id in self.applies_to


# -- live, mid-task settings (SPEC section 5.1) -----------------------------

LIVE_SETTINGS: list[LiveSetting] = [
    LiveSetting("dwell.threshold_ms", "Dwell threshold (ms)", "basic", "int", 300, 2000, 50),
    LiveSetting("dwell.visual_cursor", "Show gaze cursor", "basic", "bool"),
    LiveSetting("dwell.progress_ring", "Show dwell progress ring", "basic", "bool"),
    LiveSetting("dwell.instant_feedback", "Show instant on-target ring", "basic", "bool"),
    LiveSetting("dwell.refractory_ms", "Refractory period (ms)", "advanced", "int", 0, 2000, 50),
    LiveSetting("dwell.jitter_tolerance_px", "Jitter tolerance (px)", "advanced", "int", 0, 100, 5),
    LiveSetting("dwell.smoothing.enabled", "Gaze smoothing enabled", "advanced", "bool"),
    LiveSetting("dwell.smoothing.alpha", "Smoothing alpha", "advanced", "float", 0.05, 1.0, 0.05),
    LiveSetting("task.timeout_ms", "Trial timeout (ms)", "advanced", "int", 1000, 20000, 500),
    LiveSetting(
        "task.inter_trial_interval_ms", "Inter-trial interval (ms)", "advanced", "int", 0, 3000, 100
    ),
    LiveSetting(
        "motion.speed_frac_per_s",
        "Target speed (frac/s)",
        "advanced",
        "float",
        0.05,
        1.0,
        0.05,
        applies_to=("follow_moving",),
    ),
]


# -- structural, pre-launch-only settings (SPEC section 4) ------------------

STRUCTURAL_SETTINGS: list[StructuralSetting] = [
    StructuralSetting("trials", "Number of trials", "int", 1, 60, 1),
    StructuralSetting(
        "target.radius_px",
        "Target radius (px)",
        "int",
        30,
        200,
        5,
        applies_to=("click_static", "click_grid", "follow_moving"),
    ),
    StructuralSetting(
        "layout.radius_px", "Icon radius (px)", "int", 30, 200, 5, applies_to=("scanning",)
    ),
    StructuralSetting("grid.rows", "Grid rows", "int", 2, 6, 1, applies_to=("click_grid",)),
    StructuralSetting("grid.cols", "Grid cols", "int", 2, 6, 1, applies_to=("click_grid",)),
    StructuralSetting(
        "layout.n_icons", "Number of icons", "int", 2, 8, 1, applies_to=("scanning",)
    ),
    StructuralSetting(
        "motion.select_window_ms",
        "Selection window (ms)",
        "int",
        500,
        5000,
        100,
        applies_to=("follow_moving",),
    ),
]


def live_settings_for_task(task_id: str) -> list[LiveSetting]:
    return [s for s in LIVE_SETTINGS if s.applies(task_id)]


def structural_settings_for_task(task_id: str) -> list[StructuralSetting]:
    return [s for s in STRUCTURAL_SETTINGS if s.applies(task_id)]


# -- nested dict helpers ------------------------------------------------------

_DWELL_DEFAULTS = {
    "threshold_ms": 800,
    "refractory_ms": 500,
    "jitter_tolerance_px": 40,
    "visual_cursor": True,
    "progress_ring": True,
    "instant_feedback": True,
}
_SMOOTHING_DEFAULTS = {"enabled": True, "alpha": 0.35}


def get_nested(d: dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    node: Any = d
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_nested(d: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    node = d
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def initial_live_values(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve each LIVE_SETTINGS default from the merged run config.

    ``dwell.*``/``dwell.smoothing.*`` come straight from the config's own
    ``dwell`` block; ``task.*`` come from the task's own YAML (already merged
    into ``config["task"]``); ``motion.*`` (follow_moving only) comes from the
    task config's ``motion`` block.
    """
    dwell_cfg = config.get("dwell", {})
    smoothing_cfg = dwell_cfg.get("smoothing", {})
    task_cfg = config.get("task", {})
    motion_cfg = task_cfg.get("motion", {})
    return {
        "dwell.threshold_ms": dwell_cfg.get("threshold_ms", _DWELL_DEFAULTS["threshold_ms"]),
        "dwell.visual_cursor": dwell_cfg.get("visual_cursor", _DWELL_DEFAULTS["visual_cursor"]),
        "dwell.progress_ring": dwell_cfg.get("progress_ring", _DWELL_DEFAULTS["progress_ring"]),
        "dwell.instant_feedback": dwell_cfg.get(
            "instant_feedback", _DWELL_DEFAULTS["instant_feedback"]
        ),
        "dwell.refractory_ms": dwell_cfg.get("refractory_ms", _DWELL_DEFAULTS["refractory_ms"]),
        "dwell.jitter_tolerance_px": dwell_cfg.get(
            "jitter_tolerance_px", _DWELL_DEFAULTS["jitter_tolerance_px"]
        ),
        "dwell.smoothing.enabled": smoothing_cfg.get("enabled", _SMOOTHING_DEFAULTS["enabled"]),
        "dwell.smoothing.alpha": smoothing_cfg.get("alpha", _SMOOTHING_DEFAULTS["alpha"]),
        "task.timeout_ms": task_cfg.get("timeout_ms", 8000),
        "task.inter_trial_interval_ms": task_cfg.get("inter_trial_interval_ms", 800),
        "motion.speed_frac_per_s": motion_cfg.get("speed_frac_per_s", 0.20),
    }


def initial_structural_values(task_id: str, config: dict[str, Any]) -> dict[str, Any]:
    task_cfg = config.get("task", {})
    return {
        s.key: get_nested(task_cfg, s.key, s.min)
        for s in structural_settings_for_task(task_id)
    }
