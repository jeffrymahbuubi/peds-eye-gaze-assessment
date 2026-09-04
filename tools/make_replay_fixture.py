"""Generate a synthetic gaze replay fixture (``.jsonl``) for any task.

Simulates a cooperative subject. For the three static-target tasks
(click_static, click_grid, scanning) that means visiting each candidate
position in turn and dwelling on it long enough to trigger a selection.
For follow_moving (a moving target, not a fixed position) it means
continuously tracking the target's own live path/speed formula instead.

Positions and motion are read from the *real* task classes
(``src.tasks.*``/``src.engine.task_runner.build_task``), not hand-duplicated
here -- the original click_static-only version of this tool hardcoded its
position list and depended on a human keeping it "in sync manually" with
click_static.yaml (a real staleness risk flagged in its own comments). This
version can never drift, since it always asks the actual task class for its
current layout.

Usage::

    python tools/make_replay_fixture.py                                  # click_static -> tests/fixtures/gaze_replay_click_static.jsonl
    python tools/make_replay_fixture.py --task click_grid                # -> tests/fixtures/gaze_replay_click_grid.jsonl
    python tools/make_replay_fixture.py custom.jsonl --task scanning     # scanning, custom path

Caveat for follow_moving specifically: the live GUI paces a replay fixture
on its own independent wall-clock loop (``GazepointClient._run_replay``),
which is not synchronized with any specific trial's own elapsed-in-trial
clock. A moving target can't be guaranteed to be "caught" the way a static
one can just by being in the right place eventually -- this fixture tracks
the target's real motion formula continuously so hits are *likely* over a
multi-trial session, not guaranteed every trial. Good enough for the
settings-panel's own live-effect demo; not a claim of deterministic hits.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.config import load_task_config  # noqa: E402
from src.engine.task_runner import TASK_REGISTRY, build_task  # noqa: E402
from src.tasks.base_task import TargetSpec  # noqa: E402

FPS = 60
DT_NS = int(1e9 / FPS)

HOLD_S = 1.1  # dwell hold per position (> the default dwell threshold of 0.8s)
TRANSITION_FRAMES = 8  # invalid/blink frames between positions


def positions_for_task(task_id: str) -> list[tuple[float, float]]:
    """Distinct candidate target positions for a static-target task.

    Built from the real task class (``layout_slots`` for the multi-item
    tasks; the raw ``target.positions`` config for click_static, which has
    no ``layout_slots``) rather than re-derived by hand, so this can never
    fall out of sync with the actual task code.
    """
    cfg = load_task_config(task_id)
    task = build_task(task_id, cfg, seed=0)
    if task.layout_slots:
        return list(task.layout_slots)
    positions = cfg["task"].get("target", {}).get("positions") or [[0.5, 0.5]]
    return [(float(x), float(y)) for x, y in positions]


def build_records_positions(
    positions: list[tuple[float, float]], hold_s: float = HOLD_S, transition_frames: int = TRANSITION_FRAMES
) -> list[dict]:
    records: list[dict] = []
    frame = 0
    fix_id = 0
    for (x, y) in positions:
        fix_id += 1
        n_hold = int(hold_s * FPS)
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
        for _ in range(transition_frames):
            records.append({"t_ns": frame * DT_NS, "x": 0.5, "y": 0.5, "valid": False})
            frame += 1
    return records


def build_records_follow_moving(task, cycle_s: float) -> list[dict]:
    """Continuously track the target's own motion formula for ``cycle_s``
    seconds (one loop of the fixture), rather than dwelling on fixed points.
    """
    records: list[dict] = []
    n_frames = int(cycle_s * FPS)
    # target_position() only reads y_norm (horizontal path) / ignores it
    # entirely (circular path) -- radius_px is unused by target_position, so
    # any TargetSpec with a representative y works as the tracking anchor.
    anchor = TargetSpec(index=0, x_norm=0.5, y_norm=0.5, radius_px=90.0)
    for i in range(n_frames):
        elapsed_ns = i * DT_NS
        x, y = task.target_position(anchor, elapsed_ns)
        records.append(
            {
                "t_ns": i * DT_NS,
                "x": round(x, 5),
                "y": round(y, 5),
                "valid": True,
                "fixation_id": 1,
                "fix_duration_s": round(i / FPS, 3),
            }
        )
    return records


def default_out_path(task_id: str) -> Path:
    return Path(f"tests/fixtures/gaze_replay_{task_id}.jsonl")


def build_records(task_id: str) -> list[dict]:
    if task_id == "follow_moving":
        cfg = load_task_config(task_id)
        task = build_task(task_id, cfg, seed=0)
        cycle_s = task.timeout_ns / 1e9
        return build_records_follow_moving(task, cycle_s)
    return build_records_positions(positions_for_task(task_id))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", nargs="?", help="Output .jsonl path (default depends on --task)")
    parser.add_argument("--task", default="click_static", choices=sorted(TASK_REGISTRY))
    args = parser.parse_args(argv[1:])

    out = Path(args.out) if args.out else default_out_path(args.task)
    out.parent.mkdir(parents=True, exist_ok=True)
    records = build_records(args.task)
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    print(f"[{args.task}] wrote {len(records)} samples -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
