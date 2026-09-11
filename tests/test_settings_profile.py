"""Tests for saved per-subject, per-task settings profiles.

SPEC-live-settings-panel.md S10. Pure logic, no Qt and no device -- the
profile store is deliberately Qt-free for exactly this reason, matching
src/engine/local_state.py.
"""

from __future__ import annotations

import json

from src.engine.settings_profile import (
    known_subject_ids,
    load_settings_profile,
    resolve_settings_precedence,
    save_settings_profile,
    settings_profile_path,
)
from src.ui.settings_registry import (
    apply_live_values_to_config,
    format_calibration,
    initial_live_values,
)

LIVE = {"dwell.smoothing.alpha": 0.05, "dwell.jitter_tolerance_px": 100, "task.timeout_ms": 9000}


def test_round_trip(tmp_path):
    save_settings_profile(tmp_path, "S1", "click_grid", LIVE, {"target.radius_px": 120})
    got = load_settings_profile(tmp_path, "S1", "click_grid")
    assert got is not None
    assert got["live"] == LIVE
    assert got["structural"] == {"target.radius_px": 120}
    assert got["saved_at"]


def test_profiles_are_isolated_per_subject_and_per_task(tmp_path):
    """The clinical safety property: one child's tuning must never become
    another child's starting point, and one task's must not leak to another."""
    save_settings_profile(tmp_path, "S1", "click_grid", LIVE)
    assert load_settings_profile(tmp_path, "S2", "click_grid") is None
    assert load_settings_profile(tmp_path, "S1", "scanning") is None


def test_missing_profile_returns_none(tmp_path):
    assert load_settings_profile(tmp_path, "nobody", "click_grid") is None


def test_malformed_profile_degrades_to_none_instead_of_raising(tmp_path):
    """A corrupt profile must not be able to block a session."""
    path = settings_profile_path(tmp_path, "S1", "click_grid")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json at all", encoding="utf-8")
    assert load_settings_profile(tmp_path, "S1", "click_grid") is None


def test_profile_of_the_wrong_shape_degrades_to_none(tmp_path):
    path = settings_profile_path(tmp_path, "S1", "click_grid")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    assert load_settings_profile(tmp_path, "S1", "click_grid") is None


def test_saving_replaces_rather_than_accumulates(tmp_path):
    save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.5})
    save_settings_profile(tmp_path, "S1", "click_grid", {"dwell.smoothing.alpha": 0.1})
    got = load_settings_profile(tmp_path, "S1", "click_grid")
    assert got["live"] == {"dwell.smoothing.alpha": 0.1}


# -- applying a profile back onto a config ------------------------------------


def test_apply_round_trips_through_initial_live_values():
    """apply_live_values_to_config must be the exact inverse of
    initial_live_values, or a restored setting is silently dropped."""
    config = {
        "dwell": {"threshold_ms": 800, "smoothing": {"alpha": 0.22}},
        "task": {"timeout_ms": 8000, "motion": {"speed_frac_per_s": 0.20}},
    }
    values = initial_live_values(config)
    values["dwell.smoothing.alpha"] = 0.05
    values["task.timeout_ms"] = 9000
    values["motion.speed_frac_per_s"] = 0.44
    apply_live_values_to_config(config, values)
    assert initial_live_values(config)["dwell.smoothing.alpha"] == 0.05
    assert initial_live_values(config)["task.timeout_ms"] == 9000
    assert initial_live_values(config)["motion.speed_frac_per_s"] == 0.44


def test_motion_keys_land_under_task_not_at_top_level():
    """The specific trap apply_live_values_to_config exists to avoid: the key
    says `motion.` but the value is read from config['task']['motion']."""
    config = {"task": {"motion": {"speed_frac_per_s": 0.20}}}
    apply_live_values_to_config(config, {"motion.speed_frac_per_s": 0.9})
    assert config["task"]["motion"]["speed_frac_per_s"] == 0.9
    assert "motion" not in config


def test_unknown_keys_are_ignored():
    """A profile written by a different build must not break the run."""
    config = {"dwell": {"smoothing": {"alpha": 0.22}}}
    apply_live_values_to_config(config, {"dwell.no_such_setting": 1, "totally.made.up": 2})
    assert config == {"dwell": {"smoothing": {"alpha": 0.22}}}


# -- calibration recorded with a profile (S10.5.5) ----------------------------
# Descriptive only: nothing reads it back to change behaviour. The point is
# that settings tuned under a poor calibration may be compensating for bad
# tracking rather than suiting the child, and re-applying them under a good
# calibration would be wrong.


def test_calibration_is_stored_and_returned(tmp_path):
    save_settings_profile(
        tmp_path, "S1", "click_grid", LIVE, calibration={"error_px": 34.9, "points": 5}
    )
    got = load_settings_profile(tmp_path, "S1", "click_grid")
    assert got["calibration"] == {"error_px": 34.9, "points": 5}


