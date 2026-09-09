# SPEC-result-logic — Result Logic (session metrics, results screen, calibration data)

**Status:** §1-§9 are all implemented, unit-tested, and live-validated.
§8's redesign (calibration details inline section, the dedicated "3 ·
Results" tab, the 4-category metric layout) is now **built, not just
designed** — see §9. §3's original auto-shown-after-every-run Results page
has been reverted/replaced by §8's flow exactly as specified. A real,
previously-undocumented bug was also found and fixed this round (§9): the
Session Log panel's data source, `session.log`, was silently empty for
every normal run before this fix — see §9's "real bug" note before trusting
this doc's own earlier §8.3 claim that it needed no new capture.
**Everything in this SPEC remains UNCOMMITTED working-tree changes** —
ask-before-commit, matching this project's established pattern.
**Created:** 2026-09-09
**Last updated:** 2026-09-09

## 1. Origin / what was asked

Session objective, stated as: "The main objective on this session would be
relevant to Result logic." Investigation (before any code was written) found
that every task run already writes raw `trials.csv`/`gaze_stream.csv`/
`events.jsonl`/`metadata.json` (`src/data/recorder.py`), but the rolled-up
result (hit rate, mean reaction time, fixation/saccade/pupil aggregates,
already implemented in `src/data/exporter.py`) was only ever computed if
someone manually ran `analysis/analyze_session.py <session_dir>` afterward —
neither the GUI nor disk ever showed a result automatically right after a run.

Four items were scoped with the user (via clarifying questions):

1. Auto-generate `session_metrics.json` on every run (live GUI + headless
   `--replay`), instead of requiring the manual script.
2. Show a results screen in the GUI after a task run finishes, before
   returning to the Tasks dashboard.
3. Result-scoring logic (hit/miss/timeout) — flagged only; the user had no
   concrete change in mind, so `src/tasks/base_task.py` was explicitly left
   untouched this session.
4. A research question, not a build request: does a metric already exist
   (from Gazepoint's own API) describing a single calibration point-count's
   result (accuracy/error)? This surfaced `CALIB_RESULT`, a per-point/per-eye
   record the API already pushes that the code was silently discarding — the
   user asked to capture it now (cheap plumbing) even though the actual
   n-point comparison/tradeoff logic is explicitly deferred to later, after
   real n-point data collection with a cooperative subject.

## 2. Part 1 — auto-generated `session_metrics.json`

**New function**, `src/data/exporter.py::write_session_metrics(session_dir)`:
combines the three functions that already existed (`summarize()`,
`compute_fixation_saccade_metrics()`, `compute_trial_fixation_counts()`) into
the same `{"summary", "fixation_saccade", "fixations_per_trial"}` shape
`analysis/analyze_session.py` used to build inline, and writes it to
`session_metrics.json`.

- `analysis/analyze_session.py` now calls `write_session_metrics()` instead of
  duplicating the `json.dumps`/`write_text` — no behavior change to the
  script's own output.
- `src/app.py::AssessmentApp._shutdown()` calls it right after
  `self.recorder.close()`, so every live GUI run auto-produces the file.
- `src/engine/task_runner.py::run_headless_replay()` now explicitly calls
  `recorder.close()` right after `write_trials()` (idempotent — guarded by
  `SessionRecorder._closed`), then `write_session_metrics()`, and returns a
  new `"session_metrics_path"` key.
- No new dependency on either path — the three reused functions are stdlib
  `csv`/`json`/`statistics` only (`pandas` stays a lazy import elsewhere).

**Test:** `tests/test_task_pipeline.py::test_headless_replay_auto_writes_session_metrics`
asserts the file exists after a headless replay and its contents match
`summarize()`/`compute_fixation_saccade_metrics()` computed independently.

## 3. Part 2 — GUI results screen

**New file**, `src/ui/results_page.py` — `ResultsPage(QWidget)`. Follows
`TaskSettingsDialog`'s existing card pattern (`QFrame#wtmhCard` +
`QGraphicsDropShadowEffect`), reusing `wtmh_theme.py`'s existing
`wtmhPageTitle`/`wtmhSectionTitle`/`wtmhMuted`/`wtmhPrimary` object names — no
new CSS. Shows task/subject/session header, a "Summary" block (trials, hits,
hit rate, timeouts, mean reaction time — from `exporter.summarize()`), and a
"Gaze quality" block (valid gaze ratio, fixations, fixation duration
mean/median/max, saccades, pupil L/R mean — from
`exporter.compute_fixation_saccade_metrics()`), plus a "Continue" button
(`continue_requested` signal). Both exporter calls already degrade to
`None`/zero on an empty session rather than raising, so `populate()` needed no
extra guarding — `None` renders as "—".

