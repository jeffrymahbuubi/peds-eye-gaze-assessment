# SPEC-scanning-task-design-port — Port diki's scene_spec() Design (all 4 tasks)

**Status:** **all four tasks now ported, plus a post-port theme-consistency
fix (§6).** `scanning` (pilot, §3), `click_grid` (§5.1), and `follow_moving`
(§5.2) each implemented and live-validated via qt-mcp against the
actually-running GUI; `click_static` needed no change (diki gives it no
dedicated scene either — stays `{"mode": "single"}`). All four tasks now
also share the same `forest` theme (§6 — `click_grid`/`follow_moving` were
still on the pre-existing `space` theme, an unrelated per-task config value
the port never touched, until the user's own visual audit caught it). Full
pytest suite green except the one pre-existing, already-documented
`test_config_merges_task_over_default` failure (unrelated `target_fps` stale
assertion). **Committed and pushed to `origin/main`**: `7958ba1` (this SPEC's
companion audit doc), `43ee2a1` (the scene_spec port, §1-§5), `712c29f` (the
theme fix, §6). Filename kept from the original pilot per this project's SPEC
convention (one cumulative doc per task, not renamed mid-stream).
**Created:** 2026-09-07
**Last updated:** 2026-09-07

## 1. Origin / what was asked

Follow-up to [[SPEC-diki-design-audit]] (`docs/specs/SPEC-diki-design-audit.md`),
which documented — but did not implement — `resources/diki`'s per-task
`scene_spec()` rendering mechanism as more expressive than this repo's
current generic `layout_slots` dim-outline approach (real grid cells,
distractor *shapes*, a motion trail, depending on task).

User's own instructions, this session:
1. Proceed with the task-design port, using diki's more expressive
   `scene_spec()` approach. **One task as a pilot**, not all four at once.
2. The pilot **must be real-validated with qt-mcp** (a live, running GUI
   inspection — not just pytest).

**Scope clarified before starting** (my own stated interpretation, not
disputed): this port is the *rendering mechanism* only — `scene_spec()` +
per-mode canvas drawing + the improved 2D icon-arrangement math. It does
**not** include diki's maroon/cream colour palette/QSS
(SPEC-diki-design-audit.md S4) — that is explicitly separate "design system"
work for a future session.

## 2. Decision: which task to pilot

Asked via `AskUserQuestion` (three options: `scanning`, `click_grid`,
`follow_moving`, each with a specific tradeoff). **User chose `scanning`.**
Reasoning offered for the recommendation, accepted implicitly by the choice:
`scanning` was this repo's visually weakest task (a single horizontal row of
unlit-circle outlines, no shape variety —
`src/tasks/scanning.py` pre-port) and diki's version is the clearest, most
self-contained win (2D arrangement + 6 distinct shapes) without touching
`follow_moving`'s live target-position math or `click_grid`'s already-working
grid rendering.

## 3. What shipped

### 3.1 `src/tasks/base_task.py`

- `TargetSpec` gained `slot_index: int = -1` (frozen dataclass, defaulted so
  every existing call site is unaffected). Lets the canvas know which static
  layout slot the *current* trial's target is, via
  `FrameResult.target.slot_index` — needed so the icon scene can draw the
  active slot in colour and every other slot as a distractor.
- `BaseTask.scene_spec() -> dict` added, default `{"mode": "single"}` —
  matches pre-existing rendering exactly for every task that doesn't override
  it (`click_static`, `click_grid`, `follow_moving` — all three untouched
  this round, confirmed by `test_default_scene_spec_is_single`).

### 3.2 `src/tasks/scanning.py` — rewritten

- `layout.arrangement` now supports `row` (kept, old behaviour),
  `ring` (new), and **`grid`** (new, and the new config default) — ported
  verbatim from diki's `_layout_slots` (favours more columns than rows via
  `cols = ceil(sqrt(n_icons))`, avoiding `round()`'s unwanted 2x3-for-6-icons
  case).
  - `layout.margin_frac` (new config key, default `0.14`) controls the inset
    from the screen edge for all three arrangements.
- Each icon slot gets one of 6 shapes (`i % 6` — circle/square/triangle/
  diamond/hex/star), stored as `self.icon_shapes`.
- `TargetSpec.slot_index` populated per trial.
- `self.layout_slots` **kept** as an alias for `self.icon_slots` — this is a
  deliberate compatibility decision, not an oversight: `tools/
  make_replay_fixture.py` and the existing `test_scanning_exposes_
  layout_slots_for_gui` test both read `task.layout_slots` directly, and
  removing it would have broken both for no benefit (diki has no fixture
  tool or that test to preserve).
