![[_nav.md]]

::: row {.right}
Session |1|{.primary}   Tracker |not connected|{.error}   Calibration |none|{.warning}
:::

## 1 · Setup

> **Design note:** status badges above reflect a fresh session (just opened, nothing connected yet). After Connect + a completed/loaded calibration, Tracker reads |connected|{.success} and Calibration reads |fresh|{.success} — see the Tasks page for that state.

---

### Subject & Session Info

Subject ID
[_____________________________]{required}

Assessment Date
[2026-09-08__________________]{type:date}

Sex
[Select_______________________v]

- Female
- Male
- Other / Prefer not to say

Notes
[Free-text notes for this session..._____]{rows:4}

---

### Tracker Connection

::: row
Control Address
[26.113.49.235________________]{required}

Control Port
[4242_________________________]{required}
:::

[Connect]* [Test Connection]{.outline}

> **Design note:** Control Address is pre-filled from the last address that connected successfully *on this machine* (saved locally, never committed to git). A brand-new machine with no history defaults to `127.0.0.1`. There is no protocol-level auto-discovery — confirmed via the vendor API corpus, nothing to poll or broadcast for.

---

### Calibration

Point Count (1–9)
[5____________________________]{type:number min:1 max:9}

- [x] Show calibration window to the subject

::: row
[Do Calibration]* [Load Calibration File]{.outline} [View Calibration Details]{.outline state:disabled}
:::

::: alert warning
No calibration yet for this subject — run Do Calibration or Load Calibration File before continuing.
:::

> **Do Calibration:** runs a fresh calibration against the connected tracker using the point count/show-window controls above.
> **Load Calibration File:** file picker over a saved `calibration.json`; hard-errors if its `subject_id` doesn't match the Subject ID field above — same check the existing `--calibration-file` CLI flag already performs.
> **Alternate state (not shown above):** once calibration succeeds either way, this panel shows `::: alert success` — "Calibration loaded — 5 points, mean error 42px, valid" — in place of the warning, **and View Calibration Details becomes enabled.**
> **View Calibration Details:** disabled until a calibration result exists (same gating as Continue to Tasks below). Clicking it expands the section illustrated below **in place**, directly under this card — not a modal dialog (a modal would block the qt-mcp automation probe during testing, a known issue in this codebase, and this dashboard already prefers inline expansion elsewhere).

---

### Calibration Details (expanded state — illustrative)

> **Design note:** hidden by default; shown here expanded purely to illustrate what "View Calibration Details" reveals. In the real page this content lives *inside* the Calibration card above, appearing only after the button is clicked, and collapses again on a second click.

::: alert success
Calibration measured — 5 points, mean error 8px, valid.
:::

Per-point breakdown

| Point | Target (X, Y) | Left eye (X, Y) | Left valid | Right eye (X, Y) | Right valid | Error (px) |
|---|---|---|---|---|---|---|
| 1 | 0.500, 0.500 | 0.502, 0.503 | Yes | 0.515, 0.509 | Yes | 6.1 |
| 2 | 0.850, 0.150 | 0.849, 0.149 | Yes | 0.846, 0.148 | Yes | 4.8 |
| 3 | 0.850, 0.850 | 0.849, 0.849 | Yes | 0.846, 0.848 | Yes | 5.2 |
| 4 | 0.150, 0.850 | 0.149, 0.849 | Yes | — | No | 3.9 |
| 5 | 0.150, 0.150 | 0.149, 0.149 | Yes | 0.147, 0.148 | Yes | 4.4 |

> **Data source:** target/eye-estimate columns come straight from Gazepoint's own `CALIB_RESULT` record (per-point, per-eye) — captured but never surfaced anywhere in the UI before this design. Per-point "Error (px)" is a new derived value (Euclidean distance, target vs. each eye's estimate, screen-space) — not yet computed anywhere in this codebase; would need to be added alongside this UI.
> **Placeholder / empty state (not shown above):** if `per_point` data wasn't captured for this calibration (e.g. an older `calibration.json`, or a device/vendor path that never sent `CALIB_RESULT`), the table is replaced with a single centered row: "Per-point breakdown not available for this calibration." The summary alert above still renders normally either way — only the table degrades.

---

### Before You Start

::: alert info
Confirm in Gazepoint Control that Lens Focusing and Automatic Gain Sweep are enabled.
:::

> **Design note:** this is a read-only reminder, not a checkbox and not a gate — neither setting can be checked or changed from this app. Gazepoint Control's own Settings dialog is the only place either one lives; the OpenGaze API has no command for either (confirmed against the vendor corpus).

---

[Continue to Tasks →]*{state:disabled}

> **Design note:** disabled until Tracker shows |connected|{.success} **and** a calibration result exists (via either path above) **and** Subject ID, Assessment Date, and Sex are filled. Notes is optional. The "Before You Start" reminder above does **not** factor into this gate.
