"""Per-machine local state (e.g. the last tracker host that connected OK).

SPEC-ui-setup-task-selection.md S3.1.3: the Control Address varies per
machine (this desktop's real device is a fixed LAN IP; another machine might
run the fake server on 127.0.0.1), and there is no auto-discovery protocol to
fall back on. Rather than editing the checked-in ``configs/default.yaml``
(shared, and already skip-worktree'd for a different reason -- see
SPEC-ui-setup-task-selection.md S3.1.3's own note), the last-known-good
host/port is kept in a small gitignored file next to it. Kept Qt-free so it
can be unit tested without importing PySide6.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import CONFIG_ROOT

LOCAL_STATE_PATH = CONFIG_ROOT / "local_state.json"


def load_local_state(path: str | Path | None = None) -> dict[str, Any]:
    """Return the saved local state, or ``{}`` if absent/unreadable.

    Unreadable (missing, empty, malformed JSON) is treated the same as
    absent -- a fresh machine with no history -- rather than raising, since
    this file is a convenience, not a source of truth the app depends on.
    """
    p = Path(path) if path is not None else LOCAL_STATE_PATH
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_local_state(update: dict[str, Any], path: str | Path | None = None) -> None:
    """Merge ``update`` into the saved local state and write it back."""
    p = Path(path) if path is not None else LOCAL_STATE_PATH
    state = load_local_state(p)
    state.update(update)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