- New `scene_spec()` returns `{"mode": "icons", "slots": [...],
  "shapes": [...]}`.

### 3.3 `src/ui/canvas.py`

- New shape constants + `_shape_path()` (circle/square/triangle/diamond/hex/
  star `QPainterPath` builder) and `_draw_icon_scene()` (draws every
  distractor slot except the active one, translucent, matching the
  `layout_slots` dim-outline's existing 0.25-ish opacity feel but as real
  silhouettes) — both ported near-verbatim from diki.
- `TaskCanvas.scene`/`active_slot` state added; `set_frame()` gained optional
  `scene`/`active_slot` params (both default to a no-op-safe value so
  existing call sites without them are unaffected).
- `paintEvent` now dispatches on `self.scene.get("mode", "single")`: `"icons"`
  draws the new distractor field instead of the old generic
  `_draw_layout_slots` dim-outline path; anything else (i.e. every other
  task, unchanged) keeps the pre-existing `layout_slots` dim-outline
  rendering exactly as before.
- `_draw_target()` now draws the active slot's own shape silhouette (scaled
  to 0.78x radius, matching diki) instead of a plain circle when
  `scene.mode == "icons"`; the bright "selectable" outline ring is still
  drawn as a plain ellipse regardless of shape (matches diki exactly — a
  deliberate, not accidental, inconsistency in the source design).

### 3.4 `src/app.py`

- `self._scene = self.task.scene_spec()` cached once, right after
  `self.task = build_task(...)` — fetched once per task run, not per frame,
  matching diki's own `scene_spec()` contract (`BaseTask.scene_spec`'s own
  docstring).
- `_tick()`'s existing `canvas.set_frame(...)` call gained
  `scene=self._scene` and `active_slot=(result.target.slot_index if
  result.target else -1)`.

### 3.5 `configs/tasks/scanning.yaml`

- `layout.arrangement: row` -> `grid` (the new, more-expressive default —
  diki's own stated reasoning is that a single row "is not real visual
  search," which is exactly the aesthetic/UX complaint motivating this whole
  port).
- Added `layout.margin_frac: 0.14`.

## 4. Testing

### 4.1 Headless / pytest

