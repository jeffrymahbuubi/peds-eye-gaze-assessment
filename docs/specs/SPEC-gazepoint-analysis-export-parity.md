# SPEC-gazepoint-analysis-export-parity — Match Gazepoint Analysis's CSV export from our own recorder

**Status: DESIGN ONLY — nothing implemented.** §1–§4 are findings from the
user's sample export (verified against the files, not the manual alone).
§5 (Bucket B/C: raw fields we can record directly) and §6 (Bucket D:
fields Gazepoint Analysis computes, which we must derive) are the plan.
§6 has a two-stage gate the user set: **derive + test first, report, get
approval, only then wire into the app.**

**Created:** 2026-09-17
**Last updated:** 2026-09-17

## 1. Origin / what was asked

User, 2026-09-17, pointing at `resources/gazepoint-analysis-example-data/`
(top-level project, a real export from Gazepoint Analysis v7.3.0 made
2026-09-10): "Check whether current software already outputs data with the
data fields similar to the .csv or not. If not, check whether the API
exposes these data or not." Then, on the report: add every field the API
exposes (except the biometrics-kit ones) so "the data from the software
custom we made have similar function with the analysis"; for the fields the
API does *not* expose, "report first whether we already have the code to do
this or not, if not add to the SPEC to derive them first then test. After
tested and approved, wire it to the custom software."

This is the "planned next step" `docs/CLINICAL_DATA_REFERENCE.md` §"Gazepoint
Analysis's own session-level summary" had left open since 2026-09-03.

## 2. What the sample export contains (verified)

| File | Rows | Verified structure |
|---|---|---|
| `User 0_all_gaze.csv` | 639 samples × **62 columns** | Every `<REC>` record of the recording, in Gazepoint's own attribute names, plus Analysis-computed columns |
| `User 0_fixations.csv` | 15 rows × same 62 columns | **One row per fixation = the last valid (`FPOGV=1`) sample of each `FPOGID`.** Checked programmatically: the fixation rows' `CNT` (18, 40, 59, 104, …) equal the last-valid-sample `CNT` per `FPOGID` in `all_gaze`; the single-sample fixation `FPOGID=1` at `CNT=0` is dropped |
| `Data_Summary_export_09-10-26-11.39.31_eyetracker.csv` | header only | AOI statistics per user + averages; no data rows because no AOIs were defined in Analysis for this recording |

The 62 columns, in file order:

```
MEDIA_ID, MEDIA_NAME, CNT, TIME(<start datetime>), TIMETICK(f=1000000000),
FPOGX, FPOGY, FPOGS, FPOGD, FPOGID, FPOGV, BPOGX, BPOGY, BPOGV,
CX, CY, CS, KB, KBS, USER,
LPCX, LPCY, LPD, LPS, LPV, RPCX, RPCY, RPD, RPS, RPV,
BKID, BKDUR, BKPMIN, LPMM, LPMMV, RPMM, RPMMV,
DIAL, DIALV, GSR, GSR_US, GSR_US_TONIC, GSR_US_PHASIC, GSRV, HR, HRV, HRP, IBI,
TTL0, TTL1, TTL2, TTL3, TTL4, TTL5, TTL6, TTLV, PIXS, PIXV,
AOI, SACCADE_MAG, SACCADE_DIR, VID_FRAME
```

Two header quirks matter for parity: `TIME(...)` carries the recording's
wall-clock start in the header and counts seconds from **recording start**
(the API's `TIME` counts from Control's last init/calibration — different
origin); `TIMETICK(f=…)` carries the tick frequency in the header.

## 3. What our recorder writes today

`sessions/<run>/gaze_stream.csv` (`GazeSample.as_row`, `src/data/schema.py`):
`t_ns, x, y, valid, fixation_id, fix_duration_s, pupil_left, pupil_right` —
8 columns. Mapping the 62 export columns onto it:

