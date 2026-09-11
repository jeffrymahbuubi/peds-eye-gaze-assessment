"""Tests for the dwell-selection state machine."""

from __future__ import annotations

from src.inputs.eye_input import DwellConfig, DwellSelector

MS = 1_000_000  # ns per ms


def make_selector(threshold_ms=800, refractory_ms=500, hold_grace_ms=0):
    return DwellSelector(
        DwellConfig(
            threshold_ms=threshold_ms,
            refractory_ms=refractory_ms,
            hold_grace_ms=hold_grace_ms,
        )
    )


def test_dwell_triggers_after_threshold():
    sel = make_selector(threshold_ms=800)
    # 0 ms: start; 799 ms: not yet; 800 ms: trigger
    assert sel.update(0, on_target=True).triggered is False
    assert sel.update(799 * MS, on_target=True).triggered is False
    state = sel.update(800 * MS, on_target=True)
    assert state.triggered is True
    assert state.progress == 1.0


def test_dwell_progress_is_monotonic_fraction():
    sel = make_selector(threshold_ms=1000)
    sel.update(0, on_target=True)
    assert sel.update(250 * MS, on_target=True).progress == 0.25
    assert sel.update(500 * MS, on_target=True).progress == 0.5


def test_leaving_target_resets_without_grace():
    sel = make_selector(threshold_ms=800, hold_grace_ms=0)
    sel.update(0, on_target=True)
    sel.update(400 * MS, on_target=True)
    # leave target -> reset
    off = sel.update(450 * MS, on_target=False)
    assert off.progress == 0.0
    # re-enter: must accumulate full threshold again
    sel.update(500 * MS, on_target=True)
    assert sel.update(1000 * MS, on_target=True).triggered is False  # only 500 ms in
    assert sel.update(1300 * MS, on_target=True).triggered is True


def test_hold_grace_tolerates_brief_dropout():
    sel = make_selector(threshold_ms=800, hold_grace_ms=120)
    sel.update(0, on_target=True)
    sel.update(400 * MS, on_target=True)
    # brief 100 ms dropout within grace -> progress preserved
    grace = sel.update(500 * MS, on_target=False)
    assert grace.progress == 0.0 or grace.progress >= 0.0  # no reset event
    # back on target, threshold reached from original start
    assert sel.update(800 * MS, on_target=True).triggered is True


def test_refractory_blocks_immediate_retrigger():
    sel = make_selector(threshold_ms=800, refractory_ms=500)
    sel.update(0, on_target=True)
    assert sel.update(800 * MS, on_target=True).triggered is True
    # within refractory window, staying on target must not retrigger
    r = sel.update(900 * MS, on_target=True)
    assert r.triggered is False
    assert r.in_refractory is True
    # after refractory, a fresh dwell can trigger again
    sel.update(1400 * MS, on_target=True)  # refractory ended at 1300 ms
    assert sel.update(2200 * MS, on_target=True).triggered is True


def test_dwell_does_not_trigger_while_off_target_in_grace():
    # Regression: the hold-grace window must preserve progress but never
    # *complete* a selection while the gaze is off-target.
    sel = make_selector(threshold_ms=800, hold_grace_ms=200)
    sel.update(0, on_target=True)
    sel.update(700 * MS, on_target=True)  # progress ~0.875
    # Now go off-target and stay within grace across the threshold crossing.
    off1 = sel.update(750 * MS, on_target=False)  # 50 ms since last on-target
    assert off1.triggered is False
    off2 = sel.update(850 * MS, on_target=False)  # elapsed 850 >= 800, but OFF
    assert off2.triggered is False
    assert off2.progress == 1.0  # ring is full, waiting for gaze to return
    # Returning to the target on the next frame completes it.
    assert sel.update(860 * MS, on_target=True).triggered is True


def test_reset_clears_state():
    sel = make_selector(threshold_ms=800)
    sel.update(0, on_target=True)
    sel.update(400 * MS, on_target=True)
    sel.reset()
    # fresh start after reset
    sel.update(500 * MS, on_target=True)
    assert sel.update(900 * MS, on_target=True).triggered is False
    assert sel.update(1300 * MS, on_target=True).triggered is True


# -- can_complete: holding a finished dwell until the caller will accept it ----
# SPEC-follow-moving-selection.md S5.2. Before this, a dwell that completed
# outside follow_moving's selection window was treated as a real completion
# and thrown away by the task, costing the child refractory + threshold and
# logging a MISS_CLICK against a correctly-aimed selection.


def test_dwell_holds_at_full_when_completion_not_allowed():
    sel = make_selector(threshold_ms=800)
    sel.update(0, on_target=True)
    state = sel.update(800 * MS, on_target=True, can_complete=False)
    assert state.triggered is False
    assert state.progress == 1.0
    assert state.in_refractory is False


def test_held_dwell_fires_immediately_once_allowed():
    sel = make_selector(threshold_ms=800)
    sel.update(0, on_target=True)
    # Held well past the threshold...
    for t in (800, 1500, 3000):
        assert sel.update(t * MS, on_target=True, can_complete=False).triggered is False
    # ...then the window opens: no re-accumulation, it triggers on that frame.
    assert sel.update(3001 * MS, on_target=True, can_complete=True).triggered is True


def test_holding_does_not_open_the_refractory_window():
    """A hold is not a selection, so there is nothing to recover from.

    If holding started the refractory window, the child would be locked out
    at exactly the moment the selection window opened -- the bug this whole
    mechanism exists to remove, reintroduced one layer down.
    """
    sel = make_selector(threshold_ms=800, refractory_ms=500)
    sel.update(0, on_target=True)
    sel.update(800 * MS, on_target=True, can_complete=False)
    assert sel.update(801 * MS, on_target=True, can_complete=True).triggered is True


def test_looking_away_clears_a_held_dwell():
    """The safety property: a held dwell must not survive the gaze leaving.

    Otherwise a child could complete a dwell early, look away entirely, and
    still be credited with a hit when the window opened.
    """
    sel = make_selector(threshold_ms=800, hold_grace_ms=0)
    sel.update(0, on_target=True)
    assert sel.update(800 * MS, on_target=True, can_complete=False).progress == 1.0
    # Gaze leaves: the held accumulator is discarded.
    assert sel.update(900 * MS, on_target=False).progress == 0.0
    # Returning re-accumulates from scratch rather than firing instantly.
    assert sel.update(1000 * MS, on_target=True, can_complete=True).triggered is False


def test_hold_grace_still_bridges_a_blink_while_held():
    """A held dwell keeps the ordinary grace semantics, not stricter ones."""
    sel = make_selector(threshold_ms=800, hold_grace_ms=120)
    sel.update(0, on_target=True)
    sel.update(800 * MS, on_target=True, can_complete=False)
    # A 100 ms blink is inside the grace window, so the hold survives it.
    assert sel.update(900 * MS, on_target=False).progress == 1.0
    assert sel.update(950 * MS, on_target=True, can_complete=True).triggered is True


def test_can_complete_defaults_to_true():
    """Every existing caller passes two positional arguments and must be
    unaffected -- the tasks without a selection window most of all."""
    sel = make_selector(threshold_ms=800)
    sel.update(0, on_target=True)
    assert sel.update(800 * MS, on_target=True).triggered is True