**`src/ui/dashboard_window.py` changes:**
- `self.results_page = ResultsPage()` added to `self.stack` at construction
  (`_RESULTS_INDEX = 2`; the dynamically-appended embedded task view's index
  shifted from 2 to 3, `_RUN_INDEX = 3`).
- `_on_task_finished` split in two: it now captures
  `assessment.recorder.session_dir` before tearing down the view, calls
  `self.results_page.populate(...)`, and shows the Results page — instead of
  jumping straight back to Tasks. The former tail of `_on_task_finished`
  (mark task "Complete", re-enable nav/run buttons, switch to Tasks) moved
  into a new `_on_results_continue()`, wired to the Results page's
  `continue_requested` signal.
- **Bug this split would otherwise introduce, fixed in the same change:**
  `_go_to_tab`'s guard only checked `self._active_assessment is not None`.
  Since `_on_task_finished` sets that to `None` before showing the Results
  page, an operator clicking the top "Setup"/"Tasks" nav buttons while
  Results was showing would bypass `_on_results_continue` entirely, leaving
  Tasks' run buttons and the Setup nav button permanently disabled (their
  re-enable now only happens in `_on_results_continue`). Fixed with a new
  `self._viewing_results` flag, set/cleared alongside the page switch, and
  added to `_go_to_tab`'s guard: `if self._active_assessment is not None or
  self._viewing_results: return`.

## 4. Part 3 — result-scoring logic (hit/miss/timeout)

No code change. `src/tasks/base_task.py`'s trial state machine (hit =
on-target selection while `selectable`; anything else clicked is a
miss/attempt; no response by `timeout_ns` is a timeout) is exactly as it was
before this session. Flagged here only, per the user's own explicit answer
("nothing concrete yet — flag it, don't change it").

## 5. Part 4 — capture Gazepoint's `CALIB_RESULT` (per-point/per-eye)

**Research finding** (`docs/gazepoints/sources/gazepoint-api.md` §4.3): the
OpenGaze API pushes a `CALIB_RESULT` record once, unprompted, at the end of
calibration — per point *i*: target (`CALXi`/`CALYi`), left-eye estimate +
validity (`LXi`/`LYi`/`LVi`), right-eye estimate + validity
(`RXi`/`RYi`/`RVi`). This is richer than the single `AVE_ERROR` scalar the
code already captured via `CALIBRATE_RESULT_SUMMARY` — but
`Calibration._poll_for_result` was explicitly discarding it (the existing
comment "ignore CALIB_START_PT/CALIB_RESULT_PT progress records" covered this
line too). **No n-point comparison/tradeoff metric was built** — that's
explicitly deferred until real n-point data collection with a cooperative
subject; this session only added the raw capture.

**Changes, all in `src/engine/calibration.py`:**
- New `_parse_calib_result(attrs)` helper: finds every point index present as
  `CALXi` and builds `{"point", "target_x", "target_y", "left": {"x","y",
  "valid"}, "right": {...}}` per point (a missing eye's keys → `None` for that
  eye, not a crash).
- `CalibrationResult` gets a new field `per_point: tuple[dict, ...] | None =
  None` (a tuple, not a list, to stay compatible with the frozen/slotted
  dataclass).
- `_poll_for_result`'s read loop now also matches `tag == "CAL" and
  attrs.get("ID") == "CALIB_RESULT"`, parses it, and attaches it to every
  `CalibrationResult` the method can return. **Known, accepted limitation:**
  if `CALIB_RESULT` arrives *after* the qualifying `CALIBRATE_RESULT_SUMMARY`
  line within the same socket read, the method's existing early-return will
  miss it — best-effort enrichment, not a regression of the existing scalar
  result.
- `save_calibration_result()`/`load_calibration_result()` read/write the new
  `"per_point"` key. Unlike every other field in `calibration.json` (which
  hard-fail via `CalibrationFileError` if missing), `per_point`'s absence is
  **not** an error — `.get("per_point")` defaults to `None` — so a
  `calibration.json` written before this change still loads fine.

**Tests added, `tests/test_calibration.py`:**
`test_run_captures_calib_result_per_point_breakdown`,
`test_run_returns_none_per_point_when_calib_result_never_sent`,
`test_save_then_load_round_trips_per_point`,
`test_load_calibration_file_without_per_point_key_still_loads`.

## 6. Live validation (§2/§3, qt-mcp)

Launched `tools/fake_gazepoint_server.py 4243` (device-free testing, per this
project's established convention) and the dashboard
(`QT_MCP_PROBE=1 QT_MCP_PORT=9142 python -m src.main --dashboard`), maximized
first per this project's own qt-mcp gotcha. Full flow, subject `TESTRESULTS`,
task `click_static`:

1. Connect → "Connected."; Do Calibration → "Calibration measured — 5 points,
   mean error 8px, valid." (`calibration.json`'s `per_point` was `null` here,
   as expected — the fake server sends `CALIBRATE_RESULT_SUMMARY` only, no
   `CALIB_RESULT`).
2. Continue to Tasks → Run (Static Click) → task view appeared, live
   HUD showed `Trial: 2/32`, `0 hit 1 timeout` (fake server streams no gaze
   samples, so every trial times out — expected, not a bug).
3. "End task" → **Results page appeared** showing: Task `click_static`,
   Subject `TESTRESULTS`, Session `2026-09-09_TESTRESULTS_click_static_run1`;
   Trials 2, Hits 0, Hit rate 0.0%, Timeouts 2, Mean reaction time "—"; every
   Gaze-quality field correctly "—"/0 (no gaze stream from the fake server).
4. "Continue" → correctly returned to Tasks with status badge "Complete",
   run buttons and "Setup" nav re-enabled.
5. Confirmed on disk: `sessions/2026-09-09_TESTRESULTS_click_static_run1/
   session_metrics.json` matched the Results page's numbers exactly;
   `calibration.json` had `"per_point": null` as expected.

Test session directory deleted afterward (`sessions/` is gitignored — see
`.gitignore:18` — so this never touched git status).

## 7. Test status

Full `pytest` (`collected 122 items`, `1 failed, 121 passed`) — the failure is
`tests/test_task_pipeline.py::test_config_merges_task_over_default`
(`cfg["app"]["target_fps"] == 60` fails, actual `150`), the same single
pre-existing, unrelated failure recorded before this session's changes
(local `configs/default.yaml`/`configs/local_state.json` drift, not caused by
any change in this SPEC).

## 8. Design-only redesign round (§3's flow superseded)

**Trigger:** the user audited §3's just-built GUI via a real screenshot and
gave feedback redesigning the whole results/calibration-quality flow,
referencing a colleague's reference UI at `resources/images/diki-ui-3.png` (a
diki "Operator Dashboard" mockup: a 4-category metrics table — Data quality,
Fixation, Saccade, Selection — plus a Session Log panel). **Explicit scope for
this round, stated by the user: SPEC/design only, no implementation** — "The
implementation will be done later after I clear the context." Three
architectural forks were resolved via `AskUserQuestion` before wireframing;
resolutions folded directly into §8.1-§8.3 below.

### 8.1 Calibration quality-check — "View Calibration Details"

A new button, **"View Calibration Details,"** placed next to Do
Calibration/Load Calibration File on the Setup page, gated the same way
Continue to Tasks already is (disabled until a calibration result exists).
Clicking it expands an **inline section in place** under the Calibration card
— **not a modal dialog** (user's explicit choice; a modal would also block
the qt-mcp automation probe during testing, per
[[qt-mcp-tool-reference]]'s already-documented `QDialog.exec()` gotcha, and
this dashboard already prefers inline expansion elsewhere).

Contents: the existing one-line summary (unchanged), plus a **new per-point
breakdown table** — Point #, Target (X, Y), Left eye estimate (X, Y) + valid,
Right eye estimate (X, Y) + valid, and a **new derived per-point Error (px)**
column (Euclidean distance, target vs. each eye's estimate — not computed
anywhere in this codebase yet, would need to be added alongside this UI).
Sourced from `CalibrationResult.per_point` (§5 above). **Placeholder/empty
state:** when `per_point` is `None` (older `calibration.json`, or a device
path that never sent `CALIB_RESULT`), the table becomes a single centered row,
"Per-point breakdown not available for this calibration." — the summary alert
above still renders normally either way.

Wireframed at `docs/wireframes/setup.md` (new "Calibration Details (expanded
state — illustrative)" section) / `setup.html`.

### 8.2 §3's Results page is superseded — dedicated "3 · Results" tab instead

**§3's behavior (auto-show a Results page the instant a task run finishes,
before returning to Tasks) is superseded as of this round.** New design: a
task run finishing returns **directly to the Tasks page**, exactly like
before §3 existed. Results instead becomes **a dedicated third persistent
top-level nav tab, "3 · Results,"** alongside the existing "1 · Setup" /
"2 · Tasks" — reachable either by clicking that tab directly, or via each
task card's **"Analyze"** button (enabled only once that task shows
"Complete"). Per the user's explicit choice, it shows **the most recent run
only** for whichever task was last analyzed — no run-picker in this phase,
even though re-runs already get their own `_run1`/`_run2`/... session
folders on disk.

**This is a design decision, not yet code** — §3's `ResultsPage`/
`dashboard_window.py` wiring described above still auto-shows after every run
as originally built; reverting it into this new flow, and building the new
tab, are both future implementation work (see the Status header).

### 8.3 Dedicated Results page layout — modeled on `diki-ui-3.png`

Layout: a page header naming the task + trial count (e.g. "Static Click — 32
trials"), then **four metric-category tables**, in this exact order, matching
the reference image's own structure:

1. **Data quality** — Valid samples, On-screen samples, Effective rate,
   Calibration error (raw), Longest gap
2. **Fixation** — Mean duration, Median duration, Rate
3. **Saccade** — Mean amplitude, Mean direction, Latency (to first fixation)
4. **Selection** — Hit rate, Median RT, Mean attempts, Mean revisits, Trials
   needing re-attempt, plus a conditional warning banner (e.g. "! valid share
   62% below the 80% floor") when Valid samples falls below a floor

...then a **Session Log** panel at the bottom, showing `session.log` verbatim
— this needs **no new capture at all**, `SessionRecorder` already writes it
every run today; only a UI panel to display it is new.

Wireframed at `docs/wireframes/results.md` / `results.html` (new files), with
`docs/wireframes/_nav.md` updated to add the "Results" link (now a 3-page
nav) and `docs/wireframes/tasks.md` updated with a design note clarifying
Run→Tasks (not Results) and Analyze→`results.md`.

### 8.4 Metrics-category gap report (given to the user before wireframing)

Of the reference image's ~19 metric rows, **9 already have real data behind
them in this codebase today**: `valid_ratio`, calibration `mean_error_px`,
fixation mean/median duration, fixation rate, `hit_rate`, raw
`time_to_first_fixation_ms` per trial, raw `attempts` per trial, and
`session.log` itself. The remaining rows split into two gap classes, **none
implemented this session**:

- **Cheap — aggregation only, over data already recorded** (~6 rows):
  effective rate (`n_samples`/duration), longest gap (max consecutive `t_ns`
  delta), median RT, mean attempts, trials needing re-attempt
  (`attempts > 1` count), a session-level mean latency-to-first-fixation
  aggregate.
- **Needs genuinely new tracking/capture logic** (~3 rows): on-screen bounds
  check (x/y within `[0,1]`), saccade amplitude/direction (needs fixation
  *centroid* tracking — today only fixation-id transitions are counted, not
  positions), mean revisits (needs on-target entry/exit tracking, not just
  first-fixation + attempt count).

The wireframe at `results.md` uses "—" placeholders for every not-yet-computed
row, matching the reference image's own convention for empty/pending values.

### 8.5 Process rule adopted this round

**Any future UI design/creation task in this project must produce a
wireframe via the `/wireframe` skill first, before implementation** — adopted
per the user's explicit instruction this round, going forward for all future
sessions, not just this one.

### 8.6 What was actually touched this round (files, not app code)

`docs/wireframes/_nav.md` (added the Results link), `docs/wireframes/setup.md`
+ `setup.html` (new button + inline expanded-state section, re-rendered and
re-themed via `tools/apply_wtmh_wireframe_theme.py`), `docs/wireframes/
tasks.md` + `tasks.html` (design-note update only — re-rendered/re-themed to
keep the HTML in sync with the `.md`, but not independently re-screenshotted
since the change was text-only), new `docs/wireframes/results.md` +
`results.html`. **`setup.html` and `results.html`** were verified visually via
a Playwright screenshot (`file:///.../docs/wireframes/{setup,results}.html`)
— confirmed correct against the WTMH Clinical Teal palette, including
catching and fixing a real wiremd rendering quirk: `|Yes|{.success}` badge
syntax does **not** parse inside a markdown table cell (prints the literal
attribute string instead) — fixed by using plain "Yes"/"No" text in the
per-point breakdown table. **No file under `src/` or `tests/` was touched
this round.**

