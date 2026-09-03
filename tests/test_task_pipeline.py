"""End-to-end headless pipeline and config tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.engine.config import load_task_config
from src.engine.feedback import NullFeedback
from src.engine.task_runner import TASK_REGISTRY, build_task, run_headless_replay
from src.inputs.base import Pointer

FIXTURE = Path(__file__).parent / "fixtures" / "gaze_replay.jsonl"


def test_config_merges_task_over_default():
    cfg = load_task_config("click_static")
    assert cfg["task"]["task_id"] == "click_static"
    # default.yaml keys survive the merge
    assert "dwell" in cfg
    assert cfg["app"]["target_fps"] == 60


def test_config_unknown_task_raises():
    with pytest.raises(FileNotFoundError):
        load_task_config("does_not_exist")


def test_task_overrides_deep_merge_into_globals(tmp_path: Path):
    # A task file's `overrides:` block should win over default.yaml globals.
    (tmp_path / "tasks").mkdir()
    (tmp_path / "default.yaml").write_text(
        "app:\n  target_fps: 60\ndwell:\n  threshold_ms: 800\n  refractory_ms: 500\n",
        encoding="utf-8",
    )
    (tmp_path / "tasks" / "demo.yaml").write_text(
        "task_id: demo\ntrials: 4\noverrides:\n  dwell:\n    threshold_ms: 1200\n",
        encoding="utf-8",
    )
    cfg = load_task_config("demo", config_root=tmp_path)
    assert cfg["dwell"]["threshold_ms"] == 1200   # overridden
    assert cfg["dwell"]["refractory_ms"] == 500   # untouched default survives
    assert cfg["app"]["target_fps"] == 60
    assert cfg["task"]["trials"] == 4


def test_click_grid_exposes_layout_slots_for_gui():
    cfg = load_task_config("click_grid")
    task = build_task("click_grid", cfg)
    rows = cfg["task"]["grid"]["rows"]
    cols = cfg["task"]["grid"]["cols"]
    assert task.layout_slots is not None
    assert len(task.layout_slots) == rows * cols
    # every trial's target is one of the declared cells
    slot_set = set(task.layout_slots)
    assert all((t.x_norm, t.y_norm) in slot_set for t in task.targets)


def test_scanning_exposes_layout_slots_for_gui():
    cfg = load_task_config("scanning")
    task = build_task("scanning", cfg)
    n_icons = cfg["task"]["layout"]["n_icons"]
    assert task.layout_slots is not None
    assert len(task.layout_slots) == n_icons
    slot_set = set(task.layout_slots)
    assert all((t.x_norm, t.y_norm) in slot_set for t in task.targets)


def test_click_static_has_no_layout_slots():
    cfg = load_task_config("click_static")
    task = build_task("click_static", cfg)
    assert task.layout_slots is None


def test_set_screen_size_ignores_non_positive_values():
    cfg = load_task_config("click_static")
    task = build_task("click_static", cfg)
    assert (task.screen_w, task.screen_h) == (1920, 1080)  # config default

    task.set_screen_size(0, 500)
    assert (task.screen_w, task.screen_h) == (1920, 1080)
    task.set_screen_size(800, -1)
    assert (task.screen_w, task.screen_h) == (1920, 1080)

    task.set_screen_size(800, 600)
    assert (task.screen_w, task.screen_h) == (800, 600)


def test_hit_testing_uses_live_screen_size_not_config_default():
    """Gap B: hit-testing must track the canvas's actual size, not the
    configured screen_width_px/height_px default -- otherwise a click that
    visually lands on the target can be scored as a miss (or vice versa)
    whenever the real window isn't exactly 1920x1080."""
    cfg = load_task_config("click_static")
    cfg["input"] = {"mode": "switch"}  # clicked=True hits immediately, no dwell
    task = build_task("click_static", cfg)

    target = task.targets[0]
    # An offset that's within the hitbox on a small canvas but well outside
    # it at the configured 1920px-wide default.
    pointer_x = min(1.0, target.x_norm + 0.1)
    pointer = Pointer(x=pointer_x, y=target.y_norm, valid=True, clicked=True)

    # At the config-default 1920x1080, this click is off-target: recorded as
    # a failed attempt, trial stays open (not a hit, not finished).
    result_default_size = task.update(t_ns=1_000_000, pointer=pointer)
    assert result_default_size.just_finished_trial is False
    assert task.trials == []

    # A much narrower live canvas shrinks the same normalized offset in
    # pixels enough to fall inside the target's hitbox.
    task.set_screen_size(300, 1080)
    result_live_size = task.update(t_ns=2_000_000, pointer=pointer)
    assert result_live_size.just_finished_trial is True
    assert task.trials[-1].is_hit is True


def test_follow_moving_selection_window_gates_hits():
    cfg = load_task_config("follow_moving")
    task = build_task("follow_moving", cfg)
    target = task.targets[0]
    start, end = task.select_windows[0]
    # Before the window opens and after it closes, selection must not count.
    assert task.is_selectable(target, max(0, start - 1)) is False
    assert task.is_selectable(target, (start + end) // 2) is True
    assert task.is_selectable(target, end + 1) is False


@pytest.mark.parametrize("task_id", sorted(TASK_REGISTRY))
def test_headless_replay_runs_every_task(task_id: str, tmp_path: Path):
    result = run_headless_replay(
        task_id=task_id,
        replay_path=FIXTURE,
        output_root=tmp_path,
        max_seconds=60.0,
    )
    assert result["n_trials"] > 0
    assert (Path(result["session_dir"]) / "trials.csv").exists()
    # hits + timeouts should account for every completed trial
    assert result["n_hits"] + result["n_timeouts"] == result["n_trials"]


def test_click_static_records_hits(tmp_path: Path):
    feedback = NullFeedback()
    result = run_headless_replay(
        task_id="click_static",
        replay_path=FIXTURE,
        output_root=tmp_path,
        feedback=feedback,
        max_seconds=120.0,
    )
    # The cooperative fixture dwells on every candidate position, so most
    # trials should be hits.
    assert result["n_hits"] >= result["n_trials"] // 2
    assert any(evt[0] == "hit" for evt in feedback.events)
    assert any(evt[0] == "target_shown" for evt in feedback.events)

    # Invariant: every hit must have a first-fixation timestamp, and it must
    # not come after the click (first-fixation <= reaction time).
    from src.data.exporter import load_trials_rows

    for row in load_trials_rows(result["session_dir"]):
        if row["is_hit"] == "1":
            assert row["time_to_first_fixation_ms"] != ""
            assert float(row["time_to_first_fixation_ms"]) <= float(row["reaction_time_ms"])