def test_profile_without_calibration_loads_with_an_empty_block(tmp_path):
    """A profile written before S10.5.5 must still load cleanly."""
    path = settings_profile_path(tmp_path, "S1", "click_grid")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"live": LIVE, "saved_at": "2026-09-10"}), encoding="utf-8")
    got = load_settings_profile(tmp_path, "S1", "click_grid")
    assert got["calibration"] == {}
    assert got["live"] == LIVE


def test_format_calibration_renders_both_parts():
    assert format_calibration({"error_px": 34.94, "points": 5}) == "35px error, 5pt"


def test_format_calibration_is_empty_when_unknown():
    """Must render nothing rather than "None px" for an older/partial profile."""
    assert format_calibration(None) == ""
    assert format_calibration({}) == ""
    assert format_calibration({"error_px": None, "points": None}) == ""


def test_format_calibration_handles_a_partial_block():
    assert format_calibration({"points": 9}) == "9pt"
    assert format_calibration({"error_px": 8.0}) == "8px error"


# -- known subject IDs, for the Subject-ID completer (S10.7.3 B) --------------


def test_known_subject_ids_unions_settings_and_calibrations(tmp_path):
    """A subject usually has a saved calibration before a settings profile, so
    reading only _settings would miss the first chance to mistype the ID."""
    save_settings_profile(tmp_path, "TUNED", "click_grid", LIVE)
    (tmp_path / "_calibrations" / "CALIBRATED_ONLY").mkdir(parents=True)
    (tmp_path / "_calibrations" / "TUNED").mkdir(parents=True)
    assert known_subject_ids(tmp_path) == ["CALIBRATED_ONLY", "TUNED"]


def test_known_subject_ids_is_empty_when_nothing_is_saved(tmp_path):
    assert known_subject_ids(tmp_path) == []
    assert known_subject_ids(tmp_path / "does" / "not" / "exist") == []


def _profile(live=None, structural=None, calibration=None, saved_at="2026-09-11T10:00:00+00:00"):
    return {
        "live": live or {},
        "structural": structural or {},
        "calibration": calibration or {},
        "saved_at": saved_at,
    }


def test_carried_values_beat_a_saved_profile(tmp_path):
    """The rule the Tasks-page badge exists to report honestly (S10.7.3 A):
    with both present, the run applies the carried values, so a badge naming
    the profile would be a promise the run does not keep."""
    carried = {"dwell.smoothing.alpha": 0.4}
    resolved = resolve_settings_precedence(carried, _profile(live=LIVE))
    assert resolved["source"] == "carried"
    assert resolved["live_overrides"] == carried


def test_profile_applies_when_nothing_was_carried():
    resolved = resolve_settings_precedence(None, _profile(live=LIVE, calibration={"points": 5}))
    assert resolved["source"] == "profile"
    assert resolved["live_overrides"] == LIVE
    assert resolved["calibration"] == {"points": 5}
    assert resolved["saved_at"]


def test_no_carried_values_and_no_profile_is_defaults():
    resolved = resolve_settings_precedence(None, None)
    assert resolved["source"] == "defaults"
    assert resolved["live_overrides"] is None


def test_an_empty_profile_is_defaults_not_profile():
    """``source`` must name what the run really uses. A profile file that holds
    nothing changes nothing, so reporting "profile" would overstate it."""
    assert resolve_settings_precedence(None, _profile())["source"] == "defaults"


def test_a_structural_only_profile_still_counts_as_a_profile():
    resolved = resolve_settings_precedence(None, _profile(structural={"target.radius_px": 120}))
    assert resolved["source"] == "profile"
    assert resolved["structural_overrides"] == {"target.radius_px": 120}


def test_an_explicit_settings_dialog_choice_outranks_the_profiles_structural_block():
    resolved = resolve_settings_precedence(
        None,
        _profile(live=LIVE, structural={"target.radius_px": 120}),
        {"target.radius_px": 200},
    )
    assert resolved["structural_overrides"] == {"target.radius_px": 200}


def test_structural_overrides_survive_the_carried_branch():
    """Carrying live values must not drop a structural choice made this sitting."""
    resolved = resolve_settings_precedence(
        {"dwell.smoothing.alpha": 0.4}, None, {"target.radius_px": 200}
    )
    assert resolved["structural_overrides"] == {"target.radius_px": 200}


def test_known_subject_ids_ignores_loose_files(tmp_path):
    """Only directories are subjects; a stray file next to them is not one."""
    (tmp_path / "_settings").mkdir()
    (tmp_path / "_settings" / "S1").mkdir()
    (tmp_path / "_settings" / "notes.txt").write_text("x", encoding="utf-8")
    assert known_subject_ids(tmp_path) == ["S1"]
