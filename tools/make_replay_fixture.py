"""Generate a synthetic gaze replay fixture (``.jsonl``).

Simulates a cooperative subject who visits each candidate target position in
turn and dwells on it long enough to trigger a selection. Coordinates are
normalized (0-1). Deterministic (no RNG seeding needed beyond the fixed jitter
pattern) so the committed fixture is reproducible.

Usage::

    python tools/make_replay_fixture.py tests/fixtures/gaze_replay.jsonl
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

FPS = 60
DT_NS = int(1e9 / FPS)

# The 8 candidate positions used by click_static.yaml (kept in sync manually).
POSITIONS = [
    (0.15, 0.15),
    (0.50, 0.15),
    (0.85, 0.15),
    (0.15, 0.50),
    (0.85, 0.50),
    (0.15, 0.85),
    (0.50, 0.85),
    (0.85, 0.85),
]

HOLD_S = 1.1          # dwell hold per position (> dwell threshold 0.8 s)
TRANSITION_FRAMES = 8  # invalid/blink frames between positions


def build_records() -> list[dict]:
    records: list[dict] = []
    frame = 0
    fix_id = 0
    for (x, y) in POSITIONS:
        fix_id += 1
        n_hold = int(HOLD_S * FPS)
        for i in range(n_hold):
            # small physiological jitter (~0.3% of screen)
            jx = 0.003 * math.sin(i * 0.7)
            jy = 0.003 * math.cos(i * 0.5)
            records.append(
                {
                    "t_ns": frame * DT_NS,
                    "x": round(x + jx, 5),
                    "y": round(y + jy, 5),
                    "valid": True,
                    "fixation_id": fix_id,
                    "fix_duration_s": round(i / FPS, 3),
                }
            )
            frame += 1
        # saccade / blink: invalid samples so dwell resets before next target
        for _ in range(TRANSITION_FRAMES):
            records.append(
                {"t_ns": frame * DT_NS, "x": 0.5, "y": 0.5, "valid": False}
            )
            frame += 1
    return records


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else Path("tests/fixtures/gaze_replay.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    records = build_records()
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    print(f"Wrote {len(records)} samples -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
