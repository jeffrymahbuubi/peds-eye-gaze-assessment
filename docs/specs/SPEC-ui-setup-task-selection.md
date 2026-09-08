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
inner view) — both via Python widget config, no QSS changes.** All six
rounds (§9-§14) committed and pushed to `origin/main` as `ef8b771`.
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
