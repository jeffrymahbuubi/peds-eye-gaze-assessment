# SPEC-follow-moving-selection — Follow & Click: rejected selections and the reaction-time metric

**Status: IMPLEMENTED, tested and validated.** §5.1–§5.4 built, plus §6.3 after the user approved it explicitly. Against the user's real run's numbers: `MISS_CLICK` events **33 → 0**, `attempts` **mean 6.33 → 1 on every trial**, outcome **5 hits + 1 timeout → 6 hits**. Confirmed both headlessly (real `FollowMovingTask`, synthetic perfect tracker) and in the running app via qt-mcp. Tests: **176 collected, 175 passed, 1 pre-existing unrelated failure as of this round**; +6 new here, 4 of which were verified to fail with the fix reverted. (The suite has since grown to **181 collected / 180 passed / the same 1 failure** via `SPEC-live-settings-panel.md` §10.6's additions — verified 2026-09-11 evening.) **Not yet committed.**

**Created:** 2026-09-11
**Last updated:** 2026-09-11 (implemented same day)

## Scope note

Covers `follow_moving` ("追視點擊 / Follow & Click") only. It is **the only task that overrides `is_selectable()`** — verified across `src/tasks/*.py` — so everything below is specific to it and no other task's selection path changes. Unrelated to `SPEC-gaze-cursor-redesign.md` (that is the cursor's *rendering*; this is the *selection* decision), and unrelated to `SPEC-live-settings-panel.md` §10, which was raised in the same feedback round but is a separate subsystem.

## 1. Reported symptom

**User, 2026-09-11:** "I audit all the task behaviour and found that the follow & click need to be updated. The current behavior is that when the eye gaze the circle the dwell circle is filled, however the 'click' itself is often fail which make the subject need to redo again by gazing the circle and it will not always success."

The report is accurate in every part, including "not always success" — one trial in the user's own run timed out after seven rejected selections. The mechanism is not a bug in the dwell engine or in hit-testing; both work correctly. It is a **contradiction between two rules that were each written correctly in isolation.**

## 2. Root cause — the dwell ring fills on a target the app has already decided is not selectable

> **Line numbers in §2 and §4 describe the code as it stood at diagnosis, before §5 was implemented** (audit, 2026-09-11). The implementation shifted several of them — `MISS_CLICK` is now at `base_task.py:301`, the dwell completion branch at `eye_input.py:171`, `reaction_time_ms` at `schema.py:84` — and the quoted "before" snippets deliberately no longer match current source, because they are the *pre-fix* state this section exists to record. **Navigate by symbol name, not by these line numbers.** `follow_moving.py`'s citations are still exact (that file was not modified).

Three facts from the source as it stood at diagnosis, each read rather than inferred:

**Fact 1 — the target is selectable for only a fifth of the trial, at a random time.** `FollowMovingTask.build_targets` (`src/tasks/follow_moving.py:23-36`) gives every trial a selection window of `motion.select_window_ms` starting at a uniformly random offset:

```python
latest_start = max(0, self.timeout_ns - self.select_window_ns)
start = self.rng.randint(int(0.15 * self.timeout_ns), latest_start)
self.select_windows.append((start, start + self.select_window_ns))
```

With `configs/tasks/follow_moving.yaml`'s real values — `timeout_ms: 12000`, `select_window_ms: 2500` — the window is **2500 ms of a 12000 ms trial (20.8%)**, beginning at a random point uniform in **[1800, 9500] ms**. `is_selectable()` (`:47-49`) returns `True` only inside it. This is deliberate: the docstring at `:25-27` says the point is that "the child must actively track and catch it rather than park on it."

**Fact 2 — the dwell accumulates regardless of that window.** `BaseTask.update` (`src/tasks/base_task.py:272-283`) computes `selectable` at `:258` but does not pass it to the dwell:

```python
state = self.dwell.update(t_ns, on_target)   # `selectable` is NOT an input
dwell_progress = state.progress
clicked = state.triggered
on_target_at_click = clicked
...
hit = on_target_at_click and selectable      # ...it is only applied HERE, after the fact
```

So the ring fills whenever gaze is on target, the dwell completes on schedule, and **only then** is the selection tested against the window and thrown away.

**Fact 3 — a thrown-away selection is recorded as the child's failure.** `:285-290`:

```python
if clicked and not hit:
    self._current.attempts += 1
    self._record_event("MISS_CLICK", t_ns, x=..., y=..., selectable=selectable)
```

A correct, on-target, fully-completed dwell is counted as a failed attempt, indistinguishable in the trial record from the child selecting the wrong thing.

