"""Analyze a recorded session: RT summary + gaze heatmap.

Reads a session folder's ``trials.csv`` and ``gaze_stream.csv`` and prints a
reaction-time / hit-rate summary. If matplotlib is available it also writes
``rt_hist.png`` and ``gaze_heatmap.png`` into the session folder; otherwise it
falls back to a numpy-based text heatmap so the script is always useful.

Usage::

    python analysis/analyze_session.py sessions/2026-07-15_P001_click_static
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script (add repo root to path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.exporter import load_trials_rows, summarize  # noqa: E402


def _reaction_times_ms(session_dir: Path) -> list[float]:
    rows = load_trials_rows(session_dir)
    return [float(r["reaction_time_ms"]) for r in rows if r.get("reaction_time_ms")]


def _gaze_xy(session_dir: Path) -> tuple[list[float], list[float]]:
    import csv

    xs: list[float] = []
    ys: list[float] = []
    path = session_dir / "gaze_stream.csv"
    if not path.exists():
        return xs, ys
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("valid") == "1":
                xs.append(float(row["x"]))
                ys.append(float(row["y"]))
    return xs, ys


def _write_plots(session_dir: Path, rts: list[float], xs: list[float], ys: list[float]) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    if rts:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.hist(rts, bins=20, color="#4c78a8", edgecolor="white")
        ax.set_xlabel("Reaction time (ms)")
        ax.set_ylabel("Trials")
        ax.set_title("Reaction time distribution")
        fig.tight_layout()
        fig.savefig(session_dir / "rt_hist.png", dpi=120)
        plt.close(fig)

    if xs and ys:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.hist2d(xs, ys, bins=40, range=[[0, 1], [0, 1]], cmap="magma")
        ax.invert_yaxis()  # screen origin is top-left
        ax.set_title("Gaze heatmap (normalized screen)")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        fig.tight_layout()
        fig.savefig(session_dir / "gaze_heatmap.png", dpi=120)
        plt.close(fig)
    return True


def _text_heatmap(xs: list[float], ys: list[float], bins: int = 20) -> str:
    import numpy as np

    if not xs:
        return "(no valid gaze samples)"
    hist, _, _ = np.histogram2d(ys, xs, bins=bins, range=[[0, 1], [0, 1]])
    ramp = " .:-=+*#%@"
    hi = hist.max() or 1
    lines = []
    for row in hist:
        lines.append("".join(ramp[min(len(ramp) - 1, int(v / hi * (len(ramp) - 1)))] for v in row))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    session_dir = Path(argv[1])
    summary = summarize(session_dir)
    print(f"Session: {session_dir}")
    print(f"  trials     : {summary['n_trials']}")
    print(f"  hits       : {summary['n_hits']}  (hit rate {summary['hit_rate']})")
    print(f"  timeouts   : {summary['n_timeouts']}")
    print(f"  mean RT ms : {summary['mean_reaction_time_ms']}")

    rts = _reaction_times_ms(session_dir)
    xs, ys = _gaze_xy(session_dir)
    if _write_plots(session_dir, rts, xs, ys):
        print(f"  plots      : {session_dir / 'rt_hist.png'}, {session_dir / 'gaze_heatmap.png'}")
    else:
        print("  matplotlib not installed — text gaze heatmap:")
        print(_text_heatmap(xs, ys))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
