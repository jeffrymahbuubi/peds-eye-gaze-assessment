# SPEC-diki-design-audit — Colleague Codebase Audit: Task Design & Design System

**Status:** audit (S1-S7) complete, documentation only. **Superseded-forward
note (2026-09-07):** S3's entire `scene_spec()` mechanism — all four tasks,
not just the `scanning` pilot — has since been implemented, live-validated
via qt-mcp, and committed+pushed to `origin/main`; see
`docs/specs/SPEC-scanning-task-design-port.md` for that work. **S8 (new,
2026-09-07) is a separate, already-implemented-and-live-validated port**:
diki's live Trial/Dwell panel into `dev/`'s `OperatorPanel` sidebar. **§8.10
(2026-09-08) is the current state** — the sidebar (still in its own side
column, not a canvas overlay) is now three semi-transparent dark-slate HUD
cards, rounded and drop-shadowed, inset from the window edges and sized to
their content, on a column background matched to the canvas's own colour so
the inset blends rather than reading as a second panel; §8.9's five-card
recolour (still accurate as this round's starting point) is what it was
built from. Not yet committed. S4 (design system/palette) and S5
(window-structure notes) remain reference-only for everywhere else in
`dev/`.
**Created:** 2026-09-07
**Last updated:** 2026-09-08

## 1. Origin / what was asked

A colleague on the same project produced a parallel version of this codebase
at `D:\RESEARCH ASSISTANT\50-Gaze-Point-Project\resources\diki`, focused on
fixing **task design** (the user has already reviewed and agrees with the
result) and containing a **design system** the user wants as a visual/UX
reference, since the current app (`dev/peds-eye-gaze-assessment`) is
functionally solid but aesthetically weak.

**Explicit scope for this audit** (user's own words): only task design, the
design system, and UI/UX — everything else (live-settings wiring, calibration
protocol internals, data recording, etc.) is out of scope because that side of
the project is owned by the user's own `dev/` codebase, which has already
diverged and moved ahead of `diki` on those fronts (see
[[peds-eye-gaze-assessment-live-settings-panel-2026-09-04]] and related memory
— `dev/`'s live-settings panel, n=1-9 calibration, calibration-file reuse,
gaze smoothing, etc. have no equivalent in `diki` and are not revisited here).

**UX, as the user defined it for this task:** the app is three steps —
window 1 (subject info + calibration), window 2 (task selection), window 3
(task result). `diki` implements this as three tabs of one dashboard window
(not three literal `QMainWindow`s) — see §5.

## 2. Method

Read every file under `resources/diki` that touches rendering, layout, styling,
or task-trial logic (`ui/*.py`, `tasks/*.py`, plus `engine/config.py` and
`engine/feedback.py` for how theme/config feed the UI). Explicitly **not**
read in depth, as out of scope: `engine/session.py`, `engine/calibration.py`'s
wire-protocol internals, `data/*.py`, `inputs/*.py`, `analysis/*.py`,
`ui/task_video_recorder.py` — these are orchestration/data/hardware logic, not
task design or UI/UX. Calibration is mentioned in §5 only insofar as it
shapes window 1's on-screen flow and copy, not its OpenGaze protocol
implementation.

**Known gap in what's on disk:** `resources/diki` as given contains no
`configs/`, `themes/`, `tests/`, or plan/README document — `engine/config.py`
expects a sibling `configs/` two directories up (default.yaml, `configs/tasks/
*.yaml`, `configs/themes/*.yaml`) that isn't present in this copy. This audit
therefore documents the **theme contract** (what keys a theme dict must
supply) from how `ui/canvas.py` and `app.py` consume it, not the actual
`forest` theme's values — those aren't available to inspect. Task-tunable
parameters are documented from each task's `.get(key, default)` calls, which
give accurate defaults but not whatever `diki`'s own task YAMLs override them
to. If the colleague can share the missing `configs/`/`themes/` directory,
this SPEC should be updated with the real values.

## 3. Task design

All four tasks subclass `tasks/base_task.py:BaseTask`, which runs a per-frame
state machine identical in shape to `dev/`'s own `BaseTask` (`SHOW_TARGET →
WAIT_INPUT → HIT/MISS/TIMEOUT → ITI → next`), so the trial lifecycle itself is
not new. What differs, and is genuinely worth porting, is **each task's own
target-layout math** and a new **`scene_spec()` contract** that tells the
canvas how to draw the whole paradigm, not just the active target.

### 3.1 `scene_spec()` — the key new abstraction

`BaseTask.scene_spec()` returns a dict describing the task's **persistent**
on-screen layout, fetched once when a task starts (not per frame):

| `mode` | Returned by | Meaning |
|---|---|---|
| `single` | `click_static` (base default, no override) | one target on an empty field |
| `grid` | `click_grid` | the whole R×C cell grid stays visible, one cell lit |
| `icons` | `scanning` | a 2D field of distractor shapes, cued one highlighted |
| `moving` | `follow_moving` | a travelling target, drawn with a fading motion trail |

This is the fix for the finding already on record in
[[peds-eye-gaze-assessment-physician-feedback-2026-09-02]] (finding #1: in
`dev/`, `click_grid`/`scanning` don't render their designed layouts — only a
generic circle ever appears). `dev/` has since independently fixed the same
underlying symptom via `BaseTask.layout_slots` + `TaskCanvas._draw_layout_slots`
(dim outlines for every slot, active one highlighted) — `diki`'s approach is
architecturally similar (task exposes its static layout, canvas draws all of
it) but is a distinct, more general mechanism: one `scene_spec()`/`mode`
dispatch per task type instead of one shared "draw every slot as an outline"
helper, and it additionally drives per-mode rendering choices (grid cell
borders vs. distractor shapes vs. a motion trail) that `dev/`'s single
generic slot-outline does not attempt.

### 3.2 `click_static` (`tasks/click_static.py`, 27 lines)

Simplest task, unchanged in spirit from `dev/`: `n_trials` targets (default
32), each placed at a `rng.choice()` from `target.positions` (default
`[[0.5, 0.5]]`), fixed `radius_px` (default 90). No `scene_spec()` override —
inherits `{"mode": "single"}`.

### 3.3 `click_grid` (`tasks/click_grid.py`, 65 lines)

An R×C grid (`grid.rows`/`grid.cols`, default 3×3) of cells computed as evenly
spaced fractions of the screen inset by `grid.margin_frac` (default 0.12):

```
span = 1.0 - 2*margin
cell(r, c) = (margin + span*(c+0.5)/cols, margin + span*(r+0.5)/rows)
```

Trial order is a shuffled, tiled sequence of all cell indices (cycles through
all cells again if `trials > rows*cols`) so no cell repeats before the others
have each appeared once. `scene_spec()` returns `mode="grid"` plus the full
cell-centre list and `cell_w`/`cell_h` (in normalized units) so the canvas can
draw every cell's rounded-rect outline, not just the lit one — explicitly
framed in the docstring as "mimics a communication board."

### 3.4 `scanning` (`tasks/scanning.py`, 77 lines)

Distractor field with **three interchangeable arrangement algorithms**
(`layout.arrangement`, default `grid`):

- `row` — single horizontal line (flagged in-code as *not* real visual
  search, since the child never looks up/down — kept only as an option).
- `ring` — `n_icons` evenly spaced around a circle (`cx,cy=0.5,0.5`,
  `r=0.32`).
- `grid` (default) — `cols = ceil(sqrt(n_icons))`, `rows = ceil(n_icons/cols)`
  — deliberately favours more columns than rows to match a wide screen
  (explicitly notes `round()` would produce an unwanted 2×3 for 6 icons with
  large empty side margins).

Icons are assigned one of **6 distinct shapes** (`shapes = [i % 6 for i in
range(n_slots)]` — circle, square, triangle, diamond, hexagon, star, defined
in `ui/canvas.py`), not just distinct colours — the docstring is explicit
that this is deliberate: distinguishing by *form* is what makes it a scanning/
search task rather than a colour pop-out task. `scene_spec()` returns
`mode="icons"` plus `slots` and `shapes`; the active slot's own shape is drawn
in full colour by the target-rendering code, the rest as dim translucent
silhouettes.

### 3.5 `follow_moving` (`tasks/follow_moving.py`, 59 lines)

The only task with a genuinely live (per-frame-recomputed) target position and
a **timed selection window**, both overridden from `BaseTask`'s static
defaults:

- `target_position()`: two path shapes, `motion.path` = `horizontal` (bounces
  between x=0.1 and x=0.9 as a triangle wave, `y` fixed per-trial in
  `[0.25, 0.75]`) or `circular` (orbits centre at `r=0.3`,
  `ω = 2π·speed_frac_per_s`).
- `is_selectable()`: the target is only selectable for a
  `motion.select_window_ms` window (default 2500 ms) starting at a randomized
  offset within the trial's timeout — selecting outside that window is a
  failed attempt, not a hit. This is what forces active tracking rather than
  "park the cursor where it will arrive and wait."
- `scene_spec()` returns `mode="moving"` + `path`/`speed`, which the canvas
  uses to draw a fading trail (`ui/canvas.py:_draw_trail`, ~90 frames / 1.5s
  of history at 60Hz, alpha-faded by recency) behind the live target position
  — explicitly there so "tracked it" is visually distinguishable from "waited
  where it would arrive."

### 3.6 Shared trial-state additions in `BaseTask` worth noting

Two things in `base_task.py` go a bit beyond `dev/`'s current base task and
are candidates to port independently of the scene-rendering work:

- **`TARGET_ENTER`/`TARGET_EXIT` events** recorded every time the gaze
  crosses in/out of the target's hitbox (not just at trial end), plus a
  `revisits` counter distinguishing "acquired and held" from "found it, lost
  it, found it again" — a precision signal `dev/`'s recorder doesn't
  currently have an equivalent for.
- **`is_selectable()` hook**: a general per-frame gate on whether a selection
  counts as a hit, independent of dwell/click mechanics — `follow_moving` is
  the only current user, but it's a clean extension point for any future task
  needing a timed or conditional selection window.

## 4. Design system

`ui/dashboard.py` carries the entire visual language as one Qt stylesheet
(`_STYLESHEET`, lines 87-187) plus a handful of styled custom widgets. This is
the part most directly reusable as a reference/port target for `dev/`'s GUI,
which currently has no equivalent centralized stylesheet.

### 4.1 Palette (`dashboard.py:75-86`)

A warm maroon-and-cream palette, explicit in the code comment about *why*:
grey is kept only for genuinely neutral states (disabled, pending, muted
captions) and deliberately never used as the interface's own base colour.

| Token | Hex | Role |
|---|---|---|
| `_INK` | `#2c1810` | primary text — warm near-black, not cool grey |
| `_MUTED` | `#8a7566` | captions, disabled text, "pending" state |
| `_BORDER` | `#e3d2b8` | all card/control borders |
| `_SURFACE` | `#fffdf8` | card/control background — warm off-white |
| `_BG` | `#f3e8d3` | page background — cream |
| `_ACCENT` | `#7a1f2e` | maroon — the one bold colour, primary actions |
| `_ACCENT_DARK` | `#5c1420` | accent hover/pressed |
| `_ACCENT_SOFT` | `#f1dfd8` | pale maroon tint — header chrome, tab-title chip |
| `_OK` | `#3f7d43` | success/fresh state (green) |
| `_WARN` | `#a9761f` | caution/aging state (amber) |
| `_BAD` | `#a3272f` | error/stale/lost-signal state (red) |

A **second, separate dark palette** exists for the two child-facing/live
overlays that sit on top of the (also dark) subject canvas rather than the
cream operator UI: `TaskHud` (`rgba(15,20,26,205)` panel, `#e7edf2` text,
`#4dd0e1` cyan counter, `#7fd992`/`#b7c0cb` hit/timeout labels) and
`GazePreview` (`#11161c` panel, `#2b333d` grid lines, `#4aa3df` gaze trail,
`#39d353`/`#8a8f98`/`_BAD` for valid/idle/lost gaze dot). These are
intentionally not styled with the cream operator palette — they're meant to
read as instrumentation overlays on a dark canvas, not as part of the
paperwork-style dashboard chrome.

### 4.2 Component patterns (from the QSS + helper functions)

- **Cards**: `QFrame` with `objectName` set (never a bare `QFrame` type
  selector) + `border-radius: 10px`, 1px `_BORDER`, `_SURFACE` background.
  The code is explicit about *why* objectName-scoping matters: `QLabel` is
  itself a `QFrame` subclass in Qt, so a type-selector rule would
  unintentionally box every label inside the card too (`_card_frame`,
  `dashboard.py:203-216`, repeated for `headerBar`, `liveCounterPanel`,
  `taskRow`).
- **Status pills** (`StatusPill(QLabel)`): small rounded coloured chips
  (`border-radius: 9px`, white text, 11px bold) — one glance state, no
  reading required. Used for Session/Tracker/Calibration state in the header,
  and per-task state in the task list.
- **Group boxes**: 10px rounded corners, title rendered as a small pill
  centered on the top border (`subcontrol-position: top center`, `top: -6px`,
  its own `_ACCENT_SOFT` background + `_ACCENT` text) rather than Qt's default
  inline label — reads as a labelled section, not a plain fieldset.
- **Tabs**: unselected tab text in `_MUTED`, selected tab gets `_SURFACE`
  background + `_ACCENT` text + a border that merges into the pane below it
  (`border-bottom: none`) — the classic "attached folder tab" look.
  Disabled tabs (`2 · Tasks`/`3 · Results` before they're unlocked) render in
  a washed-out `#cbb89a`.
- **Primary buttons**: `objectName="primary"` — solid `_ACCENT` fill, white
  text, bold; darkens on hover; a distinct washed-out disabled state
  (`#d9b9bd`) rather than plain greyed-out, so a disabled primary action still
  reads as "the important one, just not clickable yet." A `danger` variant
  (task-row "End" button) is just `_BAD` text on the default button chrome —
  no fill — reserved for a destructive action that shouldn't visually compete
  with `primary`.
- **Sliders**: thin 4px flat groove in `_BORDER`, circular 15px `_ACCENT`
  handle — used identically in three places (dashboard's per-task dwell/
  smoothing controls, and the fullscreen `TaskHud`'s copy of the same two
  controls, in the dark palette instead).
- **Progress bar**: rounded, `_ACCENT` fill chunk, used both for calibration-
  adjacent status and the live per-task trial-count bar in `LiveCounterPanel`.
- **Fixed-height list rows** (`_build_task_row`, `dashboard.py:839-891`): each
  task row is a hard `setFixedHeight(80)` frame with a fixed-width
  (`210px`), non-wrapping, monospace status label — the code calls out
  *why*: without a fixed size, the row grew once "32 trials · 24 hit · 8
  timeout" replaced a "--" placeholder, shifting every row below it. A
  layout-stability pattern worth reusing anywhere `dev/`'s UI shows a summary
  string that changes length after an action completes.

### 4.3 Typography

No custom font family is loaded — everything rides Qt's default UI font at a
base `13px` (`QWidget` rule), with per-widget `QFont` overrides for emphasis:
section titles 12pt bold, the big trial counter 34pt bold (dashboard) / 22pt
bold (HUD), results-page title 13pt bold. Monospace (`Consolas`) is reserved
specifically for raw/tabular data — the calibration raw-reply log, the
task-row status summary, the session log view, the results metrics table —
consistently used as a visual signal for "this is a literal value/log, not
prose."

### 4.4 Assets

A lab logo (`wtmh_logo.PNG`, resolved from repo root two levels above
`dashboard.py`) rendered at the top-right of the header bar, scaled to 36px
height; `_set_app_icon` prefers a generated `logo.ico` (sharper in the Windows
taskbar/Alt-Tab) over the plain PNG, falling back gracefully if neither
exists. Neither file is present in this `resources/diki` copy — asset
existence, not content, is what's confirmed.

## 5. UX flow — the three "windows"

`diki` implements the three steps the user described as **three tabs of one
`DashboardWindow`** (`ui/dashboard.py:537-1056`), not three separate top-level
windows — plus a fourth, genuinely separate window (`SubjectWindow`) that is
never shown to the operator, only to the child. `ui/main_window.py` +
`ui/operator_panel.py` are an **earlier, superseded design** (a single
fullscreen canvas + fixed 240px sidebar) — nothing in `app.py` or `main.py`
constructs `MainWindow` any more; only `DashboardWindow`/`SubjectWindow` are
live. Worth flagging so a future read of this repo doesn't mistake the old
sidebar panel for the current design.

### Window 1 — "1 · Setup" tab: subject + tracker + calibration

Two columns, explicitly redesigned down from three per the code's own
docstring reasoning: subject → connect → calibrate is one linear workflow, so
splitting subject/tracker/calibration into three side-by-side boxes "split one
workflow across boxes that had nothing to do with each other's layout."

- **Left column**: Subject ID + Notes form → **Start session** (primary) →
  **Connect to tracker** (primary) → calibration instructions caption
  ("Calibrate in Gazepoint Control's own window, then Read calibration to
  pull the result in") → calibration detail line → **Read calibration**
  (primary) → **Check drift** (secondary, tooltip explains it shows a 3s
  centre dot and measures offset) → a small monospace raw-reply log box.
- **Right column**: `GazePreview` (dark live gaze-dot + fading trail monitor,
  §4.1) at a minimum 260px height, three live stat readouts (Valid / Sample
  rate / Render fps) in a row beneath it, then **Continue to tasks →**
  (primary, disabled until calibration status is `fresh` or `aging` — see
  below).
- Header status pills (Session / Tracker / Calibration) sit above both
  columns, always visible, colour-coded `_OK`/`_WARN`/`_BAD`/`_MUTED`.
- **Gating**: `set_calibration()` only enables "Continue to tasks" once
  calibration status is `fresh` or `aging` — never `stale`/`none`. The code
  comment frames this explicitly as the fix for a review finding that an
  operator silently proceeding on a stale/failed calibration was risky.
  `_finish_calibration_result()` also **auto-advances** to the Tasks tab the
  moment a read succeeds and is usable, rather than requiring a manual click.

### Window 2 — "2 · Tasks" tab: task selection + live run

- A **← Setup / recalibrate** back-link at the top (calibration is reachable
  again without losing the session).
- A **live panel row**, hidden entirely while idle (not shown as an empty
  "no task running" placeholder — the task list moves up to fill the space):
  `LiveCounterPanel` (task name, big 34pt trial counter, hit/timeout counts,
  thin progress bar) beside a `"Live controls"` group box (Pause/Skip/End
  buttons + Dwell-time and Cursor-steadiness sliders with tooltips explaining
  each in plain language, e.g. "Higher = steadier cursor, slightly slower to
  follow a new look").
- **Task list**: one fixed-height row per task (`TASK_LABELS`/`TASK_BLURBS` —
  short human name + one-line description, e.g. "Grid Click (3x3)" / "One
  cell of a visible 3x3 board lights up — selection among candidates."), each
  with a Run button and a disabled-until-done Analyze button. Running one task
  disables **Run** on every other row (but not Analyze) until it finishes.
- **Duplicated live controls on the child-facing screen**: `SubjectWindow`
  hosts a `TaskHud` overlay (top-left corner, semi-transparent dark panel,
  §4.1) carrying its own copy of the trial counter and the same two
  dwell/smoothing sliders — so the operator never has to alt-tab back to the
  dashboard mid-task, especially relevant on a single-monitor setup. Both
  copies stay in sync via `sync_controls()` in both directions. **H** toggles
  HUD visibility for a run if it's too distracting.

### Window 3 — "3 · Results" tab: task result

- Title line (e.g. "Grid Click (3x3) — 24 trials"), a caption noting results
  are also written to `metrics.json` on disk.
- A two-column metrics table (Metric / Value), populated by
  `_metric_rows()` from `AssessmentApp`: data-quality block (valid-sample %,
  on-screen %, effective Hz, raw calibration error, longest gap), fixation
  block (count, mean/median duration, rate), saccade block (count, mean
  amplitude/direction, latency-to-first-fixation), selection block (hit rate,
  median RT, mean attempts/revisits, trials needing re-attempt) — sub-rows
  indented with two leading spaces and rendered in muted colour/non-bold to
  read as a hierarchy under each bold section header. Any data-quality
  `notes` are appended as `"  ! <note>"` rows.
- A read-only monospace session log below the table.
- Reached two ways: automatically when a task finishes (`_finish_task`
  navigates here directly and raises/activates the dashboard, since the
  operator was just watching the subject window), or on demand via a task
  row's **Analyze** button (re-shows that task's last run without re-running
  it).

### Navigation mechanics

`DashboardWindow` is a single `QTabWidget` with tabs 2 and 3 **disabled**
(`setTabEnabled(False)`) until unlocked in order — Tasks unlocks once a
session exists and calibration is usable (`show_tasks_page`), Results unlocks
the first time any task finishes or Analyze is pressed (`show_results_page`).
There is no way to jump ahead of where the session actually is.

## 6. Notable divergences from `dev/`'s current design (context, not a task)

Flagged for awareness only — porting decisions are for a future session:

- `dev/`'s current app has no equivalent of `diki`'s **drift/validation
  check** (window-1's "Check drift" button: show a centre dot for 3s, measure
  actual gaze offset from it, and use that — not just elapsed time — to decide
  whether a calibration should be trusted). This is a UX capability gap, not
  just a visual one.
- `dev/`'s window flow today is a single fullscreen canvas + side operator
  panel per launch (closer to `diki`'s superseded `MainWindow`/
  `OperatorPanel`, per [[peds-eye-gaze-assessment-live-settings-panel-2026-09-04]]'s
  description of `OperatorPanel`'s Settings/Pacing boxes) rather than
  `diki`'s three-tab dashboard-plus-separate-subject-window split described
  in §5. Adopting `diki`'s window structure would be a bigger UX change than
  adopting just its colour system/component styling.
- `dev/`'s `TaskCanvas` currently renders `click_grid`/`scanning` via a single
  generic "draw every layout slot as a dim outline" helper (`layout_slots` +
  `_draw_layout_slots`); `diki`'s per-mode `scene_spec()` dispatch (§3.1) is a
  more expressive version of the same idea (real grid-cell borders, real
  distractor shapes, a motion trail) but is a larger structural change, not a
  drop-in.

## 7. Open items / suggested next steps

Not started — for the user to prioritize in a future session:

1. Obtain `diki`'s actual `configs/themes/*.yaml` (at least `forest.yaml`) to
   confirm real theme values against the contract documented in §4.1's dark
   overlay vs. canvas theme distinction — `TaskCanvas`'s theme keys
   (`background`, `target_default`, `cursor_color`, `progress_color`,
   `particle_color`) are confirmed from `ui/canvas.py`'s own `.get()` calls,
   but their actual configured values are not available in this copy.
2. Decide whether to port the **stylesheet/palette only** (lowest-risk:
   mostly self-contained in `dashboard.py:_STYLESHEET` + a few helper
   functions), the **scene_spec() rendering mechanism** (moderate: touches
   `BaseTask`, all four task subclasses, and `TaskCanvas`), or the **three-tab
   window structure** (largest: reworks `dev/`'s current window/launch model)
   — these are three independent, separately-portable pieces, not one
   monolithic decision.
3. If porting the drift/validation check (§6) is wanted, that's calibration
   *logic*, not UI — would need its own scoped design session against
   `dev/`'s own calibration engine, out of this audit's scope.

## 8. Approved port: diki's live Trial/Dwell panel → `dev/`'s `OperatorPanel` sidebar

User asked (separate session, same day) whether diki's live Trial/Dwell
settings UI was already documented here before any new inspection of
`resources/diki`. **It was** — no new code-reading of `diki` was needed,
this section only adds a port *plan*, grounded in `dev/`'s actual current
code (re-read fresh for this section, not assumed):

- The design being ported is what §5 ("Window 2") already documents: a
  `LiveCounterPanel` (task name, big trial counter, hit/timeout counts, thin
  progress bar) beside a `"Live controls"` group box (Pause/Skip/End +
  Dwell-time/Cursor-steadiness sliders, each with a plain-language tooltip),
  hidden entirely while idle so the task list expands to fill the space; and
  the slider visual spec from §4.2 (thin 4px flat groove, circular 15px
  accent handle).
- **User's three decisions** (asked via `AskUserQuestion`): (1) port the
  tooltip copy as well as the layout, not layout-only; (2) match diki's
  hide-while-idle behavior rather than keeping the panel always visible; (3)
  record this plan in this doc rather than a new SPEC file.

### 8.1 Current `dev/` state (confirmed by reading the code, not assumed)

`src/ui/operator_panel.py`'s `OperatorPanel` is four always-visible
`QGroupBox`es built once in `__init__` and never hidden: **Status** (FPS /
gaze-validity / `"Trial: i/n"` text labels, updated every frame via
`update_status()`), **Controls** (Pause/Skip buttons only — no End), and
**Settings**/**Pacing** (the `LIVE_SETTINGS` registry rows from
`src/ui/settings_registry.py`, rendered via `SliderSpinRow`/`QCheckBox`,
grouped by field origin per SPEC-live-settings-panel.md §9). `AssessmentApp`
(`src/app.py:363-369`) calls `update_status(fps, gaze_valid, trial_index,
len(self.task.targets), connected=...)` every frame — trial index/count only,
**no running hit/timeout tally exists anywhere** to feed a diki-style counter.
`LiveSetting` (`settings_registry.py:23-32`) has no tooltip/description
field today.

### 8.2 Gaps to fill when this is actually implemented (not done yet)

1. **No hit/timeout tally.** `BaseTask.update()` classifies each trial
   outcome (`"HIT"`/`"MISS"`/`"TIMEOUT"`, `base_task.py:278`) and the
   recorder logs it, but nothing accumulates a running count for live
   display — needs new counter state in `AssessmentApp`, incremented off
   that classification, and a new `OperatorPanel` slot to show it (plus the
   progress bar, driven by `trial_index/len(targets)`, which is already
   computed but not yet rendered as a bar).
2. **No tooltip field.** `LiveSetting` needs a new optional field (e.g.
   `tooltip: str | None`) plus real per-setting copy for all ~11 entries in
   `LIVE_SETTINGS`, and `_build_control()` needs to call `setToolTip()` on
   the constructed checkbox/`SliderSpinRow`.
3. **No idle/running show-hide mechanism.** `OperatorPanel`'s boxes are
   static from construction — nothing today hides/shows any group based on
   task state.
4. **Architectural mismatch, flagged for a decision before implementation
   starts, not resolved here:** diki's "idle" state is *browsing the
   persistent task list inside one still-open window, no task started yet*
   (§5, "Window 2") — the live panel collapses so that list can expand.
   `dev/`'s current launch model runs **one task per process/window**
   (`--task <id> --gui`), which is already effectively "running" for the
   whole life of that window — there is no in-window multi-task idle browse
   state to collapse back to today. Three ways to resolve this, needing the
   user's call when implementation is scheduled: (a) reinterpret "idle" as
   just the brief pre-first-trial / post-completion moments within the one
   task window; (b) treat true idle/task-list collapsing as only meaningful
   if `dev/` later adopts diki's multi-task dashboard structure (§5/§7 item
   2's "three-tab window structure" option, still entirely unstarted); or
   (c) drop the hide-behavior requirement for now and keep the panel
   always visible, revisiting it if/when (b) happens.

**Status: implemented and live-validated via qt-mcp (§8.3/§8.4).** The
original §8.1 three-decision plan text above is kept as the historical
record of what was asked before implementation; §8.3 documents what was
actually decided and built, which differs from it in two places (decision 2
below overrides the original "match diki's hide-while-idle behavior," and a
new fourth decision — adding diki's End button — was made that wasn't part
of the original three).

### 8.3 What shipped

Before implementing, the user resolved §8.2's four open points via a fresh
`AskUserQuestion` round:

1. **Architectural mismatch (§8.2 point 4): resolved as option (c).**
   Hide-while-idle is **not** implemented — `OperatorPanel`'s groups stay
   always visible, matching today's behavior. Only the visual
   layout/tooltips were ported, overriding the original §8's decision 2
   ("match diki's hide-while-idle behavior").
2. **New: add diki's End button.** `dev/` previously had no clickable "end
   task early" control (only the `Escape` key, `src/app.py`'s
   `_install_key_handler`). Added `OperatorPanel.end_button` /
   `end_requested` signal, wired directly to `AssessmentApp._shutdown` —
   the exact same clean-shutdown path `Escape` already used (writes
   completed trials, closes the recorder, stops the client, quits), so this
   is the existing behavior made visible/clickable, not new shutdown logic.
3. **Tooltip copy drafted for all ~11 `LIVE_SETTINGS` entries**, not just
   the 2 diki itself has sliders for (diki only ever shows dwell-time and
   cursor-steadiness) — written in diki's plain-language style (e.g.
   "Lower = steadier cursor, slightly slower to follow a new look" for
   `dwell.smoothing.alpha`, directly echoing diki's own cursor-steadiness
   tooltip wording).

**Files changed:**

- `src/ui/settings_registry.py` — `LiveSetting` gained `tooltip: str | None
  = None`; all 11 `LIVE_SETTINGS` entries given real tooltip text.
- `src/ui/operator_panel.py` — new **"Live"** `QGroupBox` (ported from
  diki's `LiveCounterPanel`): a large bold `trial_label` (20pt, was a plain
  small label folded into "Status"), a new `tally_label` ("Hits: N
  Timeouts: N"), and a `QProgressBar` (`setTextVisible(False)`, matching
  diki's plain fill-bar look, not a percentage readout). `update_status()`
  gained `hits`/`timeouts` keyword params (both default `0`, so the one
  existing call site keeps working if ever called without them) that drive
  the new tally label and the progress bar's range/value. New
  `end_button`/`end_requested` in **Controls**, alongside the existing
  Pause/Skip. `_build_control()` now calls `.setToolTip()` on every
  constructed checkbox/`SliderSpinRow` when the setting has one.
- `src/ui/slider_spin.py` — `SliderSpinRow.setToolTip()` overridden to also
  apply to its child `_slider`/`_spin` widgets, not just the container —
  otherwise the tooltip never shows, since the mouse is always over one of
  the two children, neither of which had a tooltip of its own.
- `src/app.py` — `_wire_operator()` connects the new `end_requested` signal
  to the existing `_shutdown` method (no new method needed). `_tick()`
  computes `hits`/`timeouts` by counting `t.is_hit`/`t.is_timeout` over
  `self.task.trials` (the task's own completed-trial records) each frame,
  rather than tracking separate counters — guarantees the live tally can
  never drift from what `trials.csv` ends up containing, and needed no
  change to `BaseTask`/`FrameResult` at all.

### 8.4 Testing

- Full pytest suite: same single pre-existing failure as every prior
  session (`test_config_merges_task_over_default`, unrelated stale
  `target_fps` assertion) — no regressions.
- **Live qt-mcp** (`QT_MCP_PROBE=1 QT_MCP_PORT=9142 python -m src.main
  --task click_static --gui --replay
  tests/fixtures/gaze_replay_click_static.jsonl --subject QAPILOT
  --skip-task-settings`): screenshot confirmed the new **"Live"** box
  rendering a large "Trial: 10/32," a "Hits: 8   Timeouts: 1" tally, and a
  visible progress-bar fill with no percentage text painted (confirming
  `setTextVisible(False)` took effect — `qt_find_widget`'s own text-property
  introspection still reports a computed "28%" internally, which is
  expected and not a rendering bug); **Controls** box showed all three
  Pause/Skip trial/End task buttons. Clicked **Skip trial** live — trial
  index and hit/timeout tally both advanced correctly. Clicked **End task**
  live — the process exited cleanly (confirmed via
  `Get-CimInstance Win32_Process` showing no leftover `*src.main*`
  process), and the session's `trials.csv` had exactly the 13 trials
  completed before the click, proving the End button uses the same
  graceful early-stop path as `Escape`. `qt_messages(level="warning")`
  showed only the two already-known `QSoundEffect` audio-device warnings —
  no new warnings or errors. The scratch QA session directory was deleted
  after the check (not real subject data).
- Tooltip application itself (`setToolTip()` calls) was verified by code
  reading, not a live hover-and-read probe — qt-mcp has no generic
  "read tooltip text" affordance; the `SliderSpinRow.setToolTip()`
  child-propagation fix was the one non-obvious risk here and was reasoned
  through directly (Qt tooltips only show for the widget literally under
  the cursor, and the slider/spin box are separate children of the row).

### 8.5 Styling validation: two different live-controls surfaces, not one

After §8.3 shipped, the user described diki's live-settings/trial-count area
from memory while re-opening `resources/diki` themselves: not a black
background like "the dashboard," each category in its own separate
container with a visible margin between them, and font-color/typography/size
that clearly matters. **Re-read `ui/dashboard.py` directly to check this,
since it's a claim about diki's actual current pixels, not something to
answer from §4's earlier summary-level palette table.** The description is
correct — but diki actually has **two** live-controls surfaces that look
opposite to each other, and confirming which one the description matches
mattered:

1. **`DashboardWindow`'s "2 · Tasks" tab (`_build_tasks_tab`,
   `ui/dashboard.py:750-814`) — this is the one the user described, and
   `dev/`'s `OperatorPanel` sidebar is its actual analog** (both are the
   operator-facing control surface, not the child-facing one). Confirmed:
   page background is cream `_BG` (`#f3e8d3`), not black
   (`_STYLESHEET`, `ui/dashboard.py:88`). `LiveCounterPanel`
   (`ui/dashboard.py:466-517`) is its own `QFrame` — off-white `_SURFACE`
   (`#fffdf8`) background, 1px `_BORDER` (`#e3d2b8`), 10px radius
   (`ui/dashboard.py:481-484`). The `"Live controls"` `QGroupBox` (Pause/
   Skip/End + Dwell/Steadiness sliders, `ui/dashboard.py:775-801`) gets the
   same off-white/border/radius treatment from the global `QGroupBox` QSS
   rule (`ui/dashboard.py:92-99`: `background: _SURFACE; border: 1px solid
   _BORDER; border-radius: 10px; margin-top: 26px; padding: 16px 14px 12px
   14px;`). These two containers sit side-by-side in a `QHBoxLayout` with
   **10px spacing** between them (`live_row.setSpacing(10)`,
   `ui/dashboard.py:771`), and a third card (the `"Tasks"` list group box)
   sits below with another 10px gap (`outer.setSpacing(10)`,
   `ui/dashboard.py:754`) — real, visible separation between bordered
   cards, not one merged panel.
2. **`TaskHud` (`ui/dashboard.py:305-391`) — a separate, child-facing
   fullscreen overlay shown on the subject's own screen during a task, not
   part of `DashboardWindow` at all** — is the opposite: one dark
   `rgba(15, 20, 26, 205)` `QFrame` with the trial counter, hit/timeout
   labels, and both sliders all stacked in a single `QVBoxLayout`
   (`layout.setSpacing(4)`, `ui/dashboard.py:334`), no internal
   sub-containers or borders between them. If "the dashboard" in the user's
   own recollection meant this overlay, that part of the premise is
   reversed — `TaskHud` is the dark, merged one; `DashboardWindow` is the
   light, separated one. This distinction was not previously called out
   this precisely — §5 only said the two share "the same two dwell/
   smoothing controls," not that their surrounding chrome is visually
   opposite (light/separated-cards vs. dark/single-panel).

**Typography/color also differ meaningfully between the two surfaces, and
even within `DashboardWindow`'s own live panel** — confirming the user's
point that styling isn't incidental here:

| Element | `DashboardWindow` (light) | `TaskHud` (dark) |
|---|---|---|
| Task name | 12pt bold, ink `#2c1810` | 10pt bold, `#e7edf2` |
| Big trial counter | 34pt bold, maroon `_ACCENT` `#7a1f2e` | 22pt bold, cyan `#4dd0e1` |
| Hit label | green `_OK` `#3f7d43`, weight 600 | green `#7fd992`, 11px, weight 600 |
| Timeout label | muted brown `_MUTED` `#8a7566`, weight 600 | grey `#b7c0cb`, 11px, weight 600 |
| Slider caption | 11px | 10px, fixed 58px width, `#b7c0cb` |
| Slider readout | 11px, weight 600 | 10px, `#e7edf2`, fixed 40px width |
| Progress bar | 8px tall, no percentage text | none — `TaskHud` has no bar |

Citations: `DashboardWindow` column from `ui/dashboard.py:488-517`
(`LiveCounterPanel`) and `:792-801`/`:816-837` (`_labelled_slider`);
`TaskHud` column from `ui/dashboard.py:336-391`.

**Superseded — was validation-only, now implemented (§8.6).** §8.3's
already-shipped port used `dev/`'s own existing dark theme colors; §8.6
below replaced that with the actual `DashboardWindow` light-card styling
from this table.

### 8.6 Styling implemented: diki's light-card look ported into `OperatorPanel`

User approved proceeding straight from §8.5's validation. Ported the
`DashboardWindow` column of §8.5's table (not `TaskHud`'s) into
`src/ui/operator_panel.py`, scoped to that one widget's subtree only.

**Approach:** a module-level `_STYLESHEET` in `operator_panel.py`, mirroring
diki's own `_STYLESHEET` (`ui/dashboard.py:87-187`) trimmed to the widget
kinds this panel actually uses (`QGroupBox`, `QPushButton`, `QSlider`,
`QProgressBar`, plus `QSpinBox`/`QDoubleSpinBox` — SliderSpinRow's readout,
which has no diki equivalent, styled to match diki's closest analogous rule,
`QLineEdit`). Applied via `self.setObjectName("operatorPanel")` +
`self.setStyleSheet(_STYLESHEET)` in `OperatorPanel.__init__` — a Qt
stylesheet set on a widget applies only to that widget and its descendants,
never to siblings or parents, so this cannot leak into `TaskCanvas` or any
other window without a separate, explicit change.

**Real gotcha hit and fixed:** the panel's own cream background
(`QWidget#operatorPanel { background: ... }`) did not paint at first —
`qt_screenshot` showed every card correctly styled (cream/border/radius) but
the strip *around/between* them stayed black. Root cause: a plain `QWidget`
ignores a stylesheet `background` property unless
`Qt.WidgetAttribute.WA_StyledBackground` is set — `QGroupBox` opts into
styled-background painting on its own, a bare `QWidget` does not. Fixed with
`self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)` before
`setStyleSheet`; re-validated live and the fix took effect immediately.
Worth remembering for any future `dev/` widget that sets a stylesheet
background directly on a plain `QWidget` (not `QFrame`/`QGroupBox`/etc.).

**Live-box widget changes** (beyond pure QSS, since these needed real
per-widget values from §8.5's table, not classes):
- `trial_label`: font bumped from the placeholder 20pt (chosen before §8.5's
  research existed) to diki's actual 34pt bold, coloured `_ACCENT` inline —
  matches `LiveCounterPanel.counter` exactly.
- The combined `tally_label` ("Hits: N   Timeouts: N") was **split into two
  separate labels**, `hit_label`/`timeout_label`, each with its own diki
  colour (`_OK` green / `_MUTED`) and diki's exact text format ("N hit"/"N
  timeout") — a single label can't carry two different inline colours, and
  diki's own `LiveCounterPanel` genuinely uses two `QLabel`s
  (`ui/dashboard.py:504-510`), so this is a faithful port, not an
  invented workaround.
- `progress_bar.setFixedHeight(8)`, matching `LiveCounterPanel.bar`.
- `end_button.setObjectName("danger")` — diki's own `stop_button` is styled
  this way (`ui/dashboard.py:787`, red text, no fill, from `_STYLESHEET`'s
  `QPushButton#danger` rule) rather than a bespoke `dev/`-only choice.

**Deliberately not ported:** diki's slider-caption/readout 11px micro-sizing
from §8.5's table applies specifically to diki's own compact 2-slider "Live
controls" box, which has no structural analog in `dev/` (`dev/`'s 11
Settings/Pacing sliders are `dev/`'s own invention, not something diki has a
version of to match sizes against) — left at the global 13px base font
rather than inventing a value with no source. A `task_name` label
(`LiveCounterPanel.task_name`, "No task running"/task label) was also not
added — that's new content, not a restyle of what's already there, and
wasn't part of the styling complaint being addressed this round.

**Testing:**
- Full pytest suite: same single pre-existing failure only
  (`test_config_merges_task_over_default`) — no regressions.
- **Live qt-mcp**, twice (once before the `WA_StyledBackground` fix, once
  after): `click_static --replay` — first screenshot caught the background
  bug directly (cards right, panel background still black); second
  screenshot after the fix confirmed the full cream sidebar with clearly
  separated white cards, maroon `QGroupBox` title pills, the 34pt maroon
  trial counter, green "N hit"/muted "N timeout" labels, and a red-text "End
  task" button — matching §8.5's `DashboardWindow` column exactly.
  `qt_messages(level="warning")` showed only the two already-known
  `QSoundEffect` warnings both times — no new warnings from the styling
  change. Clean shutdown confirmed via the End task button (no leftover
  `*src.main*` process) both times; scratch QA sessions deleted afterward.

### 8.7 Correction + design plan: a real corner `TaskHud`, not just `DashboardWindow` styling

User took a screenshot of `resources/diki` running and it did not match §8.6:
the screenshot showed **`TaskHud`** (`ui/dashboard.py:305-391`), the
compact, dark, semi-transparent corner overlay — not `DashboardWindow`'s "2
· Tasks" tab that §8.6 actually ported. §8.5/§8.6 correctly documented both
surfaces exist and look opposite, but picked `DashboardWindow` as the
`OperatorPanel` analog by structural reasoning (both are operator-facing);
the user's screenshot means that reasoning under-weighted what they
actually wanted visually. **This section corrects course — §8.6's
`DashboardWindow` port is not reverted, it becomes the secondary full-
control panel (see decision 2 below), while this section adds the actual
`TaskHud` look as a new, separate corner overlay.**

**Re-confirmed diki's exact `TaskHud` mechanics** (`ui/dashboard.py:435-455`,
`SubjectWindow`): `self.hud = TaskHud(self.canvas)` — a **child widget of
the canvas itself**, not a layout column — positioned with `.move(16, 16)`
on construction and re-pinned in `resizeEvent`, toggled with the **H** key
via `toggle_hud()`. This is a floating overlay drawn on top of the canvas,
categorically different from `dev/`'s current `QHBoxLayout` column
approach.

**Two decisions made via `AskUserQuestion` before this plan:**
1. Go all the way to a real floating HUD (not just a restyle of the
   existing sidebar to *look* dark/blended) — i.e. adopt diki's actual
   corner-overlay structure, not just its colours.
2. Since a compact corner HUD only has room for diki's own 2 sliders +
   counter (diki affords this because `DashboardWindow`, a whole separate
   window, holds everything else — `dev/` has no equivalent second window),
   **keep today's full `OperatorPanel` sidebar as-is alongside the new
   HUD** — two surfaces, mirroring diki's HUD + `DashboardWindow` split,
   rather than folding the sidebar behind a second toggle.

**Also found, independent of the HUD work — a real layout bug behind the
"vertical black bar" the user described:** `src/ui/main_window.py`'s
`QHBoxLayout(central)` sets `setContentsMargins(0,0,0,0)` but never calls
`setSpacing(0)`, so Qt's default inter-widget spacing leaves a gap between
`TaskCanvas` and `OperatorPanel` where the unstyled `central` widget's raw
(black) background shows through.

**Design:**
- New `src/ui/task_hud.py` — a `TaskHud(QFrame)` ported near-verbatim from
  diki's (`ui/dashboard.py:305-391`): same `rgba(15,20,26,205)` translucent
  background, `#e7edf2` body text, task-name label, a 22pt bold `#4dd0e1`
  counter, `hit_label`/`timeout_label` (`#7fd992`/`#b7c0cb`, 11px weight
  600), two slider rows, and a "Press H to hide" hint (`#7c8894`, 10px).
  Task-name text sourced from diki's own `TASK_LABELS` dict
  (`ui/dashboard.py:57-62`) — confirmed diki and `dev/` use the identical 4
  task ids (`click_static`/`click_grid`/`follow_moving`/`scanning`), so this
  is a verbatim port, not a guess.
- **One deliberate, disclosed deviation from diki:** diki's second slider is
  "Steadiness," a 0-100% scale where *higher* = steadier — a UI-only
  relabelling of its own smoothing value. `dev/`'s equivalent live value,
  `dwell.smoothing.alpha`, already exists with the *opposite* direction
  (lower = steadier, per its own tooltip in `settings_registry.py`).
  Inventing a translated inverse-percentage display would risk a real
  correctness bug (a mismatch between what the slider shows and what it
  actually sets) for a cosmetic match. The HUD's "Steadiness" slider
  therefore shows `dev/`'s native alpha value/range directly (0.05-1.0),
  not a synthesized 0-100% inverse. The Dwell slider has no such mismatch
  (`dwell.threshold_ms`, 300-2000ms, same direction and range diki uses) and
  is ported as-is.
- Both HUD sliders drive the **same dotted-key settings** as the sidebar's
  existing `Settings` box (`dwell.threshold_ms`, `dwell.smoothing.alpha`),
  through the same `setting_changed` signal /
  `AssessmentApp._apply_setting` path already built for
  `SPEC-live-settings-panel.md` — no parallel data path. Kept in sync
  bidirectionally (matching diki's own `sync_controls()`,
  `ui/dashboard.py:408-414`, including its `if slider.value() != value`
  guard against feedback loops): a change from either surface updates the
  other's displayed value without re-emitting.
- `OperatorPanel` gains a small addition to support that sync: constructed
  controls are now kept in a `dict[str, QWidget]` keyed by `setting.key`, so
  an external caller can push a value into the matching widget by key.
- `MainWindow`: `self.hud = TaskHud(...)` parented onto `self.canvas`
  (matching diki's `TaskHud(self.canvas)`), `.move(16, 16)`, a
  `resizeEvent` override re-pinning it (matching diki's `SubjectWindow.
  resizeEvent`), and a `toggle_hud()` method. Also fixes the
  `setSpacing(0)` bug above while touching this file.
- `AssessmentApp`: extends the existing key handler (`_install_key_handler`,
  already intercepting Space/Enter/Escape) with **H** → `toggle_hud()`,
  matching diki's own binding; `_tick()` updates the HUD's counter/tally the
  same way it already updates `OperatorPanel`.

**Not part of this plan:** diki's `SubjectWindow` is a fullscreen,
*control-free* window separate from the operator's `DashboardWindow` — the
child never sees any buttons, only the HUD counter and canvas. `dev/`'s
`MainWindow` is one window containing both the canvas and the full
operator sidebar together, and that arrangement is not being restructured
here (decision 2 above keeps it) — the new HUD is additive, layered on the
same single window `dev/` already uses.

### 8.8 Implemented and live-validated

Built exactly as planned in §8.7, plus one addition and one real bug fixed
along the way.

**Feedback-loop risk found and fixed before it shipped:** the plan's
`sync_value` design (guard on `control.value() != value` before calling
`setValue`) was not actually sufficient on its own — `SliderSpinRow.
setValue()` still triggers the underlying spin box's `valueChanged`, which
`SliderSpinRow` always re-emits as its own `valueChanged`, which would
bounce straight back into `AssessmentApp._apply_setting`. diki avoids this
in its own `sync_controls` by calling `slider.blockSignals(True)` around
`setValue` (`ui/dashboard.py:414-417`) before manually setting the readout
text directly — `dev/`'s `SliderSpinRow` had no equivalent silent setter.
Added `SliderSpinRow.set_value_silently()` (`src/ui/slider_spin.py`),
blocking both the slider and spin box's own signals while updating both
(diki only needs to block one widget since its readout is a bare label, not
another signal-emitting widget) — `OperatorPanel.sync_value`/`TaskHud.
sync_value` both use it. Caught by reasoning through the exact chain of
Qt signal connections before running anything, not by observing a runtime
hang.

**Files added/changed beyond §8.7's plan:**
- `src/ui/task_hud.py` (new) — as designed, plus tooltips on both sliders
  (diki's own copy for Dwell: "How long the child must hold their gaze
  before it selects."; a `dev/`-native rewrite for Steadiness, "Lower =
  steadier cursor, slightly slower to follow a new look.", matching the
  *actual* alpha direction rather than diki's inverted-percentage wording).
  Also styles `QSpinBox`/`QDoubleSpinBox`/`QSlider` to blend with the dark
  panel — diki's own `TaskHud` has no equivalent widget to port a rule from
  (its readout is a bare `QLabel`, not an editable spin box), since reusing
  `SliderSpinRow` for consistency with the rest of `dev/` otherwise left a
  jarring OS-default white spin box against the translucent dark panel.
- `src/ui/slider_spin.py` — new `set_value_silently()` (the loop fix above).
- `src/ui/operator_panel.py` — controls now kept in `self._controls: dict[
  str, QWidget]` keyed by `setting.key`; new `sync_value(key, value)` public
  method, handling both `QCheckBox` (blockSignals) and `SliderSpinRow`
  (`set_value_silently`) cases.
- `src/ui/main_window.py` — `layout.setSpacing(0)` added (the black-bar
  fix); `self.hud = TaskHud(task_id, initial_settings, parent=self.canvas)`,
  `.move(16, 16)`, shown; `resizeEvent` override re-pinning it;
  `toggle_hud()` method.
- `src/app.py` — `_wire_operator` connects `hud.setting_changed` to
  `_apply_setting`; `_install_key_handler` adds `Key_H` →
  `self.window.toggle_hud()`; `_apply_setting` calls `sync_value` on both
  `operator_panel` and `hud` for the two shared keys; `_tick` calls
  `self.window.hud.update_status(...)` alongside the existing
  `operator_panel.update_status(...)` call.

**Real bug caught by a live screenshot, not by reasoning:** the first live
run produced `[WARNING] Could not parse stylesheet of object TaskHud`.
Root cause: `TaskHud`'s stylesheet was built by concatenating f-string and
plain-string literals in one expression — the plain-string segments ended
in a literal `"}}"` (two real closing braces) rather than the single `"}"`
an f-string's `"}}"` escape would have produced, so three stray extra
closing braces broke Qt's CSS parser. Fixed by moving the whole stylesheet
into one module-level `_STYLESHEET` f-string (matching `operator_panel.
py`'s existing pattern) instead of a concatenation of mixed string kinds —
re-validated live, warning gone.

**Testing:**
- Full pytest suite: same single pre-existing failure only
  (`test_config_merges_task_over_default`) — no regressions, across all
  three live-launch rounds of this section.
- **Live qt-mcp**, three rounds: (1) initial HUD render — confirmed dark
  translucent corner panel matching the user's reference screenshot almost
  exactly (task name, cyan counter, green/muted hit-timeout, two sliders,
  hint text), sidebar's black gap gone; caught the plain-white spin-box
  clash by eye. (2) after the spin-box/slider dark-theme polish — also
  caught the stylesheet-parse warning via `qt_messages`. (3) after the
  stylesheet fix — warning gone, only the two already-known `QSoundEffect`
  warnings remain. **Bidirectional sync explicitly verified**: set the
  sidebar's Dwell threshold spin box to `1200` via `qt_set_property`,
  re-read the HUD's own Dwell spin box — also `1200`, confirmed both via
  widget inspection and a screenshot showing both slider handles at the
  same position, with the task continuing to run/tally throughout (no
  freeze, no duplicate/runaway `SETTING_CHANGED` events observed). **H-key
  toggle verified**: pressed `H` with canvas focused — HUD hid; pressed
  again — HUD reappeared. Clean shutdown confirmed via End task each round
  (no leftover `*src.main*` process); scratch QA sessions deleted
  afterward.

### 8.9 Correction: no separate HUD — recolor the sidebar's existing five cards instead

§8.7/§8.8's corner `TaskHud` was **not** what the user wanted. They clarified
with two reference screenshots: image 2 (`dev/`'s sidebar as §8.6 left it —
light cream cards) and image 3 (diki's `TaskHud`, dark/cyan) — asking for
the *sidebar itself* restyled to image 3's look, not a second diki-ported
widget. A follow-up round (after an `AskUserQuestion` interrupted mid-flow)
sharpened this further: keep the sidebar's existing **five separate cards**
(Status/Live/Controls/Settings/Pacing structure from §8.6, unchanged), just
recolour them to `TaskHud`'s dark/cyan palette instead of `DashboardWindow`'s
light/maroon one. Confirmed via `AskUserQuestion`: remove the corner HUD
entirely.

**This is a combination neither diki surface has on its own** — `TaskHud`
is dark but is one merged panel with no card-to-card borders; `DashboardWindow`
is card-separated but light. §8.9 applies diki's dark `TaskHud` colour
tokens to the card structure §8.6 already built, rather than porting either
surface verbatim.

**Reverted:** `src/ui/task_hud.py` deleted; `main_window.py`'s HUD
construction/`resizeEvent`/`toggle_hud` removed (the `setSpacing(0)`
black-bar fix was kept — unrelated, still correct); `app.py`'s HUD signal
wiring, `Key_H` handler, and `_tick`'s HUD update call removed;
`OperatorPanel.sync_value`/`_controls` and `SliderSpinRow.
set_value_silently` removed (dead code with no HUD left to sync against).

**Recoloured, structure unchanged:** `operator_panel.py`'s `_STYLESHEET`
palette tokens replaced end to end. `_TEXT`/`_ACCENT`/`_OK`/`_MUTED` are
diki's own `TaskHud` tokens (`ui/dashboard.py:328-391`, already documented
in S4.1/S8.5: `#e7edf2` text, `#4dd0e1` cyan accent, `#7fd992` hit green,
`#b7c0cb` muted/timeout). `_BG`/`_CARD`/`_BORDER`/`_BAD` have **no direct
diki source** — diki's only dark surface (`TaskHud`) never needed a
card-background/border/page-background triad since it has no cards, so
these four are this port's own reasoned choice (`#12161c` page, `#1b212a`
card, `#2b333d` border — reusing diki's `GazePreview` grid-line colour
already on record in S4.1 — and `#e5484d` for the danger button, since
diki's own light-theme `_BAD` (`#a3272f`) reads too dark/low-contrast against
a dark card). Disclosed as such rather than presented as a verbatim port.
Also added `QCheckBox::indicator` styling (translucent dark box, cyan when
checked) — neither diki surface needed this since `DashboardWindow` never
restyled checkboxes and `TaskHud` has none at all — so the OS-default
checkbox wouldn't clash against the new dark cards.

**Testing:** full pytest suite green (1 pre-existing unrelated failure
only, unchanged). Live qt-mcp: screenshot confirmed five dark cyan-accented
cards (Status/Live/Controls/Settings/Pacing) matching the reference
screenshot's palette closely — cyan title pills, 34pt cyan trial counter,
green/muted hit-timeout text, cyan slider handles and checkboxes, red "End
task" text. Skip trial re-verified (trial index advanced correctly). Clean
shutdown via End task confirmed (no leftover `*src.main*` process).
`qt_messages(level="warning")` showed only the two already-known
`QSoundEffect` warnings.

### 8.10 HUD-style floating-card restyle (new reference images, not from `diki` itself)

User feedback, driven by two new reference screenshots (`resources/images/
2026-09-08-current-gui.png` — `dev/`'s sidebar as §8.9 left it, a full-height
flush opaque panel; `resources/images/2026-09-08-diki-style.png` — diki's
`SubjectWindow` running live, with the compact corner `TaskHud` card floating
translucently over the pale-green canvas) and a written prompt asking for the
sidebar to read as a floating HUD card rather than a docked settings drawer:
inset from the window's top/right edges, sized to content rather than full
height, rounded corners + drop shadow, ~88-92% opacity so the canvas colour
shows through, tighter padding/denser type, and section labels collapsed into
small-caps subheadings instead of pill-titled boxes — either as one
scrollable card or a couple of stacked ones.

**This reopens exactly the question §8.9 already settled the other way**: a
true translucent bleed-through of the canvas, as the reference image shows,
only happens if the panel actually overlaps `TaskCanvas` — i.e. the corner
`TaskHud` overlay architecture §8.7/§8.8 built and §8.9 explicitly removed at
the user's own correction ("no separate HUD — recolour the sidebar's existing
five cards instead"). Rather than assume this round meant to reverse that,
asked directly via `AskUserQuestion` before writing any code:

1. **Architecture: side column, simulated float (not a canvas overlay) —
   §8.9's rejection stands.** `MainWindow`'s `QHBoxLayout(central)` (`canvas`
   + `operator_panel` side by side, `main_window.py:24-37`) is unchanged.
   Instead, `OperatorPanel`'s own background is set to the forest theme's
   canvas colour (`#e8f5e9`, `configs/themes/forest.yaml` — hardcoding this
   is a disclosed assumption tied to all four tasks now being unified to
   forest, SPEC-scanning-task-design-port.md S6) so the column's own margin
   area is visually indistinguishable from the canvas beside it; the "float"
   illusion comes from the cards being inset within that matched-colour
   column and not stretched to fill it, not from literal pixel overlap.
2. **Card grouping: a couple of stacked cards, not one scrollable card.**
   Three cards, not the original five §8.6/§8.9 boxes: Status+Live together,
   Controls alone, Settings+Pacing together — matching the "couple of stacked
   floating cards" option in the prompt over a single tall scrollable one.

**Implemented in `src/ui/operator_panel.py`** (`src/ui/main_window.py`
unchanged beyond what §8.7-8.9 already left it at):

- `_STYLESHEET`'s tokens split into two roles: `_TEXT`/`_MUTED`/`_ACCENT`/
  `_OK` stay diki's own `TaskHud` tokens, unchanged from §8.9; `_CANVAS_BG`
  (`#e8f5e9`, the column-background match above) and `_CARD_BG`
  (`rgba(43, 51, 64, 230)`, ~90% opacity slate) are new and have no diki
  source — diki's own `TaskHud` is a fully opaque overlay meant for a dark
  canvas, not a translucent one meant to blend with a light one — disclosed
  as this round's own reasoned values rather than a port.
  `QWidget#operatorPanel`'s background changed from the opaque dark `_BG`
  token (§8.9) to `_CANVAS_BG`; `QGroupBox` styling removed entirely in
  favour of a new `QFrame#hudCard` rule (`background: _CARD_BG;
  border-radius: 9px;`, no border — the drop shadow alone provides
  separation from the canvas-matched background, matching the reference's
  borderless look).
- New `_make_card()` helper builds each `QFrame#hudCard` with its own
  `QGraphicsDropShadowEffect` (blur 16, offset `(0, 4)`, `rgba(0,0,0,64)` ≈
  the requested `0 4px 12px rgba(0,0,0,0.25)`) — Qt stylesheets have no
  `box-shadow` property, so the shadow needs a real graphics effect, and Qt
  effects cannot be shared across widgets, so each card gets its own
  instance. New `_add_subheading()` renders a small-caps-style subheading
  (`QLabel[hudSubheading="true"]`, 10px, `_MUTED`, weight 700, 1px letter
  spacing) in place of the old `QGroupBox::title` pill — Qt stylesheets have
  no `text-transform`, so the label text itself is upper-cased in code.
- The outer `QVBoxLayout`'s margins became `(18, 18, 18, 18)` (was 0, implicit
  via `QGroupBox`'s own `margin-top: 26px`) with `14px` spacing between
  cards, and a trailing `addStretch(1)` so the three cards hug the top of the
  column instead of stretching to the window's full height — the same
  `addStretch(1)` pattern §8.6/§8.9 already used, just now doing real visual
  work since the cards are no longer full-height by construction.
- Type scale tightened throughout: base label font 13px → 11px; the trial
  counter 34pt (§8.6's `DashboardWindow` size) → 22pt, which is actually
  diki's own `TaskHud` counter size (S4.1/S8.5's table) — a HUD-appropriate
  value that happens to be well-sourced, not an invented one; hit/timeout
  labels to 11px (also `TaskHud`'s own size per that table); buttons,
  sliders, spin boxes, and checkboxes all received matching tighter
  padding/sizing with no direct diki source (diki's own compact 2-slider HUD
  has no analog for `dev/`'s 11-setting panel to size against, same
  reasoning §8.6 already used when it left these at the base font size —
  this round instead invents consistent HUD-density values, since the
  request this time is general HUD density, not diki fidelity).
- All existing public attributes/signals (`trial_label`, `hit_label`,
  `timeout_label`, `progress_bar`, `fps_label`, `validity_label`,
  `pause_button`, `skip_button`, `end_button`, `pause_toggled`,
  `skip_requested`, `end_requested`, `setting_changed`, `update_status()`)
  are unchanged — confirmed by grep before starting that no test touches
  `OperatorPanel` internals and `src/app.py`'s wiring (`_wire_operator`,
  `_tick`) only ever goes through these — so this is a visual/layout restyle
  only, no behaviour change, matching the prompt's own explicit constraint.

**Testing:**
- Full pytest suite: same single pre-existing failure only
  (`test_config_merges_task_over_default`) — no regressions.
- **Live qt-mcp** (`click_static --replay`): screenshot confirmed three
  rounded, drop-shadowed dark-slate cards (STATUS+LIVE, CONTROLS,
  SETTINGS+PACING small-caps subheadings) floating inset from the top/right
  of the window on the pale-green canvas background, matching the reference
  image's aesthetic — no visible seam between the column's matched-green
  background and the canvas beside it. `qt_messages(level="warning")` showed
  only the two already-known `QSoundEffect` warnings. Clicked **Skip
  trial** — trial index and hit/timeout tally both advanced correctly (4/32
  → 7/32, 2 hit → 4 hit, 1 timeout → 2 timeout). Clicked **End task** —
  confirmed via `Get-CimInstance Win32_Process -Filter "Name='python.exe'"`
  that no `*src.main*` process remained, proving the clean-shutdown path
  still works unchanged. Scratch QA session directory deleted afterward (not
  real subject data).

**Not part of this round:** the corner-overlay architecture remains rejected
per §8.9 — this restyle achieves the "floating HUD" *look* entirely within
the existing side-column layout. If a future request specifically wants true
pixel-level overlap with the canvas (e.g. so the panel can sit over gameplay
content rather than beside it), that is the §8.7/§8.8 architecture question
again and needs its own explicit decision, not an assumption from this
round's styling work.

## Log

- **2026-09-07** — Audit performed against `resources/diki` as it exists on
  disk (no git history available for that folder — treated as a point-in-time
  snapshot). Read in full: `app.py`, `main.py`, `ui/dashboard.py`,
  `ui/main_window.py`, `ui/canvas.py`, `ui/operator_panel.py`,
  `tasks/base_task.py`, `tasks/click_static.py`, `tasks/click_grid.py`,
  `tasks/scanning.py`, `tasks/follow_moving.py`, `engine/config.py`,
  `engine/feedback.py`, `engine/task_runner.py` (partial), `engine/
  calibration.py` (read for window-1 UX/copy only, not its wire-protocol
  internals, which are out of scope). Confirmed via `find`/`grep`: no
  `configs/`, `themes/`, `tests/`, or plan/README document ships with this
  copy of `diki`; `MainWindow`/`OperatorPanel` are unreferenced by `app.py`/
  `main.py` (dead code, superseded by `DashboardWindow`/`SubjectWindow`).
  This SPEC created fresh (new task, not a continuation of any existing
  `dev/peds-eye-gaze-assessment` SPEC). Nothing implemented or ported —
  documentation only, per the user's explicit scope.
- **2026-09-07, later** — `scanning`'s `scene_spec()` port (S3.1/S3.4)
  implemented as a pilot and live-validated via qt-mcp. Full account in the
  new `docs/specs/SPEC-scanning-task-design-port.md` — not duplicated here.
  This doc's own content is otherwise unchanged/still accurate as a
  reference for the undone pieces (click_grid, follow_moving, S4 palette).
- **2026-09-07, later still** — `click_grid` (S3.3) and `follow_moving`
  (S3.5) ported the same way, each live-validated via qt-mcp individually; a
  separate, unrelated theme-consistency fix (unify all four tasks to the
  `forest` theme) also applied. All of S3 (task design) is now fully
  ported — nothing left there. Committed and pushed to `origin/main` as
  `7958ba1`/`43ee2a1`/`712c29f`. Full account:
  `docs/specs/SPEC-scanning-task-design-port.md`. **This doc's own content
  (S4 palette, S5 window structure) remains undone/reference-only** — only
  the status header above was updated to reflect S3's completion.
- **2026-09-07, later still** — User asked whether diki's live Trial/Dwell
  panel design was already documented before requesting a fresh code
  inspection; confirmed it was (§4.2, §5) and no new `diki` reading was
  needed. Added §8: a port plan into `dev/`'s `OperatorPanel`, grounded in a
  fresh read of `src/ui/operator_panel.py`/`settings_registry.py`/`app.py`,
  per the user's three decisions (tooltips ported too, hide-while-idle
  behavior matched, recorded in this doc rather than a new SPEC file).
  Documentation only — nothing implemented yet; §8.2 flags an architectural
  mismatch (diki's multi-task idle browse state vs. `dev/`'s one-task-per-
  window launch model) that needs a decision before coding starts.
- **2026-09-07, later still** — User approved implementation. Resolved
  §8.2's open points (idle-state mismatch → dropped, hide-behavior not
  built; added a new End button beyond the original plan; tooltips drafted
  for all ~11 settings, not just diki's 2). Implemented in
  `src/ui/settings_registry.py`, `src/ui/operator_panel.py`,
  `src/ui/slider_spin.py`, `src/app.py`. Full account in §8.3/§8.4: pytest
  suite green (1 pre-existing unrelated failure only); live qt-mcp session
  confirmed the new Live box (big trial counter, hit/timeout tally,
  progress bar), Skip trial still advancing correctly, and the new End task
  button cleanly ending the session early via the existing shutdown path
  (13 trials written, no leftover process). **Not yet committed.**
- **2026-09-07, later still** — User described diki's live-controls area
  from memory (light, not black; separate bordered containers with a
  margin between them; font-color/typography/size all deliberate) and asked
  for validation. Re-read `ui/dashboard.py` directly rather than trusting
  §4's earlier summary. **Confirmed correct**, with one clarification added
  in §8.5: diki actually has two live-controls surfaces, and the
  description matches `DashboardWindow`'s "2 · Tasks" tab (light cream,
  separate 10px-spaced cards) — the opposite of `TaskHud` (a different,
  child-facing overlay, one merged dark panel). Added §8.5 with exact
  hex/pt/px citations and a side-by-side styling table for both surfaces.
  Validation only, per the user's explicit scope — nothing implemented or
  changed in `dev/`'s code this round.
- **2026-09-07, later still** — User approved proceeding straight from
  §8.5's validation to implementation. Ported §8.5's `DashboardWindow`
  column into `src/ui/operator_panel.py` as a new scoped `_STYLESHEET`
  (`QWidget#operatorPanel`-namespaced, so it cannot leak into `TaskCanvas`
  or any other window). Full account in §8.6: hit and fixed a real Qt
  gotcha along the way (`QWidget` ignores a stylesheet background without
  `WA_StyledBackground`, caught by a first qt-mcp screenshot showing
  correctly-styled cards on a still-black panel background); split the
  combined hit/timeout label into two separately-coloured labels to match
  diki's actual two-`QLabel` structure; bumped the trial counter from a
  placeholder 20pt to diki's real 34pt maroon. Pytest suite green (1
  pre-existing unrelated failure only); live qt-mcp confirmed the full
  cream sidebar with separated cards, correct colours/sizes throughout, and
  a clean End-task shutdown, both before and after the styling fix. **Not
  yet committed.**
- **2026-09-08** — User took a screenshot of `resources/diki` running and it
  did not match §8.6: it showed `TaskHud`, not `DashboardWindow`. §8.7
  corrected course and, after two `AskUserQuestion` rounds, designed a real
  corner-docked `TaskHud` for `dev/` (ported near-verbatim from `ui/
  dashboard.py:305-391`/`435-455`) sitting *alongside* the existing sidebar
  (§8.6 kept, not reverted) — mirroring diki's own HUD + `DashboardWindow`
  split. Also traced the user's separately-reported "vertical black bar" to
  a real bug: `main_window.py`'s `QHBoxLayout` never called `setSpacing(0)`.
  §8.8: implemented and live-validated across three qt-mcp rounds. Two real
  bugs caught and fixed along the way — a feedback-loop risk in the
  sidebar↔HUD sync (fixed with a new `SliderSpinRow.set_value_silently()`,
  since diki's own `blockSignals` guard had no direct `dev/` equivalent) and
  a stylesheet-parsing warning from mixing f-string/plain-string
  concatenation (fixed by moving to one `_STYLESHEET` f-string, matching
  `operator_panel.py`'s existing pattern). Bidirectional sync and the H-key
  toggle both explicitly verified live. Pytest suite green (1 pre-existing
  unrelated failure only) across all rounds. **Not yet committed.**
- **2026-09-08, later** — User clarified with two reference screenshots that
  §8.7/§8.8's corner `TaskHud` was not what they wanted: they wanted the
  *existing sidebar* restyled to `TaskHud`'s dark/cyan look, keeping its
  five separate cards (Status/Live/Controls/Settings/Pacing), not a second
  diki-ported widget. §8.9: removed `task_hud.py` and all its wiring
  (`main_window.py`'s HUD construction/`resizeEvent`/`toggle_hud`, `app.py`'s
  `Key_H` handler and sync calls, `OperatorPanel.sync_value`/`_controls`,
  `SliderSpinRow.set_value_silently` — all dead code once the HUD was gone);
  kept the `setSpacing(0)` black-bar fix (unrelated, still correct).
  Recoloured `operator_panel.py`'s `_STYLESHEET` from `DashboardWindow`'s
  light/maroon tokens to `TaskHud`'s dark/cyan ones, disclosing which four
  tokens (`_BG`/`_CARD`/`_BORDER`/`_BAD`) have no direct diki source since
  diki's only dark surface has no cards to source a card/border/background
  triad from. Pytest suite green (1 pre-existing unrelated failure only);
  live qt-mcp confirmed all five cards now render in the dark/cyan palette,
  Skip trial and End task both re-verified working, no new warnings. **Not
  yet committed.**
- **2026-09-08, later still** — User supplied two new reference screenshots
  (not from `diki`'s source, from actually running both apps) and a written
  prompt asking the sidebar to read as a floating HUD card rather than a
  full-height docked panel. Since a true translucent bleed-through of the
  canvas only happens via the corner-overlay architecture §8.9 explicitly
  rejected, asked via `AskUserQuestion` before coding: user chose to keep
  the side-column layout (simulating the float rather than reversing §8.9)
  and to group content into a few stacked cards rather than one scrollable
  one. §8.10: `OperatorPanel`'s five §8.9 cards regrouped into three
  (Status+Live, Controls, Settings+Pacing), each a rounded, drop-shadowed,
  ~90%-opacity `QFrame#hudCard`, inset within a column now background-matched
  to the canvas's own colour so the margin blends; type scale tightened
  throughout (trial counter to diki's own `TaskHud` 22pt size); `QGroupBox`
  pill titles replaced with small-caps subheadings. No public API changes.
  Pytest suite green (1 pre-existing unrelated failure only); live qt-mcp
  confirmed the floating-card look, Skip trial tally advancing correctly,
  and a clean End-task shutdown (no leftover `*src.main*` process). **Not
  yet committed.**