| Bucket | Export columns | Ours |
|---|---|---|
| **A — already written** (6 of 62, collapsed) | `FPOGX/Y` + `BPOGX/Y` → one `x,y` (BPOG when `BPOGV`, else FPOG); `FPOGV` + `BPOGV` → one `valid`; `FPOGID` → `fixation_id` (only when `FPOGV`); `FPOGD` → `fix_duration_s`; `LPMM`/`RPMM` → `pupil_left/right` | `rec_to_sample()`, `src/inputs/gazepoint_client.py` |
| **B — received, discarded** | `TIME` (subscribed via `enable.time`, replaced by host `t_ns`); `FPOGS`; `LPMMV`/`RPMMV`; `CX/CY/CS` (subscribed via `enable.cursor`, never stored) | On the wire already; `rec_to_sample()` drops them |
| **C — API has them, not subscribed** | `CNT`, `TIMETICK`, `KB/KBS`, `USER`, `LPCX/LPCY/LPD/LPS/LPV`, `RPCX/RPCY/RPD/RPS/RPV`, `BKID/BKDUR/BKPMIN`, `PIXS/PIXV` | One `ENABLE_SEND_*` each: `COUNTER`, `TIME_TICK`, `KB`, `USER_DATA`, `PUPIL_LEFT`/`PUPIL_RIGHT`, `BLINK`, `PIX` |
| **C′ — API has them, need the Biometrics kit** | `DIAL/DIALV`, `GSR/GSRV`, `HR/HRV/HRP/IBI`, `TTL0–6/TTLV` | **Excluded by the user.** Read 0 without the kit (the sample shows exactly that) |
| **D — not in the API** | `MEDIA_ID/NAME`, `VID_FRAME`, `AOI`, `SACCADE_MAG`, `SACCADE_DIR`, `GSR_US/_TONIC/_PHASIC` | Computed by Gazepoint Analysis at export (vendor corpus: `docs/gazepoints/synthesis/data-fields-reference.md` §"CSV-only fields") |

Nothing we write corresponds to `_fixations.csv` or `Data_Summary` *as
files*; §6 covers what of them is derivable.

## 4. Bucket D — reverse-engineered from the sample (the part that needed proof)

**`SACCADE_MAG` / `SACCADE_DIR` are fully reproducible from fields we already
record.** Definition, found by fitting the sample:

- Both are 0 on every row except a fixation's **last valid sample**, where
  they describe the jump *from the previous fixation to this one*.
- `SACCADE_MAG` = Euclidean distance in **screen pixels** between the
  previous fixation's `(FPOGX, FPOGY)` and this fixation's, i.e.
  `hypot((x1−x0)·W, (y1−y0)·H)`. A search over screen sizes gives
  **W×H = 3440×1440** for this recording with total error **0.0002 px over
  five saccades** — an exact fit, not an approximation. (1920×1080 gives a
  ~1.4–1.6× mismatch, which is what an unaware reader would see first.)
- `SACCADE_DIR` = `atan2(−dy_px, dx_px)` in degrees, **0–360, measured
  counter-clockwise from +x with screen-up positive**.
- **Both definitions verified over all 14 saccades in the sample at
  3440×1440: max error 0.0002 px in magnitude and 0.00004° in direction.**
  These are the vendor's exact formulas, not an approximation.

**`_fixations.csv`** = group `all_gaze` rows by `FPOGID`, keep the last row
with `FPOGV=1`. Trivial once the per-sample file exists.

**`Data_Summary` AOI statistics** = Gazepoint-Analysis rectangles drawn on
media. We have no media and no AOIs; the analogue is the **per-trial target
hitbox**. Of its columns, we already have time-to-first-view
(`time_to_first_fixation_ms`), clicks (`is_hit`/`attempts`), fixations on
target (`fixations_per_trial` in `session_metrics.json`); "time viewed (s / %)"
and "revisits / revisitors" need on-target entry/exit tracking we do not
have. `MEDIA_*`/`VID_FRAME` are not applicable.

### 4.1 Do we already have code for any of Bucket D? — **No.** (Reported 2026-09-17.)

Checked `src/` and `analysis/` for any amplitude/direction/`hypot`/`atan2`,
per-fixation table, or revisit logic:

