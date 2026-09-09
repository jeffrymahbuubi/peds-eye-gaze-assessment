# SPEC-ui-setup-task-selection — Setup & Task-Selection Dashboard

**Status:** section lists fully resolved across two feedback rounds, and now
also **wireframed** (`docs/wireframes/setup.md` + `tasks.md`, rendered HTML
alongside) — see §8. Committed and pushed to `origin/main` as `1404fde`.
The wireframe is now also **restyled into the WTMH lab's Clinical Teal brand
palette, with the WTMH logo placed in the titlebar** — see §9. **Implemented
in PySide6 and live-validated** (`DashboardWindow`, `src/ui/
dashboard_window.py` + `setup_page.py` + `tasks_page.py`), committed as
`b91cd27` — see §10. **A follow-on styling-pass feedback round is recorded in §11** — a
real-world critique plus two user-found bugs (unthemed `TaskSettingsDialog`,
missing status-pill states, white-on-white Sex dropdown, no run-number
indicator) evaluated against the source (§11.3), turned into a plan
(§11.5), and now **implemented and live-validated** (§11.6). **A
follow-on arrow-rendering regression from §11's own custom QComboBox/
QSpinBox arrows is fixed in §12** — root-caused to a Qt/PySide6
limitation where the CSS border-triangle technique doesn't render as a
triangle for these subcontrols; fixed with real PNG assets instead. **§13
fixes a follow-on combobox-popup regression (from §12's Fusion switch),
adds a real checkbox checkmark, root-causes a reported "Continue button
won't press" bug as a UX gap (tooltip added), fixes the app's dark default
Fusion palette generally, and replaces the calendar date-picker with a
plain auto-populated field per a user product decision.** **§14 fixes two
more leftover styling bugs — an unstyled native `QDateEdit` spin-button
sliver on Assessment Date, and §13.2's incomplete Sex-popup fix (the true
black-band source was the outer `QComboBoxPrivateContainer`, not the
inner view) — both via Python widget config, no QSS changes.** Six
rounds (§9-§14) committed and pushed to `origin/main` as `ef8b771`.
**§15: §14.2's own Sex-popup fix regressed to a solid black popup on real
on-screen compositing (a `WA_TranslucentBackground` limitation invisible
to qt-mcp's `grab()`-based screenshot tool) — root-caused and fixed for
real with an opaque background instead, validated via an actual desktop
screenshot this time.** **§16: dead vertical space on Setup/Tasks fixed
(a 2-column responsive Tasks grid + spacing increases that push Setup's
window past its own launch-size floor), a real page/card title type
scale added, and the Sex popup's remaining phantom-focus-outline and
border-seam issues fixed** — all validated live with real desktop
screenshots throughout. **§17: §16's Tasks grid fix left the grid
occupying only the top ~40% of the window — fixed by vertically
centering the grid block, after a rejected row-stretch attempt and a
rejected `setRowMinimumHeight` attempt that caused a real, confirmed-
live runaway window-growth bug (killed safely, no lasting damage).**
S14-S17 committed and pushed to `origin/main` as `8f2e82b`.
**§18: §17's centering fix still left large dead bands at real
maximized-window size — root-caused as a ghost-row-stretch bug (fixed)
plus a rejected Expanding-card attempt (awkward internal card gaps,
live-confirmed), landed instead as widget-free stretch spacer rows
around/between the card rows, distributing leftover space evenly with
every card kept at its natural size.** qt-mcp validation now maximizes
the window first, going forward. **§19 (current): the whole grid line
of work (§16-§18) was reverted by explicit user decision — Tasks is now
a plain single-column `QVBoxLayout` card stack matching Setup's own
pattern exactly, with no grid/breakpoint code at all.** Live-validated
maximized: no large or awkward empty region, though a smaller ~200px
trailing margin remains below the stack (task cards are shorter than
Setup's form-heavy ones). §16-§18 remain in this doc as historical
record only. S16-S19 committed and pushed to `origin/main` as `74efccd`,
after a clean `/spec-memory-audit` pass.
**§20: a real calibration crash bug (stale local-state port +
an unhandled socket exception crashing the whole app) found, reproduced
live against the real device, root-caused, and fixed** — see §20.
**§21: two real bugs in the dev-testing helper `tools/
fake_gazepoint_server.py` (a non-venv `python` silently producing no
output, and Ctrl+C unable to stop a blocking `accept()` on Windows)
found from the user's own hands-on testing and fixed** — see §21.
**§20-§21 committed and pushed to `origin/main` as `45908cb`** after a
clean `/spec-memory-audit` pass.
**Created:** 2026-09-08
**Last updated:** 2026-09-09

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

**Committed and pushed** — see the final Log entry below (`1404fde` on
`origin/main`).

## 9. Visual design — WTMH branding + Clinical Teal palette

Prompted by the user supplying two brand assets (`wtmh_logo.png`,
`WTMH.ico` — the lab's circular WTMH badge: Wearable Technology and Mobile
Healthcare, NCKU) and a full Clinical Teal color spec, asking (1) where to
place the logo in "GUI window 1" and (2) to apply the palette to whichever
theme/stylesheet in the codebase currently owns this UI's colors.

**Scope-resolution, asked before touching anything (two `AskUserQuestion`
rounds):** two real mismatches between the prompt's premises and the repo
were found first and flagged rather than guessed past:

1. `dev/`'s currently-**implemented** app (`OperatorPanel`/`MainWindow`,
   see [[diki-design-audit-2026-09-07]] §8.10) has no cream/maroon theme
   today — that palette only ever existed in an uncommitted intermediate
   step and was superseded by a dark HUD-card look before being committed.
   The prompt's button set ("Connect to tracker", "Read calibration",
   "Continue to tasks →") matches **this SPEC's wireframe**, not the
   running app, which has no Setup/Connect/Calibration screen at all yet.
   **User confirmed: target the wireframe** (this SPEC/§8), not the
   running app.
2. "Start session" and "Check drift" don't match any existing button label
   in either surface. **User confirmed: map to the closest existing
   element and skip what doesn't exist** — see the button-mapping table
   below.

**"GUI window 1" = §5, the Setup tab** — confirmed directly from this
SPEC's own section title ("Window 1 — Setup tab") and the wireframe's own
`## 1 · Setup` heading, not a guess.

### 9.1 Logo placement (the actual recommendation asked for)

**Two different assets, two different jobs — not the same placement:**

- **`WTMH.ico` → the OS-level window/taskbar icon**, via
  `QMainWindow.setWindowIcon()` / `QApplication.setWindowIcon()` in the
  eventual PySide6 implementation (an `.ico` is exactly what Windows
  expects there — multi-resolution, shows in the taskbar, alt-tab, and the
  window's own title bar chrome). For the wireframe itself (plain HTML,
  no OS chrome to theme) the closest equivalent is a `<link rel="icon">`
  favicon, added for completeness.
