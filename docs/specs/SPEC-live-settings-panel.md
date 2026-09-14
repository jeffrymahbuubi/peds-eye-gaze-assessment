# SPEC-live-settings-panel — Live Settings & Debug Panel

**Status:** original scope (§1-§7), §8 (slider+readout widget), and §9
(regroup OperatorPanel into always-visible "Settings"/"Pacing" boxes) are
all implemented, live-validated via qt-mcp, and committed+pushed
(`89d0019`, `c988dba`, `b3b2a2f`).

**§10 (settings persistence across runs and days, 2026-09-11) is IMPLEMENTED and live-validated**, including the "subject returns another day" case proved across an app restart. It **reverses decision #2 of §2 and all of §5.6** ("no persistence"), which are superseded rather than wrong: they were written for a debugging panel, before the dashboard existed and before the panel became physician-facing. **§10.6 closes the last two open sub-questions** (§10.5.1 and §10.5.5), both answered by the user and built. **§10.7 (Tasks-page settings badge + Subject-ID autocomplete) is implemented and live-validated — see §10.9.** **§10.8's `showMaximized()` fix FAILED and is superseded by §10.10:** its height measurements were taken offscreen without fonts and understate the panel by ~100 px, so the panel never fit a maximized window at all; the real fix is a `QScrollArea` inside `OperatorPanel`, which also covers §10.8.4's standalone `MainWindow` case. **Read §10.10 before touching panel sizing — it carries two rules about how NOT to measure and validate Qt layout.** Nothing in this SPEC is open.
**Created:** 2026-09-04
**Last updated:** 2026-09-11 (§10.10 — §10.8's fix corrected and replaced with the scroll area)

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
2. **Persistence — SUPERSEDED by §10 (2026-09-11), see there.** UI-tweaked values are **session-only** — no write-back to
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

**Superseded 2026-09-07** — this Basic/Advanced-by-relevance grouping (and
its "starting proposal" caveat above) is replaced by a grouping-by-origin
scheme; see §9 for the current design. This section stays as an accurate
record of what was designed and built on 2026-09-04.

### 5.2 OperatorPanel: Basic section + collapsible Advanced section

`OperatorPanel` (`src/ui/operator_panel.py`) gains a `QGroupBox` (or a
`QToolBox`/collapsible `QGroupBox` with a checkable title, Qt's usual
pattern) titled "Advanced", collapsed by default, below the existing
Status/Controls boxes. Basic-group widgets stay where the dwell slider is
today; Advanced-group widgets are built the same way inside the collapsed
box. No change to the panel's existing Status display or Pause/Skip buttons.

**Superseded 2026-09-07** — the collapsed-by-default/checkable-to-expand
behavior described here is retired; both groups are now always visible.
See §9. This section stays as an accurate record of what was designed and
built on 2026-09-04.

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

### 5.6 No persistence (decision #2) — **SUPERSEDED by §10 (2026-09-11)**

> **Superseded.** §10 reverses this at the user's request: live and structural
> settings now persist per subject per task. The closing sentence below —
> "if a future session wants a 'Save as default' action, that is new scope" —
> is exactly what §10 is. The original text is kept so the reasoning stays
> traceable.

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

## 8. Slider + numeric-readout widget for every int/float setting (2026-09-07)

### 8.1 Origin: this closes a documented drift, it isn't new scope

§5.1 (line 126 above) already specified `OperatorPanel` should build
"checkbox for `bool`, slider+label for `float`/`int`" per field. The
implementation that shipped in the 2026-09-04 log entry below built
`QSpinBox`/`QDoubleSpinBox` for every `int`/`float` field instead —
`src/ui/operator_panel.py` still imports `QSlider` (line 23) but never
constructs one anywhere in the file. This substitution was never recorded
in this SPEC's log at the time it happened. `src/ui/task_settings_dialog.py`
(the pre-launch structural dialog, §5.3) never had a widget type specified
for it at all, and also ended up all spin boxes.

A GUI audit this session (cross-checked against the `qt-docs` and
`context7` MCP tools — see [[qt-docs-context7-complementary]]) surfaced
this gap. Separately, the user asked (same session) to replace up/down-arrow
spin boxes with sliders "since it's much more convenient" — this is that
same gap, from the user-experience side rather than the documentation-audit
side. Resolved together as one change: reconcile the implementation back
toward §5.1's original intent, extended to also cover the pre-launch
dialog, rather than treating it as unrelated new scope.

Confirmed via clarifying questions before drafting this section:

1. **Scope: both surfaces.** `OperatorPanel`'s mid-task `LIVE_SETTINGS`
   (`dwell.threshold_ms`, `dwell.refractory_ms`, `dwell.jitter_tolerance_px`,
   `dwell.smoothing.alpha`, `task.timeout_ms`,
   `task.inter_trial_interval_ms`, `motion.speed_frac_per_s`) **and**
   `TaskSettingsDialog`'s `STRUCTURAL_SETTINGS` (`trials`,
   `target.radius_px`, `layout.radius_px`, `grid.rows`, `grid.cols`,
   `layout.n_icons`, `motion.select_window_ms`) both move to the new
   widget. `bool`-kind fields (checkboxes) are unaffected.
2. **Widget pattern: paired slider + numeric readout, synced both ways** —
   not a bare slider. A slider alone would drop the precision a
   physician-facing dwell-threshold control plausibly needs; a spin box
   alone is what's being replaced. Qt's standard combo (slider for coarse
   drag, small spin box next to it for the exact value, each updating the
   other) keeps both.

This is a **presentation-only** change: no change to `LiveSetting`/
`StructuralSetting` (§5.1's dataclasses stay exactly as defined in
`settings_registry.py`, including every already-chosen min/max/step), no
change to `AssessmentApp._apply_setting`'s dotted-key dispatch, no change
to what values are offered or their ranges.

### 8.2 Int/float → slider mapping

`QSlider` (`PySide6.QtWidgets`) is integer-position-only — it has no native
float mode. Every `LiveSetting`/`StructuralSetting` already carries
`min`/`max`/`step` (required fields, per the existing dataclasses), which
gives a uniform mapping for both `"int"` and `"float"` kind entries without
new metadata:

```
slider.setMinimum(0)
slider.setMaximum(round((max - min) / step))
slider.setValue(round((value - min) / step))

# slider -> real value, on valueChanged(position):
value = min + position * step
```

For `"int"` fields this always lands on an exact integer (step is itself an
int, e.g. `dwell.threshold_ms`'s step of 50). For `"float"` fields (only
`dwell.smoothing.alpha`, step `0.05`, and `motion.speed_frac_per_s`, step
`0.05`) the same formula holds since `step` is a `float` already declared
on the dataclass — no new precision concerns beyond what the existing spin
boxes already had via `setSingleStep`/`setDecimals(2)`.

### 8.3 Shared widget, not duplicated sync logic