**The child is then made to start over.** `DwellSelector.update` (`src/inputs/eye_input.py:137-141`) treats the completion as real — it clears the accumulator and opens a `refractory_ms` window — so after every rejection the child must wait 500 ms and then hold for another 800 ms (`configs/default.yaml`: `threshold_ms: 800`, `refractory_ms: 500`). That 1300 ms cycle repeats until the window happens to open. This is precisely the "need to redo again by gazing the circle" the user describes.

## 3. Confirmed against the user's own run — every rejection was a correct selection

`sessions/2026-09-11_testing_follow_moving_run1/`, a real GP3 HD run, 6 trials:

> **Audit note (2026-09-11):** that session directory **no longer exists** — `sessions/` is gitignored and was cleared during later testing, so the raw evidence is not re-checkable from the repo. The numbers below were read from it directly at the time and are reproduced verbatim. They are corroborated independently by the after-numbers in this SPEC's log (0 `MISS_CLICK` both in the headless simulation and in a live run), so nothing here rests on the deleted directory alone.

| Trial | Hit | Timeout | `attempts` | `reaction_time_ms` | `time_to_first_fixation_ms` |
|---:|:--:|:--:|---:|---:|---:|
| 0 | ✓ | | 6 | 10465.7 | 719.0 |
| 1 | ✓ | | 6 | 7680.4 | 393.0 |
| 2 | ✓ | | 5 | 7986.0 | 843.0 |
| 3 | ✓ | | **10** | 8116.4 | 530.5 |
| 4 | | **✗ timed out** | 7 | — | 531.8 |
| 5 | ✓ | | 4 | 4141.7 | 1094.6 |

**The decisive number: the run logged 33 `MISS_CLICK` events, and all 33 carry `"selectable": false`.** Not one was an off-target selection. Every single recorded failure in that run was a correctly-aimed, completed dwell rejected purely on timing — a mean of 5.5 rejections per trial.

**The contrast inside the table is the clearest statement of the problem:** the child found and fixated the target in **393–1095 ms** (mean 685 ms), and the app took **4142–10466 ms** to accept a selection. The gap is not the child.

Trial 4 shows the "will not always success" case concretely: seven rejected selections and then the 12 s timeout, scored as a miss. Trial 3 needed ten.

**Session-level damage:** `mean_attempts: 6.33`, `n_trials_needing_reattempt: 6` — **all six trials** flagged as needing re-attempts, and `hit_rate: 0.833` understated by one timeout that was not the child's failure.

## 4. Two consequences beyond the UX complaint

### 4.1 `attempts` is not measuring what the Results page says it measures

`attempts` feeds `mean_attempts` and `n_needing_reattempt` (`src/data/exporter.py:190-202`), surfaced on the Results page as "Mean attempts" and "Trials needing re-attempt" (`src/ui/results_page.py:113`). For every other task those read as a child's targeting accuracy. For `follow_moving` they are currently dominated by the app rejecting correct selections, so **the number is not comparable across tasks and does not mean what a clinician reading the column would assume.** Any `follow_moving` data already collected should be treated as affected.

### 4.2 `reaction_time_ms` for this task is largely a measurement of the random number generator

`TrialRecord.reaction_time_ms` (`src/data/schema.py:80-83`) is `t_click_ns - t_target_shown_ns` — measured from **trial start**. A hit cannot occur before the window opens, and the window start is uniform in [1800, 9500] ms, which alone has a standard deviation of about **2220 ms** before any child variability. The observed mean of 7678 ms sits right where that predicts.

**This is a pre-existing defect, not one the fix introduces — but the chosen fix completes it.** Once a selection fires the instant the window opens (§5), RT converges on the window start almost exactly, i.e. on the RNG. **So a window-relative reaction time is required as part of this work, not as a follow-up.** See §5.3.

Note for contrast: this does not affect the other tasks. The `mean_reaction_time_ms: 1371.37` the user highlighted is from a **scanning** run, which has no selection window, and that figure is sound.

## 5. Design

### 5.1 Decision

**Chosen by the user (`AskUserQuestion`, 2026-09-11): "fill early, fire when window opens."** The dwell may accumulate before the window; a completed dwell arms the selection and fires the moment the target becomes selectable.

Two alternatives were offered and declined, recorded so the choice stays traceable: *gate the ring so it does not fill until selectable* (the recommended option — never promises what it will reject, but makes the child begin an 800 ms dwell only once the window is already running), and *remove the window entirely* (simplest, but abandons the anti-parking design).

**The trade-off the user accepted:** the "catch it the moment it lights up" reaction demand is largely removed — a child already tracking is credited immediately. **What survives, and why this is defensible:** the target is *moving*, so staying on target is continuous smooth pursuit, not parking. With a circular path at `speed_frac_per_s: 0.20` the target completes a revolution every 5 s and its centre travels roughly 230 px during a single 800 ms dwell — more than the 140 px effective hitbox (`radius_px: 100` + `jitter_tolerance_px: 40`). Holding the dwell through the window opening still requires genuine tracking; only the timing-reaction component is given up.

