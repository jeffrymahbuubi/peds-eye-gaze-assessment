# SPEC-diki-design-audit — Colleague Codebase Audit: Task Design & Design System

**Status:** audit complete (documentation only). **Superseded-forward note
(2026-09-07):** the `scanning` task's `scene_spec()` mechanism (S3.1) has
since been implemented and live-validated — see
`docs/specs/SPEC-scanning-task-design-port.md` for that work. Everything
else in this doc (click_grid/follow_moving scenes, the S4 design system/
palette, the S5 window-structure notes) is still undone/reference-only.
**Created:** 2026-09-07
**Last updated:** 2026-09-07

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