Both `OperatorPanel._build_control` and `TaskSettingsDialog._build_spin`
need the identical slider+readout pairing and identical bidirectional sync
(slider move → update readout without re-triggering the readout's own
signal → avoid an infinite feedback loop; readout edit → update slider
position the same way). `settings_registry.py` cannot host this widget — it
is deliberately PySide6-free (its own module docstring: "so it can be unit-
tested headlessly") and must stay that way.

**Proposed:** a new small module, `src/ui/slider_spin.py`, exporting one
`QWidget` subclass (name TBD at implementation time, e.g. `SliderSpinRow`)
that:

- Takes `kind` (`"int"`/`"float"`), `min`, `max`, `step`, and an initial
  value at construction (the same fields a `LiveSetting`/`StructuralSetting`
  already carries — the constructor can take the descriptor directly).
- Internally builds one `QSlider` (`Qt.Orientation.Horizontal` — already
  the default, matching every existing row's layout direction) plus one
  `QSpinBox` or `QDoubleSpinBox` (chosen by `kind`, mirroring today's
  `_build_spin`/`_build_control` branch), laid out in a row.
- Exposes a single `valueChanged` `Signal(object)` (int or float, matching
  the existing per-field signal shape already used for `setting_changed`)
  and `.value()`/`.setValue()`, so both call sites construct one instance
  per numeric field and connect exactly the way they connect a spin box
  today — no change to `_build_control`'s or `TaskSettingsDialog`'s
  surrounding wiring beyond swapping which widget gets built.
- Owns the slider↔spin-box sync internally (block the other widget's
  signal while applying a programmatic update — the standard Qt pattern
  for a two-widget mirrored value — so callers never see an intermediate
  or duplicate `valueChanged` emission).

### 8.4 Layout note (non-blocking)

`OperatorPanel` is fixed at 280px wide (`main_window.py`:
`operator_panel.setFixedWidth(280)`). A slider + label + numeric box all in
one row is tighter there than in `TaskSettingsDialog` (an unconstrained
modal). Suggested approach, consistent with today's `_build_control` row
layout: keep the field label on its own line, then the slider+spin-box pair
in a row beneath it (rather than trying to fit label+slider+box on one
line). Exact pixel/stretch tuning is left to implementation time and a
quick qt-mcp visual check — not a design fork worth blocking on.

### 8.5 Explicitly unchanged

- `settings_registry.py`'s data (every field's `min`/`max`/`step`/`label`/
  `group`/`applies_to`) — only how a value is *displayed and dragged*
  changes, not what's offered.
- `AssessmentApp._apply_setting`'s dispatch table and the `SETTING_CHANGED`
  event logging (§5.5) — both operate on `(key, value)` regardless of which
  widget produced `value`.
- Persistence behavior (§5.6, still session-only, no config write-back).

## 9. Regroup OperatorPanel by field origin; always visible, no collapse (2026-09-07)

### 9.1 Origin and what this supersedes

User feedback (this session), about `OperatorPanel` specifically — not
`TaskSettingsDialog` (§5.3/§8), which this section does not touch: having
to manually check "Advanced" to see its settings is unwanted friction, and
the Basic/Advanced split itself should be replaced with a grouping by where
each field's value actually comes from, not by a physician-facing/
debugging-relevance judgment. This supersedes §5.1's "Basic: physician-
relevant / Advanced: the user's own debugging" rationale and §5.2's
collapsed-by-default `QGroupBox` design (both left in place above, marked
superseded, per this project's log convention of not rewriting history).

Two decisions:

1. **Always visible.** No collapsed section, no checkbox-to-expand. Every
   field in both groups is shown the moment the panel is built, exactly
   like today's Basic group already behaves — nothing new to build for
   visibility, just removing the mechanism that currently hides Advanced.
2. **Regroup by dotted-key prefix, not by relevance tier:**
   - **"Settings"** (same title text as today's Basic box) — every
     `LiveSetting` whose `key` starts with `dwell.`. Concretely, all 8
     current dwell fields: `dwell.threshold_ms`, `dwell.refractory_ms`,
     `dwell.jitter_tolerance_px`, `dwell.visual_cursor`,
     `dwell.progress_ring`, `dwell.instant_feedback`,
     `dwell.smoothing.enabled`, `dwell.smoothing.alpha` — i.e. every field
     that lives under `configs/default.yaml`'s global `dwell:` block.
   - **"Pacing"** (renamed from "Advanced" — "Task Specific" was the
     working name during design; the user chose "Pacing" as more
     immediately meaningful on the panel itself) — every `LiveSetting`
     whose key does **not** start with `dwell.`: `task.timeout_ms`,
     `task.inter_trial_interval_ms`, and `motion.speed_frac_per_s` (still
     gated by `applies_to=("follow_moving",)`, unchanged). All three govern
     how fast or slow a trial moves along; they also happen to be exactly
     the fields that come from each task's own YAML config rather than the
     global `dwell:` block.

The rule is the dotted-key prefix, not an enumerated list — a future field
added to `LIVE_SETTINGS` self-sorts into the right box by which config
block it reads from, with no separate grouping decision needed.

### 9.2 What changes, concretely

- `settings_registry.py`: every `LiveSetting`'s `group` literal moves from
  `"basic"`/`"advanced"` to `"settings"` / `"pacing"`. No change to any
  `min`/`max`/`step`/`label`/`applies_to`/`kind` value — this is a
  regrouping + visibility change only, the same scope discipline §8 used
  for the widget-presentation change.
- `src/ui/operator_panel.py`: both boxes become plain `QGroupBox` — no
  `setCheckable(True)`, no `setChecked(False)`, no `toggled.connect(...)`.
  The `_set_advanced_visible` method and the `self._advanced_content`
  bookkeeping it exists solely to support are removed entirely, since
  nothing hides/shows children anymore. Box titles: "Settings" (unchanged
  text) and "Pacing" (renamed from "Advanced"). Every field is still built
  via `_build_control`/`SliderSpinRow` (§8) exactly as before — only which
  box it's added to, and whether that box can be collapsed, changes.

### 9.3 Explicitly unchanged

- `applies_to` per-task filtering (e.g. `motion.speed_frac_per_s` only for
  `follow_moving`) — same filtering, now inside an always-visible box
  instead of a collapsed one.
- The `SliderSpinRow` widget (§8) and its slider↔spin-box sync — every
  field still gets one; only its container box changes.
- `AssessmentApp._apply_setting`'s dispatch table, `SETTING_CHANGED` event
  logging (§5.5), and persistence behavior (§5.6, session-only).
- `TaskSettingsDialog` (§5.3/§8) — out of scope for this section entirely.

## 10. Settings persistence across runs and days (2026-09-11) — DESIGN ONLY, NOT BUILT

### 10.1 Origin, and what it reverses

**User feedback, 2026-09-11:** "suppose I did run 1 and adjust some settings like smoothing alpha, trial-timeout, Inter-Trial Interval (ms). Then I did run 2, the settings on that run 2 would revert back to the default settings. In a real-world, the physician may adjust the settings based on the subject condition, therefore, run 1 might be used for testing run for the settings, while subsequent run will be used for real data collection. Additionally, it would be better if a setting of each task is saved, therefore suppose a subject do another task in another day, physician can just load the setting."

**This directly reverses decision #2 of §2 and the whole of §5.6** ("UI-tweaked values are session-only — no write-back"). That decision is not being overturned because it was wrong when made: §5.6 was written for a *debugging* panel, before the dashboard existed and before the panel became physician-facing. The clinical workflow the user describes — a deliberate throwaway tuning run followed by data-collection runs — is a use case the original SPEC did not have. §5.6 should be read as superseded by this section, not as a mistake.

**The report is confirmed from the user's own session data**, which is stronger evidence than a code read. `SETTING_CHANGED` events in three consecutive `click_grid` runs on subject `TESTING`:

| Run | `dwell.smoothing.alpha` | `dwell.jitter_tolerance_px` |
|---|---|---|
| `..._click_grid_run1` | started **0.22** → ended 0.05 | — |
| `..._click_grid_run2` | started **0.22** (reverted) → 0.05 | started **40** → 100 |
| `..._click_grid_run3` | started **0.22** (reverted) → 0.05 | started **40** (reverted) → 0 |

The same tuning was performed from scratch three times. `0.22` is `configs/default.yaml`'s `dwell.smoothing.alpha`; `40` is its `jitter_tolerance_px`.

> **Audit note (2026-09-11):** those three session directories **no longer exist** — `sessions/` is gitignored and was cleared during later testing, so the raw `SETTING_CHANGED` records are not re-checkable from the repo. The table was read from them directly at the time. The finding does not depend on them: the same revert-to-defaults behaviour is proved by the code path in §10.2, and the fix is validated independently in §10.6.3.

### 10.2 What actually happens today — two different mechanisms, only one of which is broken

This distinction matters because the fix is not uniform, and the user's phrasing ("the settings") covers both.

**Structural settings (pre-launch "Settings" dialog) already persist — but only in memory, only per task, and only while the dashboard stays open.** `DashboardWindow._task_overrides` (`src/ui/dashboard_window.py:73`) is a `dict[str, dict]` keyed by `task_id`, written at `:175` when the dialog is accepted and read back at `:185` for every subsequent run. So run 2 *does* inherit run 1's radius or trial count. It is lost on app close, and it is not associated with a subject.

**Live settings (the OperatorPanel) do not persist at all.** `AssessmentApp` is constructed fresh per run (`dashboard_window.py:197-209`) and its only settings parameter is `structural_overrides=` — **there is no live-settings equivalent**. The panel re-derives every value from the merged config each run via `initial_live_values(config)` (`src/ui/settings_registry.py:243`). All three fields the user named (`dwell.smoothing.alpha`, `task.timeout_ms`, `task.inter_trial_interval_ms`) are `LIVE_SETTINGS`, which is why all three revert.

**The values are not actually lost today — they are just never read back.** `AssessmentApp._apply_setting` keeps the complete current live state in `self._live_values` and logs a `SETTING_CHANGED` event for every change (`src/app.py:393-394`, `:423`). The table in §10.1 was reconstructed from exactly that. So this is a missing *store and load path*, not missing data capture — and `self._live_values` is the natural thing to persist, since it is already the resolved, complete set.

### 10.3 Design (decisions taken with the user, 2026-09-11)

**Keyed per subject + per task** (`AskUserQuestion`). This mirrors the calibration precedent from `SPEC-gui-audit-2026-09-10.md` item 2b — `sessions/_calibrations/<subject_id>/calibration_{n}pt.json` — so the proposed location is `sessions/_settings/<subject_id>/<task_id>.json`. A per-task *global* profile was rejected on clinical grounds: one child's tuning silently becoming the next child's starting point is a protocol hazard, not a convenience.

**Auto-applied on the next run, with the fact made visible** (`AskUserQuestion`). A saved profile loads automatically — an explicit Load button was rejected because forgetting to press it is invisible and silently collects data under the wrong settings. The visibility requirement is the other half of the decision and is not optional: the run must show which profile is in effect and when it was saved, and offer a one-click **Reset to defaults**. Auto-apply without that indicator would be the worst of both options.

**Within a sitting, carry-over is automatic and needs no save.** Run 1's ending live values become run 2's starting values. This is the user's primary complaint and the part that must work with zero extra actions.

**Persistence covers both buckets.** Structural overrides are promoted from the in-memory `_task_overrides` dict to the same on-disk profile, so "the settings" means the same thing to the physician as it does to the code. `_task_overrides` remains the in-sitting cache; the file is what survives the app closing.

**Writes should be tolerant, like `local_state.py`.** `src/engine/local_state.py` already establishes the pattern this should follow: Qt-free so it is unit-testable headlessly, and treating a missing/empty/malformed file as "no history" rather than raising. A settings profile is a convenience, never a source of truth the app depends on — a corrupt one must degrade to defaults, not block a session.

### 10.4 Provenance — required, not optional (decided with the user)

**Today a run is not reproducible from its own output.** `metadata.json` records `subject_id`, `session_id`, calibration error and point count, `input_mode`, date, sex and notes — and **no settings at all** (verified against `sessions/2026-09-11_testing_scanning_run1/metadata.json`). Structural overrides are recorded nowhere; live values are recoverable only by replaying `SETTING_CHANGED` deltas against the YAML defaults, which requires knowing which YAML was in effect.

That gap is tolerable today only because settings reset to a known default every run. **§10.3 removes exactly that guarantee**, so persistence and provenance have to ship together: once settings carry across days, two runs of the same task on the same child can legitimately differ and nothing in the saved data would say how. The user agreed this is in scope.

**Requirement:** write the resolved effective settings — live and structural, after the profile is applied — into each run's `metadata.json`, alongside a marker of where they came from (defaults / carried within sitting / loaded profile + its save date).

### 10.5 Open questions for the implementing session

1. **RESOLVED (2026-09-11) — and the question largely dissolved once saving became explicit.** This was written assuming an auto-save at run end. With an explicit Save, a profile stores exactly what is on screen when the button is pressed, so "several tweaks past the good trials" is under the operator's control rather than the code's. What *was* genuinely left was narrower and is now fixed: the OperatorPanel's Save is only reachable **during** a run, yet a physician usually only knows a run's settings were right after seeing its hit rate and reaction times. A second Save action now sits on each Tasks card, enabled once that task has a finished run, saving that run's ending values — see §10.6.
2. **Whether saving is automatic at run end or an explicit action.** §10.3 settles *loading*; it does not settle writing. Auto-saving every run means a bad exploratory run overwrites a good profile; an explicit "Save settings for this subject" button cannot do that, but can be forgotten. Leaning explicit, for the same reason a physician would not want a throwaway tuning run to become the record — but this needs the user's call.
3. **Schema versioning of the profile file.** A profile written before a future `LIVE_SETTINGS` key is added or renamed must not break the run that loads it. Unknown keys should be ignored and missing keys fall back to config defaults; worth stating explicitly so it is not discovered by a crash.
4. **Whether `metadata.json`'s new settings block needs a `schema_version` bump.** It already carries `schema_version: 1`; adding a block is additive, but any downstream reader assumption should be checked before deciding.
5. **RESOLVED (2026-09-11) — asked, approved, and built.** A saved profile now records `calibration: {error_px, points}` and the panel names it when the profile is applied. See §10.6.

## 10.6 Closing §10.5.1 and §10.5.5 (2026-09-11)

Both were put back to the user rather than decided unilaterally, since §10.5 had explicitly flagged them as needing their call.

### 10.6.1 Saving is now possible *after* a run, not only during one (§10.5.1)

**The question mostly dissolved before it was answered.** §10.5.1 was written while auto-save-at-run-end was still on the table; once saving became an explicit action (§10.5.2), "what does a profile save" has a trivial answer — whatever is on screen when the button is pressed — and the worry about "several tweaks past the good trials" became the operator's call rather than the code's.

**What survived was narrower, and real:** the OperatorPanel's Save is only reachable **while a run is in progress**, because the panel is destroyed with the run view when the run ends. But the moment a physician actually *knows* a run's settings were right is after seeing its hit rate and reaction times.

**Built:** a second "Save Settings" button on each Tasks card, disabled until that task has a finished run this sitting, saving that run's ending values. It needed no new capture — `DashboardWindow._task_live_overrides[task_id]` already holds exactly those values from `_on_task_finished`. The button confirms in place ("Settings Saved ✓" plus a tooltip naming the file), because a silent write with no dialog and no other visible effect is indistinguishable from a dead button.

Both save paths write through the same `save_settings_profile`, so there is one on-disk format and one set of semantics regardless of which button was used.

### 10.6.2 A profile now records the calibration it was tuned under (§10.5.5)

**Built, and displayed.** `save_settings_profile` gained a `calibration` block (`{error_px, points}`); the OperatorPanel's indicator names it when a profile is applied — e.g. *"Loaded from this subject's saved profile (saved 2026-09-11). Tuned under 8px error, 5pt."*

**The reason it is worth the field:** settings tuned under a poor calibration may be compensating for bad tracking rather than suiting the child, and re-applying them under a good calibration would then be wrong. Nothing in the profile would otherwise say which case it was. It is **descriptive only** — nothing reads it back to change behaviour, so it cannot cause a surprise.

`format_calibration()` lives in `settings_registry.py`, not the panel, so it is testable without importing PySide6 (this module's existing no-Qt rule). It returns `""` rather than `"None px"` for a profile written before this change, which is the case the tests pin hardest.

### 10.6.3 Validation

Tests: **+5** (calibration stored and returned; a pre-§10.5.5 profile still loading with an empty block; and three `format_calibration` cases including the partial/unknown ones). Suite **181 collected, 180 passed, 1 pre-existing unrelated failure**, no regressions.

Live, via qt-mcp against the fake server:

| Check | Result |
|---|---|
| Before any run | All four cards' "Save Settings" **disabled** |
| After running `follow_moving` only | **Only that card's** button enabled; the other three still disabled |
| Pressing it | `sessions/_settings/CALTEST/follow_moving.json` written with the tuned 0.12 / 7500 **and** `calibration: {error_px: 8.42, points: 5}`; button confirmed in place |
| App restarted, fresh sitting, task run again | *"Loaded from this subject's saved profile (saved 2026-09-11). **Tuned under 8px error, 5pt.**"* with 0.12 / 7500 restored |

**Cleanup:** `CALTEST` session and profile directories deleted, both processes killed and ports confirmed closed, `configs/local_state.json` port restored 4251 → **4242**.

## 10.7 Cross-day profile loading: it already works — what is missing is being able to *see* it (2026-09-11) — IMPLEMENTED and live-validated (see §10.9)

### 10.7.1 The question, and the direct answer

**User:** "suppose on today 09/11 I did save a setting, then on 09/12 I want to do the task again, how the setting on 09/11 is loaded? Or this feature currently not explored?"

**It is explored and it works.** A profile is keyed by **subject + task only** — `sessions/_settings/<subject_id>/<task_id>.json` — with **no date anywhere in the path or the lookup**. `saved_at` is written into the payload but is only ever *recorded*, never compared: the clock is read in exactly one place in `settings_profile.py` — `datetime.now(timezone.utc)` at line 98, inside the write — and nothing anywhere reads a date back. The calendar day is irrelevant by construction.

Concretely, with the user's own real profile `sessions/_settings/JEFFRY/click_static.json` (`dwell.smoothing.alpha: 0.05`, `calibration: {error_px: 53.74, points: 5}`): on 09/12, entering Subject ID `JEFFRY` and pressing **Run** on Static Click loads it automatically, and the panel reads *"Loaded from this subject's saved profile (saved 2026-09-11). Tuned under 54px error, 5pt."*

This was already validated in §10.6.3 across a **full app restart**, which is the same code path a new day takes — the process cannot tell the difference.

**Precedence, unchanged (§10.3):** values carried from an earlier run *in the same sitting* beat a saved profile. On a fresh day nothing is carried, so the profile applies.

### 10.7.2 The real gap: the profile is invisible until the run has already started

Nothing on **Setup** or **Tasks** indicates a saved profile exists. The only place it is ever stated is the OperatorPanel's Settings-profile card — which does not exist until the task is already running and the child is already in front of the screen.

Two consequences, both silent rather than errors:

1. **No confirmation before starting.** On 09/12 the physician cannot check what will be applied, or which tasks even have a profile, without starting a run.
2. **A mistyped Subject ID silently falls back to defaults.** `subject_id()` is `subject_id_edit.text().strip()` from a plain `QLineEdit` (`setup_page.py:345`) — no completer, no history, no picker. `JEFFR` or `JEFFRY2` simply finds no profile and the run proceeds on task defaults with nothing said anywhere. The data is then collected under different settings than intended; `metadata.json` honestly records `source: defaults`, but only after the fact.

**This is not hypothetical — it has already happened in real use.** As of the 2026-09-11 audit the working copy contains **`sessions/_settings/tseting/click_grid.json`** alongside a `2026-09-11_tseting_click_grid_run1` session: a profile and a run stored under a mistyped `tseting`. Nothing warned at the time, and nothing would have warned later when the correctly-spelled subject silently loaded task defaults instead. The autocomplete half of §10.7.3 exists for exactly this artifact.

**Latent portability note:** subject IDs differing only in case (`jeffry` vs `JEFFRY`) resolve to the same directory on Windows' case-insensitive filesystem, so they happen to match today. On a case-sensitive filesystem they would not. Not a bug now — worth knowing before this ever runs off Windows.

### 10.7.3 Decision (`AskUserQuestion`, 2026-09-11): Tasks-card badge **and** Subject-ID autocomplete

Both halves were chosen together because either alone leaves one of §10.7.2's two failures open.

**A — per-task badge on the Tasks page.** Each card states, before Run is pressed, what will actually be applied — e.g. *"Profile saved · 5pt, 54px error"* vs *"Task defaults"*. Notes for the implementing session:

- Source it from `load_settings_profile(output_root, subject_id, task_id)` — the same call `_on_run_requested` already makes — so the badge cannot disagree with what the run does.
- **It must reflect precedence, not merely file existence.** If `_task_live_overrides` holds carried values for that task, the badge should say *carried*, because that is what will win (§10.3). A badge promising the profile while the run applies carried values would be worse than no badge at all.
- Refresh points: entering the Tasks page, any change to the Subject ID, and immediately after a save (§10.6.1 already updates that card's button).
- Reuse `format_calibration()` (`settings_registry.py`) for the calibration half so the wording matches the panel exactly.

**B — Subject-ID autocomplete on Setup.** A `QCompleter` on `subject_id_edit`, case-insensitive with inline completion, populated from the subject directories already on disk. A new helper (`known_subject_ids(output_root)`, natural home `settings_profile.py`) should union the directory names under `sessions/_settings/` and `sessions/_calibrations/` — the latter matters because a subject may have a saved calibration before they have a settings profile.

**Explicitly not decided here:** whether an unmatched Subject ID should warn more loudly than the badge simply reading "Task defaults". The badge makes the state visible, which was the ask; a harder block (for example, confirming an unknown subject) is a separate question and must not be added silently.

### 10.7.4 Not in scope

Profile *age* is deliberately **not** surfaced as a warning. `saved_at` is already shown when the profile loads, and a months-old profile is a legitimate clinical choice, not an error. Flagged so a later session does not add a staleness nag unasked.

## 10.8 The operator panel is clipped on first launch (2026-09-11) — the diagnosis here is PARTLY WRONG and the fix FAILED; superseded by §10.10

### 10.8.1 Reported

**User:** "when I launch first the GUI, the panel setting is overflow to fix it I minimize and maximize again the window." Evidence: `resources/images/task-ui/run-the-gui-for-first-time.png` (Settings-profile card cut off at the window edge, "Reset to defaults" half-drawn) and `.../fixed-the-setting-panel-overflow-with-minimize-and-maximize.png` (same window, everything visible).

> **CORRECTION (2026-09-11, see §10.10): the height figures in §10.8.2 and
> §10.8.3 below are WRONG — they understate the panel by ~100 px.** They were
> measured in a `QT_QPA_PLATFORM=offscreen` process, which has no fonts
> (`QFontDatabase: Cannot find font directory`), so every label and control
> measured short. The real requirement with the app's own Windows fonts is
> **989 px** (**1038** for `follow_moving`), against **980 px** available when
> maximized on this 1920×1080 machine. The panel therefore does **not** fit on
> this display at all, §10.8.3's "fits, 41–85 px spare" row is wrong, and
> `showMaximized()` could not fix this. The sections are left intact as the
> record of what was believed at the time; §10.10 has the corrected numbers and
> the real fix. **Do not re-measure this panel offscreen.**

### 10.8.2 Root cause — measured, not estimated

`OperatorPanel` is a plain `QVBoxLayout` of four cards plus a trailing `addStretch(1)`, at `setFixedWidth(280)`, with **no `QScrollArea` anywhere**. (`grep QScrollArea src/ui/*.py` returns only `setup_page.py` — §22's scroll area — plus `wtmh_theme.py:70`, which is that scroll area's QSS rule rather than a second widget. The operator panel has neither.) Measured heights at width 280:

| Card | Height |
|---|---:|
| Status + Live | 161 px |
| Controls | 126 px |
| Settings + Pacing | 412 px |
| **Settings profile** (added by §10.6) | **114 px** |
| margins (36) + spacing (42) | 78 px |
| **Total** | **891 px** (**935 px** for `follow_moving`, which has the extra motion-speed slider) |

**`minimumSizeHint().height() == sizeHint().height()` for every task** — the panel cannot compress by a single pixel. With no scroll area, whatever does not fit is simply clipped.

**The sequence that produces the screenshot:**

1. `dashboard_window.py:102` does `resize(1024, 800)` and line 367 calls plain `window.show()` — **the app never opens maximized.** At 1024×800 the panel column has roughly **713 px** against the 891 px needed, so it is clipped **at startup**.
2. The user maximizes. On this machine (`LG FULL HD`, `availableGeometry` **1920×1032**) the column then has about **976 px** — genuinely enough. But maximizing does not rebuild the already-clipped column, so it stays clipped.
3. Minimize → restore → maximize delivers the resize event that forces a real re-layout, and it fits.

**So the screenshot is not a capacity failure at maximized size** — there was room. It is a stale layout inherited from the 1024×800 startup geometry. The two problems are causally linked: the clipping is *created* at startup size, and maximizing fails to undo it.

**Attribution, stated plainly:** the 114 px Settings-profile card added in §10.6 is what pushed the column over. Without it the panel is ~763 px, which fits at maximized and only clipped at startup size. That card was validated by reading widget values through qt-mcp rather than by screenshotting the panel — exactly the check that would have caught this; see [[feedback-qt-mcp-maximize-before-validating]], whose point this round re-proves.

### 10.8.3 Decision (`AskUserQuestion`, 2026-09-11): open the dashboard maximized

`window.show()` → `window.showMaximized()` at `dashboard_window.py:367`. `resize(1024, 800)` stays as the restore-down geometry. The startup path that creates the clipping is then never entered, and on this machine the panel clears the column with **41–85 px to spare** (976 available vs 935 / 891 needed).

A `QScrollArea` on the panel column was offered as the more robust option and **declined in favour of the one-line change**. That is a defensible call for a clinic desktop app on a known 1920×1080 machine, and the measurement supports it.

**The accepted risk, quantified so it is not rediscovered by surprise.** `showMaximized()` fixes the symptom on *this* display; it creates no headroom, because the panel still cannot compress:

| Display / scaling | Column at maximized | Needed | Result |
|---|---:|---:|---|
| 1920×1080 @ 100% (this machine) | ~976 px | 891 / 935 | fits, 41–85 px spare |
| 1600×900 @ 100% | ~796 px | 891 / 935 | **clipped, silently** |
| 1366×768 @ 100% | ~664 px | 891 / 935 | **clipped, silently** |
| 1920×1080 @ **125%** Windows scaling | ~770 px logical | 891 / 935 | **clipped, silently** |

The 125% row is the one most likely to bite: Windows commonly defaults to 125% on 1080p laptops, and this app already documents a 100%-scaling assumption elsewhere (`SPEC-gui-audit-2026-09-10.md` item 5's known limitation). In every failing row there is **no scrollbar**, so the Settings-profile card and part of Pacing become unreachable with no indication anything is missing.

**Trigger for revisiting:** if the app is ever run on a shorter screen or above 100% scaling, or if a fifth card is added, the fix is the scroll area — and the pattern is already proven in this repo at `SPEC-ui-setup-task-selection.md` §22, including its two hard-won gotchas (§22.5's `QScrollArea.setWidget()` `autoFillBackground` black-background regression, and §22.6's app-wide themed scrollbar). Do not re-derive it.

### 10.8.4 A second occurrence this decision does **not** cover

`showMaximized()` is on `DashboardWindow`. The standalone `python -m src.main --task X --gui` path builds a `MainWindow` instead, and with `configs/default.yaml`'s `app.fullscreen: false` it calls `self.resize(1280, 800)` (`main_window.py`) — a column of roughly **790 px** against the same 891 / 935 px, i.e. **permanently clipped, with no scrollbar and no maximize step to rescue it.** Setting `app.fullscreen: true` avoids it via `showFullScreen()`.

Not fixed here because the report and the decision are both about the dashboard, and the standalone path is a developer entry point rather than the clinical one. Recorded so it is not mistaken for a new bug later.

## 10.9 §10.7 + §10.8 implemented (2026-09-11)

Both built exactly as decided, with one structural change not in the design.

### 10.9.1 §10.8 — one line, and it is the whole fix — **WRONG, see §10.10**

> **This subsection's conclusion is retracted.** The one-line change is still in
> place and still removes a real (if secondary) startup-geometry problem, but it
> did **not** fix the clipping, and the screenshot cited below could not have
> shown whether it did. §10.10 has the corrected measurements and the real fix.


`dashboard_window.py`'s `run_dashboard()` now calls `window.showMaximized()`
instead of `window.show()`; `resize(1024, 800)` stays as the restore-down
geometry, as §10.8.3 specified.

**Live-validated:** the app launched at **1920×1009** rather than 1024×800, and
a screenshot of the running `OperatorPanel` (280×989) showed **all four cards
complete** — Status, Controls, Settings+Pacing, and the §10.6 Settings-profile
card with both its buttons and its full indicator text. Nothing clipped, with
no minimize/restore/maximize step. This is the check §10.8.2 says should have
been run the first time.

The accepted risk in §10.8.3's table is unchanged — this fix creates no
headroom, it only avoids the startup geometry that was consuming it.

### 10.9.2 §10.7 B — Subject-ID autocomplete

New `known_subject_ids(output_root)` in `settings_profile.py` unions the
directory names under `_settings/` and `_calibrations/`, as specified. It
deliberately does **not** scan the dated run directories: those are named
`<date>_<subject>_<task>_run<N>`, so recovering a subject from one means
parsing a composite name, and any subject ID containing an underscore parses
wrong. The two dedicated directories are keyed by subject by construction.

`setup_page.py` puts a case-insensitive `QCompleter` (`MatchContains`) on
`subject_id_edit`, refreshed at build time, after a calibration is saved, and
after a settings profile is saved — so a subject entered today is offered for
the rest of the sitting without a restart.

**Live-validated:** typing `JEFF` opened a one-row completer popup (a separate
top-level `QListView`, 1739×22) — one row because `JEFFRY` is the only match
among the two subjects on disk.

### 10.9.3 §10.7 A — Tasks-page badge, and the structural change

Each `_TaskCard` gained a `settings_label` badge beside the existing status and
run-number labels: neutral "Task defaults", green "Profile saved · <calibration>",
accent "Carried from last run". No fixed width, unlike `status_label`, because
the calibration detail varies. Wording comes from `format_calibration()`, so it
matches the OperatorPanel exactly.

**The structural change, and the reason for it.** §10.7.3 said to source the
badge from the same `load_settings_profile` call `_on_run_requested` makes. That
is necessary but not sufficient — the *precedence* logic was also inline in
`_on_run_requested`, so the badge would have had to re-implement it, which is
exactly how a badge drifts from what the run does. Instead the precedence rule
was lifted out into **`resolve_settings_precedence()` in `settings_profile.py`**
(Qt-free), and `_on_run_requested` and the badge now both resolve through
`DashboardWindow._resolve_settings()`, which is a thin wrapper over it. One
code path, two callers — a structural guarantee rather than a convention.

The move also made the rule testable headlessly, which matters because the whole
suite is Qt-free by convention and a Qt-dependent test would have been the first.

Refresh points, as specified: entering the Tasks page (both the nav button and
"Continue to Tasks"), every Subject-ID keystroke (a new `SetupPage.subjectIdChanged`
signal), after a save, and additionally **after a run finishes** — that is when
`_task_live_overrides` changes, so a badge not refreshed there would keep
promising the profile after carried values had taken over.

**Live-validated, all three states, on the real dashboard:**

| Subject | Card | Badge |
|---|---|---|
| *(empty)* | all four | "Task defaults" (neutral) |
| `JEFFJEF` (a real mistype, made accidentally while testing) | all four | "Task defaults" — the §10.7.2 silent-fallback case, now visible |
| `JEFFRY` | Static Click | **"Profile saved · 54px error, 5pt"** (green), matching the real profile's 53.74px / 5pt |
| `JEFFRY` | other three | "Task defaults" |
| `BADGETEST` (a copy of JEFFRY's profile), **after running and ending Static Click** | Static Click | **"Carried from last run"** (accent) — while the profile file still exists on disk |

The last row is the one that matters: it is the precedence property §10.7.3
called out, and it is the only row that could not have been produced by
reporting file existence.

### 10.9.4 Not changed

§10.7.3's "explicitly not decided" stands — an unmatched Subject ID still gets
no warning louder than the badge reading "Task defaults". §10.7.4 stands too:
profile *age* is still not surfaced as a staleness warning. §10.8.4's standalone
`--task X --gui` `MainWindow` clipping is still not fixed, as decided.

## 10.10 §10.8's fix did not work, and its measurement was wrong (2026-09-11)

**User, after testing the build from §10.9:** "the live-settings still behave
overflow and the fix is I need to minimized than maximized the GUI" — i.e. the
symptom §10.8 was supposed to remove, unchanged.

### 10.10.1 The measurement §10.8 rested on was taken without fonts

§10.8.2's table (891 px, 935 for `follow_moving`) came from a headless
`QT_QPA_PLATFORM=offscreen` process. That platform plugin prints
`QFontDatabase: Cannot find font directory .../PySide6/lib/fonts` and falls back
to a stub, so **every label, button and spin box measures short**. Re-running the
identical measurement on the real Windows platform with Fusion applied, exactly
as the app runs:

| Task | §10.8.2 said (offscreen) | Real (Windows fonts) | Understated by |
|---|---:|---:|---:|
| click_static / click_grid / scanning | 891 | **989** | 98 |
| follow_moving | 935 | **1038** | 103 |

Available when maximized on this machine: work area **1032** − title bar **52**
= **980 px**. So **every task overflows** — `follow_moving` by 58 px — and
§10.8.3's "fits, 41–85 px spare" conclusion was never true. `showMaximized()`
addressed a startup-geometry problem that was real but not the binding one.

**Rule for this repo: never size-measure a widget under `QT_QPA_PLATFORM=offscreen`.**
Offscreen is still fine for *rendering* checks that don't depend on text metrics
(the §11 contrast work), but any `sizeHint`/`minimumSizeHint` number taken there
is not the number the app will use.

### 10.10.2 What was actually happening, measured live

During a `follow_moving` run, before the fix:

- `OperatorPanel.minimumSizeHint` height **1038**, and `minimumSizeHint ==
  sizeHint`, so it cannot give back a pixel
- `TaskRunView` and `QStackedWidget` therefore **1038**
- **`DashboardWindow` grew to 1920×1090** — on a 1080 px screen with a 1032 px
  work area

The window is *pushed past the screen edge* by its own layout minimum (the
auto-grow mechanism recorded in [[qt-mcp-tool-reference]]), so the bottom of the
panel sits below the desktop. Confirmed that a full minimize → maximize cycle
leaves it at **1090**: a window cannot shrink below its layout minimum, so
maximizing genuinely cannot fix it. Whatever the user's minimize/maximize was
doing, it was not restoring a correct layout.

### 10.10.3 The validation in §10.9.1 was invalid

§10.9.1 claimed the fix worked on the strength of a `qt_screenshot(ref=panel)`
showing all four cards. That call is `QWidget.grab()`, which **renders a widget
at its own full size into an offscreen pixmap** — it cannot show clipping by a
parent or by the screen edge, because neither is involved in the paint. A panel
that is 1038 px tall in a 957 px hole grabs as a complete 1038 px image.

The contradiction was already present in §10.9.1's own numbers — panel 989 inside
a window of 1009 with a 52 px title bar — and was not acted on. This is the same
family as the `WA_TranslucentBackground` blind spot in [[qt-mcp-tool-reference]],
and a second instance of the failure §10.8.2 owns for the original regression.

**Rule: to check whether something is clipped, screenshot the WINDOW, or compare
the widget's height against its parent's — never grab the widget alone.**

### 10.10.4 Fix: the QScrollArea, chosen by the user once the numbers were corrected

§10.8.3 had offered the scroll area and the user declined it in favour of the
one-liner — but that choice was made against the wrong numbers. Re-asked with
989/1038 vs 980 on the table, the user chose the scroll area.

Built **inside `OperatorPanel`**, not around it: the cards move into a scrolled
content widget and the panel's own layout holds only the `QScrollArea`. That
placement means **both** embedders are fixed by one change — `DashboardWindow`'s
`TaskRunView` and the standalone `--task X --gui` `MainWindow`, which is
§10.8.4's second occurrence, previously listed as out of scope.

Both §22 gotchas handled: `setWidget()`'s `autoFillBackground` is cleared on the
viewport **and** the content widget (the QSS rule reaches only the viewport), and
the scrollbar is themed **in the panel's own stylesheet** rather than relying on
`wtmh_theme.py`'s app-wide rule — the panel sets its own sheet and also runs
under `MainWindow`, which never installs the app-wide one.

**Result, measured the same way as the bug:**

| | Before | After |
|---|---:|---:|
| `OperatorPanel.minimumSizeHint` height | 989 / **1038** | **58** |
| `DashboardWindow` during a `follow_moving` run | 1920×**1090** | 1920×**1009** |
| `OperatorPanel` actual size | 280×1038 (overflowing) | 280×**957** (= the space available) |

**Live-validated**, this time against the window: a full-window screenshot shows
the dashboard fitting entirely inside 1009 px with the panel's canvas-matched
background intact and no black bands; the scrollbar reports `maximum: 81`, which
is exactly the 1038 − 957 overflow; and scrolling to the bottom brings the
Settings-profile card fully into view with both its buttons. Suite: **191
collected, 190 passed, 1 pre-existing unrelated failure** (the `target_fps`
drift).

**§10.8.3's risk table is now moot** — the panel no longer has a height it must
have, so a shorter screen or 125 % scaling degrades to scrolling rather than to
silent clipping.

## 11. Log

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
  rather than register hits. **Root-caused and fixed later the same
  session — see the dated entry near the end of this log, after the
  click_static rename below.**
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

- **2026-09-04, later still (after the rename, and after the settings-panel
  work above was committed as `89d0019`) — the "0 hits" issue root-caused
  and fixed (user asked to tackle it directly).** Traced frame-by-frame
  with a diagnostic script driving `DwellSelector`/`BaseTask.update()`
  directly against the fixture: `on_target` did fire (confirming
  hit-testing/geometry were fine), but `dwell_progress` never rose above 0
  -- meaning `DwellSelector.update()` was never even being called.
  `BaseTask.update()` only calls it when `self.input_mode == "eye"`
  (`src/tasks/base_task.py`); the committed default is `input.mode: eye`,
  but the **local, `skip-worktree`'d `configs/default.yaml`** (see
  [[peds-eye-gaze-assessment-config-skip-worktree-2026-09-03]]) had
  `mode: switch` -- left over from an unrelated switch-mode debugging
  session days earlier. `switch` mode requires an explicit click to select
  (documented in the file's own comment as "for setup testing"); dwell
  accumulation is skipped entirely, so no `--replay` fixture -- however
  well-built -- could ever produce a hit, in either headless or live-GUI
  mode. **Not a code defect anywhere in the dwell/replay/fixture pipeline.**
  Verified by temporarily overriding `input.mode` to `eye`: the exact same
  `gaze_replay_click_static.jsonl` fixture went from 0/13 hits to 16/19
  (84%) headlessly, and `test_click_static_records_hits` passed. This is
  also the root cause of that test's own previously-flagged, previously
  "not investigated" failure across multiple prior sessions -- it was never
  a pipeline regression, just this same local config drift, unnoticed until
  now because `skip-worktree` hides it from `git status`/`git diff`.
  **Fix applied, with the user's explicit go-ahead** (asked first, since
  this file is deliberately local-only and a past session's own convention
  is not to silently revert someone's skip-worktree edit): local
  `configs/default.yaml`'s `input.mode` flipped from `switch` back to
  `eye`. Confirmed live via qt-mcp: launched `click_static --gui --replay`
  with the fix in place, watched trial progression go from ~8.8s/trial
  (constant timeouts, as in every session before this fix) to ~2.4s/trial
  (real dwell completions); a clean session close (`Escape`) showed 12/13
  hits (92%) in `trials.csv`. Full test suite: down to **one** remaining
  pre-existing failure, `test_config_merges_task_over_default` (the
  separate, already-documented `target_fps: 60` vs `150` stale assertion,
  unrelated to input mode -- not touched, still a one-line fix for whoever
  picks it up next). `README.md`'s replay section rewritten from "hits are
  currently unreliable" to a troubleshooting note pointing straight at
  `input.mode`, since a future session hitting this same symptom now has an
  immediate, correct answer instead of re-diagnosing from scratch.
  **This is a config-only fix** -- `configs/default.yaml` is
  `skip-worktree`'d, so nothing here shows in `git status`/`git diff` or
  needs a commit; only the `README.md`/this SPEC's documentation updates
  are real, committable changes from this entry. Committed and pushed as
  `c988dba` (`/sparc:devops`). **Everything in this SPEC is now on
  `origin/main`; nothing outstanding.**

- **2026-09-07 — design-only session for §8 (slider+readout widget),
  `/sparc:orchestrator`, explicit instruction: update this SPEC before
  implementing.** Triggered by two things together: a GUI audit this
  session (Qt/PySide6 best practices, verified live against the newly
  added `qt-docs` and `context7` MCP tools — see
  [[qt-docs-context7-complementary]]) found that §5.1's original
  "slider+label for float/int" design was never actually built —
  `src/ui/operator_panel.py` ships `QSpinBox`/`QDoubleSpinBox` instead, with
  an unused leftover `QSlider` import — and separately the user asked to
  replace up/down-arrow spin boxes with sliders across task settings.
  Both are the same gap. Two clarifying questions resolved the scope: (1)
  both `OperatorPanel` live settings and `TaskSettingsDialog` pre-launch
  settings get sliders, not just one; (2) paired slider + numeric readout,
  not a bare slider, to keep exact-value precision. §8 documents the
  int/float→slider mapping (reusing each setting's existing min/max/step,
  no new metadata), a proposed shared `src/ui/slider_spin.py` widget to
  avoid duplicating slider↔spin-box sync logic between the two call sites,
  and a non-blocking layout note for `OperatorPanel`'s fixed 280px width.
  **No code changed this session** — `settings_registry.py`,
  `operator_panel.py`, `task_settings_dialog.py`, and `app.py` are all
  untouched; implementation is the next step.

- **2026-09-07, later the same day — §8 implemented and live-validated.**
  New: `src/ui/slider_spin.py` (`SliderSpinRow`, exactly as designed in
  §8.2/§8.3 — internal `QSlider` + `QSpinBox`/`QDoubleSpinBox` by `kind`,
  `blockSignals` on the non-originating widget during a programmatic update
  to avoid feedback loops, single `valueChanged(object)` Signal,
  `.value()`/`.setValue()`). Changed: `src/ui/operator_panel.py`'s
  `_build_control` and `src/ui/task_settings_dialog.py`'s
  `_build_spin`→`_build_control` both now construct a `SliderSpinRow`
  instead of a bare spin box; both files' now-unused `QSpinBox`/
  `QDoubleSpinBox`/`QSlider` imports removed. No change to
  `settings_registry.py`'s data or `AssessmentApp._apply_setting`'s
  dispatch, per §8.5.
  **Tests:** full suite — same single pre-existing failure as before
  (`test_config_merges_task_over_default`, unrelated stale `target_fps`
  assertion), no new regressions.
  **qt-mcp live validation** (real running GUI, `click_static --gui
  --replay tests/fixtures/gaze_replay_click_static.jsonl`, `QT_MCP_PROBE=1`):
  `TaskSettingsDialog` showed both structural fields (`trials`,
  `target.radius_px`) as `SliderSpinRow`s with correct YAML defaults (32,
  90); setting the spin box to 18 moved the slider to the matching
  position, and moving the slider to position 40 correctly produced value
  41 (`min=1, step=1` → `1 + 40*1`), confirming §8.2's mapping in both
  directions. "Start task" proceeded normally into `MainWindow`.
  `OperatorPanel`'s Basic group showed `dwell.threshold_ms` as a
  `SliderSpinRow` (800ms default); expanding Advanced showed all 5
  Advanced numeric fields as `SliderSpinRow`s with correct defaults,
  including `dwell.smoothing.alpha` correctly using a `QDoubleSpinBox`
  (0.35) — confirming the `"float"` branch works through the shared widget,
  not just `"int"`. Changing the threshold slider to 1200 produced a
  `SETTING_CHANGED` event in `events.jsonl`
  (`{"key": "dwell.threshold_ms", "old_value": 800, "new_value": 1200}`),
  confirming the full path (slider → `SliderSpinRow.valueChanged` →
  `OperatorPanel.setting_changed` → `AssessmentApp._apply_setting` →
  recorder) still works unchanged end-to-end. App closed cleanly via
  `Escape` (exit code 0), no Qt warnings.
  **Not done yet:** committing this work (matching the project's pattern of
  asking before commit+push).

- **2026-09-07, later still — §9 design session, `/sparc:orchestrator`,
  explicit instruction: update this SPEC first, implement only after the
  user says "go ahead."** User feedback on `OperatorPanel` specifically:
  (1) stop requiring a manual check of "Advanced" to see its settings —
  show everything always; (2) regroup by where a field's value comes from
  rather than by physician/debug relevance — "Settings" becomes every
  `dwell.*` field (all 8, not just the 4 that were "Basic"), "Task
  Specific" (replacing "Advanced") becomes everything else
  (`task.timeout_ms`, `task.inter_trial_interval_ms`,
  `motion.speed_frac_per_s`). §9 documents the dwell-prefix rule, the
  `settings_registry.py`/`operator_panel.py` changes this implies, and
  marks §5.1/§5.2's original Basic/Advanced design as superseded (their
  text is left intact as historical record, per this doc's own
  convention). `TaskSettingsDialog` is explicitly out of scope for this
  change. **No code changed this session** — `settings_registry.py` and
  `operator_panel.py` are both untouched; implementation is pending the
  user's "go ahead."

- **2026-09-07, later still — §9 implemented and live-validated.** User
  was asked whether "Task Specific" had a better name; picked **"Pacing"**
  (over "Timing," which fit `task.timeout_ms`/`task.inter_trial_interval_ms`
  but not `motion.speed_frac_per_s`, a speed rather than a duration) and
  said go ahead. §9's text above updated throughout to say "Pacing"
  instead of the working name "Task Specific."
  **Changed:** `src/ui/settings_registry.py` — every `LiveSetting`'s
  `group` moved from `"basic"`/`"advanced"` to `"settings"` (all 8
  `dwell.*` fields) / `"pacing"` (`task.timeout_ms`,
  `task.inter_trial_interval_ms`, `motion.speed_frac_per_s`); no
  `min`/`max`/`step`/`label`/`applies_to`/`kind` value touched.
  `src/ui/operator_panel.py` — `_build_control`'s call sites now filter on
  `"settings"`/`"pacing"`; both boxes are now plain `QGroupBox("Settings")`
  / `QGroupBox("Pacing")` with no `setCheckable`/`setChecked`/`toggled`
  wiring; `_set_advanced_visible` and `self._advanced_content` removed
  entirely (confirmed no other file referenced them). Module docstring
  updated to describe the new two-group-by-origin design instead of the
  superseded Basic/Advanced-by-relevance one.
  **Tests:** full suite — same single pre-existing failure
  (`test_config_merges_task_over_default`), no new regressions.
  **qt-mcp live validation** (`click_static --gui --replay
  tests/fixtures/gaze_replay_click_static.jsonl --skip-task-settings`,
  `QT_MCP_PROBE=1`): `qt_snapshot` of `OperatorPanel` showed all 8 dwell
  fields under "Settings" and both applicable pacing fields
  (`task.timeout_ms`, `task.inter_trial_interval_ms`) under "Pacing" —
  `motion.speed_frac_per_s` correctly absent (click_static isn't
  follow_moving) — with **no `[hidden]`/`[disabled]` flags anywhere** in
  the tree, confirming the collapse mechanism is fully gone, not just
  visually. Changed `dwell.jitter_tolerance_px`'s slider to 60 live;
  `events.jsonl` recorded
  `{"key": "dwell.jitter_tolerance_px", "old_value": 40, "new_value": 60}`,
  confirming `AssessmentApp._apply_setting`'s dispatch is unaffected by the
  regroup. App closed cleanly via `Escape` (exit code 0).
  **Not done yet:** committing this work (matching the project's pattern of
  asking before commit+push) — this and §8's still-uncommitted slider work
  can be committed together.

- **2026-09-11 — §10 added: settings persistence across runs and days. DESIGN ONLY, no code changed** (`git status` shows only doc edits; `main` level with `origin/main` at `36f0fd1`), per the user's explicit instruction that this round produces a SPEC to review before any implementation. The report was **confirmed from the user's own session data rather than only from a code read** — `SETTING_CHANGED` events across three consecutive `click_grid` runs show the identical tuning performed from scratch three times (§10.1 table). Diagnosis found the user's "the settings" actually spans **two mechanisms that behave differently** (§10.2): structural overrides already survive run→run in `DashboardWindow._task_overrides` but die with the app and are not per-subject, while live settings have **no persistence path at all** — `AssessmentApp`'s only settings parameter is `structural_overrides=`. Also established that the values are *already captured* in `AssessmentApp._live_values` and logged per change, so this is a missing store/load path, not missing instrumentation. Four decisions taken via `AskUserQuestion`: per-subject+per-task keying (mirroring the `sessions/_calibrations/<subject_id>/` precedent), auto-apply with a visible indicator and a Reset action, automatic carry-over within a sitting, and **provenance in scope** — §10.4 found that `metadata.json` records no settings at all today, which is only safe because settings currently reset every run; persistence removes that guarantee, so the two must ship together. This section **explicitly supersedes decision #2 of §2 and §5.6**, which are annotated in place rather than deleted. Five open questions left for the implementing session (§10.5), the sharpest being whether saving a profile is automatic at run end or an explicit action — §10.3 settled loading but deliberately did **not** settle writing.

- **2026-09-11, later — §10 IMPLEMENTED and live-validated end-to-end. The two questions §10.5 left open were put back to the user and answered before any code was written.**

  **Decided this round:** profiles are written by an **explicit "Save for this subject" action**, never automatically at run end (§10.5.2) — an exploratory run must not be able to overwrite a profile that was working. (The second question put to the user in the same round belongs to `SPEC-follow-moving-selection.md` §6.3 and was approved there.)

  **What was built.** New `src/engine/settings_profile.py` — Qt-free and tolerant in the same way as `local_state.py`, so a missing/empty/malformed/wrong-shaped profile degrades to "no profile" and the run proceeds on defaults. Path: `sessions/_settings/<subject_id>/<task_id>.json`, mirroring `sessions/_calibrations/<subject_id>/`. `AssessmentApp` gained `live_overrides` / `settings_source` / `settings_saved_at`; the overrides are applied to the **config** (via a new `apply_live_values_to_config`) rather than only to `_live_values`, so `build_task()`, the engine objects and the panel cannot disagree — `_live_values` is derived from the config immediately afterwards. `DashboardWindow` gained `_task_live_overrides`, captured from the finished run's own `_live_values`, with precedence **carried-in-sitting > saved profile > defaults**. `OperatorPanel` gained a "Settings profile" card: the source indicator, "Save for this subject", and "Reset to defaults".

  **The `motion.*` trap, worth recording.** `apply_live_values_to_config` could not be a generic `set_nested`: the live keys say `motion.speed_frac_per_s` but the value is read from `config["task"]["motion"]`. It is the exact inverse of `initial_live_values` and is kept beside it for that reason — a mismatch would silently drop a restored setting rather than fail. Two tests pin this specifically.

  **Reset routes through the panel, not the engine**, so the controls move too and each key still goes through `_apply_setting` and is logged as a `SETTING_CHANGED` — a reset is a real change to the run and belongs in the record like any other.

  **§10.4 provenance shipped**, with one clarification worth stating: the `metadata.json` `settings` block is a snapshot **as resolved at run start**, deliberately not mutated afterwards, because a mid-run change is already recorded with its timestamp as a `SETTING_CHANGED` event. Start state plus the event stream reconstructs the settings at any moment; a single mutated block could not. `schema_version` is **not** bumped — the block is purely additive and every existing reader takes named keys (§10.5.4 resolved).

  **Live validation** (dashboard + `tools/fake_gazepoint_server.py`, driven via qt-mcp), covering each decision separately:

  | Check | Result |
  |---|---|
  | Run 1 with no profile | "Using task defaults." |
  | Tuned `alpha` 0.22→**0.05**, `timeout_ms` 12000→**9000**, ended run, started run 2 | Run 2 opened at **0.05 / 9000**, labelled "Carried over from the previous run in this session." |
  | "Save for this subject" | `sessions/_settings/SETTEST/follow_moving.json` written with the tuned values; label switched to the profile wording with its date |
  | "Reset to defaults" | Controls returned to **0.22 / 12000**, label back to "Using task defaults." |
  | **App killed and relaunched** (a genuinely fresh sitting, so carry-over is impossible) | Profile **auto-loaded**: 0.05 / 9000, "Loaded from this subject's saved profile (saved 2026-09-11)." |
  | `metadata.json` across the three runs | `source` recorded as `defaults` → `carried` → `profile`, each with the matching values and the profile's save timestamp |

  The relaunch is the row that actually proves the user's "subject comes back another day" requirement — everything above it could in principle have been satisfied by in-memory carry-over alone.

  **Tests: 9 new in `tests/test_settings_profile.py`** (round-trip, per-subject and per-task isolation, missing/malformed/wrong-shape degradation, replace-not-accumulate, the `initial_live_values` round-trip, the `motion.*` placement trap, and unknown-key tolerance). Suite: **176 collected, 175 passed, 1 pre-existing unrelated failure** (`test_config_merges_task_over_default`, the long-known local `target_fps` drift), no regressions.

  **Cleanup:** the three `SETTEST` QA session directories and `sessions/_settings/SETTEST` were deleted, both test processes killed and their ports confirmed closed, and `configs/local_state.json`'s port restored from the fake server's 4250 back to **4242** — the exact stale-port class that caused the 2026-09-09 calibration crash. **Not yet committed.**

  **Still open (§10.5.1, §10.5.5):** what a profile should save when a setting was changed mid-trial (it currently saves the values as shown when Save is pressed, which is the simple and probably right answer but was not put to the user), and whether a profile should record the calibration quality it was tuned under — flagged, deliberately not built.

- **2026-09-11, later still — §10.5.1 and §10.5.5 closed; see §10.6.** Both were put back to the user rather than decided unilaterally. §10.5.1 turned out to be **largely dissolved by the earlier explicit-Save decision** — what actually remained was that Save was only reachable *during* a run, which is the wrong moment to judge a run; a second Save action now sits on each Tasks card, enabled once that task has a finished run, reusing the values `_task_live_overrides` already holds. §10.5.5 was approved and built: a profile records `calibration: {error_px, points}` and the panel names it when the profile is applied ("Tuned under 8px error, 5pt"), descriptive only. `format_calibration()` deliberately lives in `settings_registry.py` rather than the panel so it stays testable without PySide6, and returns `""` rather than `"None px"` for profiles written before the change. **+5 tests; suite 181 collected, 180 passed, 1 pre-existing unrelated failure, no regressions.** Live-validated via qt-mcp end to end, including the per-card enable/disable behaviour (only the task actually run becomes saveable) and an app restart proving the calibration line appears on a genuinely fresh sitting. QA artifacts deleted, processes killed, `local_state.json` port restored to 4242. **Nothing in §10 is open any more. Not yet committed.**

- **2026-09-11, later still — two new items raised after the user tested the GUI. DIAGNOSIS + DESIGN ONLY, no code changed** (`git status` unchanged from the previous entry), on the user's explicit instruction that this round finds solutions and writes them up for a later session. **§10.7 — cross-day loading:** answered directly, it already works and was already proved in §10.6.3 across an app restart, which is the same code path a new day takes; profiles are keyed by subject+task with **no date in the path or the lookup**, and `datetime` appears exactly once in `settings_profile.py`, in the write. The real gap found is that the profile is **invisible until the run has already started**, and a mistyped Subject ID silently falls back to defaults through a plain `QLineEdit` with no completer. Decided: a per-task Tasks-page badge **and** Subject-ID autocomplete — both, because either alone leaves one failure open; the badge must reflect **precedence** (carried-in-sitting beats profile), not mere file existence. **§10.8 — panel clipping:** measured rather than guessed — the panel needs **891 px** (935 for `follow_moving`) and `minimumSizeHint == sizeHint`, so it cannot compress at all, and there is no `QScrollArea` anywhere in it. The user's screenshot is **not** a capacity failure: the clipping is created at the `resize(1024, 800)` + plain `show()` startup geometry (~713 px available), and maximizing to this machine's real ~976 px column does not rebuild the already-clipped layout — minimize/restore/maximize supplies the resize event that does. Decided: **`showMaximized()` only** (one line at `dashboard_window.py:367`); the scroll-area option was offered and declined, and §10.8.3 quantifies the accepted risk by screen size and OS scaling so it is not rediscovered by surprise — the 125%-scaling row is the likely one. **Owned:** the 114 px Settings-profile card added in §10.6 is what pushed the column over, and it was validated by reading widget values via qt-mcp rather than screenshotting the panel — the exact check that would have caught it. §10.8.4 records a second occurrence the chosen fix does not cover (the standalone `--task X --gui` `MainWindow` at `resize(1280, 800)` with `app.fullscreen: false`).

- **2026-09-11, evening — §10.7 implemented and live-validated; §10.8 implemented but its validation was WRONG (see the next entry and §10.10); see §10.9.** Both built as decided. §10.8 is the single `show()` → `showMaximized()` line, and the app now opens at 1920×1009 with the full 280×989 `OperatorPanel` rendering all four cards — validated **by screenshotting the panel**, which is the check §10.8.2 admits was skipped the first time and would have caught the regression. **That last clause is exactly the error: `qt_screenshot(ref=panel)` is `QWidget.grab()` and cannot show clipping at all — the panel was still overflowing. Retracted; see §10.10.3.** §10.7 B added `known_subject_ids()` (unioning `_settings/` and `_calibrations/`, deliberately not parsing the composite run-directory names) behind a case-insensitive `QCompleter`, refreshed after a saved calibration or profile as well as at build time. §10.7 A added the per-card badge.

  **One structural change beyond the design, and it is the substantive part of this round.** §10.7.3 said to source the badge from the same `load_settings_profile` call the run makes — necessary, but the *precedence* logic was still inline in `_on_run_requested`, so the badge would have had to re-implement it. The rule was instead lifted into Qt-free **`resolve_settings_precedence()`** in `settings_profile.py`, with `_on_run_requested` and the badge both resolving through a thin `DashboardWindow._resolve_settings()` wrapper. That turns "the badge cannot disagree with the run" from a convention into one code path with two callers, and makes the rule testable headlessly — which the Qt-free test suite required.

  **Live-validated on the real dashboard, all three badge states (§10.9.3 table),** including the row that actually discriminates: with subject `BADGETEST` (a copy of JEFFRY's profile) the badge read "Profile saved · 54px error, 5pt", and after running and ending Static Click it flipped to **"Carried from last run"** while the profile file was still on disk. A badge reporting mere file existence could not produce that row. An accidental real mistype during testing (`JEFFJEF`) also produced "Task defaults" on all four cards — the §10.7.2 silent-fallback case, now visible before a run rather than only afterwards in `metadata.json`.

  **Tests: +10** in `tests/test_settings_profile.py` — 7 on `resolve_settings_precedence` (carried beats a profile; profile applies when nothing was carried; neither is defaults; an *empty* profile file is `defaults` not `profile`, so `source` names what the run uses rather than what exists; a structural-only profile still counts; an explicit Settings-dialog choice outranks the profile's structural block; structural overrides survive the carried branch) and 3 on `known_subject_ids` (the union, the empty/missing root, and ignoring loose files). Suite: **191 collected, 190 passed, 1 pre-existing unrelated failure** (the long-known `target_fps` drift), no regressions.

  **Cleanup:** `BADGETEST` profile and session directory deleted, the dashboard and `tools/fake_gazepoint_server.py` processes killed with ports 4250/9142 confirmed closed, and `configs/local_state.json` restored from the fake server's 4250 back to **4242** — the same stale-port class as the 2026-09-09 calibration crash.

  **SUPERSEDED IN PART, same day — §10.9.1's claim that §10.8 fixed the panel clipping is WRONG; see the entry below and §10.10.** The §10.7 badge and autocomplete work in this entry stands.

- **2026-09-11, evening (later) — the user reported the overflow was still there, and they were right. §10.8's fix could never have worked, and §10.9.1's validation of it was invalid. Root-caused, corrected, and refixed with the QScrollArea; see §10.10.** Two compounding mistakes, both mine. **(1) The measurement was taken without fonts.** §10.8.2's 891/935 came from a `QT_QPA_PLATFORM=offscreen` process, which has no font directory and so measures every control short; the real requirement on the Windows platform is **989 px (1038 for `follow_moving`)** against **980 px** available when maximized — so the panel does not fit on a 1920×1080 screen at all, and §10.8.3's "fits, 41–85 px spare" was never true. **(2) The validation could not have detected the failure.** §10.9.1 screenshotted the panel alone via `qt_screenshot(ref=...)`, i.e. `QWidget.grab()`, which renders a widget at its own full size and structurally cannot show clipping by a parent or the screen edge — and §10.9.1's own numbers (panel 989 inside a 957 px hole) already contained the contradiction unnoticed. Measured live before the fix: panel `minimumSizeHint` 1038 with `minimumSizeHint == sizeHint`, `QStackedWidget` 1038, and **`DashboardWindow` grown to 1920×1090 on a 1080 px screen**, staying at 1090 through a full minimize→maximize cycle because a window cannot shrink below its layout minimum. **Fix:** the `QScrollArea` §10.8.3 had offered and the user had declined against the wrong numbers — re-asked with the corrected figures, they chose it. Built *inside* `OperatorPanel` rather than around it, so it also fixes §10.8.4's standalone `MainWindow` occurrence, previously out of scope. Both `SPEC-ui-setup-task-selection.md` §22 gotchas handled (`autoFillBackground` cleared on viewport *and* content widget; scrollbar themed in the panel's own sheet, since `MainWindow` never installs the app-wide one). **Result:** panel `minimumSizeHint` **1038 → 58**, window **1090 → 1009**, panel sized **957** = exactly the space available, scrollbar `maximum: 81` = exactly the former overflow, and the Settings-profile card reachable by scrolling. Validated against a **full-window** screenshot this time. Suite **191 collected, 190 passed, 1 pre-existing unrelated failure**. Two rules recorded in §10.10 for future sessions: never take a size measurement under `offscreen`, and never judge clipping from a `grab()` of the widget alone.