### 5.2 Proposed mechanism — hold the dwell at full rather than completing it

The clean place to express this is `DwellSelector`, not the task, because the required "arming" semantics are exactly the accumulate/reset/grace semantics the selector already implements. Duplicating them in `BaseTask` would mean re-implementing `hold_grace_ms` a second time.

**Proposal:** give `DwellSelector.update()` a third argument (`can_complete`, default `True`, so every other caller is unaffected). When the accumulator reaches `threshold_ms` but `can_complete` is `False`:

- **do not** trigger, **do not** clear `_dwell_start_ns`, **do not** open the refractory window;
- return `progress=1.0, triggered=False`.

The instant `can_complete` becomes `True` while gaze is still on target, the existing completion branch fires normally. `BaseTask.update` passes `selectable` as `can_complete`.

**Why this is safe on the question that matters — a child cannot bank a selection and look away.** Arming is not new state; it *is* the live dwell accumulator. If gaze leaves the target beyond `hold_grace_ms`, the existing off-target branch (`eye_input.py:114-129`) clears `_dwell_start_ns` and the arming evaporates with it. Blinks are bridged exactly as they are today, by the same grace window, with no new code. Adding a separate `_armed` flag in the task would *not* get this for free and could credit a hit to a child who had stopped looking — that is the failure mode this design is chosen to avoid.

**Consequence for `attempts`:** an out-of-window completion is no longer a `MISS_CLICK` and no longer increments `attempts`, because it is no longer a completion at all. Since the dwell only ever accumulates while on target, `follow_moving` should now record `attempts: 1` on a clean hit — which is what the Results page's "Mean attempts" column has always claimed to mean.

### 5.3 Required alongside: a window-relative reaction time

Per §4.2, record `t_selectable_start_ns` on the trial record (the first frame `is_selectable()` returned `True`) and derive a reaction time relative to it for tasks that have a selection window. The existing trial-start-relative `reaction_time_ms` should be kept unchanged for cross-task continuity; this is an added field, not a redefinition. Naming, and whether the Results page shows it in place of the existing RT for this task, are for the implementing session.

### 5.4 Visual state — do not leave it implicit

A ring sitting at 100% while nothing happens is a new on-screen state and needs to be readable as "ready, waiting for the target" rather than as the app being stuck. Two existing details already help and should be checked rather than rebuilt: `_draw_target` (`src/ui/canvas.py`) already draws a non-selectable target darker (`color.darker(180)`) and withholds the bright white "catch me now" outline until it is selectable. Worth deciding at implementation time whether the held ring should be visually distinguished from a filling one.

**Also worth checking in the same pass:** `_draw_instant_feedback` (the bright on-target ring) is currently drawn whenever `on_target`, with no reference to `selectable` — so today it signals "you're on it" on a target that cannot be selected. That is part of the same contradictory-affordance family as this SPEC's main finding, though it was not what the user reported.

## 6. Open questions for the implementing session

1. **Should `select_window_ms` / the 20.8% duty cycle be revisited at all now?** With rejections gone the short window is far less punishing — the child simply holds. Left as-is in this design deliberately; flagged because the numbers were derived here and a future reader will wonder.
2. **How to treat `follow_moving` data already collected.** §3's run and any like it have `attempts`, `n_needing_reattempt`, `hit_rate` and `reaction_time_ms` all affected. Recommend marking them non-comparable rather than attempting a retroactive correction — the `MISS_CLICK` events carry `selectable: false`, so a corrected `attempts` is *reconstructable* in principle, but `hit_rate` is not (trial 4's timeout cannot be turned into the hit it would have been).
3. **Whether `_draw_instant_feedback` should be gated on `selectable`** (§5.4) — related, not reported, do not fold it in silently.
4. **Whether `can_complete` is the right name**, and whether the argument should be keyword-only to protect the two existing call sites.
5. **Test strategy.** `DwellSelector` is pure logic with no Qt dependency and is already covered by `tests/test_dwell_logic.py`, so the hold-at-full behaviour and the "gaze leaves → arming evaporates" case are both directly unit-testable. Per the §9 discipline established in `SPEC-gui-audit-2026-09-10.md`, each new test should be verified to genuinely fail without its fix.

## Log

