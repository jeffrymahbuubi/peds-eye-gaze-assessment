# SPEC-live-settings-panel — Live Settings & Debug Panel

**Status:** implemented, live-validated via qt-mcp, and per-task replay
fixtures built (2026-09-04). Not yet committed.
**Created:** 2026-09-04
**Last updated:** 2026-09-04

## 1. Origin / what was asked

The user's own understanding, stated verbatim (lightly trimmed): there are
global config values — dwell time (`threshold_ms`), `jitter_tolerance_px`,
`smoothing`, `progress_ring`, `instant_feedback` — but only `threshold_ms` is
currently exposed anywhere in the UI. Since the physician isn't familiar with
these settings, exposing them **while a task is running** would let the
physician see the effect immediately, and would also help the user's own
development/debugging. Separately, each task also has its own YAML-only
parameters (grid size, radius, trial count, motion speed, ...) that are
likewise only reachable by hand-editing a file today.

**Ask:** design (not build) the capability to expose both the global dwell/
feedback settings and task-specific settings in the UI.

## 2. Decisions made this session (via clarifying questions)

Three forks were resolved with the user before drafting the design below —
they shape the architecture, not just cosmetics:

1. **Mid-task live scope:** only the *cheap* continuous parameters (dwell
   timing/smoothing/visual toggles, `timeout_ms`, `inter_trial_interval_ms`)
   go live mid-task. Structural/layout parameters (grid size, target radius,
   icon count, trial count, ...) are adjusted through a **pre-launch settings
   step**, not mid-run — see §4 for why these two groups aren't
   interchangeable at the code level.
2. **Persistence:** UI-tweaked values are **session-only** — no write-back to
   any YAML file, matching how the existing `threshold_ms` slider already
   behaves. Tuning found in the UI still has to be copied into YAML by hand
   if it should become a new default.