- **`wtmh_logo.png` → an in-window header/brand element**, top-left of the
  persistent titlebar/nav bar that already runs across both tabs (§8's
  `_nav.md`), immediately to the left of the "Pediatric Eye-Gaze
  Assessment" title text, at the opposite end from the Session/Tracker/
  Calibration status badges (§5.1's `::: row {.right}`). This keeps a
  standard clinical-software header band — brand mark + product name on
  the left, live status on the right — and doesn't compete with the
  functional `OperatorPanel` sidebar (§8.10), which stays content-only.

**Implemented in the wireframe:** `docs/wireframes/_nav.md`'s `:eye:`
placeholder icon replaced with the real logo (see §9.2 for why this
required a markup change, not just a CSS one); `WTMH.ico` wired as the
page favicon. Both render on `setup.html` and `tasks.html` since both
include the shared `_nav.md` bar.

### 9.2 Palette application — mechanism

**Finding, checked against source, not assumed:** wiremd's 7 built-in
styles (`sketch`/**`clean`**/`wireframe`/`material`/`tailwind`/`brutal`/
`none`) are fixed CSS presets baked into `resources/styling/wiremd/src/
renderer/styles.ts` — there is no custom-palette CLI flag or config. A
brand palette has to be applied as a **post-render retint pass** over the
CSS `wiremd` itself generates, not a wiremd feature.

**New tool, not a one-off hand-edit:** `tools/apply_wtmh_wireframe_theme.py`
— a small script holding an explicit (old CSS text → new CSS text) list,
each entry an exact substring lifted from wiremd's real "clean"-style
output, applied to the rendered HTML after every `wiremd ... --style
clean` re-render. It raises loudly if an expected old string is ever
missing (e.g. after a future wiremd upgrade changes this CSS), rather than
silently no-op'ing. It also injects the logo `<img>` into the nav bar and
the favicon `<link>`, since neither is expressible through wiremd's own
Markdown syntax (§9.2's next paragraph). Usage:
`python tools/apply_wtmh_wireframe_theme.py docs/wireframes/setup.html
docs/wireframes/tasks.html` — run after any future `wiremd` re-render of
either page.

**Real logo image confirmed NOT insertable via wiremd's own nav syntax**
(`[[ :icon: Label | ... ]]`) — tested directly: `:icon:` tokens always
render as a generic bullet placeholder glyph (`data-icon="..."`), by
design (wiremd is a low-fidelity wireframing tool; icons are deliberately
not real assets), and an inline `![img](path)` inside the `[[ ]]` bracket
syntax is silently dropped by the parser. The logo is therefore injected
as a plain `<img>` by the same post-render script, not through `_nav.md`
markup.

**Real bug caught and fixed during this pass, worth remembering:**
removing `_nav.md`'s `:eye:` icon prefix (so the real logo could take its
place) changed which wiremd AST node the title text becomes — it now
parses as `.wmd-brand` (a real "first plain-text segment = brand" node)
instead of `.wmd-nav-item` (which is what it was when prefixed with an
icon token). `.wmd-brand` has **no color rule at all** in wiremd's "clean"
style, so once the nav bar itself was retinted dark (§9.3), the brand text
silently inherited the page's dark ink color and was nearly invisible
against the dark titlebar — caught by an actual Playwright screenshot
comparison, not assumed fixed from the CSS diff alone. Fixed by adding an
explicit `color: #CFE6EE` rule for `.wmd-brand` in the theme script.
**How to apply:** if a future wireframe page's title text looks washed out
against a dark header, check whether it rendered as `.wmd-brand` (needs
its own color rule) vs. `.wmd-nav-item` (already has one) before assuming
the retint script itself is wrong.

### 9.3 Palette mapping (source of truth for a future PySide6 QSS re-implementation)

| Token | Hex / value | Applied to |
|---|---|---|
| Accent | `#1F7A9C` | Ghost-button hover border, tab-active text, input focus border, blockquote rule, alert left-border, brand-logo accent |
| Accent gradient | `linear-gradient(90deg, #2FA8C4, #1A6F95)` | Primary buttons (Connect, Do Calibration, Continue to Tasks) |
| Titlebar surface | `#12374A` | `.wmd-nav` (the shared header bar) |
| Titlebar text | `#CFE6EE` | `.wmd-brand`, `.wmd-nav-item` |
| Soft accent | `#DCF0F5` | Secondary buttons, ghost-button hover fill, Session badge, alert background |
| Secondary text on soft accent | `#0F5670` | Secondary-button text, Session badge text |
| Background | `#F5F9FB` | Page body, container base bg |
| Panel/card bg | `#FFFFFF` (unchanged from before) | Inputs, `::: card` blocks, modal |
| Border | `#DBE6EC` | All generic borders (buttons, inputs, cards, separators, h1 rule) |
| Ink | `#122B3A` | Body/heading text, ghost-button text, input text |
| Muted text | `#5C7684` | Paragraph text, default/neutral badges, blockquote text |
| Danger (kept) | `#E15353` | New `.wmd-badge-danger` (reserved, unused by these 2 pages today) + `.wmd-button-danger` |
| Session-status green (kept) | `#2F9E6E` | `.wmd-badge-success` ("connected", "fresh", "Complete") |

**A genuine semantic call, disclosed rather than silently made:** the
prompt's own categorization puts "Tracker: not connected" and
"Calibration: none" under **neutral** status badges ("light gray, muted
text"), not danger/warning — but the wireframe's pre-existing markup
tagged them `{.error}`/`{.warning}` (i.e. wiremd's red/amber badge
classes). Rather than leave "not connected" reading as an alarming red
pill, **`.wmd-badge-error` and `.wmd-badge-warning` were both retinted to
the neutral gray** (`#E6EDF1`/`#5C7684`) to match the user's own stated
semantics for these specific instances, and a new, currently-unused
`.wmd-badge-danger` rule was added holding the real kept danger red
(`#E15353`) for a future genuinely-urgent badge (e.g. a "SIGNAL LOST"
state on the live gaze/signal viewer, which doesn't exist as a wireframed
element yet). **If a future page needs an actually-alarming badge, use the
new `.wmd-badge-danger` class, not `.wmd-badge-error`/`-warning`** — those
two now mean "neutral/inactive" in this theme, not "problem."

**Button-label mapping** (resolving the two unmatched names from the
prompt, per the user's own chosen resolution):

| Prompt's label | Maps to | Note |
|---|---|---|
| "Connect to tracker" | `[Connect]*` (setup.md) | exact match, wording shortened in the wireframe |
| "Read calibration" | `[Load Calibration File]{.outline}` (setup.md) | exact match |
| "Check drift" | *(none)* | no such feature/button exists in either surface yet; no color applied |
| "Start session" | `[Continue to Tasks →]` (setup.md) | closest existing action; **promoted from a plain to a primary button** (added the `*` marker) so it actually receives the accent-gradient treatment the prompt asks for — previously plain/unstyled-disabled only |
| "Continue to tasks →" | `[Continue to Tasks →]*{state:disabled}` (setup.md) | exact match, now primary |

**Also retinted for consistency, though not directly named in the
prompt:** `::: card` (task cards), `::: alert` (all three severities — see
next paragraph), the literal `::: tabs` component (unused by these 2
pages today, kept in sync for any future page that adds one), the unused
`container-sidebar`/`grid-item-card` rules.

**Known wiremd limitation surfaced, not fixed:** `::: alert warning` /
`::: alert info` / `::: alert success` all render as the exact same
`<div class="wmd-container-alert">` in "clean" style — the severity word
is not captured as a distinguishing CSS class anywhere in the parser or
renderer (confirmed by reading both `remark-containers.ts`'s output and
the actual rendered HTML). All three severities therefore share **one**
consistent accent-tinted informational card look in this palette; true
per-severity alert coloring isn't available without a wiremd source
change, which was out of scope here.

**Verified live via Playwright** (`docs/wireframes/setup.html` +
`tasks.html`, full-page screenshots): titlebar reads correctly with the
logo + legible title text; Connect/Do Calibration render in the accent
gradient; Continue-to-Tasks renders in the (dimmed, since disabled) accent
gradient; Tracker/Calibration badges read as neutral gray when inactive
and solid green when connected/fresh/complete; task cards, alerts, and
inputs all read cleanly against the new light background.

**Files added:** `configs/assets/branding/wtmh_logo.png`,
`configs/assets/branding/WTMH.ico` (copied in from the top-level
`resources/styling/` — that directory isn't part of this git repo, so the
assets are duplicated into `dev/` for the repo to be self-contained, per
[[feedback-no-separate-working-folder-from-repo]]), `tools/
apply_wtmh_wireframe_theme.py`.
**Files changed:** `docs/wireframes/_nav.md` (icon → real logo),
`docs/wireframes/setup.md` (Continue-to-Tasks promoted to primary),
`docs/wireframes/setup.html` + `tasks.html` (regenerated + themed).
**Left uncommitted**, matching this project's established ask-before-
commit pattern.

## 10. Implementation (PySide6) — `DashboardWindow`

Built the real dashboard from §5/§6/§9: a persistent window replacing the
one-task-per-process launch model for interactive use, wired to the
already-existing engine (`GazepointClient`, `Calibration`, `AssessmentApp`,
`TaskSettingsDialog`) rather than duplicating any of it. Added as an
**additional** entry point (`python -m src.main --dashboard`) — the
standalone `--task X --gui` CLI path is untouched and behaves exactly as
before (verified: same public `MainWindow` attributes, same default
parameter values, full pytest suite unchanged except the one pre-existing
failure).

**Core architectural problem, and how it was resolved:** `AssessmentApp`
always built its own `MainWindow` (a top-level `QMainWindow`) and always
connected + calibrated its own `GazepointClient` in its constructor — the
opposite of §3.1.7's decision that Run "embeds ... into this same window
... nothing gets relaunched." Rather than forking a second implementation
of the task-run loop for the dashboard, `AssessmentApp` and `MainWindow`
were both split instead:

- `src/ui/main_window.py`: the canvas+sidebar content was extracted into a
  new `TaskRunView(QWidget)`; `MainWindow(QMainWindow)` is now a thin
  wrapper around one, unchanged in every public attribute
  (`.canvas`/`.operator_panel`) from before the split.
- `src/app.py`: `AssessmentApp.__init__` gained four new, all-optional
  parameters — `client`, `preset_calibration_result`, `embedded`,
  `on_finished` (plus `assessment_date`/`sex`/`notes` for the metadata
  fields finalized in §4) — every one defaulting to the exact standalone
  behavior (own client, own calibration, own top-level window, quit on
  end) it always had. When the dashboard supplies `client`+
  `preset_calibration_result`, `connect()`/`Calibration.run()` are skipped
  entirely (the socket is never reopened, no second calibration UI ever
  shows); `client.stop()` is only called if this instance opened the
  client itself (`_owns_client`), never a dashboard-owned one that other
  task runs still need. `embedded=True` builds a bare `TaskRunView`
  instead of a fullscreen `MainWindow`, and `_shutdown` calls
  `on_finished()` instead of `QApplication.quit()` — a `_shutdown_done`
  guard was added since the End button and `task.is_done` can now both
  fire in the same tick without one of them trying to tear down an
  already-torn-down session.
- `DashboardWindow` (`src/ui/dashboard_window.py`) owns a `QStackedWidget`
  with the Setup page, the Tasks page, and (added/removed per run) the
  active `AssessmentApp`'s `.view`. Run constructs `AssessmentApp(...,
  client=self.setup_page.client, preset_calibration_result=self.setup_page
  .calibration_result, embedded=True, on_finished=self._on_task_finished)`
  and keeps the whole `AssessmentApp` instance alive in
  `self._active_assessment` (it owns the `QTimer` driving the task) until
  `on_finished` fires, at which point the view is removed, the task's card
  is marked Complete, and the Tasks tab is shown again.

**Same-day re-run collision, fixed generally, not just for the dashboard:**
`AssessmentApp`'s session-dir naming had no run/time component
(`<date>_<subject>_<task>`), and `SessionRecorder` creates its directory
with `exist_ok=True` — a second same-day run would have silently reused,
and overwritten, the first's directory. Rather than scope the §3.1.8
run-index decision to only the embedded path, `next_session_id()`
(`src/engine/session_naming.py`, Qt-free, unit-tested) was applied
unconditionally in `AssessmentApp`, so `--task X --gui` gets the same
overwrite protection. No test or tool in this repo asserted the old
naming (checked via grep before changing it).

**New Setup-tab pieces:**

- `src/ui/setup_page.py` — Subject & Session Info, Tracker Connection,
  Calibration, and the read-only device notice, matching §5 exactly. The
  two device operations that block on real socket I/O (`GazepointClient
  .connect()`'s 5s timeout on a bad host; a real calibration's several
  seconds of point-by-point polling) each run on a small `QThread` worker
  so the whole dashboard doesn't freeze — the same concurrency budget
  `GazepointClient`'s own reader thread already spends. "Test Connection"
  reuses the same worker with `keep=False`: it connects, immediately
  closes the throwaway client, and never touches the page's real
  connection or its Tracker badge.
- `src/engine/local_state.py` (Qt-free, unit-tested) persists the last
  host/port that connected successfully to `configs/local_state.json`
  (gitignored — added to `.gitignore` this round), per §3.1.3's "defaults
  to `127.0.0.1` on a fresh machine, not the checked-in device address."
- Continue-to-Tasks gating (`SetupPage.can_continue()`) matches §5.6
  exactly: tracker connected AND a calibration result exists (either path)
  AND Subject ID/Assessment Date/Sex filled — the device notice never
  factors in.

**New Tasks-tab pieces:** `src/ui/tasks_page.py` — one card per
`TASK_REGISTRY` entry (name/description text lifted verbatim from
`docs/wireframes/tasks.md`, not re-worded), Run/Settings/Analyze buttons
(Analyze stays disabled — deferred per §6.2, not a bug), "Back to Setup".
**Settings vs. Run, resolved as two genuinely separate actions** (not
flagged as open in §7, but the wireframe's own separate buttons implied
it): Settings opens `TaskSettingsDialog` and stores whatever overrides
were accepted in `DashboardWindow._task_overrides[task_id]`; Run applies
whatever was last stored (or the task's own YAML defaults, if Settings was
never opened) without popping the dialog again — a real UX decision, not
just reusing the CLI's always-ask-at-launch behavior, since a clinical
operator running the same task repeatedly shouldn't see a config dialog
every time.

**Bug caught by live testing, not by review:** the dashboard froze
mid-task the first time "End task" was clicked, live-verified via the
Qt console log (`qt-mcp` doesn't surface Python tracebacks in its own
tools; the redirected stdout/stderr log file did) — `on_finished=lambda:
self._on_task_finished(task_id)` passed an argument `_on_task_finished`
doesn't take (it already reads the task id off `self._active_task_id`).
Because this raised *after* `self.timer.stop()`, the first click actually
did stop the tick loop and close the recorder, and the exception itself
just prevented the dashboard-side cleanup from running — the frozen
canvas was `_shutdown`'s own `_shutdown_done` guard silently no-op'ing the
second click. Fixed by passing `self._on_task_finished` directly (no
lambda, no argument). **How to apply:** a `QThread`/callback wiring bug in
this codebase can look exactly like "the button did nothing" or "it
froze" — check the redirected stdout/stderr log before assuming a Qt- or
timing-level cause.

**Second bug caught by live testing:** the "Show calibration window to the
subject" checkbox's label text was completely invisible against its white
card in the actual running app, despite `qt_widget_details` confirming the
text was set correctly — root cause was the OS's dark-mode default
`QCheckBox` text color, which every *other* widget in `wtmh_theme.py`'s
stylesheet had an explicit `color:` override for except `QCheckBox`
(matching a gotcha `operator_panel.py`'s own docstring already flags for
this codebase). Fixed by adding `QWidget#wtmhDashboard QCheckBox { color:
... }`. **How to apply:** any future widget type added to this dashboard
needs its own explicit text-color rule in `wtmh_theme.py` — nothing here
inherits a usable color from the OS palette by default.

**Live-validated end-to-end via qt-mcp**, against `tools/
fake_gazepoint_server.py` (no real device needed): typed Subject ID,
selected Sex, connected to `127.0.0.1:4242`, ran a real calibration
(measured 5 points/8px via the fake server's fixed response, not a stub),
confirmed Continue-to-Tasks correctly gated and then enabled, ran Static
Click embedded-in-place (confirmed via screenshot: same titlebar, same
window, task canvas + the existing `OperatorPanel` HUD sidebar both
rendering inside the dashboard, trial count advancing), ended it cleanly
(returned to the Tasks tab, card marked Complete, no leftover process),
and re-ran the same task a second time to confirm the run-index naming
(`_run1`/`_run2`/`_run3` on disk, no collisions). Confirmed
`assessment_date`/`sex`/`notes` all reach `metadata.json` correctly after
the fix above. Full pytest suite: 113 passed, the same single pre-existing
failure (`test_config_merges_task_over_default`) — no regressions from
either the `AssessmentApp`/`MainWindow` split or the `SessionMetadata`
field additions (checked: no test asserts on `SessionMetadata`'s exact
field set). Added `tests/test_dashboard_helpers.py` (6 tests) for the two
Qt-free helpers.

**Files added:** `src/ui/dashboard_window.py`, `src/ui/setup_page.py`,
`src/ui/tasks_page.py`, `src/ui/wtmh_theme.py`, `src/engine/
session_naming.py`, `src/engine/local_state.py`,
`tests/test_dashboard_helpers.py`.
**Files changed:** `src/app.py`, `src/ui/main_window.py`, `src/main.py`
(new `--dashboard` flag), `src/data/schema.py` (`SessionMetadata` gained
`assessment_date`/`sex`), `.gitignore` (`configs/local_state.json`),
`README.md` (new dashboard section, corrected stale pytest count 80→114).
**Left uncommitted**, matching this project's established ask-before-
commit pattern.

## 11. Styling-pass feedback round (design/evaluation only, nothing implemented)

**Origin:** the user ran a separate, codebase-blind Claude session against a
screenshot of the running dashboard and got back a styling critique. That
critique is reproduced verbatim below. The user also found two bugs of their
own while testing. **This session's job was strictly to evaluate the
critique against the real code (grounded via file/line reads) and record a
plan — not to write any code.**

### 11.1 The critique prompt, verbatim

> Do a full styling pass on the PyQt GUI, applying the Clinical Teal palette
> consistently and fixing the following issues found in review. This covers
> the Setup screen, Tasks screen, and Task settings modal.
>
> **1. Task settings modal (highest priority — currently unthemed)**
> The modal ("Task settings — click_static") is still using the default dark
> Qt dialog style and looks completely disconnected from the rest of the
> app. Apply the same light theme as the main window (white/panel background
> `#FFFFFF`, ink text `#122B3A`, border `#DBE6EC`); add border-radius (~8px)
> and a soft drop shadow; title bar should match app chrome, not default OS
> dark styling; "Start task" → primary style (accent gradient `#2FA8C4` →
> `#1A6F95`, white text); "Cancel" → ghost/secondary style (transparent,
> border, ink text) — currently both buttons read with similar visual
> weight; sliders/steppers inside the modal should match the themed controls
> used elsewhere, not native OS styling.
>
> **2. Establish a real button hierarchy, apply everywhere**
> Primary (solid accent gradient, white text — Connect/Run/Start task);
> Secondary (soft accent bg `#DCF0F5`, accent-strong text `#0F5670` — Test
> Connection/Load Calibration File); Ghost/tertiary (transparent, 1px border
> `#DBE6EC`, ink text — Settings/Cancel); Disabled (~45% opacity, no hover).
> "Do Calibration" currently uses a washed-out light-teal fill that barely
> reads as clickable — restyle it as a proper secondary button.
>
> **3. Differentiate static info/banners from clickable CTAs**
> The pale blue background used for the "No calibration yet..." warning
> banner and the "Confirm in Gazepoint Control..." reminder is visually
> identical to the "Continue to Tasks →" button, which IS clickable.
> Info/warning banners should keep a tinted background but lose any
> button-like affordance (no rounded pill shape matching buttons, left
> accent border in a distinct muted color e.g. `#8FB4C2`, with an icon if
> feasible). "Continue to Tasks →" stays a true primary button.
>
> **4. Theme form controls to match the app, not native OS chrome**
> Dropdowns (Assessment Date, Sex): custom chevron icon matching accent
> color, themed border, remove native OS arrow styling. Number steppers
> (Control Port, Point Count): themed up/down buttons. Checkboxes ("Show
> calibration window to the subject"): custom check style using accent color
> `#1F7A9C` for the checked state, not native OS checkbox.
>
> **5. Spacing and rhythm**
> Standardize card padding across Setup and Tasks screens — Tasks screen
> cards currently feel tighter than Setup screen cards. Add consistent
> vertical spacing between a field's label and its input (currently too
> tight), and more separation between one field group and the next within a
> card.
>
> **6. Status pill system (Tasks screen)**
> "Pending" currently uses a neutral gray pill. Define the full set: Pending
> (neutral gray, keep as-is); Running (soft accent `#DCF0F5` bg,
> accent-strong text); Complete (soft green bg, success green `#2F9E6E`
> family text); Error (soft red bg, danger red `#E15353` family text).
>
> Keep all existing layout structure, screen flow, and functionality — this
> is a styling/QSS pass, not a restructure.

### 11.2 The user's own two findings (from live testing, not the critique)

- **A. Sex dropdown unreadable.** Opening the Sex `QComboBox` on the Setup
  tab renders every popup list item white-on-white — no option is
  distinguishable or clickable by sight.
- **B. No run-number indicator.** Running the same task multiple times
  (Run, then Run again) gives no on-screen indication of which attempt is
  which — no "run 1"/"run 2" anywhere on the Tasks screen.

### 11.3 Grounded evaluation (verified against the real source this session)

1. **Critique #1 (modal unthemed) — CONFIRMED, fully valid, highest-value
   fix.** `src/ui/task_settings_dialog.py`'s `TaskSettingsDialog(QDialog)`
   applies zero styling anywhere — no `objectName`, no stylesheet, entirely
   native OS default. `src/ui/wtmh_theme.py`'s `STYLESHEET` is deliberately
   scoped to `QWidget#wtmhDashboard` descendants only (its own docstring:
   so it can never leak into `TaskCanvas`) — the dialog is a separate
   top-level window that was never brought into that scope.
2. **Critique #2 (button hierarchy) — PARTIALLY ALREADY IMPLEMENTED; the
   critique is screenshot-derived and stale in one respect.**
   `wtmh_theme.py` already defines and applies three tiers
   (`wtmhPrimary`/`wtmhSecondary`/`wtmhGhost`): Connect=primary, Test
   Connection=ghost, Do Calibration=primary, Load Calibration File=ghost,
   Continue to Tasks=primary (`src/ui/setup_page.py` lines ~149, 215, 220,
   249, 255). The "washed-out Do Calibration" the critique saw is almost
   certainly the button's DISABLED state
   (`setup_page.py:250`, `self.do_calibration_button.setEnabled(False)  #
   needs a connected tracker first`) — `wtmhPrimary:disabled` falls back to
   the soft-accent colors, which reads exactly as "washed-out light-teal."
   Real, confirmed, independent gap: only `wtmhPrimary` has an explicit
   `:disabled` rule; `wtmhSecondary`/`wtmhGhost` have none, so they don't
   get the critique's proposed universal disabled treatment (~45% opacity,
   no hover).