| D item | Existing code | Gap |
|---|---|---|
| `SACCADE_MAG`/`SACCADE_DIR` | None. `compute_fixation_saccade_metrics()` counts saccades from `fixation_id` transitions only; the Results page's "Mean amplitude / Mean direction" rows are hard-coded "—" (`results_page.py`) | Whole computation |
| Per-fixation table | None emitted. The grouping loop in `compute_fixation_saccade_metrics()` keeps only each fixation's final `FPOGD`; start time and POG are discarded | Emit a table instead of a scalar |
| AOI "time viewed" / "revisits" | None. `results_page.py` "Mean revisits" is hard-coded "—" | On-target entry/exit tracking — new instrumentation, not a derivation |
| **Prerequisite:** screen size in px | `GazepointClient` already queries `SCREEN_SIZE` at connect (used for `set_gaze_geometry`), but **`SessionMetadata` has no screen-size field** — nothing on disk says what W×H a session's normalized POG maps to | Persist `screen_width_px`/`screen_height_px` in `metadata.json` (additive) |

### 4.2 Which "screen size" — monitor, not canvas (decided 2026-09-17, user question)

The user asked whether the HUD-excluded canvas size (what hit-testing uses
during a task) is the right basis, on the intuition that it makes the gaze
cursor "more correct". **It is not, and the intuition is inverted.** From
`src/tasks/base_task.py` / `src/app.py::_tick`, two sizes are in use at the
same time for different jobs:

| Size | Set by (every frame) | Used for |
|---|---|---|
| Canvas (window minus the operator-panel column) | `set_screen_size(canvas.width(), canvas.height())` | Target positions and hitboxes — target coordinates are authored normalized-to-canvas |
| **Full tracked monitor** (`SCREEN_SIZE` from Gazepoint Control) + canvas on-screen offset | `set_gaze_geometry(...)` via `_sync_gaze_geometry()` | Converting the gaze pointer: `px = x·W_monitor − offset_x` |

The cursor is correct precisely *because* the pointer conversion uses the
monitor size, not the canvas: `FPOGX/BPOGX` are fractions of the calibrated
monitor and the tracker knows nothing about our window. Using the canvas
size there was the confirmed bug of `SPEC-gui-audit-2026-09-10.md` item 5.

**Rule for Bucket D (and for any downstream analysis of `gaze_stream.csv`
/ `all_gaze.csv`):**

1. Pixel saccade magnitude/direction = normalized Δ × **monitor** W×H.
   What we record is the raw device sample (`EyeInput.latest_sample()`,
   "used for recording, never for the pointer"), i.e. monitor-normalized.
2. The canvas must **never** be the scale factor. Because the panel is a
   *side* column, the canvas is narrower but not shorter than the monitor,
   so canvas scaling would shrink Δx by ~W_canvas/W_monitor (≈0.84 for a
   ~300 px column on 1920) and leave Δy alone — every direction rotated
   toward vertical and horizontal amplitudes under-read by ~16%. A
   systematic, anisotropic bias, not noise.
3. The canvas *offset* cancels out of any Δ, so it is irrelevant to
   `SACCADE_MAG`/`DIR`. Canvas size + offset are still worth persisting for
   position-relative analyses (on-target fixations, heatmaps over the task
   scene) — as a separate frame, never as the scale.
4. Monitor size is what Gazepoint Analysis uses (§4: the 3440×1440 fit is
   exact), so a methods section can cite "computed as in Gazepoint Analysis
   v7.3" truthfully.

**Persist at run start in `metadata.json`** (all additive; extends the §4.1
prerequisite):
- `screen_width_px`, `screen_height_px` — from `device_info.screen_width/
  height` (`SCREEN_SIZE`), the basis for every px-unit derivation;
- `canvas_width_px`, `canvas_height_px`, `canvas_offset_x_px`,
  `canvas_offset_y_px` — the frame targets live in;
- `screen_physical_width_mm`, `screen_physical_height_mm` — from config or
  `QScreen.physicalSize()` (validate: EDID values are sometimes wrong);
- `viewing_distance_mm` — config / a Setup-page field (Gazepoint's nominal
  operating distance is ~650 mm).

**Units for publication:** store amplitude in **px** (the vendor-comparable
quantity) and derive **degrees of visual angle** from the persisted physical
values — pixels are device-dependent (600 px on a 3440-px ultrawide is not
the eye movement 600 px on a 1920-px laptop is). Never store only degrees;
the px value plus the geometry is what makes a later re-analysis possible.
This resolves the second §8 question in favour of "both".

