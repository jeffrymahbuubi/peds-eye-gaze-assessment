# SPEC-live-settings-panel — Live Settings & Debug Panel

**Status:** original scope (§1-§7), §8 (slider+readout widget), and §9
(regroup OperatorPanel into always-visible "Settings"/"Pacing" boxes) are
all implemented, live-validated via qt-mcp, and committed+pushed
(`89d0019`, `c988dba`, `b3b2a2f`). **Everything in this SPEC is now on
`origin/main`; nothing outstanding.**
**Created:** 2026-09-04
**Last updated:** 2026-09-07

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

## 10. Log

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