- `tests/test_task_pipeline.py`: 5 new tests (at the time of the pilot) —
  `test_default_scene_spec_is_single` (originally covered all 3 not-yet-ported
  tasks; narrowed to just `click_static` once §5 ported the other two —
  see that test's current form),
  `test_scanning_scene_spec_is_icons_with_shapes_and_slots`,
  `test_scanning_grid_arrangement_is_two_dimensional` (guards against a
  silent regression back to the single-row layout),
  `test_scanning_target_slot_index_matches_its_own_position`. Existing
  `test_scanning_exposes_layout_slots_for_gui`/`test_click_grid_...`/
  `test_click_static_has_no_layout_slots` all still pass unmodified.
- Full suite: same single pre-existing failure as every prior session
  (`test_config_merges_task_over_default`, stale `target_fps` 60-vs-150
  assertion — untouched, out of scope, documented in multiple earlier
  SPECs/memory).
- `tests/fixtures/gaze_replay_scanning.jsonl` regenerated via
  `tools/make_replay_fixture.py --task scanning` (target positions changed
  under the new grid arrangement, so the old row-based fixture no longer
  matched real target positions).
- Headless replay against the regenerated fixture:
  `python -m src.main --task scanning --replay tests/fixtures/gaze_replay_scanning.jsonl`
  -> `trials=6 hits=6 timeouts=0`. Confirms hit-testing/`slot_index`/position
  math all agree at runtime, not just in unit tests.

### 4.2 Live qt-mcp validation (the user's explicit ask)

Launched the real GUI (`QT_MCP_PROBE=1 QT_MCP_PORT=9142 python -m src.main
--task scanning --gui --replay <fixture> --subject QAPILOT`) and drove it via
the `qt-mcp` tools against the actually-running app — not a mock or an
offscreen script.

- Clicked through the (unrelated, pre-existing) `TaskSettingsDialog`
  pre-launch dialog via `qt_click` on its "Start task" button, then confirmed
  the main task window opened (`qt_list_windows` -> `MainWindow 1280x800`).
- `qt_screenshot(full_window=true)` **visually confirmed**: 4 icons in a real
  2x2 grid (not a single row), 4 distinct shapes rendered (circle, square,
  triangle, diamond — the 4th/5th/6th shapes weren't exercised at
  `n_icons=4`, expected), the active target (a diamond that trial) in full
  saturated colour with the white "selectable" outline ring, the other 3
  rendered as pale translucent silhouettes exactly matching their true
  shapes (not generic dim circles). `OperatorPanel` showed accurate live
  status (`Trial: 1/6`, `FPS: 167`, `Gaze: valid`) throughout, confirming the
  change didn't regress the existing operator-facing telemetry.
- `qt_messages(level="warning")` showed only the two already-known,
  already-documented `QSoundEffect` audio-device warnings (see
  [[peds-eye-gaze-assessment-sound-feedback-2026-09-03]]) — **no new
  warnings or errors** from this change.
- Let a full 6-trial run play out (a deliberately slow, QA-only replay
  fixture built in the scratchpad — `hold_s=0.3s` per position, below the
  800ms dwell threshold, so every trial times out instead of completing in
  ~5s, giving a wide inspection window instead of racing a fast-finishing
  process). Cross-checked the resulting `trials.csv`: target coordinates
  were exactly `(0.32, 0.32)`/`(0.32, 0.68)`/`(0.68, 0.32)`/`(0.68, 0.68)` —
  precisely what the grid formula predicts for `n_icons=4`,
  `margin_frac=0.14` (`span=0.72`, `cols=rows=2`,
  `x = 0.14 + 0.72*(c+0.5)/2`). Confirms the live app's actual runtime
  positions match the algorithm exactly, not just the unit tests' own
  assertions about it.
- Process exited cleanly on its own once all 6 trials finished (confirmed via
  `Get-CimInstance Win32_Process` showing no leftover process) — no hang, no
  crash.

**Process gotcha hit and resolved this session, worth remembering for next
time:** launching a GUI app via `Bash ... & ; echo done` with
`run_in_background: true` reports the *wrapper shell* as "completed" almost
immediately (since `&` detaches it), **not** the actual long-running Qt
process — the notification arriving quickly does not mean the app exited.
Conversely, `qt_list_windows` right after launch can fail with
`Failed to connect to probe ... refused` if `QT_MCP_PROBE=1`/`QT_MCP_PORT`
weren't set on that launch (the probe never attaches without them — see
[[qt-mcp-tool-reference]], which already documented this but it was easy to
forget when composing a one-off launch command). Two stray prior-attempt
processes were left running simultaneously before this was sorted out;
cleaned up via `Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
Where CommandLine -like '*src.main*' | Stop-Process -Force` (the same
Windows-specific pattern already on record in
[[peds-eye-gaze-assessment-physician-feedback-2026-09-02]] for killing a
detached background process by real PID, not `tasklist`).

## 5. `click_grid` and `follow_moving` (rest of the port)

User: "proceed with porting the rest of the tas[ks], validated for each port
with qt-mcp." No new clarifying question was needed — the pattern was already
settled by the pilot (§1-§4): same `scene_spec()` mechanism, same
compatibility approach (keep `layout_slots` where an existing consumer reads
it), same out-of-scope boundary (no palette/QSS). Unlike `scanning`, neither
task's `build_targets()`/hit-testing math changed — both ports are purely
additive rendering, so no config defaults changed and no fixtures needed
regenerating.

### 5.1 `click_grid` -> `"grid"` mode

- `src/tasks/click_grid.py`: now stores `self.rows`/`self.cols`/`self.cells`/
  `self.cell_w`/`self.cell_h` (identical cell-centre math as before, just
  retained on the instance) and populates `TargetSpec.slot_index` per trial.
  `self.layout_slots = cells` kept for the existing
  `test_click_grid_exposes_layout_slots_for_gui` test and
  `tools/make_replay_fixture.py`. New `scene_spec()` returns `{"mode":
  "grid", "rows", "cols", "cells", "cell_w", "cell_h"}`.
- `src/ui/canvas.py`: new `_draw_grid_scene()` (ported from diki) draws every
  *inactive* cell as a real rounded-rect (`drawRoundedRect`, 14px radius, a
  faint themed border + fill) instead of the old generic dim-outline circle;
  `paintEvent` dispatches to it when `scene.mode == "grid"`. The active cell
  is still drawn by the existing `_draw_target` (a plain filled circle —
  diki does not shape-brand the grid task's target, only `scanning`'s, and
  this port matches that exactly).
