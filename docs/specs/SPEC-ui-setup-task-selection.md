# SPEC-ui-setup-task-selection — Setup & Task-Selection Dashboard

**Status:** section lists fully resolved across two feedback rounds, and now
also **wireframed** (`docs/wireframes/setup.md` + `tasks.md`, rendered HTML
alongside) — see §8. **No PySide6 code implemented yet.** Ready for an
implementation session, with a rendered reference to build against.
**Created:** 2026-09-08
**Last updated:** 2026-09-08

## 1. Origin / what was asked

The user wants to add real pre-task UI to `dev/peds-eye-gaze-assessment`,
replacing today's "launch straight into one task" flow with two screens:

- **Objective 1 — Setup:** run/reuse calibration, capture subject info,
  surface general Gazepoint device settings (specifically the two the user
  personally always turns on — Lens Focusing, Automatic Gain Sweep — see
  `resources/images/gazepoint-control-settings.png`/
  `gazepoint-control-debug-control.png`), and handle the Control Address
  (`gazepoint.host`), which the user has found differs per machine (this
  desktop: `26.113.49.235`; a fake-server or another laptop: different).
- **Objective 2 — Task selection:** let the operator pick one of the 4
  existing tasks to run.

Reference only, not a template to copy: the user's colleague's parallel
`resources/diki` codebase implements this as a persistent `DashboardWindow`
with tabs (`1 · Setup` / `2 · Tasks` / `3 · Results`) — see
`resources/images/diki-ui-window-1-setup.png` /
`diki-ui-window-2-task-selection.png`, and the existing
`SPEC-diki-design-audit.md` for the code-level account of that window.

**Explicit session scope:** brainstorm and list UI sections only. No code,
no implementation, this round.

## 2. Facts checked before drafting (grounds the design below)

- **`dev/`'s current launch model is strictly one-task-per-process.**
  `python -m src.main --task X --gui` (`src/main.py`) goes straight into
  `MainWindow` (`src/ui/main_window.py`), which hosts exactly one
  `TaskCanvas` + `OperatorPanel`, fullscreen, for one task. There is no
  setup screen or task-selection screen anywhere in `dev/` today — Windows
  1 and 2 are both genuinely new.
- **No OpenGaze API command exists for "Lens Focusing" or "Automatic Gain
  Sweep."** Both are confirmed (via the verified vendor corpus,
  `docs/gazepoints/sources/gazepoint-control.md:247` and
  `synthesis/troubleshooting.md:86`) to be Gazepoint Control's own
  Settings-dialog-only toggles. The OpenGaze TCP API `dev/` talks to has no
  command set for either — our app **cannot** set them remotely, only
  remind the operator to check them in Gazepoint Control itself.
- **No auto-discovery mechanism exists for the Control Address.** An
  exhaustive look at the OpenGaze API corpus found no broadcast/mDNS/
  query-for-host command. `gazepoint.host`/`port` (`configs/default.yaml`)
  is a plain, manually-set TCP endpoint with no protocol-level way to find
  it automatically — any "auto-connect" has to be a local heuristic, not a
  real handshake.
- **Calibration reuse already exists, but only via a known file path.**
  `SPEC-2026-09-02.md` item 7 Goal 1 (shipped) added `--calibration-file
  PATH`, `save_calibration_result`/`load_calibration_result`/
  `CalibrationFileError` (`src/engine/calibration.py`), hard-erroring on a
  subject_id mismatch or malformed file, no staleness cutoff. It
  auto-saves to `<session_dir>/calibration.json` whenever a real
  calibration runs. Session dirs are named
  `<output_root>/<YYYY-MM-DD>_<subject_id>_<task_id>/`
  (`src/app.py:119-121`) — one per task launch, so there is **no existing
  "find the most recent calibration for subject X" lookup**; the caller
  must already know the path.
