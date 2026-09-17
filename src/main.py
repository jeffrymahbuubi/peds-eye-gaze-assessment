"""Command-line entry point.

Headless replay demo (no tracker, no GUI required)::

    python -m src.main --task click_static --replay tests/fixtures/gaze_replay_click_static.jsonl

Live GUI, one task per process (requires the ``gui`` extra and a Gazepoint
tracker or replay)::

    python -m src.main --task click_static --gui

Persistent Setup/Task-selection dashboard -- tracker connection and
calibration made once in Setup carry over to every task Run
(SPEC-ui-setup-task-selection.md); an additional entry point, not a
replacement for ``--task ... --gui`` above::

    python -m src.main --dashboard

Compiled build (PyInstaller one-folder, ``tools/pyinstaller/``): the exe
runs ``main()`` too. With no arguments it launches the dashboard, works from
its own folder (so ``sessions/`` and ``configs/local_state.json`` land next
to the exe wherever it was launched from), and mirrors stdout/stderr and Qt
messages into ``logs/`` since a windowed exe has no console.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from .engine.task_runner import TASK_REGISTRY, run_headless_replay


def is_frozen() -> bool:
    """True inside a PyInstaller build."""
    return bool(getattr(sys, "frozen", False))


def prepare_frozen_environment() -> Path | None:
    """One-time setup for the compiled exe; a no-op when run from source.

    Returns the log file path when one was opened. Everything here is about
    the exe having no console and no fixed working directory -- none of it
    changes behaviour when run from source.
    """
    if not is_frozen():
        return None
    exe_dir = Path(sys.executable).resolve().parent
    os.chdir(exe_dir)

    log_dir = exe_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"app-{datetime.now():%Y%m%d-%H%M%S}.log"
    # A windowed PyInstaller exe starts with sys.stdout/stderr set to None;
    # anything printed would raise. Line-buffered so a crash keeps the tail.
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = log_file
    sys.stderr = log_file
    print(f"=== start {datetime.now():%Y-%m-%d %H:%M:%S} cwd={exe_dir} argv={sys.argv[1:]}")

    try:
        from PySide6.QtCore import qInstallMessageHandler

        def _qt_to_log(_mode, _context, message: str) -> None:
            print(f"[qt] {message}")

        qInstallMessageHandler(_qt_to_log)
    except ImportError:  # pragma: no cover - GUI optional
        pass
    return log_path


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
        "--dashboard",
        action="store_true",
        help=(
            "Launch the persistent Setup/Task-selection dashboard instead of "
            "a single task. Ignores --task/--replay/--subject/--calibration-file/"
            "--skip-task-settings; the dashboard collects those interactively."
        ),
    )
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
    prepare_frozen_environment()
    if argv is None:
        argv = sys.argv[1:]
    if is_frozen() and not argv:
        # Double-clicked exe: the dashboard is the product; the headless and
        # single-task modes stay reachable by passing their flags explicitly.
        argv = ["--dashboard"]
    args = build_parser().parse_args(argv)

    if args.dashboard:
        try:
            from .ui.dashboard_window import run_dashboard
        except ImportError as exc:  # pragma: no cover - GUI optional
            print(f"GUI dependencies not available: {exc}", file=sys.stderr)
            print("Install with: pip install -e '.[gui]'", file=sys.stderr)
            return 2
        return run_dashboard()

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