- **2026-09-11** — Created. Raised by the user in the same `/sparc:orchestrator` round as `SPEC-live-settings-panel.md` §10, split into its own SPEC because it is a separate subsystem with no existing home. **Diagnosis and design only, no code changed** (`git status` clean of source; `main` level with `origin/main` at `36f0fd1`). Root cause traced through `follow_moving.py:23-49` → `base_task.py:258-290` → `eye_input.py:103-144` and then **confirmed against the user's own real-device run rather than left as a code-read prediction**: all **33** `MISS_CLICK` events in `sessions/2026-09-11_testing_follow_moving_run1/` carry `"selectable": false`, i.e. every recorded failure was a correct selection rejected on timing, at a mean of 5.5 per trial. The same run supplied the sharpest evidence in the SPEC — the child fixated the target in a mean of 685 ms while recorded reaction time averaged 7678 ms. Two consequences were found that the user did not report and that are not visible from the symptom: `attempts`/`n_needing_reattempt` do not mean for this task what the Results page implies (§4.1), and `reaction_time_ms` is dominated by the random window offset (§4.2) — a **pre-existing** defect that the chosen fix would complete, which is why §5.3 makes a window-relative RT part of this work rather than a follow-up. Fix approach chosen by the user over the recommended option; §5.1 records the trade-off accepted and the argument for why it remains defensible on a moving target. §5.2's mechanism was chosen specifically so that arming cannot survive the child looking away — it reuses the dwell accumulator and its existing `hold_grace_ms` semantics instead of introducing a separate flag that would need that safety re-implemented.

- **2026-09-11, later — IMPLEMENTED, tested and live-validated. §5.1-§5.4 all built; §6.3 folded in after the user approved it explicitly.**

  **§5.2 (the mechanism).** `DwellSelector.update()` gained a keyword-only `can_complete` (default `True`, so the other call sites are untouched — §6.4 resolved that way deliberately). When the accumulator reaches threshold with `can_complete=False` it returns `progress=1.0, triggered=False` **without** clearing `_dwell_start_ns` and **without** opening the refractory window; the next frame with `can_complete=True` triggers immediately. `BaseTask.update()` passes `selectable` as `can_complete`. The `hit = on_target_at_click and selectable` line is deliberately left in place: `state.triggered` now implies `selectable` in eye mode, but the mouse/switch path still needs it — a click genuinely made at the wrong time is still a real miss.

  **§5.3 (window-relative RT).** `TrialRecord` gained `t_selectable_start_ns` (set on the first frame `is_selectable()` returns true) and a derived `reaction_time_from_selectable_ms`; both are in `trials.csv`, and mean/median of the latter are in `session_metrics.json`. The trial-start-relative `reaction_time_ms` is **unchanged**, for cross-task continuity. Surfaced on the Results page as a new "Median RT (from selectable)" row — leaving it recorded but invisible would have left the misleading figure as the only one a physician sees, which is the actual clinical harm §4.2 identified. Reads "—" for every task without a selection window and for sessions recorded before this change.

  **§5.4 / §6.3.** `_draw_instant_feedback` is now gated on `selectable` too.

  **Tests: 6 new in `tests/test_dwell_logic.py`.** Honest accounting: **4 of the 6 were verified to genuinely fail with the fix reverted** (hold-at-full, fire-once-allowed, no-refractory-on-hold, grace-still-bridges). The other two — the `can_complete` default and "looking away clears a held dwell" — pass either way by construction; they are regression guards for the backward-compatibility and safety properties, not discriminating tests, and are kept on that basis rather than counted as proof.

  **End-to-end validation, headless, driving the real `FollowMovingTask` with a synthetic perfect tracker** — the numbers are directly comparable to §3's real run:

  | | §3, real run (before) | simulation (after) |
  |---|---|---|
  | `MISS_CLICK` events | **33**, all `selectable: false` | **0** |
  | `attempts` | 6, 6, 5, 10, 7, 4 (mean 6.33) | **1 on every trial** |
  | outcome | 5 hits, 1 timeout | **6 hits, 0 timeouts** |

  `reaction_time_from_selectable_ms` came out at **0 on every trial**, which is correct rather than suspicious: a *perfect* synthetic tracker holds a full dwell when the window opens, so it fires on that frame. A real child will not, which is exactly why the metric is worth having.

  **Also confirmed in the running app** (dashboard + fake server, driven via qt-mcp): a live `follow_moving` run recorded **0** `MISS_CLICK` events.

  **Full suite: 176 collected, 175 passed, 1 pre-existing unrelated failure** (`test_config_merges_task_over_default`, the long-known local `target_fps` 60-vs-150 config drift), **+15 new tests across both items of this round, no regressions.**

  **Open item 6.2 stands and is now more concrete:** the pre-change `follow_moving` data is not comparable to anything collected after this. `attempts` is reconstructable from the `MISS_CLICK` records (they carry `selectable: false`), but `hit_rate` is not — §3's trial 4 timed out after 7 rejections and cannot be turned into the hit it would have been.
