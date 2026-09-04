"""Command-line entry point.

Headless replay demo (no tracker, no GUI required)::

    python -m src.main --task click_static --replay tests/fixtures/gaze_replay_click_static.jsonl

Live GUI (requires the ``gui`` extra and a Gazepoint tracker or replay)::

    python -m src.main --task click_static --gui
"""

from __future__ import annotations

import argparse
import sys

from .engine.task_runner import TASK_REGISTRY, run_headless_replay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pediatric eye-gaze assessment tool")
    parser.add_argument(
        "--task",
        default="click_static",
        choices=sorted(TASK_REGISTRY),
        help="Task to run.",
    )
    parser.add_argument(
        "--replay",
        metavar="JSONL",
        help="Run headless against a gaze fixture (.jsonl) and export data.",
    )
    parser.add_argument("--subject", default="REPLAY", help="Subject id for the session folder.")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for target order.")
    parser.add_argument("--output", default="sessions", help="Session output root dir.")
    parser.add_argument("--gui", action="store_true", help="Launch the PySide6 GUI.")
    parser.add_argument(
        "--calibration-file",
        metavar="PATH",
        help=(
            "Reuse a previously-saved calibration.json instead of "
            "recalibrating this run (--gui only; its subject_id must match "
            "--subject). Written automatically to <session_dir>/calibration.json "
            "whenever a real calibration runs."
        ),
    )
    parser.add_argument(
        "--skip-task-settings",
        action="store_true",
        help=(
            "Skip the pre-launch task settings dialog (grid size, radius, "
            "trial count, ...) and start immediately with the task's YAML "
            "defaults. --gui only. Useful for scripted/automated launches."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.gui:
        try:
            from .app import run_gui
        except ImportError as exc:  # pragma: no cover - GUI optional
            print(f"GUI dependencies not available: {exc}", file=sys.stderr)
            print("Install with: pip install -e '.[gui]'", file=sys.stderr)
            return 2
        return run_gui(
            task_id=args.task,
            replay_path=args.replay,
            subject_id=args.subject,
            calibration_file=args.calibration_file,
            skip_task_settings_dialog=args.skip_task_settings,
        )

    if args.calibration_file:
        print("--calibration-file has no effect without --gui; ignoring.", file=sys.stderr)

    if not args.replay:
        print("Nothing to do: pass --replay <fixture> for headless mode, or --gui.", file=sys.stderr)
        return 2

    result = run_headless_replay(
        task_id=args.task,
        replay_path=args.replay,
        subject_id=args.subject,
        output_root=args.output,
        seed=args.seed,
    )
    print(
        f"[{args.task}] trials={result['n_trials']} "
        f"hits={result['n_hits']} timeouts={result['n_timeouts']}"
    )
    print(f"Session written to: {result['session_dir']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