## 5. Plan — Bucket B + C: record the raw stream (decided)

**Decision (`AskUserQuestion`, 2026-09-17): a new per-sample file in the
exact Gazepoint Analysis column layout**, alongside the untouched
`gaze_stream.csv`. Rejected: widening `gaze_stream.csv` (mixes our
normalized names with Gazepoint's and stops being a drop-in for
Analysis-format tools); "both" was the same as the chosen option plus
duplication. Rationale for the chosen option: every existing reader and
test keeps working unchanged, and third-party tooling written for Gazepoint
exports (e.g. the `gp3tools` R package) reads our sessions directly.

### 5.1 File: `sessions/<run>/all_gaze.csv`

- Columns **in the sample's exact order and spelling** (§2), including the
  `TIME(<start>)` / `TIMETICK(f=…)` header forms so the file is
  byte-compatible with what Analysis produces.
- Columns whose source we deliberately don't have are still present and
  written as Analysis would for absent data: `MEDIA_ID`=0,
  `MEDIA_NAME`="" , biometrics (C′) as 0 / validity 0, `AOI`="" ,
  `VID_FRAME`=0. **`SACCADE_MAG`/`SACCADE_DIR` are written 0 until §6 is
  approved and wired**, then filled in the same file. Keeping the columns
  from day one means the header never changes shape later.
- `TIME` = seconds since **recording start** (recompute from the device
  `TIME` minus the first record's `TIME`), header stamped with the
  recorder's `open()` wall-clock time — matching Analysis, not the raw API
  origin. `TIMETICK` raw, with `TIME_TICK_FREQUENCY` queried once at
  connect for the header.
- One row per `<REC>` received, whether or not `valid` — Analysis writes
  every record.

### 5.2 Subscriptions and config

`configs/default.yaml` `gazepoint.enable.*` gains `counter`, `time_tick`,
`kb`, `user_data`, `pupil_left_px` / `pupil_right_px` (the pixel `LPD/RPD`
family — **distinct from** the existing `pupil_left`/`pupil_right` keys,
which are the mm `PUPILMM` switch; see the fix recorded in
[[peds-eye-gaze-assessment-pupilmm-fix-2026-08-31]] for why those names
must not be conflated), `blink`, `pix`. All default **on**; `enable_command`
mapping in `gazepoint_client.py` extended accordingly. Biometrics switches
(`DIAL`, `GSR`, `HR*`, `TTL`) are **not** added.

### 5.3 Where it plugs in

`GazepointClient`'s reader thread already parses every `<REC>` into an
attribute dict before `rec_to_sample()`; the raw dict is what
`all_gaze.csv` needs. Proposed: the client exposes the raw attrs alongside
the `GazeSample` (it already keeps a `_last_raw_pog` subset for the
dropout diagnostic), and `SessionRecorder` gains an `all_gaze` writer
opened next to `gaze_stream.csv`, gated by a new
`recording.save_all_gaze: true`. `gaze_stream.csv` and `rec_to_sample()`
are **not** changed — Bucket A stays as-is.

### 5.4 Tests (to write with the implementation)

- Header equality: our header == the sample file's header, column for
  column (one assertion against a checked-in copy of the 62-name list).
- A fake `<REC>` with every Bucket B/C attribute round-trips to the right
  column; a `<REC>` missing an attribute writes the Analysis-style default,
  never a blank shift.
- `TIME` origin: first row 0.0, monotone thereafter.
- `save_all_gaze: false` writes nothing and changes nothing else.
- The fake server (`tools/fake_gazepoint_server.py`) needs to emit the new
  attributes so the live path is exercisable without a subject.

## 6. Plan — Bucket D: derive, test, report, approve, then wire (gated)

**Stage 1 — derive + test, no app wiring.** A Qt-free module
(`src/data/saccades.py` or inside `exporter.py`) with:

- `fixation_table(rows, screen_w, screen_h)` → one record per fixation
  (last valid sample), carrying `FPOGID`, `FPOGS`, `FPOGD`, `FPOGX/Y`, and
  the derived `SACCADE_MAG`/`SACCADE_DIR` from the previous fixation.
- `saccade_mag_dir(prev_xy, cur_xy, screen_w, screen_h)` implementing §4
  exactly.

**The test that settles it:** run the derivation over the user's real
`User 0_all_gaze.csv` with W×H = 3440×1440 and assert the recomputed
`SACCADE_MAG`/`SACCADE_DIR` match the file's own columns on every fixation
row to within 0.01 px / 0.01°, and that the derived fixation rows are the
same `CNT`s as `User 0_fixations.csv`. That is a golden test against the
vendor's own output, not against our reading of the manual. (The sample
files are checked into the top-level `resources/`; the test needs a copy or
a fixture path under `tests/fixtures/`.)