- Tests: `test_click_grid_scene_spec_is_grid_with_cells`,
  `test_click_grid_target_slot_index_matches_its_own_cell` (new). Existing
  `test_click_grid_exposes_layout_slots_for_gui` untouched, still passes.
- Headless: `python -m src.main --task click_grid --replay
  tests/fixtures/gaze_replay_click_grid.jsonl` -> `trials=18 hits=12
  timeouts=6`, **identical to pre-port** (this fixture/hit-testing path was
  not touched — confirms the port is rendering-only).
- **Live qt-mcp**: launched against the existing committed fixture (no
  QA-only slow fixture needed this time — the real fixture's own timeout
  trials already gave enough of a window). Screenshot confirmed a real 3x3
  grid of rounded-rect cells (dark, faint-bordered) with the active cell
  showing the full-colour circular target + white selectable-ring on top;
  `qt_messages(level="warning")` showed only the same two already-known
  `QSoundEffect` warnings, nothing new.

### 5.2 `follow_moving` -> `"moving"` mode

- `src/tasks/follow_moving.py`: new `scene_spec()` returns `{"mode":
  "moving", "path": self.path, "speed": self.speed}` — `self.path`/
  `self.speed` already existed on the instance (set in `build_targets`), no
  new state needed. `target_position()`/`is_selectable()` untouched.
- `src/ui/canvas.py`: new `TaskCanvas._trail` history list + trail-management
  logic added to `set_frame()` itself (not `paintEvent`) — appends the live
  `target_xy_norm` every frame when `scene.mode == "moving"`, capped at 90
  entries (~1.5s at 60Hz), and clears when `target_xy_norm` goes `None`
  (i.e. during ITI between trials) so the trail never bridges a teleport to
  the next trial's start position. New `_draw_trail()` (ported from diki)
  paints it as a fading series of shrinking, alpha-fading circles in the
  target's own colour; `paintEvent` dispatches to it when
  `scene.mode == "moving"`.
- Tests: `test_follow_moving_scene_spec_is_moving_with_path_and_speed` (new).
- Headless: `python -m src.main --task follow_moving --replay
  tests/fixtures/gaze_replay_follow_moving.jsonl` -> `trials=6 hits=3
  timeouts=3`, **identical to pre-port** (same reasoning as click_grid above
  — target-position/selection-window math untouched).