## 9. §8.1-§8.3 implemented and live-validated

**All of §8's design is now built.** New/changed files, all in
`dev/peds-eye-gaze-assessment/`:

- `src/data/exporter.py` — `compute_fixation_saccade_metrics()` gained
  `on_screen_ratio` (fraction of valid samples whose normalized x/y both fall
  in `[0, 1]`), `effective_rate_hz` (`n_samples / duration_s`), and
  `longest_gap_s` (max consecutive `t_ns` delta). `summarize()` gained
  `median_reaction_time_ms`, `mean_attempts` (over *all* trials, including
  0-attempt timeouts — a deliberate choice, not a bug, since a trial that was
  never clicked is still a real data point for the mean), `n_trials_needing_
  reattempt` (`attempts > 1` count), and `mean_time_to_first_fixation_ms`.
- `src/engine/calibration.py` — new `per_point_errors_px(per_point,
  screen_width_px, screen_height_px)`: per-eye Euclidean pixel error (target
  vs. estimate, normalized coordinates scaled by the configured screen
  dimensions, same convention as `BaseTask.set_screen_size`). An eye with
  `valid: false` still gets an error computed if its estimate is present —
  validity and "was a distance computed" are different questions.
- `src/ui/setup_page.py` — new "View Calibration Details" button (disabled
  until a calibration result exists, same gating as Continue to Tasks),
  toggling an inline `QTableWidget` per-point breakdown (Point / Target (X,Y)
  / Left eye (X,Y) / Left valid / Right eye (X,Y) / Right valid / Error (px))
  under the Calibration card — not a modal, per §8.1. Shows "Per-point
  breakdown not available for this calibration." when `per_point` is `None`.
  Collapses on every new `Do Calibration`/`Load Calibration File` result so a
  stale table from a prior subject/run can never linger visible.