3. **UI disclosure:** two-tier — a small **Basic** group of always-visible
   controls (physician-facing) plus a collapsible **Advanced** section
   (everything else, for the user's own debugging).

## 3. Current state (verified against the working copy, 2026-09-04)

Only `dwell.threshold_ms` is wired end-to-end today:
`OperatorPanel`'s slider (`src/ui/operator_panel.py`) emits
`dwell_threshold_changed` → `AssessmentApp._set_dwell_threshold`
(`src/app.py:261`) → rebuilds `task.dwell.config`, a frozen `DwellConfig`
dataclass consumed fresh on every `DwellSelector.update()` call.

Critically, **every other field the user named already exists as a plain,
cheap-to-mutate live attribute** — the gap is UI wiring, not the engine:

| Field | Lives on | Read | Mutation cost |
|---|---|---|---|
| `dwell.threshold_ms` / `refractory_ms` | `task.dwell.config` (frozen `DwellConfig`) | every `DwellSelector.update()` | already proven live (swap the dataclass, as `_set_dwell_threshold` does) |
| `dwell.jitter_tolerance_px` | `task.jitter_px` (plain float) | every frame, `BaseTask.update()` | trivial — direct attribute set |
| `dwell.visual_cursor` | `canvas.show_cursor` (plain bool) | every `paintEvent` | trivial |
| `dwell.progress_ring` | `canvas.show_progress_ring` | every `paintEvent` | trivial |
| `dwell.instant_feedback` | `canvas.show_instant_feedback` | every `paintEvent` | trivial |
| `dwell.smoothing.enabled` / `alpha` | `eye.smoother.config` (frozen `SmoothingConfig`) | every `GazeSmoother.update()` | trivial — swap the dataclass (see caveat in §5.4) |

None of these need an engine change to become live — they need a control in
the UI and a small dispatcher in `AssessmentApp` to apply the new value to
the right object. This is a much smaller lift than task-specific params.

## 4. Task-specific parameters: why they don't all behave the same way

Every task subclass computes its full trial list **once**, in
`build_targets()`, called from `BaseTask.__init__`. Some fields it reads are
then re-read live from a plain instance attribute at point of use; others are
baked into a frozen `TargetSpec` per trial, or into a precomputed list
covering *all* trials, and never re-read again. This is the real reason
"expose task settings live" can't be one uniform mechanism:

| Field | Task(s) | Where it ends up | Live-safe? |
|---|---|---|---|
| `timeout_ms` | all | `self.timeout_ns`, re-read every frame (`elapsed >= self.timeout_ns`) | **Yes** — cheap attribute set |
| `inter_trial_interval_ms` | all | `self.iti_ns`, re-read at each `_finish_trial()` | **Yes** — cheap attribute set (affects the *next* ITI, not one already in progress) |
| `motion.speed_frac_per_s` | `follow_moving` | `self.speed`, re-read every frame in `target_position()` | **Yes** — cheap attribute set |
| `target.radius_px` | all | baked into each frozen `TargetSpec.radius_px` at build time | **No** — would need every remaining `TargetSpec` rebuilt |
| `trials` (count) | all | determines the length of the whole `self.targets` list | **No** — defines the trial sequence itself |
| `grid.rows` / `cols` / `margin_frac` | `click_grid` | baked into `self.layout_slots` + the shuffled cell order, once | **No** |
| `layout.n_icons` / `arrangement` | `scanning` | baked into `self.layout_slots` + per-trial slot choice, once | **No** |
| `target.positions` | `click_static` | the candidate-position list sampled once per trial at build time | **No** — could add positions for *future* trials but not cleanly |
| `motion.select_window_ms` | `follow_moving` | **surprising case:** baked into `self.select_windows[i]` — an absolute-ns `(start, end)` pair computed **for every trial up front**, not re-read per frame | **No**, despite reading like a continuous "speed"-style dial — this is structural, same bucket as grid/radius |

`motion.select_window_ms` is the one field that looks like it should belong
with `speed_frac_per_s` (both live under `motion:`) but doesn't — worth
flagging explicitly so a future implementer doesn't wire it as "live" by
analogy and silently make it a no-op for already-computed trials.

**Practical result under decision #1 (§2):** `timeout_ms` and
`inter_trial_interval_ms` join the global dwell/feedback fields as
mid-task-live, wired through the same dispatcher. Everything else in this
table is pre-launch-only.

## 5. Design

### 5.1 A field registry, not one signal per field

`OperatorPanel` today hand-wires one `Signal` + one slot per live field
(`dwell_threshold_changed` → `_set_dwell_threshold`). Repeating that
one-off pattern seven more times is exactly the kind of duplication the
user's own "makes it easier for me during development" goal argues against —
every future tunable would mean a new Signal, a new slot, and a new
`AssessmentApp` method.

Instead: a small declarative list of `LiveSetting` descriptors, one entry per
mid-task-live field —

```python
@dataclass(frozen=True, slots=True)
class LiveSetting:
    key: str              # dotted config path, e.g. "dwell.jitter_tolerance_px"
    label: str             # UI label
    group: str              # "basic" | "advanced"
    kind: str                # "bool" | "float" | "int"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    applies_to: str = ""       # which task types this is relevant for ("" = all)
```

`OperatorPanel` builds one widget (checkbox for `bool`, slider+label for
`float`/`int`) per descriptor instead of bespoke code per field, grouped by
`group`. A single `Signal(str, object)` (`setting_changed`) carries
`(key, new_value)` for every field. `AssessmentApp` gets **one** dispatcher
(`_apply_setting(key, value)`) with a small lookup table mapping each dotted
key to the object/attribute it mutates — replacing `_set_dwell_threshold`
with one case in that table, and adding each new field named in §3/§4 as one
more line, not one more method.

Proposed initial registry (all live per §3/§4; grouping per decision #3):

- **Basic:** `dwell.threshold_ms` (existing), `dwell.visual_cursor`,
  `dwell.progress_ring`, `dwell.instant_feedback` — these are the ones a
  physician watching the child would plausibly want to toggle live to see
  the effect ("does turning off the cursor help him focus on the target?").
- **Advanced:** `dwell.refractory_ms`, `dwell.jitter_tolerance_px`,
  `dwell.smoothing.enabled`, `dwell.smoothing.alpha`, `task.timeout_ms`,
  `task.inter_trial_interval_ms`, and — only when the active task is
  `follow_moving` (`applies_to`) — `motion.speed_frac_per_s`.

This grouping is a starting proposal, not a hard boundary; because it's
registry-driven, moving a field between Basic/Advanced later is a one-word
change, not a UI rewrite.

### 5.2 OperatorPanel: Basic section + collapsible Advanced section

`OperatorPanel` (`src/ui/operator_panel.py`) gains a `QGroupBox` (or a
`QToolBox`/collapsible `QGroupBox` with a checkable title, Qt's usual
pattern) titled "Advanced", collapsed by default, below the existing
Status/Controls boxes. Basic-group widgets stay where the dwell slider is
today; Advanced-group widgets are built the same way inside the collapsed
box. No change to the panel's existing Status display or Pause/Skip buttons.

### 5.3 Pre-launch settings step for structural/task parameters

The §4 "No" column (grid size, radius, trial count, icon count, positions,
`select_window_ms`) needs a **decision point before `AssessmentApp` is
constructed**, since `build_targets()` runs once inside `__init__` and there
is no reload path today. Concretely: a small dialog shown by `run_gui()`
(`src/app.py`) after the task is chosen but before `AssessmentApp(...)` is
built, pre-filled from the merged config (`load_task_config(task_id)`, the
same function already used today) and letting the operator override any of
that task's structural fields. The collected overrides are merged into the
config exactly the way `load_task_config` already merges a task YAML's own
`overrides:` block (`src/engine/config.py::_deep_merge`) — no new merge
logic, just a dict built from dialog widgets instead of parsed from YAML,
passed into `build_task()`. This reuses the config pipeline as-is; the only
new code is the dialog itself and constructing the override dict from it.

Because this is pre-launch, it needs no live-apply plumbing, no rebuild
mechanism, and carries none of the mid-task-safety concerns in §5.5 below.

### 5.4 Smoothing reset caveat

`GazeSmoother` keeps running EMA state (`_x`/`_y`) across calls. If the
Advanced panel's `smoothing.enabled` or `smoothing.alpha` control changes
live, the dispatcher should call `eye.smoother.reset()` immediately after
swapping the config — otherwise the very next sample blends against a
possibly-stale average from before the change, producing a brief visible
glitch rather than a clean transition. `GazeSmoother.reset()` already exists
(used today on gaze drop-out) and needs no change, just an extra call site.

### 5.5 Mid-task changes affect the trial in progress — log it

Because every Basic/Advanced field is read fresh every frame (that's what
makes it cheap), a change made mid-trial takes effect **within that same
trial**, not just future ones — e.g. widening `jitter_tolerance_px` mid-dwell
changes hit-testing for the attempt already underway. This is the literal
behavior the user asked for ("see the effect immediately"), so it's not a
bug to prevent — but it is a data-provenance gap: `trials.csv` has no record
that a trial's effective parameters changed partway through it.

Proposed fix, cheap given existing infrastructure: `_apply_setting` also
calls `self.recorder.record_event("SETTING_CHANGED", t_ns, key=key,
old_value=..., new_value=...)`. `SessionRecorder.record_event`
(`src/data/recorder.py`) already accepts an arbitrary `kind` + payload dict
and writes it to `events.jsonl` — no recorder change needed, just one new
call site in the dispatcher. A future analysis pass (`analyze_session.py`)
could then flag or exclude trials whose window overlaps a `SETTING_CHANGED`
event, without this SPEC needing to design that analysis now.

### 5.6 No persistence (decision #2)

No config-writer is designed or built. Every value shown in the panel is
initialized from the merged config at task start and reset to that on the
next launch, exactly like today's `threshold_ms` slider. If a future session
wants a "Save as default" action, that is new scope, not covered here.

## 6. Explicitly out of scope, and why

| Field(s) | Why excluded |
|---|---|
| `calibration.*` | Resolved and consumed before the task/UI even exists (`Calibration.run()` completes during `AssessmentApp.__init__`, before `MainWindow` is shown) — nothing to make "live" mid-task. |
| `gazepoint.host` / `port` / `enable.*` | Connection is already open by the time any panel could show; changing these mid-session means tearing down and reopening the socket, a much larger and riskier change than this SPEC's scope. |
| `app.target_fps` / `app.fullscreen` | Not tunables a physician or the user would plausibly want to flip mid-task; not named in the original ask. |
| `recording.save_gaze_stream` / `save_screen_capture` | Toggling mid-session risks an inconsistent `gaze_stream.csv` (header written once at `open()`, rows conditionally written per `_tick`) — flagged as unsafe to expose without a dedicated design, not attempted here. |
| `theme` | Visual identity, not a debugging/tuning parameter; changing it mid-task would also require reloading sound assets already bound to `GuiFeedback`. |

## 7. Open questions for the implementing session

1. Exact widget choice for the collapsible Advanced section (`QToolBox` vs.
   a checkable `QGroupBox` vs. a simple show/hide button) — a Qt/PySide6
   detail, not a design fork, left to implementation time.
2. Whether the pre-launch settings dialog is a separate `QDialog` shown from
   `run_gui()`, or a first screen inside `MainWindow` itself before the task
   starts — both satisfy §5.3's requirement; whichever is less disruptive to
   the current single-window flow should win.
3. Numeric ranges (min/max/step) for each Advanced slider — not yet chosen;
   should default to sane bounds (e.g. `jitter_tolerance_px` 0-100,
   `smoothing.alpha` 0.05-1.0) but deserves a quick sanity pass against real
   values once the device is available again.
4. Whether `SETTING_CHANGED` events should also appear in the human-readable
   `session.log`, not just `events.jsonl` — small, deferred to implementation.

## 8. Log

- **2026-09-04** — SPEC created. Design-only session (`/sparc:orchestrator`,
  explicit user instruction: design the approach, do not implement). Grounded
  entirely in reading the current working copy (`src/app.py`,
  `src/ui/operator_panel.py`, `src/ui/main_window.py`, `src/ui/canvas.py`,
  `src/inputs/eye_input.py`, `src/tasks/base_task.py` and all four task
  subclasses, `src/engine/config.py`, `src/data/recorder.py`,
  `configs/default.yaml`, all four `configs/tasks/*.yaml`) — no fields or
  behaviors in this document are assumed. Three scope-defining questions
  were asked and resolved before drafting (§2). No code changed this
  session.

- **2026-09-04, later the same day — implemented and validated.**
  New: `src/ui/settings_registry.py` (`LiveSetting`/`StructuralSetting`
  dataclasses, `LIVE_SETTINGS`/`STRUCTURAL_SETTINGS` registries,
  `initial_live_values`/`initial_structural_values`, `get_nested`/
  `set_nested`), `src/ui/task_settings_dialog.py` (`TaskSettingsDialog`, the
  pre-launch structural-params dialog from §5.3). Changed:
  `src/engine/config.py` (`_deep_merge` renamed to public `deep_merge`, old
  name kept as an alias — one existing test imports it by the old name),
  `src/ui/operator_panel.py` (rebuilt from the registry: Basic group always
  visible, collapsible Advanced `QGroupBox` built the same way, single
  `setting_changed(str, object)` signal replacing the old
  `dwell_threshold_changed`), `src/ui/main_window.py` (passes `task_id`/
  `initial_settings` through instead of a bare `dwell_threshold_ms`),
  `src/app.py` (`AssessmentApp` gained `structural_overrides`; `_live_values`
  snapshot seeds both the panel and the live objects; `_apply_setting`
  dispatcher replaces `_set_dwell_threshold`, covers all 11 live keys via
  `dataclasses.replace` for the two frozen configs, calls
  `GazeSmoother.reset()` on any smoothing change per §5.4, and logs a
  `SETTING_CHANGED` event to both `events.jsonl` and `session.log` per §5.5/
  open question 4 — resolved yes; `run_gui` shows `TaskSettingsDialog`
  before constructing `AssessmentApp`, gated by a new
  `--skip-task-settings` CLI flag for scripted/automated launches, not in
  the original design but a small, non-breaking addition), `src/main.py`
  (the new flag, threaded through to `run_gui`).
  Open question resolutions: #1 (collapsible-section widget) — a checkable
  `QGroupBox` (Qt auto-disables + this code hides children on uncheck). #2
  (dialog vs. in-window step) — a separate modal `QDialog`, shown from
  `run_gui()` before `AssessmentApp` is constructed; "Start task" with no
  edits reproduces prior behavior exactly, "Cancel" aborts the launch
  (`run_gui` returns 0). #3 (numeric ranges) — chosen in
  `settings_registry.py`, not yet sanity-checked against real GP3HD noise
  (still needs the live device, same caveat as the underlying smoothing/
  jitter defaults). #4 (session.log) — yes, done.
  **Tests:** full suite still shows only the same 2 pre-existing failures
  (`test_config_merges_task_over_default`, `test_click_static_records_hits`)
  — no regressions. A new offscreen functional script (not pytest, matching
  this project's convention for Qt-wiring checks) proved: `TaskSettingsDialog`
  defaults match YAML and `overrides()` reflects edits; `AssessmentApp`
  applies `structural_overrides` onto `build_targets()` output (click_grid
  trial count 18->6, layout_slots 9->6); all 11 live keys actually mutate
  their target object; `replace()` preserves sibling fields (changing
  `refractory_ms` doesn't reset an already-applied `threshold_ms`);
  `motion.speed_frac_per_s` is a no-op on non-follow_moving tasks and applies
  correctly on follow_moving; >=10 `SETTING_CHANGED` events land in
  `events.jsonl`.
  **qt-mcp live validation** (real running GUI, not offscreen, against
  `tests/fixtures/gaze_replay.jsonl`, no real device): `click_grid` launched
  with the pre-launch dialog showing exactly its 4 applicable structural
  fields (trials/target.radius_px/grid.rows/grid.cols) at correct YAML
  defaults (18/80/3/3); set trials=6, grid.rows=2 via the dialog, clicked
  "Start task" — canvas rendered a 2x3 (6-slot) grid instead of the default
  3x3 (9-slot) one, and the session's `trials.csv` had exactly 6 rows,
  confirming the structural-override path end-to-end in the real app,
  not just headlessly. Expanded the Advanced section live (checkable
  `QGroupBox` correctly shows/hides+enables/disables its 5 fields).
  Unchecked "Show gaze cursor" live — the on-screen cursor dot disappeared
  on the very next frame; `events.jsonl`/`session.log` both recorded the
  `SETTING_CHANGED` entry for `dwell.visual_cursor`. Separately launched
  `follow_moving` with `--skip-task-settings` and confirmed its Advanced
  section has a 6th field, "Target speed (frac/s)" (`motion.speed_frac_per_s`,
  default 0.20) absent from click_grid's Advanced section — proving the
  `applies_to` per-task filtering works live, not just in the registry.
  Changed it to 0.60 via the panel; `events.jsonl` recorded the matching
  `SETTING_CHANGED` event.
  **Not done yet:** committing this work (matching the project's pattern of
  asking before commit+push).

- **2026-09-04, later still — step 3, replay fixtures per task (user
  approved before starting).** Rewrote `tools/make_replay_fixture.py`,
  which previously only handled click_static via a hardcoded position list
  the tool's own docstring admitted needed "keeping in sync manually" with
  `click_static.yaml`. The new version derives positions from the *real*
  task classes (`build_task(...).layout_slots` for click_grid/scanning; the
  raw `target.positions` config for click_static, which has no
  `layout_slots`) so it can never drift from actual behavior again; added a
  `--task` flag (default `click_static`, preserving the exact original
  invocation). Verified the regenerated click_static output is
  byte-identical to the committed `tests/fixtures/gaze_replay.jsonl` except
  for a CRLF-vs-LF line-ending difference from this environment (confirmed
  via a byte-level diff) — the committed fixture itself was deliberately
  left untouched, only the 3 missing fixtures were added:
  `tests/fixtures/gaze_replay_click_grid.jsonl` (666 samples, 9 grid cells),
  `tests/fixtures/gaze_replay_scanning.jsonl` (296 samples, 4 icon slots),
  `tests/fixtures/gaze_replay_follow_moving.jsonl` (720 samples — a
  continuous 12s trace of `FollowMovingTask.target_position()`'s own
  formula, not fixed-point dwelling, since the target moves).
  **Important finding, disclosed rather than silently left implicit:**
  headless (`--replay`, no `--gui`) replay of every task — including the
  long-committed click_static fixture, not just the 3 new ones — currently
  produces 0 hits (all trials time out). Confirmed this is the exact same
  pre-existing, already-flagged, deliberately-not-investigated issue behind
  `tests/test_task_pipeline.py::test_click_static_records_hits`'s known
  failure (see this file's own 2026-09-04 log entry above), not a defect in
  the new fixture-generation logic — the new fixtures are structurally
  correct and behave identically to the existing baseline. Also confirmed,
  via a live qt-mcp GUI run of `scanning` against its own correctly-matched
  new fixture, that this is **not headless-only** — the same 0-hit pattern
  reproduces in the real `--gui --replay` path too. Not fixed here
  (unrelated to this task's scope, and previously left alone twice before);
  flagged clearly in `README.md`'s replay section so a future session (or
  the user evaluating a replay run) isn't confused by trials that time out
  rather than register hits. **Worth investigating in a dedicated future
  session** — this affects every task's replay-mode usefulness, not just
  the ones touched today.
  Also updated `README.md`: per-task fixture generation commands, the new
  pre-launch task settings dialog + `--skip-task-settings`, and the Basic/
  Advanced operator-panel controls, replacing the stale single dwell-slider
  description.

- **2026-09-04, later still — click_static's fixture renamed for
  consistency, per user feedback.** The user noticed
  `tests/fixtures/gaze_replay.jsonl` (click_static's fixture, unchanged
  since before this task) didn't show up alongside the 3 new
  `gaze_replay_<task>.jsonl` files — reasonable, since it didn't share their
  naming pattern and, being already git-tracked and untouched, didn't
  appear in `git status` either. Asked which fix they wanted (rename only,
  vs. explain where it is); the user's own answer was "I delete it, create
  it again" — interpreted as: delete the old file and regenerate it under
  the consistent name via the same tool used for the other three, so all
  four are both consistently named and freshly tool-generated.
  `git rm tests/fixtures/gaze_replay.jsonl`, then
  `python tools/make_replay_fixture.py --task click_static` (now defaults
  to `tests/fixtures/gaze_replay_click_static.jsonl` -- the click_static
  special case in `default_out_path()` was removed). Updated every real
  reference: `tests/test_task_pipeline.py`'s `FIXTURE` constant (the one
  functional dependency -- full suite re-run afterward, same 2 pre-existing
  failures, no new breakage), `src/main.py`'s docstring example, and
  `README.md` (all four `gaze_replay.jsonl` mentions, plus the "including
  click_static's own long-committed fixture" aside in the 0-hits note,
  which stopped being accurate the moment the file was regenerated).
  **Deliberately left untouched:** `docs/HANDOVER_GAZEPOINT.md` (explicitly
  version-pinned to an old commit, `4e7e592` -- a point-in-time onboarding
  snapshot, not a living usage doc) and the *prior*, already-dated log
  entries in this file and in `SPEC-2026-09-02.md` that mention
  `gaze_replay.jsonl` by its old name -- those describe actions genuinely
  taken against that filename at the time and stay accurate as historical
  record; only this new entry and current-usage docs reflect the rename.