- **Live qt-mcp**: launched against the existing committed fixture (circular
  path, per `configs/tasks/follow_moving.yaml`'s `motion.path: circular`).
  Screenshot **visually confirmed a real fading trail** behind the moving
  target — a distinct blue tail curving away from the ball in the direction
  of travel, alongside the (pre-existing, unaffected) yellow selectable-
  window ring and gaze cursor dot. `qt_messages(level="warning")` — same two
  already-known warnings only.

### 5.3 Process notes for this round

Same qt-mcp launch pattern as §4.2 (`QT_MCP_PROBE=1 QT_MCP_PORT=9142`,
kill any leftover `*src.main*` python process between task launches via
`Get-CimInstance Win32_Process` before starting the next one). One
`qt_snapshot` call returned a transient `"Connection lost"` immediately after
the `click_grid` launch — matches the already-documented
[[qt-mcp-tool-reference]] gotcha (retry once rather than assuming the probe
setup broke); the retry succeeded immediately.

## 6. Post-port theme-consistency fix

User's own visual audit of the ported tasks: "I audit[ed] the click_grid and
follow_moving task, the theme background color is differ with the other two
task, it still used the old one."

**Root cause, confirmed by reading the configs before changing anything**
(not assumed): each task YAML has always carried its own `theme:` key,
untouched by any of §3-§5's work — `click_static.yaml`/`scanning.yaml` were
already `theme: forest` (light green `#e8f5e9`), `click_grid.yaml`/
`follow_moving.yaml` were already `theme: space` (dark navy `#0d1b2a`). This
predates the whole scene_spec port; nothing in this SPEC's own changes
touched theme loading (`src/app.py:112-113`) or any task's `theme:` value.

**Asked the user which direction to resolve it** (three options: unify to
`forest`, unify to `space`, or leave the two-theme split as intentional
variety) rather than assuming — this is a content/design decision, not a
bug fix. **User chose: unify all four to `forest`.**

- `configs/tasks/click_grid.yaml` and `configs/tasks/follow_moving.yaml`:
  `theme: space` -> `theme: forest`.
- Confirmed `forest`'s sound assets exist at
  `configs/assets/sounds/forest_{hit,miss}.wav` (both tasks' `feedback.
  hit_sound`/`miss_sound` are `true`, so a missing asset would have been a
  real regression, not just cosmetic) before making the change, not after.
- Full pytest suite re-run: same single pre-existing failure, no new ones.
- **Live qt-mcp, both tasks individually**: `click_grid` screenshot now
  shows the light `forest` background with the 3x3 rounded-rect grid in
  forest's palette (green cursor dot, red target) instead of the previous
  dark navy; `follow_moving` screenshot likewise shows the light background
  with the motion trail (§5.2) still rendering correctly in forest's red
  target colour. `qt_messages(level="warning")` — same two already-known
  `QSoundEffect` warnings only, both times, confirming the forest sound
  assets loaded without error.

## 7. Not done / open items

- **Committed and pushed** to `origin/main` as three commits: `7958ba1`
  (`docs/specs/SPEC-diki-design-audit.md`), `43ee2a1` (the scene_spec port —
  `configs/tasks/scanning.yaml`, `src/app.py`, `src/tasks/base_task.py`,
  `src/tasks/click_grid.py`, `src/tasks/follow_moving.py`,
  `src/tasks/scanning.py`, `src/ui/canvas.py`,
  `tests/fixtures/gaze_replay_scanning.jsonl`, `tests/test_task_pipeline.py`,
  and this SPEC), `712c29f` (the theme fix —
  `configs/tasks/click_grid.yaml` + `follow_moving.yaml`). Confirmed via
  `git log --oneline origin/main..HEAD` returning empty (nothing ahead) after
  the push. Nothing from this line of work remains uncommitted.
- **All four tasks' `scene_spec()` rendering is now ported** — this item
  from the original pilot's open list is resolved; nothing left on the
  rendering-mechanism side of SPEC-diki-design-audit.md S3.
- **diki's colour palette/QSS is still not ported** — explicitly out of
  scope for this whole line of work (see S1). All three ported tasks render
  their new shapes/cells/trail in the *existing* `dev/` theme colours
  (`configs/themes/*.yaml`), not diki's maroon/cream system. This remains
  the one undone piece of SPEC-diki-design-audit.md's three (task design /
  design system / UX flow) — task design is now fully ported, design system
  is not started, UX flow (the 3-window structure) was explicitly out of
  scope for this line of work entirely.
- The QA-only slow fixture used for `scanning`'s live inspection
  (`gaze_replay_scanning_slow.jsonl`) lives only in that session's
  scratchpad, not the repo — never meant to be committed.

## Log

- **2026-09-07** — Pilot task-design port (`scanning`) implemented and
  live-validated. Full account in §1-§4. Headless: full pytest suite green
  (1 pre-existing unrelated failure), replay 6/6 hits. Live: qt-mcp
  screenshot + `trials.csv` cross-check confirm the 2x2 grid, 4 distinct
  shapes, and correct active/distractor rendering against the
  actually-running GUI.
- **2026-09-07, later** — `click_grid` and `follow_moving` ported the same
  way, each live-validated via qt-mcp individually. Full account in §5.
  Headless hit/timeout counts for both are bit-identical to pre-port (purely
  additive rendering change, no hit-testing/build_targets math touched).
  Live: `click_grid` screenshot confirmed real rounded-rect grid cells;
  `follow_moving` screenshot confirmed a real fading motion trail behind the
  live target. No new Qt warnings in either case. All four tasks' scene
  rendering is now ported end-to-end.
- **2026-09-07, later still** — User's own visual audit caught
  `click_grid`/`follow_moving` still rendering the pre-existing `space`
  (dark) theme instead of `forest` (light), unlike `click_static`/`scanning`.
  Confirmed the root cause was each task's own long-standing `theme:` config
  value, untouched by this SPEC's own port work. Asked the user which
  direction to unify (3 options); **user chose `forest` for all four**.
  `configs/tasks/click_grid.yaml` + `follow_moving.yaml` updated; full pytest
  suite still green (1 pre-existing failure only); both tasks individually
  re-validated live via qt-mcp — screenshots confirm the light background
  now applies and each task's ported scene (grid cells / motion trail) still
  renders correctly under it; no new Qt warnings. Full account in §6.
- **2026-09-07, later still (via `/sparc:devops`)** — All of the above
  committed as three commits (`7958ba1`, `43ee2a1`, `712c29f`) and pushed to
  `origin/main`. Nothing from this SPEC remains uncommitted.