- `src/ui/wtmh_theme.py` — new `QTableWidget`/`QHeaderView` styling (no table
  had ever been themed in this app before); `QPlainTextEdit` added to the
  existing input-field theming block (see the real bug below).
- `src/ui/results_page.py` — **fully rewritten**, not incrementally changed,
  from §3's single-card summary+gaze-quality form into §8.3's design: a page
  header (task name + trial count), a conditional warning banner (shown when
  valid-sample share falls below an 80% floor, per §8.3's example wording),
  four metric-category cards — **Data quality** / **Fixation** / **Saccade**
  / **Selection** — and a **Session Log** panel showing `session.log`
  verbatim. Implemented as `QFormLayout` metric→value rows inside
  `QFrame#wtmhCard` cards (reusing the existing card pattern) rather than a
  literal `QTableWidget` per category — a deliberate simplification, visually
  equivalent to the wireframe's table rows without introducing new per-row
  widget styling. Per §8.4's gap classes, **Saccade's Mean amplitude/Mean
  direction and Selection's Mean revisits are deliberately left "—"** — they
  need fixation-centroid/on-target-revisit tracking this codebase still
  doesn't capture, not implemented this round. The page's signal was renamed
  `continue_requested` → `backRequested` (no more "continue past a blocking
  step" semantics — Results is just a tab now).
- `src/ui/tasks_page.py` — `_TASK_INFO` renamed to public `TASK_INFO` (now
  also imported by `results_page.py` for task display names). `_TaskCard`/
  `TasksPage` gained an `analyzeRequested(task_id)` signal wired to the
  previously-inert Analyze button (was permanently disabled with a "Coming
  soon" tooltip since §6.2; now enabled exactly when that task's status is
  "Complete", matching the existing status-badge logic).
- `src/ui/dashboard_window.py` — the core rewiring. §3's auto-show-Results-
  after-every-run behavior and its `_viewing_results` flag are gone entirely;
  `_on_task_finished` now returns straight to Tasks (the pre-§3 behavior),
  but records the finished run's session dir into a new `self._task_session_
  dirs: dict[str, Path]` keyed by `task_id` — most-recent-run-only, per
  §8.2's explicit no-run-picker decision (a same-day re-run overwrites the
  prior entry, on-disk `_run<N>` folders are untouched either way). A third,
  persistent "Results" nav button now sits alongside Setup/Tasks in the title
  bar. New `_on_analyze_requested(task_id)` populates `ResultsPage` from
  `_task_session_dirs` and switches to it — reachable via a task's own
  Analyze button or the Results nav button directly, at any time, not just
  right after that task's own run.

### 9.1 Real bug found and fixed: `session.log` was silently empty

**This SPEC's own §8.3 claimed the Session Log panel "needs no new capture
at all... `SessionRecorder` already writes it every run today" — verified
FALSE live, not just re-read.** After building the panel, a live qt-mcp run
against `tools/fake_gazepoint_server.py` showed it as a solid black,
completely empty box. `qt_get_text` on the widget confirmed 0 characters,
and reading the session's actual `session.log` off disk confirmed it was a
genuine 0-byte file, not a display bug. Tracing `src/app.py` found
`SessionRecorder.log()` was called from exactly one place in the entire
codebase — `_apply_setting()`'s live-settings-panel change handler — so any
run where the operator never touched a live slider produced a `session.log`
with nothing in it at all, despite the file always being created.

**Fixed in `src/app.py`:** `AssessmentApp.__init__` now logs "Session
started: `<session_id>`", "Connected to Gazepoint Control." (only when this
instance owns the client — the dashboard's embedded-run path reuses an
already-connected client from Setup, so nothing new was connected this run,
and the log correctly omits that line in that case), and a calibration-
result line ("Calibration measured — N points, mean error Xpx, valid." or
"...invalid or unmeasured." for a failed/skipped calibration) — all three
deferred until right after `self.recorder.open()`, even though connect/
calibrate both happen earlier, because calibration must run before the
recorder exists (same ordering constraint documented in [[peds-eye-gaze-
assessment-calibration-fix-2026-08-31]]) and `recorder.log()` needs an open
file handle. A "Running `<task_id>` (N trials) at WxH." line was added right
after `build_task()`. `_shutdown()` now logs "Wrote N trials -> `<path>`"
right after `write_trials()`. Two style tokens (`QPlainTextEdit` missing from
`wtmh_theme.py`'s themed-input list) were fixed in the same round — see the
file list above — since the panel rendering solid black was a second,
separate symptom of the same investigation (a styling gap, not a data gap).

**Two of the two combined fixes were both real and independently necessary**
— fixing only the empty-log data bug would have left a themed-but-blank
panel; fixing only the QPlainTextEdit styling would have left a correctly
light-themed but permanently empty panel. Re-verified live after both fixes
together: `session.log` for a real run now reads (verbatim, from a live QA
session):
```
Session started: 2026-09-09_RESULTQA01_click_static_run1
Calibration measured — 5 points, mean error 8.4px, valid.
Running click_static (32 trials) at 1920x1080.
Wrote 0 trials -> sessions\2026-09-09_RESULTQA01_click_static_run1\trials.csv
```
("Connected to Gazepoint Control." absent here because the dashboard's Setup
tab already owned the connection, as expected; "Wrote 0 trials" because the
QA run was ended immediately via End task, not because of a bug.)

**How to apply:** `run_headless_replay()` (`src/engine/task_runner.py`) was
**not** touched by this fix — the Session Log panel is a GUI-only (dashboard)
feature, and a headless `--replay` session's `session.log` remains whatever
it was before. If a future session wants headless replay sessions to carry
the same narrative (e.g. for `analysis/analyze_session.py`-driven review),
that's separate, unstarted work.

### 9.2 Live validation (qt-mcp)

`tools/fake_gazepoint_server.py 4244` (a port other than 4242/4243, both
already bound by the real Gazepoint Control app on this machine, per
[[peds-eye-gaze-assessment-calibration-crash-2026-09-09]]'s established
convention) + `QT_MCP_PROBE=1 QT_MCP_PORT=9142 python -m src.main
--dashboard`, `showMaximized()`'d first per [[feedback-qt-mcp-maximize-
before-validating]]. Full flow, subject `RESULTQA01`:

1. Connect → "Connected."; Sex → Female; Do Calibration → "Calibration
   measured — 5 points, mean error 8px, valid."
2. **View Calibration Details** → correctly showed "Per-point breakdown not
   available for this calibration." (the fake server never sends
   `CALIB_RESULT`, only `CALIBRATE_RESULT_SUMMARY` — the intended empty-state
   path, confirmed live; the populated-table path is covered by
   `per_point_errors_px`'s own unit tests instead, since no real device was
   available this round).
3. Continue to Tasks → Run (Static Click) → **End task** → confirmed landed
   directly back on **Tasks**, status "Complete" — **not** an auto-shown
   Results page, confirming §3's old behavior is gone.
4. Task cards' **Analyze** buttons: confirmed only the just-completed task's
   button was enabled (the other three stayed disabled, per the existing
   "Complete"-gated logic) — clicked it.
5. **Results tab rendered correctly**: header "Static Click — 0 trials",
   subject/session subtitle, all four category cards populated (mostly "—"
   since the fake server streams no gaze data — expected, matches §6's
   original live-validation pattern), Session Log panel showing the real
   4-line narrative from §9.1 above, properly light-themed (not black).
6. **Back to Tasks** button confirmed working; the persistent **Results** nav
   button (title bar) also confirmed reachable independent of Analyze.

Two full dashboard relaunches were needed mid-round: one caught a real
`ImportError` (a leftover `_TASK_INFO` reference in `results_page.py` after
the `TASK_INFO` rename, missed on the first pass — the launch log itself
surfaced it immediately, not a silent failure) — see this as a reminder that
a rename touching multiple files needs a grep-and-relaunch check, not just an
editor-wide search that feels complete. The second relaunch picked up the
§9.1 `app.py` fix. Scratch QA session directories deleted afterward
(`sessions/` is gitignored, so this never touched `git status`); both QA
processes (dashboard + fake server, ports 9142/4244) killed cleanly via
`taskkill /F /T`, confirmed no leftover listeners via `netstat`.

### 9.3 Test status

Full pytest run three times across this round (after the exporter/
calibration additions, after fixing an accidental test-file splice caught by
the very next run, and after the §9.1 `app.py` fix): consistently **125
passed, 1 pre-existing unrelated failure** (126 collected total — corrected
here 2026-09-09 during a `/spec-memory-audit` pass; an earlier draft of this
section misstated it as "131 passed," not verified against an actual count
at the time it was written)
(`test_config_merges_task_over_default`, the long-documented `target_fps`
60-vs-150 local config drift — see [[peds-eye-gaze-assessment-config-skip-
worktree-2026-09-03]]). New tests: `tests/test_recorder.py` (on_screen_ratio,
effective_rate_hz, longest_gap_s, an off-screen-sample case, and the new
`summarize()` fields), `tests/test_calibration.py`
(`test_per_point_errors_px_*`, 3 new cases).

`run_headless_replay()`/`analysis/analyze_session.py` were not touched this
round beyond what §2 already covers — no new headless-path tests were
needed.

## Log

- **2026-09-09 — §1-§5 above implemented, unit-tested, and (§2/§3) live-
  validated via qt-mcp, all via `/sparc:orchestrator`.** Files changed:
  `src/data/exporter.py`, `src/app.py`, `src/engine/task_runner.py`,
  `analysis/analyze_session.py`, `src/ui/results_page.py` (new),
  `src/ui/dashboard_window.py`, `src/engine/calibration.py`,
  `tests/test_task_pipeline.py`, `tests/test_calibration.py`. **Left
  uncommitted**, same ask-before-commit pattern as the rest of this project's
  SPEC docs.

- **2026-09-09, later — §8: design-only redesign round, via
  `/sparc:orchestrator`, explicitly no implementation this round.** User
  audited §3's Results page against a real screenshot and, referencing
  `resources/images/diki-ui-3.png`, asked for: (1) a calibration
  quality-check button/section, (2) §3's auto-show-after-run Results page
  **superseded** by a dedicated persistent "3 · Results" tab reached via
  Analyze, (3) that tab modeled on the reference image's 4-category table
  layout, and (4) a metrics-category gap report before any wireframing.
  Three architectural forks resolved via `AskUserQuestion` (nav-tab-vs-
  button-only → persistent tab; modal-vs-inline for calibration details →
  inline; single-run-vs-run-picker for Results → most-recent-run-only). Gap
  report produced and given to the user (§8.4) before wireframing, per their
  explicit "report to me first." Two wireframes built and live-verified via
  Playwright screenshots (§8.6); a mandatory wireframe-before-UI-
  implementation process rule adopted (§8.5). **Confirmed: zero `src/`/
  `tests/` changes this round** — only `docs/wireframes/*` and this SPEC.
  Implementation of §8.1-§8.3 (including reverting §3's now-superseded
  auto-show behavior) is deferred to a future session, per the user's own
  explicit instruction.

- **2026-09-09, later still — §9: §8.1-§8.3 implemented and live-validated,
  via `/sparc:orchestrator` (session resumed after a `/clear`, restored via
  `/memory-restore`).** Every item from §8's design is now built: the
  Setup-page "View Calibration Details" inline section, the dedicated
  persistent "3 · Results" nav tab (reached via the Results button or a
  completed task's Analyze button), and the 4-category metric layout.
  §3's old auto-show-after-run Results page is fully reverted — a run now
  returns straight to Tasks, exactly as §8.2 specified. A real bug was found
  and fixed along the way (not part of the original plan): this SPEC's own
  §8.3 had claimed the Session Log panel needed no new capture, which live
  qt-mcp testing proved false — `session.log` was silently empty for any
  ordinary run before this round's fix to `src/app.py` (§9.1 has the full
  account). Full live-validation walkthrough: §9.2. Test status: §9.3 (125
  passed, 1 pre-existing unrelated failure, no regressions). **Files
  changed:** `src/data/exporter.py`, `src/engine/calibration.py`,
  `src/ui/setup_page.py`, `src/ui/wtmh_theme.py`, `src/ui/results_page.py`,
  `src/ui/tasks_page.py`, `src/ui/dashboard_window.py`, `src/app.py`,
  `tests/test_recorder.py`, `tests/test_calibration.py`. **Left
  uncommitted**, same ask-before-commit pattern as the rest of this SPEC's
  history — nothing from this whole Result-logic line of work is on
  `origin/main` yet.