3. **Critique #3 (banners vs CTAs) — ALREADY LARGELY CORRECT; one small
   real gap.** `wtmhAlertInfo`/`wtmhAlertWarning`/`wtmhAlertSuccess`/
   `wtmhAlertError` already use left-accent-border cards, not pill/button
   shapes, and read as visually distinct from `wtmhPrimary`'s gradient-fill
   pills — the stated confusion doesn't hold against the current CSS. Real
   gap: `wtmhAlertInfo` and `wtmhAlertWarning` currently share IDENTICAL
   styling (both soft-accent bg + accent-color left border), so info vs.
   warning severity isn't visually distinguished. No icon exists on any
   alert today (critique's "with an icon if feasible" — unaddressed).
4. **Critique #4 (form controls) — CONFIRMED, valid, unaddressed; also the
   direct root cause of finding A.** No dropdown/stepper/checkbox in
   `setup_page.py` has any custom chrome — `QComboBox`/`QSpinBox`/
   `QCheckBox` get only border/padding on the closed box
   (`wtmh_theme.py` lines ~141-158), nothing else.
5. **Critique #5 (spacing) — PARTIALLY CONFIRMED; the critique overstates
   the card-padding difference.** Card margins are actually IDENTICAL
   between the two screens — both `setup_page.py`'s card layout and
   `tasks_page.py`'s `_TaskCard` layout use
   `setContentsMargins(16, 14, 16, 14)`; the only difference is inner
   `setSpacing()` (8 in `setup_page.py` vs. 6 in `tasks_page.py`), a 2px
   difference, not the pronounced gap described. The label-glued-to-field
   complaint IS confirmed: neither of `setup_page.py`'s two
   `QFormLayout()` instances (lines ~168, 235) calls
   `setVerticalSpacing()`, so both fall back to the tight platform default.
6. **Critique #6 (status pills) — CONFIRMED, real, and the most
   functionally significant finding.** `tasks_page.py`'s
   `_TaskCard.set_status()` (line ~83) only branches on
   `status == "Complete"` (→ `wtmhBadgeSuccess`) vs. everything else
   (→ `wtmhBadgeNeutral`). `dashboard_window.py:186` already calls
   `set_task_status(task_id, "Running")` when a run starts — but since
   `set_status()` has no "Running" branch, it silently renders as the same
   neutral gray as "Pending." No "Error" status is ever set anywhere in the
   codebase today — the one caught exception
   (`CalibrationFileError`, `dashboard_window.py:179`) reverts the card to
   "Pending", not an Error state — Error is entirely unimplemented, not
   just unstyled.
7. **Finding A (white-on-white Sex dropdown) — ROOT-CAUSED.** Same bug
   family as an already-documented gotcha in this SPEC (§10: "any future
   widget type added to this dashboard needs its own explicit text-color
   rule in `wtmh_theme.py` — nothing here inherits a usable color from the
   OS palette by default", found for `QCheckBox`). A `QComboBox`'s dropdown
   popup is a separate top-level `QAbstractItemView`, not a layout-tree
   descendant of `QWidget#wtmhDashboard` — so `STYLESHEET`'s
   `QWidget#wtmhDashboard QComboBox {...}` rule styles the closed box
   correctly but never reaches the popup list, which falls back to the
   OS/Qt default palette. Needs an explicit
   `QComboBox QAbstractItemView { ... }` rule — same root-cause family as
   the already-fixed checkbox bug, not a new class of problem.
8. **Finding B (no run-number indicator) — CONFIRMED gap.**
   `session_naming.py`'s `next_session_id()` already computes a
   collision-free `_run<N>` suffix on disk, but nothing in
   `tasks_page.py`/`dashboard_window.py` ever surfaces that number to the
   operator — `_TaskCard` has no run-count label/badge at all.

### 11.4 Decisions (three forks, all resolved via `AskUserQuestion`, user picked the recommended option each time)

1. **Button hierarchy: keep today's per-panel-primary pattern.** Connect /
   Do Calibration / Continue to Tasks all stay primary tier — each is the
   main action of its own panel. Rejected: collapsing to a single
   primary-per-screen model (the critique's literal ask). Instead, fix the
   DISABLED state to read clearly as disabled — extend a real `:disabled`
   treatment (reduced opacity, no hover) to `wtmhSecondary`/`wtmhGhost` too,
   not just `wtmhPrimary`.
2. **Error status: style only this round.** Add the Error pill's colors
   (soft red bg, danger red text) so the token exists, matching the same
   "reserved for a future real use" pattern already used for the unused
   `.wmd-badge-danger` class in §9.3's wireframe palette. Do **not** wire
   actual error detection (a `try`/`except` around the embedded task run in
   `dashboard_window.py`) this round — that's a functional change, out of
   scope for a styling pass, left for a future round.
3. **Run-number indicator: derive from disk.** Reuse
   `session_naming.py`'s own directory-scan logic (not a fresh in-memory
   counter in `DashboardWindow`) so the shown count stays correct even
   across a dashboard restart mid-session — consistent with how the
   `_run<N>` suffix itself is already computed. Rejected: an in-memory
   per-task counter (simpler, but would silently reset to 0 on a restart
   even though old runs still exist on disk).

### 11.5 Planned changes (for the next, implementation, session — nothing below is built yet)

- Theme `TaskSettingsDialog`: bring it into (or extend) the
  `wtmh_theme.py` `STYLESHEET` scope — likely by giving the dialog an
  `objectName` the stylesheet selectors can target (or applying
  `STYLESHEET` directly to the dialog), adding border-radius + a drop
  shadow (`QGraphicsDropShadowEffect`, same pattern already used for
  `OperatorPanel`'s HUD cards), and restyling its `QDialogButtonBox` Ok/
  Cancel into `wtmhPrimary`/`wtmhGhost` respectively. Its `SliderSpinRow`
  controls should inherit app-wide styling once brought into the themed
  scope — verify this live, don't assume.
- Extend `:disabled` styling to `wtmhSecondary`/`wtmhGhost` in
  `wtmh_theme.py`.
- Differentiate `wtmhAlertInfo` vs. `wtmhAlertWarning` with distinct
  colors (currently identical).
- Add a `QComboBox QAbstractItemView` popup-styling rule to fix the
  white-on-white dropdown bug (covers Sex and any future `QComboBox`) —
  a root-cause fix, not a one-off patch.
- Add themed custom chrome for `QSpinBox` steppers and a custom
  `QCheckBox` check style, per critique #4.
- Add `setVerticalSpacing()` to `setup_page.py`'s two `QFormLayout`
  instances.
- Add a "Running" branch to `_TaskCard.set_status()` (soft accent bg/
  text) and an "Error" pill (soft red bg/danger red text — styled but not
  yet triggered by any code path, per §11.4 decision 2).
- Add a run-count label/badge to `_TaskCard`, sourced by scanning the
  output directory the same way `next_session_id()` does (read-only
  reuse, not a new counting mechanism, per §11.4 decision 3).

### 11.6 Implementation and live validation

Every item in §11.5's plan is now implemented.

**Files changed:**

- `src/ui/wtmh_theme.py` — added `:disabled` styling for `wtmhSecondary`
  (previously only `wtmhPrimary` had one); two new banner-differentiation
  tokens, `BANNER_BORDER` (`#8FB4C2`, deliberately distinct from the vivid
  `ACCENT` used on primary-button gradients/focus rings) and
  `WARNING_BG`/`WARNING_BORDER` (`#FBF0DC`/`#D9A441`, amber), so
  `wtmhAlertInfo` and `wtmhAlertWarning` are no longer visually identical;
  `QDoubleSpinBox` added to the shared themed-form-control selector group
  (previously only `QSpinBox` was covered, so `TaskSettingsDialog`'s
  float-kind `SliderSpinRow` controls fell back to native styling); a
  `QComboBox QAbstractItemView` popup rule (background/color/selection
  colors) — the root-cause fix for finding A, exploiting Qt's standard
  behavior of forwarding a `QComboBox`'s own effective stylesheet into its
  popup view even though the popup is a separate top-level widget; a
  CSS-triangle (zero-size + border) custom chevron for
  `QComboBox::down-arrow` and up/down-arrow steppers for
  `QSpinBox`/`QDoubleSpinBox`, replacing native OS arrows with no new
  image asset; a custom `QCheckBox::indicator` (bordered, accent-filled
  when checked); a themed `QSlider` groove/handle/sub-page in the accent
  gradient color; and a new `wtmhBadgeDanger` label style (soft red bg /
  danger red text) for the Error status pill. Left `wtmhBadgeSuccess`
  ("Complete") in its existing solid-green/white-text style rather than
  restyling it to match the new soft-tint family — a deliberate
  scope-discipline call: §11.5's plan only committed to adding the
  missing Running/Error states, not revisiting an already-shipped,
  already-approved pill.
- `src/ui/task_settings_dialog.py` — the headline fix. The dialog now
  sets `objectName("wtmhDashboard")` and applies `wtmh_theme.STYLESHEET`
  directly to itself, so every ancestor-scoped rule in the shared
  stylesheet (form controls, all three button tiers, the new slider
  styling) applies automatically with no CSS duplication. Content is
  wrapped in a `QFrame` (`objectName("wtmhCard")`: white background,
  bordered, 8px radius) with its own `QGraphicsDropShadowEffect` (blur
  20, offset (0,6), `rgba(0,0,0,60)`) — same pattern already established
  for `OperatorPanel`'s HUD cards — giving the "lifted off the app" look
  the critique asked for. An in-card title label restates "Task settings
  — `<task_id>`" since the dialog keeps its native OS title bar (this app
  never goes frameless anywhere, not even `DashboardWindow` itself, which
  only adds a styled bar below the OS chrome — consistent with the app's
  own established pattern, not a shortfall). "Start task" is now
  `objectName("wtmhPrimary")`, "Cancel" is `wtmhGhost` (previously
  neither `QDialogButtonBox` button had any styling).
- `src/ui/setup_page.py` — added `form.setVerticalSpacing(10)` to both
  `QFormLayout` instances (Subject & Session Info card, Calibration
  card), fixing the confirmed label-glued-to-field gap.
- `src/ui/tasks_page.py` — `_TaskCard`'s layout spacing changed from 6 to
  8 to exactly match `setup_page.py`'s card rhythm. `set_status()` now
  maps all 4 states via a `_STATUS_BADGES` dict (Pending→neutral,
  Running→`wtmhBadgeAccent` [newly wired — `dashboard_window.py` already
  called this, it just silently fell through to neutral before],
  Complete→`wtmhBadgeSuccess` [unchanged], Error→`wtmhBadgeDanger`
  [styled and reachable, but per §11.4 decision 2 nothing in the app
  actually triggers it yet]). Added a `run_label` QLabel ("No runs yet"
  initially) next to the status pill and a `set_run_count(n)` method
  setting it to `f"Run {n}"`; `TasksPage.set_task_run_number(task_id, n)`
  passes this through from `DashboardWindow`.
- `src/engine/session_naming.py` — extracted a new public
  `next_run_number(output_root, subject_id, task_id, date_str=None) ->
  int` out of the existing `next_session_id()` (which now calls it
  internally) — a pure refactor, `next_session_id()`'s own
  behavior/return value is unchanged and no existing test needed
  updating.
- `src/ui/dashboard_window.py` — imports `next_run_number`;
  `_on_run_requested` now computes the upcoming run's number (via the
  subject ID and the task's own `recording.output_root` from
  `load_task_config`) before constructing `AssessmentApp`, and calls
  `self.tasks_page.set_task_run_number(task_id, run_number)` alongside
  the existing `set_task_status(task_id, "Running")` call. This predicts
  the same number `AssessmentApp`/`SessionRecorder` will independently
  compute moments later via their own `next_session_id()` call — safe
  since nothing else can create a session directory between the two
  calls in this single-threaded UI flow.
- `tests/test_dashboard_helpers.py` — added 3 new tests for
  `next_run_number` (first-run-is-one, increments-past-existing-runs,
  and a cross-check that it agrees with what `next_session_id` derives
  from it).

**Testing:** full pytest suite: 116 passed, 1 failed (same single
pre-existing failure, `test_config_merges_task_over_default` /
`target_fps` 60-vs-150, unrelated, on record since 2026-08-31) — no
regressions. 3 new tests added and passing.

**Live validation** (qt-mcp, against `tools/fake_gazepoint_server.py` on
port 4243 — not the real GP3HD; port 4242 was found already bound by the
real Gazepoint Control application running on this machine, so a
non-default port was used deliberately to avoid touching it):

- Setup tab screenshot confirmed: the disabled "Do Calibration" button
  reads visibly different (soft washed-out teal) from its enabled state
  (full gradient) once connected — direct visual confirmation of the
  §11.3 root-cause diagnosis (the critique's "washed-out" complaint was
  the disabled state, not a wrong tier); the warning banner ("No
  calibration yet...") now renders in a distinct amber/tan tint versus
  the info banner ("Before You Start")'s muted teal-blue — the
  info/warning differentiation confirmed live.
- Opening the Sex `QComboBox`: qt-mcp's synthetic click does open the
  real native popup (a separate top-level `QFrame`/`QListView`,
  confirmed via `qt_list_windows` and `qt_snapshot` with
  `skip_hidden=false`) but the popup isn't part of the normal widget
  tree qt-mcp searches, and a synthetic click on a popup row doesn't
  reliably commit a selection through the tool — a qt-mcp limitation,
  not an app bug. Screenshotting the popup widget directly by ref showed
  dark ink-colored text ("Select" / "Female" / "Male" / "Other / Prefer
  not to say") clearly readable on a white background with a soft-accent
  highlight on the current item — the white-on-white bug is confirmed
  fixed. Selecting a value for the later Continue-to-Tasks gating step
  was done via `qt_set_property(currentIndex)` instead, since that was
  the goal (proving the gate), not re-proving the popup click itself.
- `TaskSettingsDialog` could **not** be opened through its real trigger
  (Tasks tab's Settings button) via qt-mcp — clicking it calls the
  dialog's `.exec()`, which blocks the same synchronous call stack the
  click's own RPC response needs to complete on, wedging the qt-mcp
  probe entirely (`qt_list_windows` and `qt_snapshot` both then failed
  too, requiring the whole dashboard process to be killed and
  relaunched). **New, evergreen qt-mcp finding worth remembering for any
  future modal-dialog QA in this app:** `.exec()`-based modals cannot be
  opened via a qt-mcp-driven click and screenshotted in the same
  session — write a small scratch script that constructs the dialog
  directly and calls `.show()` instead of `.exec()` for visual QA
  purposes only (a testing-only workaround; the app's own use of
  `.exec()` is correct, standard, blocking-by-design UX and was not
  changed). Did exactly that (a throwaway script under the session
  scratchpad, deleted after use) and confirmed via screenshot: a white,
  bordered, rounded card with a visible soft drop shadow against the
  gray dialog backdrop, the accent-teal themed slider + spinbox stepper
  controls, "Start task" in the full primary gradient, "Cancel" as a
  bordered ghost button.
- Full run-flow live-validated against the fake server: connected
  (127.0.0.1:4243), ran a real calibration (5 points, 8px mean error,
  valid — success alert rendered in green), set Sex via property (to
  satisfy the Continue-to-Tasks gate, confirmed it flipped from disabled
  to enabled), continued to Tasks, ran Static Click twice in a row.
  First run: card ended on "Complete" (still the pre-existing
  solid-green pill, unchanged) with a new "Run 1" label beside it.
  Mid-second-run, captured the status label's live text via
  `qt_get_text` and confirmed it read "Running" (proving the previously-
  silent Running branch is now actually reached, not just present in
  the CSS) before ending the task; second run ended showing "Complete" /
  "Run 2" — confirming the run-number indicator increments correctly
  across repeated runs, resolving finding B end-to-end, not just the
  helper-function unit tests. No new Qt warnings beyond the already-known
  `QSoundEffect` audio-device ones (`qt_messages` checked at "warning"
  level, 4 messages, all pre-existing/unrelated).
- Scratch QA session directories created during this validation
  (`sessions/2026-09-08_QASTYLE01_click_static_run1` and `_run2`) were
  deleted afterward; all QA python/fake-server processes were stopped; a
  stray empty junk file accidentally created by an earlier shell command
  was found and removed before checking git status.

**Scope note:** per §11.4 decision 2, the Error pill is styled and
reachable through `_TaskCard.set_status()` but nothing in the app
actually calls it with "Error" yet — no `try`/`except` was added around
the embedded task run this round, matching the agreed scope (styling
pass, not a functional change).

**Left uncommitted**, matching this project's established ask-before-
commit pattern (every prior round in this SPEC's history, §8 through
§11, followed the same pattern).

## 12. Arrow-rendering regression fix

Right after §11's implementation landed, the user ran another external
codebase-blind Claude critique against a screenshot of the updated GUI.
It reported the QSpinBox up/down arrows (Control Port, Point Count)
rendering as "tiny, malformed slivers" instead of distinct caret
buttons, and the QComboBox dropdown chevron (Assessment Date, Sex)
rendering as a "squashed/compressed dash" instead of a clean downward
chevron — both introduced by §11.5's own custom-arrow QSS. Core ask:
fix `QSpinBox::up-button`/`down-button`/`up-arrow`/`down-arrow` and
`QComboBox::drop-down`/`down-arrow` so each QSpinBox shows two clearly
distinct ~16x12px caret buttons with a visible 1px separator, accent
teal (`#1F7A9C`) arrow color, and each QComboBox shows a single clean
~10-12px downward chevron, verified at actual rendered size in the
app — explicitly scoped as "a targeted fix for the arrow rendering
regression only," not other styling changes.

**This critique was accurate, not stale.** §11.6's own live-validation
screenshot had these controls too small to properly assess and this was
noted in passing at the time ("appears at very small size / bit hard to
see... acceptable at this resolution") without actually zooming in to
verify — the regression was real and should have been caught during
§11's own live validation.

### 12.1 Investigation and root cause (two layers)

**Layer 1 (partial fix, insufficient alone).** The §11.5 QSS gave
`::up-arrow`/`::down-arrow`/`::down-arrow` (combobox) a zero-width/
zero-height box drawn via CSS borders (the standard web-CSS "triangle
trick") but never gave those specific arrow subcontrols their own
`subcontrol-origin`/`subcontrol-position` — so Qt fell back to its
platform style's own tiny built-in icon-metric box to contain them,
clipping the border-drawn shape regardless of the width/height
declared. Fixed by adding `subcontrol-origin: padding;
subcontrol-position: center` (or `center right` for the combobox) to
each arrow rule, and adding a 1px border between the QSpinBox
up-button and down-button (previously absent, per the critique's
explicit ask for a visible separator). This visibly fixed the
button-area separation/spacing (confirmed via a qt-mcp screenshot
showing two now-distinct button segments) but a further zoomed
pixel-level inspection showed the arrow **glyph** itself was still not
rendering correctly.

**Layer 2 (the real root cause).** A qt-mcp screenshot at actual UI
scale wasn't conclusive at this resolution, so a scratch diagnostic
script grabbed the QSpinBox/QComboBox as `QPixmap`s directly and
upscaled them 8x with nearest-neighbor filtering (preserving exact
pixel boundaries) for a true pixel-level inspection. This revealed the
arrows were rendering as **solid filled rectangles, not triangles at
all** — confirming the CSS "zero-size box + border" triangle trick
simply does not render as a triangle for `::up-arrow`/`::down-arrow`
subcontrols in this Qt/PySide6 build, under the app's default platform
style ("windowsvista" on Windows, which the app had never overridden).

A real, closable decision point followed: the standard, reliable fix
for this whole class of Qt QSS limitation is switching `QApplication`
to the "Fusion" style (which fully honors custom subcontrol QSS) — but
that's a bigger lever than pure CSS, applied via
`QApplication.setStyle()` and affecting the whole app's render engine,
arguably outside the critique's literal "don't change other styling"
instruction even though it touches no color/QSS rule itself. Asked the
user via `AskUserQuestion`; **user chose to switch to Fusion** (the
recommended option) over continuing to iterate on QSS-only
workarounds. Implemented in `src/ui/dashboard_window.py`'s
`run_dashboard()`: `QApplication.setStyle("Fusion")`, guarded to only
apply when this call is the one constructing a fresh `QApplication`
instance (checked via `QApplication.instance() is None` before
construction) — deliberately **not** touching the separate standalone
`--task X --gui` launch path (`src/app.py`'s `run_gui()`), since that
path's `OperatorPanel`/`MainWindow` controls were never reported broken
and the fix was kept narrowly scoped to the actually-affected dashboard
path.

Re-tested with the same 8x-nearest-neighbor pixel-zoom diagnostic under
Fusion: **still rendered as solid filled rectangles, not triangles** —
Fusion did not fix it either. This proved the CSS border-triangle
technique itself is fundamentally unreliable for these Qt subcontrols
in this environment, regardless of style, not merely a
subcontrol-geometry or platform-style problem.

### 12.2 Real fix: image assets, not CSS triangles

Replaced the CSS-triangle technique entirely with real PNG image
assets. A one-time scratch generator script used `QPainter` to draw
three small anti-aliased accent-teal (`#1F7A9C`) triangles onto
transparent-background `QPixmap`s (a 16x16 canvas with a 10x6 chevron
for the combobox; two 12x12 canvases with 8x5 carets for the spinbox
up/down arrows) and saved them as PNGs. These are now committed, real
repo assets at `configs/assets/icons/chevron-down.png`, `spin-up.png`,
`spin-down.png` (parallel to the existing `configs/assets/branding/`
pattern for the WTMH logo/icon).

`src/ui/wtmh_theme.py` now imports `CONFIG_ROOT` from
`src/engine/config.py` and builds an absolute, CWD-independent
`_ICONS_DIR` path (`(CONFIG_ROOT / "assets" / "icons").as_posix()`) —
important because QSS `url()` on a stylesheet string set via
`setStyleSheet()` (not loaded from a `.qss` file) resolves relative
paths against the process's current working directory, which this
app's launch method doesn't reliably control. The `::up-arrow`/
`::down-arrow` QSS rules now use `image:
url({_ICONS_DIR}/spin-up.png)` etc. with explicit width/height
matching each PNG's canvas size, keeping the `subcontrol-origin:
padding; subcontrol-position: center` positioning fix from §12.1
(still needed to reserve a properly-sized box for the image, same
reasoning as before). The QSpinBox arrows' color also changed from the
old `SOFT_ACCENT_TEXT` (`#0F5670`) to `ACCENT` (`#1F7A9C`) to match the
critique's explicit color spec, which asked for accent teal on both
controls, not the previously-used darker teal variant on the spinbox
arrows specifically; the combobox chevron was already `ACCENT`, no
change needed there.

**Verification:** re-ran the same 8x pixel-zoom diagnostic script —
confirmed clean, unambiguous triangles this time (crisp up-caret,
down-caret with a visible gap/separator between the two spinbox
buttons, and a proper downward chevron on the combobox). Then killed
and relaunched the **real** dashboard app (not the isolated
diagnostic) via qt-mcp and re-confirmed live: enlarged the actual live
widgets via `qt_set_property(minimumHeight)` as a temporary, QA-only
zoom (not a code change, reverted by relaunching fresh afterward) and
screenshotted them directly — same clean triangles confirmed in the
real running app, not just the isolated test harness. `qt_messages` at
"warning" level showed no new warnings (empty). Full pytest suite: 116
passed, same single pre-existing failure, no regressions (this was a
pure QSS + one new `QApplication.setStyle()` call + new binary assets,
no test-relevant logic changed). The scratch generator/diagnostic
scripts and their temporary output files were deleted after use; the
three real PNG assets are the only lasting new files. Two more stray
empty junk files (accidentally created by earlier shell command
parsing quirks, unrelated to any real work) were found and removed
before checking git status, same as during the §11.6 round.

**Files changed this round:**

- `src/ui/wtmh_theme.py` — `CONFIG_ROOT` import + `_ICONS_DIR`;
  QComboBox/QSpinBox/QDoubleSpinBox arrow rules switched from
  CSS-triangle to `image: url(...)`; QSpinBox arrow color changed to
  `ACCENT`; added `subcontrol-origin`/`subcontrol-position` to all
  three arrow rules; added a 1px separator border between QSpinBox's
  up-button and down-button; bumped up/down-button width from 16px to
  18px.
- `src/ui/dashboard_window.py` — `run_dashboard()` now calls
  `QApplication.setStyle("Fusion")` when it's the one constructing a
  fresh `QApplication` instance.
- `configs/assets/icons/chevron-down.png`, `spin-up.png`,
  `spin-down.png` — new committed binary assets.

**Scope note:** `src/app.py`'s `run_gui()` (the standalone `--task X
--gui` launch path, used by `MainWindow`/`OperatorPanel`) was
deliberately **not** changed to also set Fusion style — that path's
controls were never reported broken, and the user's fork decision was
scoped to fixing the dashboard's actually-broken controls, not a
proactive whole-app style change beyond what was needed.

**Left uncommitted**, matching this project's established
ask-before-commit pattern — now four rounds (§9-§12) sit uncommitted
together.

## 13. Combobox popup, checkbox, calendar decision, and a real functional bug

The user reported two things together: (1) another external
codebase-blind critique against a fresh screenshot, reporting three
remaining styling gaps — the QCalendarWidget popup (unthemed, dark
default), the QComboBox dropdown popup (heavy black border, no
rounding, no hover/selected states — a regression, since this exact
popup had already been fixed once in §11), and the checkbox (solid flat
fill, no visible checkmark, no border in the unchecked state); (2)
their own bug report: "after load calibration when I click continue
task button, I cant press it."

### 13.1 The functional bug — root-caused as a UX gap, not a code defect

Verified via a scratch script that monkeypatched only
`QFileDialog.getOpenFileName` (the real one blocks the same way
`QDialog.exec()` does, wedging the qt-mcp probe the same way
`TaskSettingsDialog` did in §11 — confirmed by testing it directly
first) to exercise `SetupPage._on_load_calibration_clicked`'s real,
unmodified code path. Confirmed: after loading a calibration file
successfully (`calibration_result` populated correctly, success alert
shown correctly), `can_continue()` still correctly returns `False` and
Continue stays disabled — because `can_continue()` has always also
required a live connected tracker
(`self._client is not None and self._client.is_connected()`),
independently of where the calibration came from, per the original
§5.6 gate design. Verified the positive case too: after also connecting
a real client (against `tools/fake_gazepoint_server.py`),
`can_continue()` flips `True` and the button enables correctly. **Not a
code bug** — a real UX gap: the success alert after loading calibration
never told the user a tracker connection was still separately required,
so a user who used Load Calibration File specifically to skip
re-calibrating could reasonably not realize Connect was still needed.

**Fix:** added `SetupPage._missing_requirements()` (checks tracker/
calibration/subject-ID/sex, matching `can_continue()`'s real
conditions) and wired it into `_on_state_changed()` so the disabled
Continue button now carries a live-updating tooltip, e.g. "Still
needed: connect to the tracker; run or load a calibration; enter a
Subject ID." — confirmed live via qt-mcp (`qt_widget_details` on the
real disabled button showed exactly this tooltip text, updating
correctly as state changed).

**One-off observation, not resolved either way:** during one qt-mcp
click on the Sex combobox's open popup, the whole dashboard process
died with an empty log (no Python traceback, consistent with a
native-level exit) and the qt-mcp probe connection was lost
immediately after; reproducing the same click sequence a second time
did **not** crash (process survived, probe reconnected). Treated as
inconclusive/likely a qt-mcp-side transient (matches an already-
documented gotcha about transient probe connection loss) rather than a
confirmed deterministic app crash, since it didn't reproduce on retry —
worth remembering if it's ever seen again, not a resolved or dismissed
issue.

### 13.2 QComboBox popup regression — root-caused and fixed

The popup was correctly themed in §11 (white bg, 1px border, dark
readable text — confirmed via a live qt-mcp screenshot at the time).
After §12 switched the app to the Fusion QStyle (to fix the arrow-icon
rendering regression), the popup regressed to a heavy black border with
no rounding and tight padding — confirmed live via qt-mcp screenshot
this round, matching the critique's report exactly, not stale.

**Root cause:** Qt's QComboBox popup is wrapped in an undocumented,
unstyleable `QComboBoxPrivateContainer` (a `QFrame`) that draws its own
native frame decoration independently of the QSS already applied to
the popup's `QAbstractItemView` — invisible under the native
"windowsvista" style (§11), but very visible under Fusion (§12). QSS
has no selector that can reach that undocumented container class.

**Fix:** `setup_page.py` now calls
`self.sex_combo.view().setFrameShape(QFrame.Shape.NoFrame)` right
after constructing the Sex combobox, removing the native frame
decoration so the `QAbstractItemView`'s own QSS border/radius is the
only one visible — confirmed via a live qt-mcp screenshot: clean 1px
border, 8px rounded corners, comfortable item padding, no heavy black
border.

Also extended per the critique's explicit ask:
`QComboBox QAbstractItemView::item` now has ~9px/12px padding, a
`:hover` state (soft accent background), and a `:selected` state
(accent-strong background, white text) — previously only a single
non-differentiated `selection-background-color`/`selection-color`
property existed, which couldn't distinguish hover from selected.

**Residual, minor, disclosed detail:** Qt's Fusion style still draws
its own thin native "current item" indicator rectangle around the
keyboard-focused row (distinct from hover/selected, a standard Qt
accessibility affordance) that `::item:focus { border: none }` did not
suppress — left as-is since it's a subtle 1px accessibility affordance,
not the "heavy black border / unstyled debug outline" look the
critique was actually complaining about, and chasing it further hit the
same native-chrome-resists-QSS wall as other fixes today.

### 13.3 Checkbox — fixed with a real image asset

Confirmed via live screenshot the checkbox previously had no visible
checkmark in the checked state (just a solid accent-teal fill) and only
a plain fallback border in the unchecked state — matching the critique.
Consistent with §12's established finding that CSS-only glyph tricks
are unreliable for Qt indicator subcontrols in this build, generated a
real 14x14 white checkmark PNG (via a `QPainter` scratch script, an
antialiased polyline) at `configs/assets/icons/checkmark.png`,
referenced via `QCheckBox::indicator:checked { image: url(...) }`
alongside the existing accent-fill background. Confirmed live via
qt-mcp: a clearly visible white checkmark now renders inside the
accent-teal checked box.

### 13.4 QCalendarWidget popup — attempted, then superseded by a product decision

Investigation of the calendar popup surfaced a **third** instance of
the same "native chrome resists QSS" pattern already hit twice this
session (§12's arrows, §13.2's combobox popup frame): the weekday
header row's background could not be changed via QSS at all — neither
an ancestor-scoped rule nor a stylesheet applied directly to the
`QHeaderView` instance had any visible effect (confirmed via a scratch
diagnostic: setting
`header.setStyleSheet("QHeaderView::section { background: red }")`
directly on the instance produced no visible change).

**Root-caused further, and it's session-wide, not calendar-specific:**
a `QPalette`-level override on the header instance *did* work
(confirmed: setting the header's Button/Window palette roles to a test
color visibly changed its rendering), revealing that
`QApplication`'s default Fusion palette on this machine is **dark**
(Window `#1e1e1e`, Button `#3c3c3c`), because Windows dark mode gets
auto-inherited by Qt6 regardless of which QStyle is active — anything
not explicitly covered by this app's own QSS silently falls back to
that dark palette instead of a neutral light one. This is very likely
the real, general explanation behind most of this whole line of work's
"looks dark/unthemed" complaints (the original `TaskSettingsDialog`
critique included), not just the calendar header specifically.

**Fixed generally:** `dashboard_window.py`'s `run_dashboard()` now also
calls `app.setPalette(QStyleFactory.create("Fusion").standardPalette())`
right after `setStyle("Fusion")` — Fusion's own standard palette is a
real light default, independent of OS dark-mode inheritance, so any
future not-yet-explicitly-styled widget/subcontrol now falls back to
something reasonable instead of near-black. This is a general
robustness fix, not scoped only to the calendar.

Even with the palette fix applied app-wide, the calendar header's exact
brand background color (`PANEL_BG` white) still did not match precisely
when tested (came out as a dark charcoal rather than white, root cause
not further chased) — mid-investigation of this, **the user
interrupted with a product-level reconsideration**: "it didn't make
sense for a physician to choose the date of the data being recorded
since this is not a booking system like that, therefore populate the
date with current date." Recommended and implemented: kept
`QDateEdit(QDate.currentDate())` auto-populated with today's date by
default (already the prior behavior) but **removed
`setCalendarPopup(True)` entirely** — no calendar picker, no popup,
sidestepping the whole `QCalendarWidget` theming problem rather than
continuing to chase it. Left the field editable (not read-only) via
keyboard/segment-spinner, since a physician occasionally needing to
correct the date (e.g. entering metadata for a session recorded the day
before) is a real data-entry need, just not a browse-a-calendar one.

Removed as dead code: the `_theme_calendar_popup()` method and its
`QCalendarWidget` QSS block (unreachable now, no popup exists), plus
the now-unused `configs/assets/icons/chevron-left.png`/
`chevron-right.png` assets generated for the calendar's prev/next-month
buttons that never shipped.

### 13.5 Testing and files changed

Full pytest suite: 116 passed, same single pre-existing failure, no
regressions, throughout every step of this round.

**Files changed:**

- `src/ui/setup_page.py` — `sex_combo.view().setFrameShape(QFrame
  .Shape.NoFrame)`; removed `setCalendarPopup(True)` and the (now-
  deleted) `_theme_calendar_popup()` method entirely; added
  `_missing_requirements()` and wired it into `_on_state_changed()`
  for the Continue-button tooltip; cleaned up now-unused imports
  (`QColor`, `QPalette`, `QTextCharFormat`, `QTableView`, `Qt`,
  `MUTED`, `PANEL_BG`, `STYLESHEET`).
- `src/ui/wtmh_theme.py` — extended `QComboBox QAbstractItemView::item`
  with padding/hover/selected/focus states; added `image:
  url(checkmark.png)` to `QCheckBox::indicator:checked`; removed the
  entire (now-dead) `QCalendarWidget` QSS block.
- `src/ui/dashboard_window.py` — `run_dashboard()` now also sets
  `app.setPalette(QStyleFactory.create("Fusion").standardPalette())`.
- `configs/assets/icons/checkmark.png` — new committed binary asset.
  (`chevron-left.png`/`chevron-right.png` were generated then removed
  again in the same round, per §13.4.)

**Scope note:** none of this round's changes touch `src/app.py`'s
`run_gui()` (the standalone `--task X --gui` launch path) — same
deliberate scope discipline as §12.

**Left uncommitted**, matching this project's established
ask-before-commit pattern — five rounds (§9-§13) now sit uncommitted
together.

## 14. Two leftover styling bugs — Assessment Date sliver and Sex popup black band

Another external codebase-blind critique (same pattern as §11-§13) reported
two remaining Setup-screen bugs, both root-caused against the real source
and confirmed live via qt-mcp before any fix was written, then re-confirmed
fixed with fresh screenshots afterward.

### 14.1 Assessment Date — leftover dropdown/spin-button sliver

**Bug:** a small vertical bar/sliver remained on the right edge of the
Assessment Date field, unlike the clean Subject ID field above it.

**Root cause:** §13.4 removed `setCalendarPopup(True)` but kept `date_edit`
as a `QDateEdit` (deliberately — it still gives free date-section
validation/keyboard editing). `QDateEdit` is a `QAbstractSpinBox`
subclass, so even with the calendar gone it still paints its own native
up/down step buttons on the right edge. `wtmh_theme.py`'s QSS never
targeted `QDateEdit`'s `::up-button`/`::down-button`/arrow subcontrols —
only `QSpinBox`/`QDoubleSpinBox` got themed steppers (S12) — so those
native buttons rendered completely unstyled, which is what read as a bare
sliver. There is no leftover `::drop-down`/`::down-arrow` QSS rule to
remove for this field — the existing rules at that selector have only ever
targeted `QComboBox`, never `QDateEdit` (confirmed by reading
`wtmh_theme.py` directly, not assumed).

**Fix — `src/ui/setup_page.py`, no QSS change:**
```python
self.date_edit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
```
Disables the native steppers outright rather than theming them (unlike the
QSpinBox/QDoubleSpinBox steppers) — the field is meant to read as a plain,
keyboard-editable text box, not a steppable control. Requires importing
`QAbstractSpinBox` from `PySide6.QtWidgets`.

### 14.2 Sex popup — black band around the list

**Bug:** opening the Sex combo box showed a heavy black band/frame
wrapping the top and bottom of an otherwise-clean white popup list.

**Root cause:** §13.2's fix (`sex_combo.view().setFrameShape(QFrame
.Shape.NoFrame)`) removed the frame on the *inner* `QAbstractItemView`
only. That view sits inside a second, outer `QFrame` — Qt's undocumented
`QComboBoxPrivateContainer`, which is the popup's actual top-level window
— and that outer frame draws its own default border completely
independently of the inner view's frame shape. QSS cannot reach it at all
(no selector resolves to this private container). Under Fusion it renders
as the reported heavy black band. This means §13.2's own "how to apply"
note (view-frame-only) was incomplete, not wrong — it fixed the inner
view but left the true source of the border unaddressed.

**Fix — `src/ui/setup_page.py`, no QSS change:**
```python
popup_container = self.sex_combo.view().parentWidget()
if popup_container is not None:
    popup_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    popup_container.setStyleSheet("background: transparent; border: none;")
```
`view().parentWidget()` is the `QComboBoxPrivateContainer` itself.
Disabling its native background/frame painting leaves only the inner
view's existing QSS-drawn white background/1px `#DBE6EC` border/8px
radius (S11/§13.2, unchanged) visible. Requires importing `Qt` from
`PySide6.QtCore` (already imported for other purposes elsewhere in the
file).

**Superseded — this specific fix rendered solid black on real on-screen
compositing; see §15 for the root cause and the actual working fix.**
Kept here as the original record of what shipped in `ef8b771`/`8aac60c`,
not as current guidance.

### 14.3 Why no QSS diff — both fixes are Python-side

The user's prompt asked for a before/after QSS diff for both bugs. There
isn't one: neither bug had a matching, wrong, or leftover QSS rule to
fix. `wtmh_theme.py` is untouched by this round (confirmed via `git diff
--stat` showing zero new hunks there this session). Bug 1 was an
unstyled-and-unstylable native subcontrol (no QSS selector for it existed
before or after); bug 2 was a private native frame QSS structurally
cannot select at all (confirmed by the qt-mcp-tool-reference memory's own
prior finding on this exact class). Both fixes are `setup_page.py` widget
configuration only.

### 14.4 Validation

Live qt-mcp session against the actually-running `DashboardWindow`
(`QT_MCP_PROBE=1 QT_MCP_PORT=9142`, no real Gazepoint device connection
needed — both bugs are static styling, no tracker required):
- **Before:** screenshot of `date_edit` showed the reported sliver;
  screenshot of the opened Sex popup (a separate top-level `QFrame`,
  `qt_list_windows(skip_hidden=False)`) showed the reported heavy black
  band around all four edges.
- **After the fix + a clean process kill/relaunch:** `date_edit`
  screenshot shows a clean field matching Subject ID, no trailing
  artifact; the Sex popup screenshot shows a clean white background with
  a single thin light border, no black anywhere.

Full pytest suite: 116 passed, same single pre-existing failure
(`test_config_merges_task_over_default`, the already-documented
`target_fps` 60-vs-150 stale assertion), no regressions. QA process
killed cleanly afterward (`Get-CimInstance Win32_Process` confirmed no
leftover `*src.main*` process).

**Files changed:** `src/ui/setup_page.py` only (import reorder + new
`QAbstractSpinBox` import; the two fixes above).

**Left uncommitted**, matching this project's established
ask-before-commit pattern — six rounds (§9-§14) now sit uncommitted
together.

## 15. Sex popup fix (§14.2) regressed to solid black — real root cause and fix

After §14 was committed and pushed (`ef8b771`/`8aac60c`), the user shared a
real screenshot of the running app (not a qt-mcp capture) showing the Sex
popup rendering as a **solid black rectangle** — worse than §14.2's
original black band, and a genuine regression from that round's own fix.

### 15.1 Root cause

§14.2's fix set `WA_TranslucentBackground` on the popup's outer container
(`view().parentWidget()`, the `QComboBoxPrivateContainer`) plus a
`background: transparent` stylesheet, intending the desktop compositor to
blend it away so only the inner view's own white background showed
through. **This is a known Qt/Windows quirk:** an alpha-enabled
`Qt::Popup` top-level window does not reliably get proper DWM-composited
alpha blending, and instead of rendering as transparent it renders as
**solid black** on this machine's real on-screen output.

**Why the earlier live qt-mcp validation (§14.4) missed this entirely:**
`qt_screenshot` calls `QWidget.grab()`, which paints the widget tree
directly into an offscreen pixmap by invoking each widget's own paint
logic — it does **not** go through the OS window compositor at all, so a
translucency/compositing-dependent bug is structurally invisible to it.
The grab-based screenshot showed a clean white popup (each widget painted
its own content correctly in isolation); only the real, composited
on-screen window showed black. This is a new, evergreen qt-mcp
limitation, not specific to this bug — recorded in the
`qt-mcp-tool-reference` memory.

### 15.2 Real fix — opaque background, no compositor dependency

Replaced §14.2's translucency-based approach entirely. Instead of trying
to make the outer container invisible via transparency, give it an
ordinary **opaque** background matching the app's own white card color —
this has no dependency on compositing succeeding, so it cannot fail the
same way:

```python
# src/ui/setup_page.py
from .wtmh_theme import BORDER, PANEL_BG
...
self.sex_combo.view().setFrameShape(QFrame.Shape.NoFrame)
popup_container = self.sex_combo.view().parentWidget()
if popup_container is not None:
    popup_container.setStyleSheet(
        f"background: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 8px;"
    )
```

The `WA_TranslucentBackground` attribute call was removed entirely. This
also made the `Qt` import (added in §14.2 solely for that attribute) dead
code — removed from `setup_page.py`'s imports, and `PANEL_BG`/`BORDER`
imported from `wtmh_theme` instead (previously removed as unused in
§13.5, now genuinely needed again).

### 15.3 Validation — a real compositor-level screenshot this time

Given §14.4's validation gap, this round did **not** trust `qt_screenshot`
alone. After relaunching the dashboard and opening the Sex popup via
`qt_click`, a real desktop screenshot was captured independently of
qt-mcp — PowerShell + `System.Drawing.Graphics.CopyFromScreen` over the
full virtual screen bounds, saved to PNG and read directly — to confirm
the actual composited on-screen output, not just the widget tree's own
paint logic. Result: clean white popup, single thin `#DBE6EC` border,
fully readable dark text, no black anywhere, matching the original design
intent from the very first ask in §14.

Full pytest suite: 116 passed, same single pre-existing failure
(`test_config_merges_task_over_default`), no regressions. QA process
killed cleanly afterward, confirmed via `Get-CimInstance Win32_Process`
(no leftover `*src.main*`).

**How to apply:** any future qt-mcp-driven visual verification of a
translucency/compositing-dependent Qt fix (anything using
`WA_TranslucentBackground`, layered windows, or alpha blending) must be
cross-checked with a real screen capture, not `qt_screenshot` alone —
`grab()`-based screenshots cannot detect this entire class of bug.

**Files changed:** `src/ui/setup_page.py` only (swap the §14.2 popup-
container fix for the opaque version above; drop the now-unused `Qt`
import; add `PANEL_BG`/`BORDER` imports from `wtmh_theme`).

**Left uncommitted.**

## 16. Layout space usage, typography hierarchy, and Sex-popup polish

Another external codebase-blind critique covering three areas: unused
vertical space on both Setup and Tasks, a missing page/card typography
scale, and remaining Sex-popup polish beyond §15's black-band fix. Per the
user's explicit instruction, every claim was checked against the real
source and the actually-running dashboard (both `qt_screenshot` and a real
desktop capture, given §15's lesson about the former's blind spot) before
writing this plan — findings below are what was confirmed, not what the
critique assumed.

### 16.1 Confirmed findings

1. **Dead space, confirmed real on both screens** at the ~1500×800 size
   from the critique's own screenshots (reproduced via a real desktop
   capture after resizing the actual window with a `user32.dll`
   `MoveWindow` call, not just `qt_screenshot`). Root cause on both pages:
   `_build_ui()` ends with `outer.addStretch(1)` after the last widget —
   confirmed in `setup_page.py` (after the Continue button) and
   `tasks_page.py` (after the 4th task card). On Tasks specifically, the
   4 cards stack in a single `QVBoxLayout` column, so roughly 40% of a
   1500px-wide window's horizontal space next to the cards is unused too.
2. **Typography hierarchy — confirmed, but not the way the critique
   described it, and differently broken per screen:**
   - *Setup:* all 4 card titles (`"Subject & Session Info"`,
     `"Tracker Connection"`, `"Calibration"`, `"Before You Start"`) are
     plain `QLabel(...)` calls with **no `objectName` set at all** —
     confirmed by reading `setup_page.py` directly (`grep` for
     `QLabel(`/`setObjectName` shows no object name on any of the four).
     They inherit only the base `QWidget#wtmhDashboard QLabel { color:
     INK }` rule — same font size/weight as every other label on the
     page. This is a stronger version of the critique's claim: they don't
     just "roughly match" body text, they're the exact same style.
   - *Tasks:* the opposite problem. `_TaskCard`'s title labels (`"Static
     Click"` etc.) already use `objectName("wtmhSectionTitle")` — **the
     same object name as the page-level title** (`"1 · Setup"`/
     `"2 · Tasks"`, also `wtmhSectionTitle`). Confirmed in
     `wtmh_theme.py`: `QLabel#wtmhSectionTitle { font-size: 18px;
     font-weight: 600; }` is one rule serving both roles today, so page
     and card titles are pixel-identical in size/weight — confirmed
     visually in the real screenshot too (hard to tell "2 · Tasks" apart
     from "Static Click" at a glance).
   - Field labels (`"Subject ID"`, etc., added via `QFormLayout.addRow`)
     and body/description text are already visually subordinate to
     both of the above (default label styling vs. `wtmhMuted`), so no
     change is needed there — the fix is entirely about establishing two
     *new*, distinct tiers above them.
3. **Sex popup polish — 3 of 4 points confirmed, 1 needs correction:**
   - **Confirmed, but on the wrong item:** a real screenshot of a freshly
     opened popup (nothing clicked) shows a bare rectangular outline
     around **"Select" (index 0)**, not "Other / Prefer not to say" (the
     last item) as the critique described. Index 0 is also the combo's
     actual `currentIndex()` (nothing has been chosen yet), so the
     outline *is* landing on "the combo box's actual current value,"
     which is what the user asked for semantically — the real bug is
     that it renders as a bare, unfilled outline with no matching visual
     treatment, not that it's on the wrong row. (The critique's screenshot
     may have been taken with a stale selection or a different mouse
     position; not chasing that further since the actual live behavior is
     the ground truth here.)
   - **Not reproducible as described — already correct:** item padding is
     already `9px 12px` in `wtmh_theme.py` (`QAbstractItemView::item`),
     inside the requested 8-10px range. No "tightly packed" items found
     live. No change planned for this point.
   - **Confirmed already implemented, unaffected by this round:** hover
     state (`::item:hover { background: {SOFT_ACCENT}; }`) already
     exists and matches the ask exactly.
   - **Confirmed, real but minor:** a slight doubled-border look where the
     closed field's own bottom border sits flush against the popup
     container's own top border (from §15's opaque-background fix, which
     gave the container a full 1px border on all 4 sides).

### 16.2 Plan

1. **Tasks — switch to a responsive `QGridLayout`, 2 columns above a
   width threshold, 1 column below it.** Threshold chosen at 700px
   content width (comfortably clears both the default 1024px launch size
   and the ~1500px size in the critique's screenshots, so the common
   cases both get 2 columns) — implemented via a `resizeEvent` override
   on `TasksPage` that reflows the grid only when the column count
   actually changes (not on every resize event). This directly shrinks
   both the used width (cards now share the row) and the used height (2
   rows of 2 instead of 4 rows of 1), which is the most effective lever
   against the reported dead zone.
2. **Setup — no structural change (deliberately, per the "not a
   redesign" instruction and the menu of options offered); moderately
   increase spacing/padding instead** to close some of the gap without
   restructuring: outer layout spacing 14→16px, each card's internal
   `QVBoxLayout` spacing 8→10px, `QFormLayout` vertical spacing stays at
   10px (already reasonable). Combined with the new title `margin-bottom`
   from the typography fix below, this makes the page organically taller
   without changing its single-column, top-aligned structure.
3. **New two-tier title scale**, added to `wtmh_theme.py`:
   - `QLabel#wtmhPageTitle { font-size: 22px; font-weight: 700; }` — new,
     applied to `"1 · Setup"`/`"2 · Tasks"` (both files, replacing their
     current `wtmhSectionTitle` object name).
   - `QLabel#wtmhSectionTitle { font-size: 16px; font-weight: 600;
     margin-bottom: 6px; }` — resized down from 18px (so it's clearly
     subordinate to the new page title) and applied, for the first time,
     to all 4 of Setup's previously-unstyled card titles. The
     `margin-bottom` addition is the "breathing room after the title"
     ask — done once in the shared QSS rule rather than touching every
     card-builder call site individually, so it applies uniformly to
     every card on both screens with a single change.
4. **Sex popup — 2 targeted fixes, 2 points left as-is (already
   correct, see §16.1):**
   - Try `outline: 0;`(equivalent to the existing `outline: none;`) plus
     an explicit `border: 1px solid transparent;` on
     `QAbstractItemView::item:focus`, to give Qt's Fusion-style focus
     rect an explicit transparent color to paint instead of relying on
     `outline` suppression alone. Verified live after the change (a
     stylesheet-only guess is not trusted without a real screenshot,
     given §15's lesson) — see §16.3 for the actual result and any
     follow-up needed if this alone doesn't clear it.
   - Popup container (`setup_page.py`'s direct `setStyleSheet` call on
     `view().parentWidget()`, from §15) gets `border-top: none` added, so
     the field's own existing bottom border is the only line at that
     seam instead of two 1px borders sitting flush — makes it a
     deliberate single divider rather than an accidental double one.

### 16.3 Implementation, testing, and validation

All of §16.2 was implemented as planned, with one correction found only
by testing live (item 4a below) and one mechanism that turned out
different from — but more effective than — what §16.2 predicted (item 1
below). Every visual claim in this section is grounded in a **real
desktop screenshot** (PowerShell + `System.Drawing.Graphics
.CopyFromScreen`), not `qt_screenshot` alone, per §15's own lesson about
that tool's compositing blind spot; `qt_screenshot`/`qt_find_widget` were
still used for locating widgets and driving clicks.

1. **Dead space — eliminated, not just reduced, and by a different
   mechanism than planned.** The spacing/margin increases (outer 14→16,
   card layout 8→10, plus the new title `margin-bottom: 6px`) raised the
   Setup page's *natural minimum content height* from what it was before
   this round to a point that now **exceeds** `dashboard_window.py`'s
   hardcoded `self.resize(1024, 800)` launch call. Confirmed live: two
   separate attempts to force the real OS window back down to 800px tall
   via a `user32.dll` `MoveWindow` call were both silently overridden by
   Qt back up to its content-driven minimum (1008px tall at 1484px
   content width). Practical effect: since Qt always honors the *larger*
   of an explicit `resize()` request and the layout's minimum, the
   window now effectively always opens sized to fit its content exactly
   — there is no longer a way for it to end up larger than its content
   needs (short of a user manually dragging it bigger), which structurally
   forecloses the "large empty area below the last card" bug rather than
   just shrinking it. Confirmed via a real screenshot at the enforced
   1484×1008 size: the Continue button's bottom edge sits right at the
   window's bottom margin, no leftover gray space. `resize(1024, 800)`
   was left as-is in code (harmless — Qt overrides it upward as needed;
   changing the literal wouldn't add anything since the real floor is
   layout-driven, not a fixed number).
2. **Tasks grid — implemented as planned, substantially reduces the gap
   (not fully eliminated, and that's expected).** The 2-column
   `QGridLayout` (`_GRID_BREAKPOINT_PX = 700`) is live in
   `tasks_page.py`, reflowed via `resizeEvent`. Confirmed live at
   1484px width: all 4 cards render as a 2×2 grid, using the
   previously-empty right half of the window. Some empty space remains
   below the grid — expected and disclosed rather than overclaimed:
   Tasks fundamentally has less content than Setup (4 short cards vs. 4
   dense forms/alerts), so even a fully space-efficient 2×2 layout
   doesn't need the same vertical extent Setup's content does. This
   matches the user's own acceptance criterion of "eliminated **or
   substantially reduced**," not a claim of zero remaining space.
3. **Typography — implemented as planned.** `wtmh_theme.py` now has
   `QLabel#wtmhPageTitle` (22px/700) and a resized `QLabel#wtmhSectionTitle`
   (18px→16px/600, plus `margin-bottom: 6px`). `setup_page.py`'s page
   title switched to `wtmhPageTitle`; all 4 of its card titles — which
   had **no object name at all** before this round (see §16.1, a
   stronger gap than the critique described) — now use a new
   `_card_title()` helper that applies `wtmhSectionTitle`. `tasks_page.py`'s
   page title also switched to `wtmhPageTitle` (`_TaskCard`'s own card
   titles already used `wtmhSectionTitle` and needed no change beyond the
   shared rule's new size). Confirmed live: page titles are now clearly
   the largest/boldest element on both screens, and Setup's 4 card titles
   — previously indistinguishable from body text — now read as real
   headings.
4. **Sex popup — 2 fixes landed, 1 needed a different approach than
   planned, 2 confirmed already correct (no change):**
   - **a. Phantom outline on the current item — the QSS-only attempt from
     §16.2 did NOT work, confirmed live** (`outline: 0` + an explicit
     `border: 1px solid transparent` on `::item:focus`: the bare outline
     was still there on "Select" after this change, screenshotted before
     moving on). Root cause confirmed to be Qt's own
     `QStyle::PE_FrameFocusRect` primitive, painted independently of the
     stylesheet-driven item delegate paint — no `::item:focus` QSS
     property can suppress it. **Real fix:**
     `self.sex_combo.view().setFocusPolicy(Qt.FocusPolicy.NoFocus)` in
     `setup_page.py`, which stops the view from ever reporting
     `State_HasFocus` at all. Confirmed live: "Select" (the actual
     current value, index 0) shows no box of any kind on a fresh popup
     open. Arrow-key selection is unaffected — that's driven by
     `QComboBox`'s own key forwarding, independent of the popup view's
     focus policy.
   - **b. Item padding — confirmed still correct, no change** (already
     `9px 12px`, matching §16.1's finding).
   - **c. Hover state — confirmed still correct, no change** (already
     `SOFT_ACCENT` on `::item:hover`, unaffected by this round).
   - **d. Seam at the field/popup boundary — fixed as planned.** The
     popup container's own `setStyleSheet` call (from §15) gained
     `border-top: none`, so only the closed field's own bottom border
     shows at that boundary. Confirmed live: a single clean line, no
     doubled border.
   - **Testing note, disclosed for anyone re-verifying this later:**
     automated verification of "no stray highlight" is entangled with
     exactly where a synthetic `qt_click` leaves the OS mouse cursor —
     a follow-up screenshot after moving the cursor away via
     `SetCursorPos` still showed a pale highlight on whichever row
     happened to be under the *original* click position, because
     `SetCursorPos` alone doesn't reliably deliver the mouse-move events
     Qt needs to update hover state, unlike a real user's natural mouse
     movement. This is judged to be a testing-methodology artifact, not
     an app bug: the fix specifically targeted and resolved the
     bare-outline artifact on the *current-value* item (confirmed gone),
     which is the actual bug reported; a real user moving their mouse
     naturally after opening the popup gets correct hover leave/enter
     behavior, which is unrelated code Qt already handles.

**Full pytest suite: 116 passed, same single pre-existing failure**
(`test_config_merges_task_over_default`), no regressions, run after all
of the above. QA process killed cleanly each round, confirmed via
`Get-CimInstance Win32_Process` (no leftover `*src.main*`).

**Files changed:** `src/ui/setup_page.py` (title helper, card titles,
outer/card spacing, popup container `border-top`, `NoFocus` on the popup
view, `Qt` import restored), `src/ui/tasks_page.py` (`QGridLayout` +
`resizeEvent` reflow, page title, spacing), `src/ui/wtmh_theme.py`
(`wtmhPageTitle`, resized `wtmhSectionTitle`, `::item:focus` tweak — this
last one turned out insufficient alone, kept anyway since it's harmless
and documents the attempt inline).

**Left uncommitted.**

## 17. Tasks grid dead space (§16's own fix) — reversed to vertical space, fixed for real

§16.2's Tasks fix (a 2-column `QGridLayout`) solved the *horizontal*
dead-space problem but left the opposite one: at the ~1500×800 test size,
the grid only occupies roughly the top 40% of the window, leaving a
large uninterrupted empty region below it — reported via another
external critique, and confirmed live (real screenshot) before any
change, per this project's standing discipline.

The Setup screen was cited as the reference for "good" space usage — no
new investigation needed there, since §16.3 already established *why*
Setup fills its window (its natural minimum content height now exceeds
the launch-time `resize()` call, so Qt enforces the larger, content-driven
size). Tasks doesn't have that property: even a fully space-efficient
2×2 grid of 4 short cards has a much smaller natural minimum height than
Setup's dense stack of forms/alerts, so the same mechanism doesn't apply
here — Tasks needed its own, different fix.

### 17.1 Attempt 1 — Expanding size policy + row stretch (tried first, per instruction)

The user explicitly asked this be tried first. Implemented: each
`_TaskCard` given `QSizePolicy.Expanding` (both directions),
`self._grid.setRowStretch(row, 1)` for every row, and the grid given the
outer layout's whole stretch share (`outer.addLayout(self._grid,
stretch=1)`, replacing the trailing `addStretch(1)`).

**Empirically under-delivered — confirmed via `qt_widget_details`, not
just a screenshot impression.** At the test size, `TasksPage`'s own
height was 956px with ~822px genuinely available for the grid after
subtracting title/back-button/margins; each card's `sizeHint` was
164px tall, but the *actual* rendered height was only 202px — barely
more than sizeHint, nowhere close to the ~400px each row should have
gotten from a proportional 50/50 split of ~822px. The precise Qt-internal
reason for this shortfall was not conclusively identified (several
QGridLayout/QBoxLayout stretch-interaction theories were considered);
rather than keep guessing, the approach was abandoned in favor of
something verifiable.

### 17.2 Attempt 2 — explicit computed row heights (rejected: real runaway bug)

Tried an alternative: compute each row's target height directly from
the page's actual height budget in `resizeEvent`, and set it via
`setRowMinimumHeight`. Implemented and relaunched.

**This caused a real, live, confirmed runaway feedback loop.**
`qt_list_windows` immediately after landing on the Tasks screen reported
the window as **1484×524473** — over half a million pixels tall. Root
cause, reasoned through after the fact: raising a row's *minimum* height
raises the page's own required minimum size; per §16.3's own finding,
this app's window now auto-grows to match its content's minimum size
whenever that minimum exceeds the current window size. So: computing a
row height from "currently available space" → calling
`setRowMinimumHeight` → growing the page's required minimum →
the window growing to match (§16's mechanism) → firing another
`resizeEvent` with a *larger* height → computing an even larger row
height → forever. The process was killed immediately
(`Stop-Process`, confirmed via `Get-CimInstance Win32_Process` afterward
that nothing was left running) before it could do anything worse than
consume memory/CPU on a garbage layout computation. **This combination —
computing a size from available space and feeding it into any widget's
*minimum* size, in an app where the window itself auto-sizes to content
minimums — is a feedback loop by construction, not a one-off bug in this
one spot.** Reverted entirely; `setRowMinimumHeight`/the `resizeEvent`-
driven computation were removed, along with the row-stretch calls and
the `Expanding` size policy from attempt 1 (no longer needed for the
approach that replaced them).

### 17.3 Real fix — vertically center the grid block (the user's own sanctioned fallback)

The user's own prompt explicitly offered this as the fallback if
expanding looked awkward or didn't pan out: "consider vertically
centering the 2×2 grid block within the available window space rather
than anchoring it to the top." Implemented in `tasks_page.py`:

```python
self._outer.addStretch(1)
self._outer.addLayout(self._grid)
self._outer.addStretch(1)
```

Title and back button stay pinned at the top (unchanged); only the grid
block itself centers in the remaining space below them. This is safe by
construction against the class of bug in §17.2: `addStretch()` only ever
consumes *leftover* space that already exists — it cannot raise any
widget's minimum size, so it cannot feed back into §16's
window-auto-sizing mechanism the way `setRowMinimumHeight` did.

**Validated live, cautiously** (process re-checked for runaway growth
after every resize this round, not just after launch): at the ~1500×800
test size, the grid sits centered with a moderate, roughly-even gap
above and below it — no single large uninterrupted empty region, matching
the user's acceptance criterion ("space should be distributed
proportionally"). The existing 2-column/1-column responsive breakpoint
(§16, `_GRID_BREAKPOINT_PX = 700`) was re-verified unaffected: narrowing
the real window to 634px live-reflowed to a single stacked column
correctly, confirmed via a real screenshot, with no runaway growth at
any point during the resize.

Per the user's own framing ("try Expanding first... pick whichever looks
better... show me both if it's a close call"): this wasn't a close call
between two working options — Expanding under-delivered and its
more-aggressive variant was actively dangerous, so centering is the only
approach carried forward, not a stylistic pick between two viable ones.

Full pytest suite: 116 passed, same single pre-existing failure, no
regressions. QA process killed cleanly, confirmed via
`Get-CimInstance Win32_Process` (no leftover `*src.main*`, and
specifically no leftover runaway-sized window either).

**Files changed:** `src/ui/tasks_page.py` only (`_TaskCard`'s size
policy reverted to default; `_build_ui`/`_reflow_grid` rewritten;
`_resize_grid_rows` and its `resizeEvent` call removed entirely — the
whole attempt-2 code path no longer exists in any form).

**Left uncommitted.**

## 18. Tasks grid dead space (§17's own fix) reported again — root cause was two bugs, not one

**New process rule adopted this round, applies to every future qt-mcp
validation in this project:** the target window is now maximized
(`qt_invoke_slot(window_ref, "showMaximized")`) *before* any
layout/spacing validation screenshot. §17's own centering fix was
apparently validated at a smaller test size (~1500×800) where the
problem read as "a moderate, roughly-even gap" — at a real maximized
1920×1009 window the same centered grid left large, clearly dead bands
above and below the card block. Testing at real usage size going
forward should prevent this class of miss recurring.

### 18.1 Validated the report first

Launched the dashboard live, maximized, navigated to Tasks via qt-mcp.
Confirmed: at 1920×1009, §17's `addStretch`/grid/`addStretch` centering
left large near-symmetric empty bands above *and* below the card block
(the report's "~60% dead space... below the grid" framing was right in
substance, if not in exact geometry — §17's own mechanism splits it
top/bottom rather than concentrating it below). The Setup screen at the
same size, by contrast, filled the full window height with its stacked
cards, `Continue to Tasks →` reaching near the very bottom. Claim
confirmed true before writing any code.

### 18.2 Attempt 1 — Expanding size policy (tried first, per instruction), and the real reason it under-delivers

Gave `_TaskCard` a `QSizePolicy(Preferred, Expanding)`, gave the grid
layout item itself `stretch=1` where added to the outer `QVBoxLayout`
(`outer.addLayout(self._grid, stretch=1)` — §17.1's account had reported
trying "Expanding size policy + `setRowStretch`" without this piece),
and set `QGridLayout.setRowStretch()` on the active card rows.

Root-caused, via an offscreen diagnostic script (`QT_QPA_PLATFORM=
offscreen`, constructing `TasksPage()` directly and reading
`QGridLayout.cellRect()`/`rowStretch()`/`rowCount()` after a resize —
much faster than relaunching the live GUI per iteration), **why this
still under-delivered**: `QGridLayout.rowCount()` never shrinks once a
row index has been used. The 1-column reflow (4 rows) runs first at
construction (before the window reaches its real maximized width), so
rows 0-3 all get `stretch=1`; switching to the 2-column reflow (2 rows)
removes the widgets from rows 2-3 via `takeAt()` but does **not** reset
their stretch — those "ghost rows" kept `stretch=1` and silently split
the surplus space 4 ways instead of 2, so the real rows only ever got
about half of what they should have. This is very likely the same
mechanism §17.1 hit and described as "under-delivered... root cause not
conclusively identified" — the diagnostic script here is the first time
it was actually pinned down with numbers rather than inferred from a
screenshot.

Fixed by explicitly zeroing stretch on every row up to the
widest-ever-used index (`2 * len(self._cards)`) on every reflow, not
just the rows currently in use. Confirmed via the same diagnostic
script: cards grew from a 164px `sizeHint` to a genuine ~419px, filling
the grid's full allocated rectangle with no leftover gap inside it.

### 18.3 Attempt 1, continued — rejected live despite fixing the math, exactly as the prompt warned it might

With the ghost-row bug fixed, a live qt-mcp screenshot (maximized) showed
the fully-Expanding cards looked awkward: `_TaskCard`'s own
`QVBoxLayout` has no `addStretch()` call, so Qt distributed each
stretched card's ~250px of surplus height as three separate large gaps
*between* its title, description, status row, and buttons — not as one
trailing margin below the content. This is precisely the risk the
prompt itself flagged ("if expanding the cards themselves looks awkward
with sparse content..."). Confirmed live, reverted — `_TaskCard`'s size
policy is back to the framework default (`Preferred`/`Preferred`).

### 18.4 Attempt 2 — spacer rows around and between the grid rows (the prompt's offered fallback), implemented

Redesigned `TasksPage._reflow_grid` to place cards on **odd** grid row
indices (1, 3, 5, ...) and use the **even** indices (0, 2, 4, ...) as
widget-free spacer rows, each given equal `stretch=1`:

```python
n_card_rows = -(-len(self._cards) // columns)  # ceil division
total_rows = 2 * n_card_rows + 1  # spacer, card, spacer, card, ..., spacer

max_total_rows = 2 * len(self._cards) + 1
for row in range(max_total_rows):
    is_spacer_row = row % 2 == 0
    self._grid.setRowStretch(row, 1 if (is_spacer_row and row < total_rows) else 0)

for i, card in enumerate(self._cards.values()):
    card_row, col = divmod(i, columns)
    self._grid.addWidget(card, 2 * card_row + 1, col)
```

This distributes 100% of the leftover space the outer layout hands the
grid (`stretch=1`, kept from §18.2) as N+1 equal bands — above the
first card row, between each pair of card rows, and below the last —
while every card keeps its exact natural, content-driven size (correct
height-for-width text wrapping at its real column width too, unlike the
isolated `sizeHint()` a card reports before being placed). The same
ghost-row-stretch reset from §18.2 still runs on every reflow, now
covering both row parity and the widest-ever-used row count.

**Live qt-mcp validation, maximized (1920×1009):** cards render with
unchanged internal proportions, matching their pre-§18 look exactly;
the leftover space appears as three roughly-even ~170px bands around
and between the two card rows instead of one large dead zone at the
bottom; no single uninterrupted empty region remains anywhere in the
window.

**1-column responsive breakpoint re-verified** — via the same offscreen
diagnostic script at a 600×900 resize (a live qt-mcp resize of a
top-level `QMainWindow` via `qt_set_property(ref, "geometry", "x,y,w,h")`
did **not** actually resize the real window this session — worth noting
as a qt-mcp limitation; the offscreen script was the reliable way to
check a specific narrow width instead): 4 card rows + 5 spacer rows, all
evenly distributed, no dead zone, `_GRID_BREAKPOINT_PX = 700` unaffected.

### 18.5 Testing and scope

Full pytest suite: 116 passed, the same single pre-existing failure only
(`test_config_merges_task_over_default`, the already-documented
unrelated stale `target_fps` assertion), no regressions at any point
across both attempts. No functional/behavioral code touched — only
`src/ui/tasks_page.py`'s layout geometry (`_TaskCard.__init__`'s size
policy line added then removed again; `_build_ui`'s grid-construction
comment and `stretch=1` argument; `_reflow_grid` rewritten). Run/
Settings/Analyze buttons, status pills, run-count labels, and the
2-col/1-col breakpoint decision itself are all unchanged in behavior,
only in the resulting vertical spacing. No QA session ever reached a
running task (all validation stayed on the Tasks landing screen), so no
scratch session directories were created this round.

**Files changed:** `src/ui/tasks_page.py` only.

**Left uncommitted**, matching this project's established
ask-before-commit pattern — nothing from §18 is on `origin/main` yet
(last commit remains `4aa6a51`, per §17's own commit-status entry).

## 19. Reverted the Tasks grid entirely — single-column stack, matching Setup

**§16-§18 are now historical record only** — everything below describes
the *current* Tasks screen; §16's responsive grid, §17's centering fix,
and §18's ghost-row-stretch fix + spacer-row fallback no longer exist in
the code. This section supersedes them by explicit user decision, not
because anything in them was wrong on its own terms.

**Trigger:** the user reconsidered the whole grid-based direction
("on second thought I think in UI 2 instead of grid, a single-column
stacked layout is preferred") and asked to revert the Tasks screen from
the 2×2 `QGridLayout` back to a single-column `QVBoxLayout` stack,
matching the pattern already used on the Setup screen — explicitly
choosing to stop fixing the grid's empty-space problem rather than
continue iterating on it.

### 19.1 Implementation

In `src/ui/tasks_page.py`:

- Removed `_GRID_BREAKPOINT_PX`, the `QGridLayout` import, the
  `QResizeEvent` import, `_grid_columns` state, `_reflow_grid()`, and
  the `resizeEvent()` override entirely — no grid/breakpoint logic
  remains anywhere in the file.
- `TasksPage._build_ui()` now iterates `TASK_REGISTRY`, constructs each
  `_TaskCard`, and calls `self._outer.addWidget(card)` directly (same
  outer `QVBoxLayout`, same margins `(24, 20, 24, 20)` and spacing `16`
  it already had), followed by one trailing `self._outer.addStretch(1)`
  — the identical shape as `SetupPage._build_ui()`'s own card stack
  (`setup_page.py`: `outer.addWidget(card)` ×4, then the Continue
  button, then `outer.addStretch(1)`).
- `_TaskCard`'s internal content (title, description, status pill,
  run-count label, Run/Settings/Analyze buttons) was untouched —
  confirmed via diff, this was a layout-container-only change as
  instructed.

### 19.2 Validation

Live-validated via qt-mcp, maximized (the standing practice adopted in
§18): at 1920×1009, the 4 stacked cards render top-to-bottom with
clean, unchanged internal proportions, filling roughly the top 3/4 of
the available height with one plain trailing margin below the last card
(`Scanning Search`) — no large or awkward empty region, no gaps inside
any card, no split top/middle/bottom bands the way the grid attempts
left.

This is a smaller fill ratio than Setup's own stack — Setup's cards are
form-heavy enough to reach almost to the bottom on natural content
alone, while the 4 task cards are shorter, so a real ~200px margin
remains below the stack even with the identical pattern reused. That
margin is a single, unremarkable trailing gap, though, not the "large
uninterrupted empty region" §16-§18's whole line of work was about, and
matches what was actually asked for this round: reuse Setup's approach,
not chase pixel-perfect parity with it.

Full pytest suite: 116 passed, the same single pre-existing failure
only (`test_config_merges_task_over_default`, the already-documented
unrelated stale `target_fps` assertion), no regressions. No functional/
behavioral code touched beyond the layout container swap — Run/
Settings/Analyze buttons, status pills, and run-count labels are all
confirmed unchanged in behavior (`_TaskCard` itself, `set_task_status`,
`set_task_run_number`, `set_all_runs_enabled` are byte-identical to
before; only `TasksPage._build_ui`'s layout construction changed). No
QA session reached a running task; no scratch session directories were
created.

**Files changed:** `src/ui/tasks_page.py` only.

**Left uncommitted**, matching this project's established
ask-before-commit pattern — nothing from §16 through §19 is on
`origin/main` yet (last commit remains `4aa6a51`).

## 20. Calibration crash bug — stale local-state port + an unhandled socket exception

User feedback via `/sparc:orchestrator`: "when I do calibration it didn't
show any calibration window from gazepoint." Two clarifying questions
first (Gazepoint Control's location relative to what was being watched,
and what the Calibration card actually displayed) ruled out the
two-PC/remote-display explanation early: Gazepoint Control and the
dashboard are on the same machine/screen, the Tracker Connection card
said "Connected.", and the Calibration card was stuck on "Calibrating…"
indefinitely.

### 20.1 Reproduced live before touching any code

Launched `python -m src.main --dashboard` with the qt-mcp probe against
the real device. `qt_find_widget`/`qt_click` through Connect (→
"Connected.") then Do Calibration reproduced the exact stuck state — the
alert label stayed `"Calibrating…"` for 35+ seconds, well past the
internal ~15s poll timeout `Calibration._poll_for_result` should have
hit. Checking `qt_list_windows` afterward returned a probe connection
error, and no `python.exe` process for `src.main` remained at all — the
whole dashboard process had actually died, not just hung. The launch
log's stderr had the real cause:

```
Error calling Python override of QThread::run(): Traceback (most recent call last):
  File ".../src/ui/setup_page.py", line 85, in run
    self.finished_ok.emit(calibration.run())
  File ".../src/engine/calibration.py", line 227, in run
    sock.sendall(f'<SET ID="CALIBRATE_SHOW" STATE="{show_state}" />\r\n'.encode("ascii"))
ConnectionAbortedError: [WinError 10053] An established connection was aborted by the software in your host machine
```

### 20.2 Root cause #1 — stale per-machine local state pointed at the wrong port

`configs/local_state.json` (gitignored, `src/engine/local_state.py`,
§3.1.3's own per-machine host/port design) held `"port": 4243` — a
leftover from an earlier QA round (§11.6) that deliberately ran
`tools/fake_gazepoint_server.py` on 4243 because the real Gazepoint
Control app was already bound to port 4242 on this same machine.
`ipconfig` confirmed `26.113.49.235` (the "real device" host from
[[peds-eye-gaze-assessment-config-skip-worktree-2026-09-03]]) is this
machine's own Radmin-VPN adapter address, not a separate physical
machine — so the two-PC theory was never in play here. `netstat -ano`
plus `Get-CimInstance Win32_Process` confirmed the real Gazepoint
Control process (`Gazepoint.exe`) is listening on **both** 4242 and
4243. Port 4243 completes a TCP handshake (so `SetupPage`'s "Connected."
status is not lying, exactly) but doesn't speak the real OpenGaze
command protocol — sending a real command (`CALIBRATE_SHOW`) gets the
connection aborted from the far end.

**Fix:** corrected `configs/local_state.json`'s `port` back to `4242`.
This is a local data-only fix (the file is gitignored, per its own
design as a convenience the app doesn't depend on as a source of truth)
— not a commit.

### 20.3 Root cause #2 — the actual crash: an unhandled `OSError` in `Calibration.run()`

Independent of the wrong port, this is a real code gap: `Calibration
.run()` (`src/engine/calibration.py`) wrapped none of its `sock.sendall
()` calls (CALIBRATE_DELAY/TIMEOUT, `_configure_points`, CALIBRATE_SHOW,
CALIBRATE_START) in a `try/except`, unlike `_poll_for_result`, which
already catches `OSError` on `recv()` and returns gracefully. When the
socket aborted, the `OSError` propagated out of `Calibration.run()`,
out of `_CalibrationThread.run()` (`src/ui/setup_page.py`) uncaught,
and PySide6 treated it as fatal to the whole process (confirmed live:
the entire dashboard process died, not just the QThread) — the "stuck
on Calibrating…" the user saw was Windows holding the last-painted
frame of the dying window on screen, not a live hang.

**Fix:** wrapped the `sendall` block in `Calibration.run()` in a
`try/except OSError`, returning `CalibrationResult(n_points=self
.n_points, mean_error_px=None, valid=False)` on failure — the same
"unmeasured" contract `_poll_for_result` already uses on its own
`OSError`. This means any future device hiccup mid-calibration (not
just this specific wrong-port scenario) degrades to the dashboard's
existing "Calibration did not produce a valid result" error path
instead of crashing the whole app.

### 20.4 Re-validated live after both fixes

Killed the crashed process, relaunched fresh with the qt-mcp probe.
`qt_find_widget` on the Control Port spin box confirmed `4242` (no
longer `4243`). Repeated Connect → "Connected." → Do Calibration. A
**real desktop screenshot** (PowerShell + `System.Drawing.Graphics
.CopyFromScreen`, not qt-mcp's `grab()`-based `qt_screenshot` — the
same compositor-blind-spot precedent as §15) confirmed Gazepoint
Control's actual on-screen calibration overlay appeared: a real
10-point animated calibration screen with "LEFT/RIGHT eye: Insufficient
valid points (0), minimum required is 4" — the already-documented
vendor floor from
[[peds-eye-gaze-assessment-physician-feedback-2026-09-02]], expected
here since no human eye was present for this automated test, not a new
bug. Dismissed the overlay with Escape; the dashboard correctly resumed
and reported "Calibration did not produce a valid result. Try again or
adjust point count." — no crash, no hang. Confirmed no orphan process
remained afterward.

Full pytest suite: 116 passed, the same single pre-existing failure
only (`test_config_merges_task_over_default`, the already-documented
`target_fps` 60-vs-150 stale assertion), no regressions.

**Files changed:** `src/engine/calibration.py` (the `try/except` fix).
`configs/local_state.json` also changed but is gitignored/local-only —
not part of any commit.

**Left uncommitted**, matching this project's established
ask-before-commit pattern.

## 21. Dev-testing workflow follow-on — two real bugs in `tools/fake_gazepoint_server.py` itself

Follow-on from §20: since a real human calibration always fails without
a subject actually looking at the screen (the same vendor floor as
§20.4), the user asked how to test the dashboard's Tasks screen/flow at
all. Answer: `tools/fake_gazepoint_server.py` already exists for exactly
this (built for [[peds-eye-gaze-assessment-physician-feedback-2026-09-02]]
item 7, reused once already in S11.6) — a minimal OpenGaze-protocol stub
that always answers `CALIBRATE_RESULT_SUMMARY` with a fixed, valid
result. Live-validated the intended procedure end-to-end via qt-mcp
before handing it to the user: `python tools/fake_gazepoint_server.py
4243` (port 4243, not 4242, for the same reason as §20 — Gazepoint
Control already owns 4242 on this machine) → dashboard's Control Address/
Port set to `127.0.0.1`/`4243` → Connect → Do Calibration (immediately
valid) → Continue to Tasks → real "2 · Tasks" screen reached. Recorded as
[[peds-eye-gaze-assessment-dashboard-testing-without-subject-2026-09-09]].

**Two real bugs then surfaced in the tool itself, both found from the
user's own hands-on use, not assumed:**

### 21.1 "Nothing printed, terminal froze" — bare `python` wasn't the venv

User ran `python tools/fake_gazepoint_server.py 4243` and saw zero
output at all. Confirmed via a clarifying question this wasn't the
expected "prints once, then blocks" behavior — genuinely nothing
printed. Root-caused by checking what bare `python` actually resolves
to on this machine (`where python`, `python --version` in Bash,
PowerShell, and `cmd /c`, all three shells): a `pyenv-win` shim with no
global version configured, which errors immediately with "No global/
local python version has been set yet" in this session's own shells —
plausible that the user's real interactive terminal instead fell
through to the Windows Store's `python.exe` stub (also on `where
python`'s output), which is well known to silently do nothing rather
than error. Either way, the fix is the same: **use the project's own
venv interpreter explicitly** rather than relying on what `python`
resolves to. Also hardened the script defensively regardless of the
exact cause: every `print()` in `tools/fake_gazepoint_server.py` now
passes `flush=True`, so the "listening on…" message can never be
silently delayed by output buffering once the correct interpreter is
actually used.

### 21.2 Ctrl+C didn't stop it — a real, confirmed Windows blocking-socket bug

User then activated the venv correctly (prompt showed `(.venv) PS
...>`), got the "listening on 127.0.0.1:4243 (Ctrl+C to stop)" message
immediately (confirming §21.1's fix worked), but reported being unable
to stop the server with Ctrl+C. Root cause, found by reading `main()`
before assuming anything: `listener.accept()` was called with **no
timeout**, blocking indefinitely. On Windows, CPython only services a
pending `KeyboardInterrupt` between bytecode instructions — a thread
blocked inside a C-level blocking socket call doesn't return control to
the interpreter until that call itself returns, which for `accept()`
with nothing ever connecting is never. This is the identical class of
bug this codebase already works around elsewhere (`GazepointClient
._run_socket`'s `recv()` loop and `Calibration._poll_for_result`'s
`recv()` loop both already use a short socket timeout specifically so a
blocking call can't starve signal handling / stop-event checks — this
script's own `handle_client` even already used this pattern for its
per-client socket, just not for the top-level listener).

**Fix:** `listener.settimeout(0.5)` before the accept loop, with the
loop catching `TimeoutError` and continuing — the interpreter now gets
control back (and can service a pending Ctrl+C) at least every 0.5s
even with no client ever connecting. Added a `"[fake-server] stopping"`
message on the `KeyboardInterrupt` path so a successful Ctrl+C is
visibly confirmed, not just silent.

**Validated:** launched the fixed script directly, confirmed the
"listening…" message printed immediately (§21.1's fix holding), then
connected a real client via a scratch script sending `<GET
ID="CALIBRATE_RESULT_SUMMARY" />` and confirmed the expected `<ACK ...
AVE_ERROR="8.42" VALID_POINTS="5" />` reply still came back correctly —
i.e. the new accept-timeout loop causes no regression in normal client
handling. (Testing the Ctrl+C path itself end-to-end needs a real
interactive console session sending an actual `CTRL_C_EVENT`, which
this automated environment can't faithfully reproduce — the fix is the
established, already-precedented pattern used elsewhere in this exact
codebase for exactly this Windows limitation, and the surrounding
behavior was confirmed unaffected.) Full pytest suite: 116 passed, same
single pre-existing failure only, no regressions (this tool has no
pytest coverage of its own — a standalone dev script, not part of the
app).

**Files changed:** `tools/fake_gazepoint_server.py` only (the `flush=
True` prints from §21.1 plus the `settimeout`/`TimeoutError` loop from
§21.2). **Left uncommitted**, alongside §20's `src/engine/
calibration.py` fix — same ask-before-commit pattern.

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

- **2026-09-08, later still — `/spec-memory-audit` run (clean, no fixes
  needed), then committed and pushed.** Audit checked: Log chronology
  (correct), all `[[cross-links]]` in the two new memory files (resolve
  both directions), `MEMORY.md` index lines (match), and every artifact
  this SPEC/memory claims exists (`docs/wireframes/*.md`/`*.html`,
  `.claude/skills/wireframe/`, `resources/styling/wiremd/package.json`
  version, the README sections) — all verified present. `docs/specs/
  SPEC-ui-setup-task-selection.md` and `docs/wireframes/` (6 files)
  committed as `1404fde` ("Add SPEC and wiremd wireframes for the
  Setup/Task-selection dashboard") and pushed to `origin/main`
  (`0da595b..1404fde`). `git status` clean after push. Note: the
  `.claude/skills/wireframe/` install and `resources/styling/wiremd/` build
  live in the top-level workspace, which is **not** a git repo (per the
  top-level `README.md`) — only this SPEC and the wireframe files, both
  inside `dev/peds-eye-gaze-assessment`, were committed.

- **2026-09-08, later still — wireframe restyled to WTMH Clinical Teal +
  logo placed (§9).** Two scope mismatches between the user's prompt and
  the repo were found and resolved via `AskUserQuestion` before any file
  was touched (see §9's opening paragraph): the target surface is this
  SPEC's wireframe, not the currently-implemented dark-HUD `OperatorPanel`
  (which has no cream/maroon theme and no Setup screen to restyle); and
  "Start session"/"Check drift" don't match any existing button, resolved
  by mapping "Start session" onto "Continue to Tasks →" (promoted to a
  primary button) and skipping "Check drift" (no such element exists).
  Copied `wtmh_logo.png`/`WTMH.ico` into the repo at `configs/assets/
  branding/`; placed the logo top-left of the shared titlebar (`_nav.md`)
  and the `.ico` as the page favicon (documented as `setWindowIcon()`'s
  real-app equivalent). Built `tools/apply_wtmh_wireframe_theme.py` — a
  reusable post-render retint pass, since wiremd's styles are fixed CSS
  presets with no custom-palette mechanism — mapping every prompt-given
  hex onto the actual CSS selectors in wiremd's "clean" style output,
  including a disclosed semantic call (inactive Tracker/Calibration badges
  recolored neutral gray rather than red/amber, matching the user's own
  stated intent, with the kept danger red reserved on a new unused
  `.wmd-badge-danger` class for a real future alarm state). Caught and
  fixed one real bug via Playwright screenshot (not just CSS review):
  dropping `_nav.md`'s `:eye:` icon changed the title's wiremd node type
  from `.wmd-nav-item` to `.wmd-brand`, which has no color rule of its own
  and went unreadable against the newly-dark titlebar until fixed. Full
  palette-token table, button-label mapping, and the wiremd alert/icon
  limitations found along the way are recorded in §9. Verified live via
  Playwright full-page screenshots of both `setup.html` and `tasks.html`.
  **Left uncommitted**, same ask-before-commit pattern as the rest of this
  SPEC's history.

- **2026-09-08, later still — implemented in PySide6 and live-validated
  (§10), via `/sparc:orchestrator`.** User: "proceed to the implementation
  of the UI in Qt based on the wireframe." Split `AssessmentApp`/
  `MainWindow` so a task run can embed into an existing window with a
  reused `GazepointClient`/calibration instead of always owning both
  (§3.1.7's design finally implemented, not just decided); built
  `DashboardWindow`+`SetupPage`+`TasksPage`; added a general same-day
  re-run collision fix (`next_session_id`, applied to `--task ... --gui`
  too, not just the dashboard); added `assessment_date`/`sex` to
  `SessionMetadata` for §4's finalized fields. Live-validated end-to-end
  via `qt-mcp` against `tools/fake_gazepoint_server.py` (connect,
  calibrate, gate, embed-in-place run, clean end-and-return, a same-day
  re-run). Two real bugs were caught by that live run (not by code review)
  and fixed: an `on_finished` callback argument mismatch that froze the
  embedded task on "End task", and an invisible `QCheckBox` label caused
  by the OS's dark-mode default text color. Full pytest suite: 113 passed,
  same single pre-existing failure, no regressions; added 6 new tests for
  the two new Qt-free helpers. Full account, file list, and the "how to
  apply" notes for both bugs are in §10. **Left uncommitted**, same
  ask-before-commit pattern as the rest of this SPEC's history.

- **2026-09-08, later still — styling-pass feedback round, design/
  evaluation only (§11), via `/sparc:orchestrator`.** The user ran a
  separate codebase-blind Claude session against a screenshot of the
  running dashboard and got back a 6-point styling critique (reproduced
  verbatim in §11.1), and separately found two bugs of their own while
  testing (§11.2: a white-on-white Sex dropdown, and no run-number
  indicator on the Tasks screen). Evaluated every critique point against
  the real source (`wtmh_theme.py`, `setup_page.py`, `tasks_page.py`,
  `task_settings_dialog.py`, `dashboard_window.py`, `session_naming.py`)
  rather than trusting either the critique or memory — found the modal-
  theming and status-pill points fully confirmed, the button-hierarchy and
  banner-vs-CTA points already partially implemented (critique was
  screenshot-derived and read a disabled-button state as a styling defect
  in one case), the spacing point overstated in one half and confirmed in
  the other, and root-caused both of the user's own findings (§11.3).
  Asked three `AskUserQuestion` clarifications on real forks the critique
  and findings raised (button-hierarchy pattern, Error-status scope,
  run-indicator data source) — user picked the recommended option on all
  three (§11.4). Recorded a concrete implementation plan (§11.5). **No
  code written this session**, per the user's explicit instruction —
  this SPEC is now ready for an implementation session to pick up §11.5.

- **2026-09-08, later still — §11.5's plan implemented and live-validated
  (§11.6), via `/sparc:orchestrator`.** User: "Proceed with implementing
  the §11.5 plan." Every planned change landed: `TaskSettingsDialog`
  themed (the headline fix — white bordered card, drop shadow, primary/
  ghost buttons, themed slider/spinbox controls); the `QComboBox
  QAbstractItemView` popup rule fixing the white-on-white Sex dropdown;
  custom chevron/steppers/checkbox indicator/slider styling; info/warning
  banner differentiation; a `wtmhSecondary:disabled` rule; the Running
  and Error status-pill branches wired into `_TaskCard.set_status()`; a
  run-count label sourced from a new `next_run_number()` helper extracted
  out of `session_naming.py`; and `QFormLayout.setVerticalSpacing()` /
  card-spacing parity fixes. Full pytest suite: 116 passed, the same
  single pre-existing failure, no regressions; 3 new tests added.
  Live-validated end-to-end via `qt-mcp` against `tools/
  fake_gazepoint_server.py` on a non-default port (4243, since the real
  Gazepoint Control application was already bound to 4242 on this
  machine) — confirmed the disabled/enabled "Do Calibration" contrast,
  the amber-vs-teal info/warning banner split, the Sex dropdown's popup
  rendering readable dark-on-white text, and a full connect → calibrate →
  gate → run → "Running" → "Complete"/"Run 1" → re-run → "Complete"/
  "Run 2" flow. Found and documented a new, evergreen qt-mcp limitation:
  a `.exec()`-based modal (`TaskSettingsDialog`'s real trigger) wedges
  the qt-mcp probe when clicked, requiring a throwaway `.show()`-based
  scratch script for visual QA instead (testing-only workaround, not an
  app change) — recorded in §11.6 for any future modal-dialog QA in this
  app. All scratch QA session directories and processes were cleaned up
  afterward. Full account, file list, and both live-validation write-ups
  are in §11.6. **Left uncommitted**, same ask-before-commit pattern as
  the rest of this SPEC's history.

- **2026-09-08, later still — arrow-rendering regression found and fixed
  (§12), via `/sparc:orchestrator`.** Another external codebase-blind
  Claude critique, this time against a screenshot of the just-updated GUI,
  reported §11's new custom QComboBox/QSpinBox arrows rendering as
  malformed slivers/a squashed dash rather than clean carets/chevron.
  Confirmed accurate — §11.6's own live validation had these controls too
  small to properly assess and said so at the time, without actually
  zooming in. Root-caused in two layers: first, missing
  `subcontrol-origin`/`subcontrol-position` on the arrow subcontrols
  (fixed, but a further pixel-level zoomed diagnostic — grabbing the
  widgets as `QPixmap`s and upscaling 8x nearest-neighbor — revealed the
  deeper issue: the CSS "zero-size box + border" triangle trick renders as
  a solid filled rectangle, not a triangle, for these subcontrols in this
  Qt/PySide6 build, under both the app's default "windowsvista" style and
  "Fusion" (tried via an `AskUserQuestion`-approved `QApplication
  .setStyle("Fusion")` in `run_dashboard()` — user picked this over
  continuing to iterate on QSS-only workarounds, though it turned out not
  to be sufficient alone). Real fix: three real PNG triangle assets
  (`configs/assets/icons/chevron-down.png`/`spin-up.png`/`spin-down.png`,
  generated once via a scratch `QPainter` script) referenced via QSS
  `image: url(...)` instead of CSS borders — re-verified via the same
  pixel-zoom diagnostic (clean triangles this time) and directly in the
  real running dashboard via qt-mcp. Full pytest suite: 116 passed, same
  single pre-existing failure, no regressions. Full account, root-cause
  narrative, and file list are in §12. **Left uncommitted** — four rounds
  (§9-§12) now sit uncommitted together.

- **2026-09-08, later still — combobox popup regression fixed, checkbox
  checkmark added, a real functional bug root-caused as a UX gap, and the
  calendar popup replaced by a product decision (§13), via
  `/sparc:orchestrator`.** Another external codebase-blind critique
  reported three remaining gaps (calendar unthemed, combobox popup
  regressed to a heavy black border, checkbox missing a checkmark); the
  user separately reported "after load calibration when I click continue
  task button, I cant press it." Root-caused the bug first: `can_continue()`
  has always required a connected tracker independently of where
  calibration came from (verified via a scratch script exercising the real
  `_on_load_calibration_clicked` code path with only `QFileDialog
  .getOpenFileName` monkeypatched) — not a code defect, a missing UI
  explanation, fixed with a live-updating tooltip on the disabled Continue
  button (§13.1). Root-caused the combobox regression to Qt's undocumented
  `QComboBoxPrivateContainer` popup frame drawing its own native border
  independently of the QSS-styled `QAbstractItemView` inside it, invisible
  under §11's native style but exposed by §12's Fusion switch — fixed via
  `sex_combo.view().setFrameShape(QFrame.Shape.NoFrame)` plus extended
  item padding/hover/selected QSS (§13.2). Fixed the checkbox with a real
  checkmark PNG asset, same reasoning as §12's arrow-icon fix (§13.3).
  Investigating the calendar popup surfaced a session-wide root cause —
  `QApplication`'s default Fusion palette is dark on this machine because
  Windows dark mode gets auto-inherited by Qt6 — fixed generally via
  `app.setPalette(QStyleFactory.create("Fusion").standardPalette())`: but
  mid-investigation the user reconsidered the underlying requirement
  entirely ("didn't make sense for a physician to choose the date... not a
  booking system") and asked for a recommendation; recommended and
  implemented removing `setCalendarPopup(True)` altogether, keeping the
  field auto-populated with today's date and still keyboard-editable,
  sidestepping the whole `QCalendarWidget` theming problem rather than
  continuing to chase it (§13.4). Full pytest suite: 116 passed, same
  single pre-existing failure, no regressions, at every step. Full
  account, root-cause narratives, and file list are in §13. **Left
  uncommitted** — five rounds (§9-§13) now sit uncommitted together.

- **2026-09-08, later still — two leftover styling bugs fixed (§14), via
  `/sparc:orchestrator`.** Another external codebase-blind critique
  reported a leftover sliver on the Assessment Date field and a black band
  around the Sex popup. Both root-caused against source and confirmed live
  via qt-mcp *before* any fix, then re-confirmed fixed with fresh
  screenshots after. Assessment Date: `date_edit` is still a `QDateEdit`
  (kept deliberately in §13.4 for its built-in validation), and as a
  `QAbstractSpinBox` it still paints native, unstyled up/down step
  buttons even with the calendar popup gone — fixed via `setButtonSymbols
  (QAbstractSpinBox.ButtonSymbols.NoButtons)` (§14.1). Sex popup:
  §13.2's `view().setFrameShape(NoFrame)` only cleared the inner
  `QAbstractItemView`'s frame; the true source was the outer
  `QComboBoxPrivateContainer` (the popup's actual top-level window),
  unreachable by QSS — fixed via `WA_TranslucentBackground` +
  a transparent stylesheet on `view().parentWidget()` (§14.2). **Neither
  fix touched `wtmh_theme.py`** — both bugs were unstylable-by-QSS native
  chrome, not wrong/leftover QSS rules, so there is no QSS diff to show
  (§14.3, explicitly disclosed since the user's prompt expected one). Full
  pytest suite: 116 passed, same single pre-existing failure, no
  regressions. **Left uncommitted** — six rounds (§9-§14) now sit
  uncommitted together.

- **2026-09-08, later still — §9-§14 committed and pushed, via
  `/sparc:devops`.** User: "Commit this along with §9-§13" (§14 landed
  the same session, bundled in). All six accumulated rounds committed as
  one commit, `ef8b771`, and pushed to `origin/main`
  (`b91cd27..ef8b771`). Full pytest suite re-run immediately before
  committing: 116 passed, same single pre-existing failure, no
  regressions. `git status` clean after push — nothing from this whole
  Setup/Tasks-dashboard styling line of work remains uncommitted.

- **2026-09-08, later still — §14.2's Sex-popup fix regressed to solid
  black; root-caused and fixed for real (§15), via `/sparc:orchestrator`.**
  User shared a real screenshot of the running app (not a qt-mcp capture)
  showing the popup as a solid black rectangle. Root cause: §14.2's
  `WA_TranslucentBackground` + transparent-stylesheet approach relies on
  the desktop compositor, which does not reliably alpha-blend an
  alpha-enabled `Qt::Popup` window on this machine — it paints solid black
  instead. This was invisible to §14.4's own qt-mcp validation because
  `qt_screenshot` uses `QWidget.grab()`, which bypasses real window
  compositing entirely (paints each widget's own logic into a pixmap
  directly) — a structural blind spot for this whole bug class, not a one-
  off miss. Fixed by dropping translucency altogether: the popup container
  now gets an ordinary **opaque** background/border matching
  `wtmh_theme.py`'s own `PANEL_BG`/`BORDER` tokens, which has no
  compositor dependency to fail. This time validated with a **real desktop
  screenshot** (PowerShell + `System.Drawing.Graphics.CopyFromScreen`,
  independent of qt-mcp) confirming a clean white popup, no black
  anywhere. Full pytest suite: 116 passed, same single pre-existing
  failure, no regressions. Full account: `docs/specs/
  SPEC-ui-setup-task-selection.md` §15; the `qt-mcp-tool-reference` memory
  updated with the new evergreen finding about `qt_screenshot`'s blind
  spot for compositing bugs. **Left uncommitted.**

- **2026-09-08, later still — layout dead-space, title typography, and
  further Sex-popup polish (§16), via `/sparc:orchestrator`.** Another
  external critique covering three areas; per the user's instruction the
  SPEC was updated with the plan (§16.1/§16.2) before any implementation,
  every claim checked against real source/a real running dashboard first.
  Two findings corrected the critique's own description rather than just
  confirming it: Setup's 4 card titles had **no styling at all** (not
  merely "roughly matching" body text), and Tasks' card titles were
  **pixel-identical to the page title** (both used the same
  `wtmhSectionTitle` rule) — two different manifestations of the same
  missing-tier problem. Implemented: a new `wtmhPageTitle` tier (22px/700)
  plus a resized `wtmhSectionTitle` (16px/600, `margin-bottom: 6px`)
  applied consistently on both screens; a responsive 2-column
  `QGridLayout` for the 4 task cards (`tasks_page.py`, breakpoint 700px,
  reflowed via `resizeEvent`); modest spacing increases on Setup. The
  dead-space fix turned out to work by a different, more effective
  mechanism than planned: the spacing increases pushed Setup's natural
  minimum content height above `dashboard_window.py`'s hardcoded
  `resize(1024, 800)` call, so Qt now always enforces the *larger*,
  content-driven size — confirmed live by two failed attempts to force
  the real window back down to 800px tall via `MoveWindow`, both silently
  overridden upward by Qt. Net effect: the dead zone is structurally
  gone on Setup, not just visually reduced.

  Sex-popup polish: item padding and hover state were both already
  correct (no change); the field/popup border seam was fixed with
  `border-top: none` on the popup container. The phantom-outline fix
  needed two attempts — a QSS-only try (`outline: 0` + a transparent
  `::item:focus` border) was tested live and confirmed NOT to work (Qt's
  own `PE_FrameFocusRect` primitive paints independently of stylesheet
  item-delegate state), so the real fix disables the popup view's focus
  policy outright (`setFocusPolicy(Qt.FocusPolicy.NoFocus)`), confirmed
  live to clear the outline on the actual current-value item
  ("Select") while leaving arrow-key selection intact (handled by
  `QComboBox` itself, not the view's focus state). Also corrected the
  critique's own claim: the outline was landing on the combo's actual
  current value (index 0, "Select"), not the last item as described.

  Every visual claim validated with a **real desktop screenshot**
  (PowerShell + `System.Drawing.Graphics.CopyFromScreen`), continuing
  §15's practice, not `qt_screenshot` alone. Full pytest suite: 116
  passed, same single pre-existing failure, no regressions. Full account:
  `docs/specs/SPEC-ui-setup-task-selection.md` §16. **Left uncommitted.**

- **2026-09-08, later still — §16's Tasks grid fix reversed the dead-
  space problem (horizontal fixed, vertical now empty); fixed for real
  after a rejected attempt caused a genuine runaway bug (§17), via
  `/sparc:orchestrator`.** Another critique, confirmed live first: the
  2×2 grid only filled the top ~40% of the Tasks window. Tried, per the
  user's explicit instruction, an `Expanding` size-policy + row-stretch
  approach first — confirmed via `qt_widget_details` (not just a
  screenshot) that it badly under-delivered (cards grew from a 164px
  sizeHint to only 202px actual, despite ~822px genuinely available).
  Tried a second approach — computing and setting each row's minimum
  height directly from available space in `resizeEvent` — and this
  **caused a real, live runaway feedback loop**: `qt_list_windows`
  reported the window at **1484×524473px** immediately after switching
  to Tasks. Root cause: raising a row's *minimum* height raises the
  page's own required minimum, which (per §16.3's own established
  mechanism — this window auto-grows to match its content's minimum)
  grows the window, firing another `resizeEvent` with a larger height,
  computing an even larger minimum, forever. Killed the runaway process
  immediately, confirmed no leftover process afterward, and reverted the
  entire attempt. **Real fix:** the user's own explicitly-offered
  fallback — vertically centering the grid block via a stretch on each
  side of it (`addStretch(1)` / grid / `addStretch(1)`, title and back
  button unaffected) — which only ever consumes already-existing leftover
  space and can't raise any minimum size, so it can't trigger the same
  bug class. Validated live and cautiously (re-checked for runaway growth
  after every resize this round): grid now centers with a moderate,
  roughly-even gap above and below at the ~1500×800 test size, no single
  large dead region; the existing 2-col/1-col responsive breakpoint
  re-verified unaffected at a real narrowed window (634px → 1 column,
  live-reflowed correctly). Full pytest suite: 116 passed, same single
  pre-existing failure, no regressions. Full account: `docs/specs/
  SPEC-ui-setup-task-selection.md` §17. **Left uncommitted.**

- **2026-09-08, later still — `/spec-memory-audit` run, then S14-S17
  committed and pushed, via `/sparc:orchestrator`.** Audit checked log
  chronology (clean — all "2026-09-08, later still" entries verified
  against the actual commit order and session sequence), every code
  claim from §14-§17 against the current source (`NoFocus`, `border-top:
  none`, `PANEL_BG`/`BORDER` imports, `wtmhPageTitle`/`wtmhSectionTitle`,
  the vertical-centering `addStretch` pair, and confirmed no leftover
  code from either rejected Tasks-grid attempt — all checked out), a
  fresh pytest run (116 passed, same single pre-existing failure,
  matching the claims), and cross-links in the touched memory files (all
  resolved). **One real staleness issue found and fixed:** the
  `MEMORY.md` index line for this SPEC's memory pointer still said
  "S9-S13 all uncommitted," stale since S14 was committed earlier this
  session and didn't mention S15-S17 at all — corrected to reflect
  S1-S14 committed (`1404fde`/`86ccd91`/`b91cd27`/`ef8b771`/`8aac60c`)
  and S15-S17 as the current uncommitted work. All of S14-S17 then
  committed as one commit, `8f2e82b`, and pushed to `origin/main`
  (`8aac60c..8f2e82b`). `git status` clean after push.

- **2026-09-08, later still — Tasks grid dead space reported again after
  §17's centering fix; root-caused as two real bugs and fixed for real
  (§18), via `/sparc:orchestrator`.** New process rule adopted this
  round and applied throughout: qt-mcp validation now maximizes the
  target window first, since §17's own fix was apparently validated at
  a smaller size where the problem read as minor. Validated the report
  live before changing anything: at a real maximized 1920×1009 window,
  §17's centered grid did leave large dead bands (split top/bottom by
  its own centering mechanism), confirmed true against the Setup screen
  filling the same window edge-to-edge.

  Tried Expanding size policy + row stretch again first, per the user's
  explicit instruction. An offscreen diagnostic script (constructing
  `TasksPage()` directly under `QT_QPA_PLATFORM=offscreen`, faster than
  relaunching the live GUI per iteration) found the actual root cause of
  §17.1's "under-delivered, root cause not conclusively identified"
  result: `QGridLayout.rowCount()` never shrinks once a row index has
  been used, so switching from the 1-column reflow (4 rows) to
  2-column (2 rows) left ghost rows 2-3 still carrying `stretch=1` from
  the earlier reflow, silently halving the real rows' share of surplus
  space. Fixed that, confirmed live that Expanding cards then genuinely
  filled the window — but the live screenshot showed it looked awkward
  exactly as the prompt had warned it might: each card's own
  `QVBoxLayout` has no internal `addStretch()`, so the surplus height
  landed as three separate gaps between title/description/status/buttons
  rather than one trailing margin. Reverted per the prompt's own
  fallback instruction.

  Implemented the fallback instead: cards keep their natural,
  content-driven size; the grid's even row indices become widget-free
  spacer rows (one above the first card row, one between each pair, one
  below the last), each with equal stretch, distributing 100% of the
  leftover space evenly around the block without touching any card's own
  internal layout. Live qt-mcp validation (maximized): cards visually
  unchanged, leftover space now three even ~170px bands instead of one
  dead zone. 1-column responsive breakpoint re-verified via the same
  offscreen script at 600×900 (a live qt-mcp resize via
  `qt_set_property(geometry=...)` did not actually resize the real
  window this session — noted as a qt-mcp limitation, the offscreen
  script is the reliable fallback for testing a specific width). Full
  pytest suite: 116 passed, same single pre-existing failure, no
  regressions. Only `src/ui/tasks_page.py` changed; no functional/
  behavioral code touched. Full account: `docs/specs/
  SPEC-ui-setup-task-selection.md` §18. **Left uncommitted** — nothing
  from §18 is on `origin/main` yet (last commit remains `4aa6a51`).

- **2026-09-08, later still — Tasks grid reverted entirely to a
  single-column stack matching Setup, superseding §16-§18, via
  `/sparc:orchestrator`.** User reconsidered the whole grid direction
  ("on second thought... a single-column stacked layout is preferred")
  and asked to stop fixing the grid's empty-space problem and instead
  revert to a plain `QVBoxLayout` card stack matching `SetupPage`'s own
  pattern (`addWidget()` per card, one trailing `addStretch(1)`).

  Implemented exactly as asked in `src/ui/tasks_page.py`: removed
  `_GRID_BREAKPOINT_PX`, the `QGridLayout`/`QResizeEvent` imports,
  `_grid_columns`, `_reflow_grid()`, and the `resizeEvent()` override
  entirely; `_build_ui()` now just stacks the 4 cards via `addWidget()`
  plus a trailing `addStretch(1)`, identical in shape to Setup's own
  stack. `_TaskCard`'s internal content was untouched — a layout-
  container-only change, confirmed via diff.

  Live-validated via qt-mcp, maximized: the 4 cards fill roughly the
  top 3/4 of the window with one plain trailing margin below the last
  card — no large or awkward empty region, no internal card gaps, no
  split top/middle/bottom bands the way the grid attempts left. A real
  ~200px margin remains below the stack (Setup's own cards are form-
  heavy enough to reach almost to the bottom on content alone; the 4
  task cards are shorter even with the identical pattern reused), but
  it reads as a single unremarkable trailing gap, not the "large
  uninterrupted empty region" the original §16-§18 line of work was
  about. Full pytest suite: 116 passed, same single pre-existing
  failure, no regressions. Only `src/ui/tasks_page.py` changed; no
  functional/behavioral code touched. Full account: `docs/specs/
  SPEC-ui-setup-task-selection.md` §19. **§16-§18 are now historical
  record only — the grid, breakpoint, centering, and spacer-row code
  they describe no longer exists.** **Left uncommitted** — nothing from
  §16 through §19 is on `origin/main` yet (last commit remains
  `4aa6a51`).

- **2026-09-08, later still — `/spec-memory-audit` run (clean, no fixes
  needed), then S16-S19 committed and pushed, via `/sparc:orchestrator`.**
  Audit verified log chronology (§18's entry then §19's entry, both
  correctly appended after the S14-S17 commit entry, no reordering
  needed), every code claim against current source (grepped
  `src/ui/tasks_page.py`: zero `QGridLayout`/`_reflow_grid`/
  `resizeEvent`/`_GRID_BREAKPOINT_PX`/`_grid_columns` remain outside one
  historical comment; zero leftover `setSizePolicy` from the reverted
  §18.2 Expanding-card attempt), and a fresh pytest run (116 passed, 1
  failed — the same pre-existing `target_fps` assertion, counted
  precisely from the dot/F progress line since this pytest config
  doesn't print a final summary count line). Confirmed all cross-links
  between the touched memory files resolve. Nothing needed fixing.

  All of S16-S19 then committed as one commit, `74efccd`
  ("Fix then revert Tasks screen grid dead space; ship single-column
  stack (S16-S19)"), and pushed to `origin/main` (`4aa6a51..74efccd`).
  `git status` clean after push — nothing from this whole Tasks-layout
  line of work (the grid, its fixes, and its revert) remains
  uncommitted.

- **2026-09-09 — §20: a real calibration crash bug found, reproduced live,
  root-caused, and fixed, via `/sparc:orchestrator`.** User feedback: "when
  I do calibration it didn't show any calibration window from gazepoint."
  Two clarifying questions ruled out a two-PC/remote-display explanation
  before touching any code (Gazepoint Control confirmed on the same
  machine/screen; Tracker Connection said "Connected."; Calibration was
  stuck on "Calibrating…"). Reproduced live via qt-mcp against the real
  device first: Connect → "Connected." → Do Calibration hung indefinitely,
  and the whole dashboard process was found to have actually died (not
  just hung) — the launch log showed an unhandled `ConnectionAbortedError`
  inside `Calibration.run()`'s `CALIBRATE_SHOW` `sendall`.

  Two independent root causes, both fixed: (1) `configs/local_state.json`
  (gitignored per-machine state) held a stale `port: 4243` left over from
  an earlier fake-server QA round — `26.113.49.235` is this machine's own
  Radmin-VPN address, and the real Gazepoint Control process happens to
  also accept a raw TCP connection on 4243 without speaking the real
  OpenGaze protocol there, so "Connected." was misleading and any real
  command aborted the socket; corrected to `4242`. (2) `Calibration.run()`
  had no exception handling around its `sendall` calls (unlike
  `_poll_for_result`, which already catches `OSError` on `recv()`), so the
  abort's `OSError` escaped uncaught and crashed the entire app, not just
  the calibration thread — fixed with a `try/except OSError` returning an
  unmeasured/invalid result, matching `_poll_for_result`'s own contract.

  Re-validated live after both fixes: Control Port correctly showed 4242;
  Do Calibration now genuinely triggered Gazepoint Control's real on-screen
  10-point calibration overlay, confirmed via a real desktop screenshot
  (not qt-mcp's `grab()`-based `qt_screenshot`, per the §15 compositor-
  blind-spot precedent); dismissed with Escape; the dashboard correctly
  reported "Calibration did not produce a valid result" (expected — no
  human eye present for the automated test, same vendor floor as
  [[peds-eye-gaze-assessment-physician-feedback-2026-09-02]]) instead of
  crashing or hanging. Full pytest suite: 116 passed, same single
  pre-existing failure only, no regressions. Full account: §20. **Files
  changed:** `src/engine/calibration.py` (committable);
  `configs/local_state.json` (gitignored, local-only). **Left
  uncommitted**, same ask-before-commit pattern as the rest of this SPEC.

- **2026-09-09, later — §21: two real bugs in `tools/fake_gazepoint_server.py`
  found and fixed from the user's own hands-on testing, via
  `/sparc:orchestrator`.** User asked how to test the Tasks screen without a
  real gaze subject (since real calibration always fails without one, per
  §20.4) — pointed at the already-existing `tools/fake_gazepoint_server.py`,
  live-validated the full Connect→Calibrate→Continue→Tasks flow with it
  first. User then reported the script itself printed nothing and appeared
  to freeze; root-caused to bare `python` not resolving to the project's
  venv on this machine (a misconfigured `pyenv-win` shim, or the Windows
  Store `python.exe` stub — confirmed the former errors immediately in this
  session's own shells; recommended using the venv interpreter explicitly
  regardless) and hardened the script's prints with `flush=True` so the
  "listening…" message can never be silently delayed by buffering once the
  right interpreter is used (§21.1).

  User then correctly activated the venv, saw the "listening…" message
  immediately, but reported Ctrl+C didn't stop the server. Root-caused to
  `listener.accept()` blocking with no timeout — a well-known Windows
  CPython limitation (a thread blocked in a C-level blocking socket call
  can't service a pending `KeyboardInterrupt` until the call returns, which
  for an `accept()` with nothing connecting is never), the same class of
  bug this codebase already works around elsewhere (`GazepointClient
  ._run_socket`, `Calibration._poll_for_result`). Fixed with
  `listener.settimeout(0.5)` plus a `TimeoutError`-catching loop, matching
  the existing precedent (§21.2). Validated a real client still gets a
  correct `CALIBRATE_RESULT_SUMMARY` ACK through the new accept-timeout
  loop (no regression); the Ctrl+C path itself follows the same
  already-established pattern used elsewhere in this codebase for the
  identical Windows limitation. Full pytest suite: 116 passed, same single
  pre-existing failure only, no regressions (tool has no pytest coverage of
  its own). Full account: §21. **Files changed:** `tools/
  fake_gazepoint_server.py` only. **Left uncommitted**, alongside §20's
  `src/engine/calibration.py` fix.

- **2026-09-09, later still — a clean `/spec-memory-audit` pass, then §20
  and §21 committed and pushed, via `/sparc:orchestrator`.** Audit checked
  the Log's chronological order (clean), every §20/§21 code claim against
  current source (`Calibration.run()`'s `try/except OSError`, `tools/
  fake_gazepoint_server.py`'s `flush=True` prints and `settimeout`/
  `TimeoutError` accept loop, `configs/local_state.json`'s current value),
  all cross-links in the two new memory files (all resolved), and a fresh
  pytest run — confirmed precisely 116 passed / 1 pre-existing failure
  (counted via a small script rather than eyeballing dot-progress lines,
  since a naive count of `.`/`F` characters miscounts by matching the word
  "FAILED" in the summary line as a second failure — corrected during this
  audit, not a real second failure). Nothing needed fixing.

  Committed as `45908cb` ("Fix calibration crash and fake-server testing
  tool bugs (SPEC S20-21)") and pushed to `origin/main` (`4c28a29..45908cb`).
  `git status` clean after push — nothing from §20/§21 remains uncommitted.
  `configs/local_state.json` (currently `127.0.0.1:4243`, from §21's live
  fake-server testing) is gitignored and intentionally not part of this or
  any commit.