- **The `Calibration` class already supports everything Window 1's
  calibration panel needs** — 1-9 point layouts
  (`_CALIBRATION_POINT_POOL`/`_layout_for`), `show`/`enabled`/
  `point_timeout_s`/`point_delay_s` — none of it is surfaced in any GUI
  today, this is a UI-wiring gap, not an engine gap (same pattern as
  `SPEC-live-settings-panel.md`'s finding for dwell settings).
- **No subject-metadata fields exist anywhere today.** `configs/
  default.yaml` has `calibration.*`, `gazepoint.*`, `input.mode`, etc., but
  subject identity is CLI-only (`--subject`, a bare string).

## 3. Decisions made this session (via clarifying questions)

Three forks were resolved with the user before drafting the section lists
below — they shape the architecture, not just cosmetics:

1. **Window lifecycle: persistent dashboard, diki-style — not sequential
   standalone windows, not a subprocess launched per task.** One window,
   one process, tabbed; the Gazepoint connection and calibration state
   stay alive across multiple task runs in the same sitting. This is a
   bigger rearchitecture than "two dialogs in front of the existing app" —
   today's per-task fullscreen `MainWindow` becomes something the
   dashboard *hosts*, not the whole app. See §6 for what's deliberately
   left unresolved here.
2. **Device settings (Lens Focusing / Auto Gain Sweep): operator
   checklist/reminder only.** Two self-attested checkboxes in Window 1,
   recorded into session `metadata.json` for an audit trail. No in-app
   control — confirmed impossible per §2 above. (Rejected for this round:
   researching whether Gazepoint Control persists these in a config/
   registry file `dev/` could read/write directly — undocumented, outside
   the OpenGaze API corpus, real feasibility unknown; not investigated
   this session.)
3. **Control Address: remember last-known-good + manual fallback.**
   Persist the last successfully-connected host locally per machine (not
   committed to git — same pattern as `configs/default.yaml`'s existing
   `skip-worktree` trick, see the
   `peds-eye-gaze-assessment-config-skip-worktree-2026-09-03` memory),
   pre-filled into an editable field with a "Test Connection" button.
   Fresh machine with no history defaults to `127.0.0.1`. (Rejected:
   additionally auto-probing a list of candidate local IPs — real
   complexity for a heuristic with no protocol guarantee behind it.)

### 3.1 Second-round refinements (same day, after user feedback)

Four more forks resolved, tightening §4-§7 below:

4. **Subject metadata pruned to exactly four fields** — Subject ID,
   Assessment Date, Sex, free-text Notes. Every other candidate in §4's
   original table (DOB/age, diagnosis/clinical group, examiner, visit
   number, corrective lenses, visual-impairment notes, seating/
   positioning, alertness state, consent checkbox) is dropped from this
   SPEC entirely — the user's explicit choice, not a deferral.
5. **Calibration panel has exactly two paths: Do Calibration, or Load
   Calibration File.** The auto-lookup-by-subject-ID capability proposed
   in the first round is dropped — "Load Calibration File" is a manual
   file picker over the *already-shipped* `--calibration-file` mechanism
   (`load_calibration_result`, `src/engine/calibration.py`, subject_id
   cross-check hard error included), just given a GUI browse control
   instead of a CLI flag. No new engine capability needed for this path.
6. **Device pre-flight (Lens Focusing / Auto Gain Sweep) is a read-only
   reminder notice, not an attestation, and does not block "Continue to
   Tasks."** The user's own clarification: "just a notice for the user to
   read, not mandatory to check or turn on, since there's no way to check
   from the API." So this is plain reminder text, not interactive
   checkboxes, and it doesn't gate navigation. The actual mandatory gate
   the user meant is **calibration existing** (via either path in #5) —
   see the revised §5.6 gating rule.
7. **Task hosting: embed in the same window.** Clicking Run in the Tasks
   tab swaps the dashboard's content to the task canvas + operator sidebar
   in place — no new window, no subprocess. Resolves the "how does shared
   `GazepointClient`/calibration state thread through" question left open
   in the first round: since nothing is relaunched, the same session state
   just continues to be used by the embedded task view. Ends by returning
   to the Tasks tab when the task completes.
8. **Session-directory collision on re-running a task: append a run
   index.** Surfaced while finalizing #7 (see the now-resolved §7 below)
   and put to the user directly: session dirs become
   `<output_root>/<YYYY-MM-DD>_<subject_id>_<task_id>_run<N>/`
   (`run1`, `run2`, ...) instead of today's bare
   `<date>_<subject_id>_<task_id>/` (`src/app.py:119-121`), so every
   attempt is kept rather than the second overwriting the first. Rejected:
   a time-of-day suffix (less obviously "which attempt number" at a
   glance) and blocking re-runs outright (the dashboard's whole point is
   to support re-running freely, per diki's own "run in any order, re-run
   freely" reference).

## 4. Subject/session metadata fields (finalized by the user, second round)

The first round proposed a 13-field candidate table. The user pruned it to
exactly four fields for Window 1's Subject & Session Info panel — no others:

| Field | Why it matters |
|---|---|
| Subject ID | Already exists as `--subject`; primary key for session dirs and the loaded-calibration subject cross-check |
| Assessment date | Already implicit in the session-dir date prefix; auto-filled, editable |
| Sex | Standard demographic covariate |
| Free-text notes | General catch-all; already present in the diki reference screenshot |

Everything else from the first-round table (DOB/age, diagnosis/clinical
group, examiner, visit number, corrective lenses, visual-impairment notes,
seating/positioning, alertness state, consent checkbox) is explicitly
pruned — not deferred, dropped. The earlier open question about DOB-vs-
age-only de-identification is moot now that DOB isn't collected at all.

## 5. Window 1 — Setup tab, proposed sections

1. **Persistent status header** (Session, Tracker connection state,
   Calibration state) — visible across both tabs since the dashboard
   persists (mirrors diki's top bar in the reference screenshots).
2. **Subject & Session Info panel** — the four fields in §4 (Subject ID,
   Assessment Date, Sex, Notes). Final, not open for further pruning.
3. **Tracker Connection panel** — Control Address field (pre-filled from
   last-known-good per §3.3), Control Port, Connect button, live
   connection status, Test Connection.
4. **Calibration panel — exactly two paths, no auto-lookup:**
   - *Do Calibration* — run a fresh calibration (point count 1-9, show/
     hide, per-point timing; all already supported by `Calibration`, just
     needs GUI controls) and display the result (error px, valid/invalid,
     point count).
   - *Load Calibration File* — a file picker over the already-shipped
     `--calibration-file` mechanism (`load_calibration_result`,
     `src/engine/calibration.py`); hard-errors on a subject_id mismatch or
     malformed file, same as today's CLI flag.
5. **Device pre-flight notice** — a read-only reminder ("Before starting,
   confirm in Gazepoint Control: Lens Focusing enabled, Automatic Gain
   Sweep enabled") — plain text, not interactive checkboxes, not stored,
   **not a gate**. Confirmed impossible to verify via the API (§2), and the
   user's explicit call: this is informational only.
6. **"Continue to Tasks" navigation** — gated on: tracker connected +
   a calibration result exists (via *either* Do Calibration or Load
   Calibration File in #4) + the four required subject fields filled. The
   device pre-flight notice in #5 does **not** factor into this gate.

## 6. Window 2 — Tasks tab, proposed sections

1. Same persistent status header as Window 1.
2. **Task list** — one card per task (Static Click, Grid Click 3x3, Follow
   & Click, Scanning Search): name, one-line description, status
   (Pending/Running/Complete), Run button, per-task settings access
   (reuse the existing `TaskSettingsDialog`, `src/ui/
   task_settings_dialog.py`, rather than building a new one), Analyze
   button (stub/deferred — see below). **Run behavior (resolved §3.1.7):**
   embeds the task canvas + operator sidebar into the same dashboard
   window in place of the Tasks tab content — no new window/process — and
   returns to the Tasks tab, status updated to Complete, when the task
   ends.
3. **"Back to Setup / recalibrate"** link.
4. **Explicitly out of scope this round:** a Results tab/window. Diki has
   one; the user's two stated objectives this session were only Setup and
   Task Selection.

## 7. Still open — needs the user's answer

**None.** Every fork raised across both feedback rounds is resolved — see
§3.1 items 1-8, including the session-directory run-index question (§3.1.8)
that was the last open item.

Two implementation-level details are left for the implementation session
itself (no user decision needed, purely mechanical): the exact Qt
widget-swap mechanism for embedding a task view into the dashboard (e.g.
`QStackedWidget`), and where the "Load Calibration File" browse dialog
should default to (likely the session output root).

## 8. Wireframe (docs/wireframes/)

Both windows are now wireframed with `wiremd` (extended-Markdown → HTML
mockup) — a text-first reference to build against, not a design tool
requiring Figma/Balsamiq. Tool setup, versioning, and the project-wide
skill install are documented in the top-level `README.md` ("UI wireframing
(wiremd)"), not repeated here.

**Files:** `_nav.md` (shared top bar, included via `![[_nav.md]]`),
`setup.md`, `tasks.md` — multi-page, matching §3.1.1's persistent-dashboard
architecture (two pages standing in for the two tabs). Rendered to
`setup.html`/`tasks.html` (`--style clean`), cross-page `.md` hrefs rewritten
to `.html` for direct `file://` opening. Both screenshotted and visually
verified via `qt`-independent Playwright (not `qt-mcp` — this is a static
mockup, no running Qt app yet).

**What each page encodes**, directly off §4-§6 above — every field, gate,
and status badge in the wireframe traces to a specific SPEC line, not
invented:

- `setup.md`: the 4-field Subject & Session Info panel (§5.2/§4), Tracker
  Connection with the pre-filled Control Address (§5.3/§3.3), Calibration
  with exactly the two paths and point-count/show controls (§5.4/§3.1.5),
  the non-blocking read-only device notice worded as "Before You Start"
  (§5.5/§3.1.6), and a disabled "Continue to Tasks" button annotated with
  the exact gate condition (§5.6).
- `tasks.md`: all 4 tasks as cards with Pending/Complete status badges and
  Run/Settings/Analyze buttons (§6.2), a "Back to Setup" link (§6.3), a
  design-note annotation explaining the embed-in-place Run behavior
  (§3.1.7) and the run-index re-run guarantee (§3.1.8), and a Task Settings
  modal reusing the existing `TaskSettingsDialog` concept (§6.2).

**Known cosmetic rendering quirk, not a content bug:** `::: alert` blocks
in wiremd's `clean` style eat the whitespace immediately around inline
`**bold**` spans (confirmed by comparing against blockquote annotations
elsewhere on the same page, which render the identical bold pattern
correctly) — worked around by not bolding inside the two `::: alert` blocks
in `setup.md`, rather than fighting the renderer.

**Deliberately not wireframed:** a Results tab/window (out of scope per
§6.4), and the Do-Calibration-in-progress / Load-Calibration-File-picker
states themselves (the SPEC doesn't define those as separate screens — the
wireframe shows the entry controls and the two resulting alert states via
annotation instead).

**Not committed** — new/untracked in `git status` (`docs/specs/
SPEC-ui-setup-task-selection.md` and `docs/wireframes/`), matching this
project's ask-before-commit convention.

## Log

- **2026-09-08** — Session opened via `/sparc:orchestrator`; user described
  two new UI objectives (Setup, Task Selection) with two Gazepoint-Control
  reference screenshots and two `diki` reference screenshots. Verified
  today's one-task-per-process architecture, confirmed no API control
  exists for Lens Focusing/Auto Gain Sweep, confirmed no address
  auto-discovery protocol exists, and reviewed the existing calibration-
  reuse mechanism and `Calibration` class capabilities before drafting.
  Asked three clarifying questions (window lifecycle, device-settings
  handling, control-address UX) and got answers — recorded in §3. Drafted
  the brainstormed subject-field list (§4) and both windows' proposed
  section lists (§5, §6). **No code written.** This SPEC is the entire
  deliverable for the session.

- **2026-09-08, later same session — second feedback round, all §7 items
  from the first round resolved.** User pruned subject metadata to exactly
  four fields (§4), dropped the calibration auto-lookup capability in
  favor of two explicit paths — Do Calibration / Load Calibration File
  (§5.4) — and clarified the device pre-flight item is a non-blocking
  read-only notice, not an attestation (§5.5), after asking two more
  clarifying questions (pre-flight gate semantics, task-hosting mechanism)
  and getting answers — recorded in §3.1. Task hosting resolved as
  embed-in-same-window (§6). While finalizing the Run behavior, found and
  flagged one new unresolved issue: `dev/`'s session-dir naming has no
  run-index/time component, so re-running the same task for the same
  subject same day (which §6's design explicitly wants to support) could
  silently collide with/overwrite the prior run — see §7. **Still no code
  written.**

- **2026-09-08, later still — the session-dir collision question answered,
  every fork now resolved.** User chose an appended run index
  (`_run<N>` suffix on the session dir, §3.1.8) over a time-of-day suffix
  or blocking re-runs outright. §7 now has no open items. **This SPEC is
  ready for an implementation session; still no code written.**

- **2026-09-08, later still — wiremd tool set up workspace-wide and both
  windows wireframed (§8).** Inspected the `wiremd` tool vendored at
  `resources/styling/wiremd/` (verified as a real, actively-developed
  package via web search), built it locally (0.1.7, newer than the 0.1.5
  on the npm registry — needed for sidebar-layout CSS and cross-page nav
  links), `npm link`ed it onto `PATH`, and installed its bundled skill at
  this workspace's `.claude/skills/wireframe/` (matching the existing
  `pdf-corpus-builder` project-skill convention). Documented all of this in
  the top-level `README.md`. Then authored and rendered `docs/wireframes/
  _nav.md` + `setup.md` + `tasks.md` directly off §4-§6 of this SPEC,
  screenshotted both pages via Playwright to visually verify, and fixed one
  cosmetic whitespace-around-bold rendering quirk in two `::: alert` blocks.
  **Still no PySide6 code written** — this is a text-first mockup, not an
  implementation.
