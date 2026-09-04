"""YAML configuration loading and merging.

The effective config for a run is ``default.yaml`` deep-merged with a task file
(``configs/tasks/<id>.yaml``) and, optionally, CLI overrides. Kept dependency-
light (pyyaml only) so therapists can edit plain YAML (plan US-02).
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

CONFIG_ROOT = Path(__file__).resolve().parents[2] / "configs"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` onto ``base``, returning a new dict.

    Public (not just an implementation detail of :func:`load_task_config`)
    because the pre-launch task settings dialog (SPEC-live-settings-panel.md
    section 5.3) reuses this exact merge to apply structural overrides onto
    ``config["task"]`` -- the same mechanism a task YAML's own ``overrides:``
    block already goes through, just fed a dict built from dialog widgets
    instead of parsed from YAML.
    """
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


_deep_merge = deep_merge  # backward-compatible alias for any existing internal callers


def load_yaml(path: str | Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data or {}


def load_default(config_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(config_root) if config_root else CONFIG_ROOT
    return load_yaml(root / "default.yaml")


def load_task_config(
    task_id: str, config_root: str | Path | None = None
) -> dict[str, Any]:
    """Return the effective config for a task.

    The task file's contents are exposed under the ``task`` key (target size,
    trials, timeout, ...). A task file may ALSO carry a top-level ``overrides:``
    block whose contents are deep-merged over the global default sections
    (``dwell``, ``app``, ``input``, ``recording``); this is the supported way for
    a therapist to, e.g., raise the dwell threshold for one task without editing
    ``default.yaml`` (plan US-02).
    """
    root = Path(config_root) if config_root else CONFIG_ROOT
    base = load_default(root)
    task_path = root / "tasks" / f"{task_id}.yaml"
    if not task_path.exists():
        raise FileNotFoundError(f"No task config for '{task_id}': {task_path}")
    task = load_yaml(task_path)

    overrides = task.get("overrides", {})
    merged = _deep_merge(base, overrides) if overrides else deepcopy(base)
    merged["task"] = task
    return merged


def load_theme(name: str, config_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(config_root) if config_root else CONFIG_ROOT
    path = root / "themes" / f"{name}.yaml"
    if not path.exists():
        return {}
    return load_yaml(path)
