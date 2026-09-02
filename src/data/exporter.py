"""Read a recorded session back into analysis-friendly structures.

Kept separate from :mod:`recorder` so analysis notebooks can depend on it
without pulling in write-side logic. ``pandas`` is imported lazily so the module
imports cleanly in environments where it is not installed.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_metadata(session_dir: str | Path) -> dict[str, Any]:
    path = Path(session_dir) / "metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_events(session_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(session_dir) / "events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def load_trials_rows(session_dir: str | Path) -> list[dict[str, str]]:
    """Load ``trials.csv`` as a list of dict rows (no pandas dependency)."""
    path = Path(session_dir) / "trials.csv"
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_trials_df(session_dir: str | Path):
    """Load ``trials.csv`` as a pandas DataFrame (requires pandas)."""
    import pandas as pd  # local import: optional dependency

    return pd.read_csv(Path(session_dir) / "trials.csv")


def load_gaze_df(session_dir: str | Path):
    """Load ``gaze_stream.csv`` as a pandas DataFrame (requires pandas)."""
    import pandas as pd

    return pd.read_csv(Path(session_dir) / "gaze_stream.csv")


def summarize(session_dir: str | Path) -> dict[str, Any]:
    """Compute a small headline summary from ``trials.csv`` without pandas."""
    rows = load_trials_rows(session_dir)
    n = len(rows)
    hits = sum(1 for r in rows if r.get("is_hit") == "1")
    timeouts = sum(1 for r in rows if r.get("is_timeout") == "1")
    rts = [float(r["reaction_time_ms"]) for r in rows if r.get("reaction_time_ms")]
    mean_rt = sum(rts) / len(rts) if rts else None
    return {
        "n_trials": n,
        "n_hits": hits,
        "n_timeouts": timeouts,
        "hit_rate": (hits / n) if n else None,
        "mean_reaction_time_ms": round(mean_rt, 2) if mean_rt is not None else None,
    }
