"""Task registry + headless replay pipeline (plan sections 5.4, 6/Phase 2).

The registry maps task ids to task classes. :func:`run_headless_replay` runs a
full session against a recorded gaze fixture with no GUI and no threads, so the
whole "calibrate -> task -> export" loop is reproducible and testable — this is
the backbone of the ``--replay`` demo in :mod:`src.main`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..data.recorder import SessionRecorder
from ..data.schema import GazeSample, SessionMetadata
from ..inputs.base import Pointer
from ..inputs.eye_input import DwellConfig, DwellSelector
from ..inputs.gazepoint_client import ReplayGazeSource
from ..tasks.base_task import BaseTask
from ..tasks.click_grid import ClickGridTask
from ..tasks.click_static import ClickStaticTask
from ..tasks.follow_moving import FollowMovingTask
from ..tasks.scanning import ScanningTask
from .config import load_task_config

TASK_REGISTRY: dict[str, type[BaseTask]] = {
    "click_static": ClickStaticTask,
    "click_grid": ClickGridTask,
    "follow_moving": FollowMovingTask,
    "scanning": ScanningTask,
}


def build_task(
    task_id: str,
    config: dict[str, Any],
    recorder: SessionRecorder | None = None,
    feedback=None,
    seed: int = 0,
) -> BaseTask:
    if task_id not in TASK_REGISTRY:
        raise KeyError(f"Unknown task '{task_id}'. Known: {sorted(TASK_REGISTRY)}")
    app_cfg = config.get("app", {})
    dwell_cfg = config.get("dwell", {})
    dwell = DwellSelector(
        DwellConfig(
            threshold_ms=float(dwell_cfg.get("threshold_ms", 800)),
            refractory_ms=float(dwell_cfg.get("refractory_ms", 500)),
        )
    )
    return TASK_REGISTRY[task_id](
        config=config,
        screen_width_px=int(app_cfg.get("screen_width_px", 1920)),
        screen_height_px=int(app_cfg.get("screen_height_px", 1080)),
        recorder=recorder,
        feedback=feedback,
        dwell=dwell,
        input_mode=config.get("input", {}).get("mode", "eye"),
        seed=seed,
    )


def run_headless_replay(
    task_id: str,
    replay_path: str | Path,
    subject_id: str = "REPLAY",
    session_id: str | None = None,
    output_root: str | Path = "sessions",
    config_root: str | Path | None = None,
    seed: int = 0,
    max_seconds: float = 600.0,
    feedback=None,
) -> dict[str, Any]:
    """Run a full session from a gaze fixture and write session artifacts.

    Returns a dict with ``session_dir``, ``n_trials`` and summary counts.
    """
    config = load_task_config(task_id, config_root)
    fps = int(config.get("app", {}).get("target_fps", 60))
    dt_ns = int(1e9 / fps)

    source = ReplayGazeSource(replay_path, loop=True)

    session_id = session_id or f"replay_{task_id}_{subject_id}"
    metadata = SessionMetadata(
        subject_id=subject_id,
        session_id=session_id,
        started_ns=0,
        input_mode=config.get("input", {}).get("mode", "eye"),
        tasks=[task_id],
        notes="headless replay",
    )

    with SessionRecorder(metadata, output_root=output_root) as recorder:
        task = build_task(task_id, config, recorder=recorder, feedback=feedback, seed=seed)
        recorder.log(f"Starting headless replay: task={task_id} fps={fps}")

        max_frames = int(max_seconds * fps)
        save_gaze = config.get("recording", {}).get("save_gaze_stream", True)

        for frame in range(max_frames):
            t_ns = frame * dt_ns
            sample = source.sample_at(t_ns / 1e9)
            sample = GazeSample(
                t_ns=t_ns,
                x=sample.x,
                y=sample.y,
                valid=sample.valid,
                fixation_id=sample.fixation_id,
                fix_duration_s=sample.fix_duration_s,
                pupil_left=sample.pupil_left,
                pupil_right=sample.pupil_right,
            )
            if save_gaze:
                recorder.record_gaze(sample)
            pointer = Pointer(x=sample.x, y=sample.y, valid=sample.valid, clicked=False)
            task.update(t_ns, pointer)
            if task.is_done:
                break

        trials_path = recorder.write_trials(task.trials)
        recorder.log(f"Wrote {len(task.trials)} trials -> {trials_path}")

        n_hits = sum(1 for tr in task.trials if tr.is_hit)
        n_timeouts = sum(1 for tr in task.trials if tr.is_timeout)
        return {
            "session_dir": str(recorder.session_dir),
            "trials_csv": str(trials_path),
            "n_trials": len(task.trials),
            "n_hits": n_hits,
            "n_timeouts": n_timeouts,
        }