**Stage 1 deliverable = a report to the user** with that test's result and
the session-level aggregates it enables (mean/median saccade amplitude in
px and, once screen physical size is known, in degrees of visual angle;
direction distribution). **Stop there.**

**Stage 2 — only after approval:** persist `screen_width_px`/`_height_px`
in `metadata.json` (§4.1 prerequisite); fill `SACCADE_MAG`/`SACCADE_DIR` in
`all_gaze.csv` at session close (they depend on the *next* fixation, so
they are a post-pass, exactly as Analysis does at export); write
`fixations.csv`; add `mean_saccade_amplitude_px` etc. to
`session_metrics.json`; replace the Results page's "—" for Mean amplitude /
Mean direction. AOI-style "time viewed / revisits" stay out of scope unless
separately requested — they need new on-target tracking (§4), not a
derivation.

## 7. Out of scope / not applicable

- Biometrics kit fields (C′) — user's decision; columns kept as zeros for
  layout parity only.
- `Data_Summary_export_*.csv` as a file — its AOI model has no counterpart
  here; the per-trial analogue already lives in `trials.csv` +
  `session_metrics.json`.
- Any change to `gaze_stream.csv`, `rec_to_sample()`, or the hit-testing
  path — §5.3 is purely additive.

## 8. Open questions

- §5.1: should `USER` carry our own event markers (e.g. `TARGET_SHOWN`,
  trial id) so `all_gaze.csv` is self-describing to an Analysis-format
  tool, or stay blank as the API sends it? Cheap either way; the former is
  more useful, the latter is stricter parity. Default if unasked: blank
  (strict parity), events stay in `events.jsonl`.
- ~~§6 Stage 2: report saccade amplitude in px only, or also in degrees of
  visual angle?~~ **Resolved in §4.2: both** — px stored, degrees derived
  from persisted physical size + viewing distance (to be added to
  `metadata.json` and the Setup page/config).

## 9. Log

- **2026-09-17 — §1–§4 findings + §5–§6 plan written, via
  `/sparc:orchestrator`; design only, zero `src`/`tests` changes.** The
  sample export was analysed programmatically (fixation-row rule, 62-column
  list, `SACCADE_MAG`/`DIR` definition and the 3440×1440 screen fit). §4.1
  answered the user's "do we already have the code for D?" — no, for every
  item, plus the unrecorded-screen-size prerequisite. File-layout fork
  decided by `AskUserQuestion` (new Analysis-format `all_gaze.csv`).
  `docs/CLINICAL_DATA_REFERENCE.md`'s "planned next step" paragraph replaced
  with a pointer here; `docs/DATA_SCHEMA.md` given a one-line pointer to the
  planned file. Uncommitted, ask-before-commit as always.

- **2026-09-17, later — §4.2 added: monitor size, not canvas size, is the
  basis for pixel saccade metrics.** Answers the user's two follow-up
  questions (does the HUD-excluded canvas make the cursor "more correct"?
  — no, the pointer conversion deliberately uses the monitor size; which
  size for downstream/paper analysis? — monitor, canvas scaling would bias
  amplitude ~16% and rotate direction). Extends the §4.1 prerequisite to
  persist monitor px, canvas px + offset, physical mm, and viewing distance
  in `metadata.json`; resolves the §8 px-vs-degrees question as "both".
  Still design only.
