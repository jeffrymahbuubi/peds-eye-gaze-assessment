# SPEC-ui-setup-task-selection — Setup & Task-Selection Dashboard

**Status:** section lists fully resolved across two feedback rounds, and now
also **wireframed** (`docs/wireframes/setup.md` + `tasks.md`, rendered HTML
alongside) — see §8. Committed and pushed to `origin/main` as `1404fde`.
The wireframe is now also **restyled into the WTMH lab's Clinical Teal brand
palette, with the WTMH logo placed in the titlebar** — see §9. **No PySide6
code implemented yet.** Ready for an implementation session, with a
rendered, on-brand reference to build against.
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
