# Clinical Data Reference

Cross-reference for every field this app saves: what it means, exactly which
Gazepoint OpenGaze API call/attribute it comes from, and why it's relevant
(or not yet used) for assessing Cerebral Palsy (CP) and similar neuro
conditions. Companion to [`DATA_SCHEMA.md`](DATA_SCHEMA.md) (full schema,
no clinical framing) and [`gazepoint_api_cheatsheet.md`](gazepoint_api_cheatsheet.md)
(raw API mechanics, no clinical framing) — this doc exists so a future
session doesn't have to re-derive both at once.

Originally compiled 2026-09-02 while triaging physician feedback; see
`docs/specs/SPEC-2026-09-02.md` in the top-level project (not this repo) for
the full triage context this was extracted from.

## Session folder layout

```
sessions/2026-07-15_P001_click_static/
  metadata.json      # subject + session + calibration + schema_version
  session.log        # human-readable timeline
  gaze_stream.csv    # per-frame gaze samples
  trials.csv         # one row per trial (analysis-ready)
  events.jsonl        # discrete events (TARGET_SHOWN, HIT, TIMEOUT, MISS_CLICK)
```

All timestamps are **nanoseconds** (`time.time_ns()` domain). Coordinates are
**normalized** (0–1, origin top-left) unless the field name ends in `_px`.

## gaze_stream.csv — per-frame raw gaze

The most clinically dense file: everything here originates directly from a
single Gazepoint `<REC .../>` record.

| Field | OpenGaze API source | Meaning | Clinical relevance for CP / neuro assessment |
|---|---|---|---|
| `t_ns` | (client receive time, not a REC attribute) | Capture timestamp | Needed to derive latency/duration metrics below; not itself clinical. |
| `x`, `y` | `BPOGX`/`BPOGY` (fallback `FPOGX`/`FPOGY` if best-POG invalid) — enabled by `ENABLE_SEND_POG_BEST` / `ENABLE_SEND_POG_FIX` | Normalized point of gaze | Raw gaze position; the input to every derived spatial/accuracy metric (hit rate, gaze heatmap). On its own mainly a QA signal — see `valid` below for how much of it can be trusted. |
| `valid` | `BPOGV` (or `FPOGV` on fallback) | Whether the tracker considers this sample valid | Proportion of invalid samples ("off-screen proportion") is itself one of the features found to reliably distinguish CVI/CP-related visual impairment from typical development (see Sources). Not currently aggregated by this app (see "Unused" section below). |
| `fixation_id` | `FPOGID` — enabled by `ENABLE_SEND_POG_FIX` | Increments once per new fixation | Lets you count **fixation frequency** and segment the stream into discrete fixations — a core input to CP/CVI oculomotor classification. Not currently aggregated. |
| `fix_duration_s` | `FPOGD` | Duration of the current fixation so far, seconds | **Fixation duration** — one of the most-used eye-tracking metrics in developmental/cognitive research generally, and specifically one of the features with AUC ≥0.90 distinguishing CVI/CP children from controls in the 2025 study cited below. Not currently aggregated. |
| `pupil_left`, `pupil_right` | `LPMM`/`RPMM` — enabled by `ENABLE_SEND_PUPILMM` (see API note below) | Pupil diameter, millimeters | Used in the literature mainly as a cognitive-load / attention / arousal signal rather than a CP-specific oculomotor marker — secondary priority unless the clinical goal explicitly includes engagement/attention tracking. Not currently aggregated. |

**API note (corrected 2026-09-02):** pupil diameter is gated by
`ENABLE_SEND_PUPILMM` (OpenGaze manual §5.16), **not**
`ENABLE_SEND_PUPIL_LEFT`/`ENABLE_SEND_PUPIL_RIGHT` — those instead gate the
*pixel*-based `LPD`/`RPD` fields (§5.9/5.10), which this app does not read.
`gazepoint_api_cheatsheet.md` previously stated this incorrectly; both are
now fixed (see [[peds-eye-gaze-assessment-pupilmm-fix]] equivalent in the
top-level project memory for the original bug this was caught by).

## trials.csv — one row per completed trial

Derived/aggregated from the raw gaze stream plus task logic, not read
directly from a REC record.

| Field | Derivation | Meaning | Clinical relevance |
|---|---|---|---|
| `trial_id`, `task_id` | app-generated | Trial index, task name | Bookkeeping. |
| `target_x`, `target_y`, `target_radius_px` | app-generated (task config) | Where/how big the target was | Needed to interpret accuracy; not itself a subject measurement. |
| `t_target_shown_ns` | app event timestamp | Target onset | Baseline for every latency metric below. |
| `t_first_gaze_on_target_ns` | first frame where `(x,y)` (from `BPOGX/Y`/`FPOGX/Y`) entered the target hitbox | First-fixation time | Input to `time_to_first_fixation_ms` below — a direct analogue of **saccade/fixation latency**, one of the CVI/CP-classifying features cited below. |
| `t_click_ns` | first frame dwell selection triggers | Selection time | Input to `reaction_time_ms`. |
| `t_end_ns` | app event timestamp | Trial end (hit or timeout) | Bookkeeping. |
| `is_hit`, `is_timeout` | app logic | Outcome flags | **Selection accuracy** — matches the accuracy metric used in a published longitudinal study of gaze-based AT performance in children with CP (Compass software; see Sources) — this app's `click_grid` task is explicitly modeled on that same software. |
| `attempts` | app logic (counts off-target selections too) | Selection attempts this trial | A rough proxy for gaze-control precision/impulsivity — not validated against literature here, but directly analogous to "false selection" counts used in AAC-access research. |
| `reaction_time_ms` | `t_click_ns − t_target_shown_ns` | Time to complete selection | **Reaction time** / **time-on-task** — the other half of the Compass-study accuracy metric above. |
| `time_to_first_fixation_ms` | `t_first_gaze_on_target_ns − t_target_shown_ns` | Time to first look at target | Closest analogue in this app's data to **saccade latency**, one of six oculomotor features reaching AUC ≥0.90 in classifying CVI (common in CP) vs. typically-developing children in the 2025 study below. |

## metadata.json — session-level

| Field | Source | Meaning | Clinical relevance |
|---|---|---|---|
| `calibration_error_px` | Gazepoint `CALIBRATE_RESULT_SUMMARY` (`<GET ID="CALIBRATE_RESULT_SUMMARY" />`), mean across calibration points | Mean calibration accuracy | Not just a QA metric: a 2025 CP-specific study found 6 of 39 children *could not calibrate to the required accuracy at all* — calibration success/quality is itself a data point about a child's oculomotor control, worth tracking per-subject over time. |
| `calibration_points` | app config (`calibration.points`, 5 or 9) | Calibration density used | Context for interpreting `calibration_error_px` across sessions/subjects. |
| `input_mode`, `gazepoint_model`, `subject_id`, `session_id`, `schema_version`, `tasks`, `notes` | app-generated | Bookkeeping | Not clinical data. |

## events.jsonl

Raw event log (`TARGET_SHOWN`, `HIT`, `TIMEOUT`, `MISS_CLICK`, `LATENCY_SAMPLE`)
that `trials.csv` is derived from — useful for re-deriving custom metrics
later, but not a distinct clinical data source beyond what's summarized above.

## Fields recorded today but not yet analyzed

`analysis/analyze_session.py` currently only computes hit rate, timeout
count, mean reaction time, a reaction-time histogram, and a 2D gaze heatmap.
The following are already being **recorded** in `gaze_stream.csv` but never
**aggregated** into a session-level summary, despite being clinically
relevant per the sources below:

- Fixation frequency/count (`fixation_id`)
- Fixation duration distribution (`fix_duration_s`)
- Off-screen / invalid-sample proportion (`valid`)
- Pupil diameter trends (`pupil_left`/`pupil_right`)

This is a candidate for a future analysis-script extension, not something
implemented as part of this reference doc.

## Gazepoint Analysis's own session-level summary — is it API-accessible?

**No.** "Gazepoint API" refers to two different things and it's easy to
conflate them:

- **The OpenGaze API** (port 4242, served by Gazepoint Control) — a
  **live, real-time per-sample data stream**. This is the one this app
  already integrates against. It does **not** carry session summaries or
  AOI statistics, and it doesn't even carry saccade magnitude/direction —
  `SACCADE_MAG`/`SACCADE_DIR` are explicitly CSV-export-only fields with
  no API stream equivalent (confirmed in our own vendor-corpus synthesis,
  `docs/gazepoints/synthesis/data-fields-reference.md` in the top-level
  project).
- **Gazepoint Analysis** (the separate desktop GUI app bundled with the
  tracker) — this is where session-level summaries actually get computed:
  AOI statistics (viewed/not, time-to-first-view, time viewed %, revisits,
  revisitors, clicks, plus per-AOI biometric averages). But per its own
  manual (`docs/gazepoints/sources/gazepoint-analysis.md`, current and a
  2014 edition both checked), the **only** way this data leaves the app is
  a manual GUI action — pressing **Export** writes
  `{RECORDING}_all_gaze.csv`, `{RECORDING}_fixations.csv`, and
  `Data_Summary_export_{DATETIME}.csv` to a `\result\` folder. No CLI flag,
  scripting hook, or batch-automation mode is documented anywhere for
  triggering or reading that export programmatically.
- External corroboration: a 2026 peer-reviewed R package, `gp3tools`
  (Balaskas 2026, *J Eye Movement Research*), exists specifically to parse
  Gazepoint Analysis's *manually exported* CSV files — its own
  documentation notes this is a workaround because there's no live API for
  the summary data, and that metrics it recomputes from the raw exports
  "may not always exactly reproduce Gazepoint's internal calculations."

**Practical implication:** this app already bypasses Gazepoint Analysis
entirely (it talks to Gazepoint Control's live API directly), so any
session-level summary metrics wanted here — including saccade
amplitude/direction — have to be computed by this app's own analysis layer
from `gaze_stream.csv`, not pulled from Gazepoint Analysis.

### Session-level metrics worth designing toward (external research)

| Category | Metric | Why it matters for CP/neuro assessment | Already recorded? |
|---|---|---|---|
| Data quality | % valid/on-screen samples, calibration error | A 2025 CP study found 6/39 children couldn't calibrate to the required accuracy at all — a clinical signal, not just QC. A toddler eye-tracking battery study (eLife 2023) uses accuracy + precision as its two general per-session data-quality proxies. | `valid`, `calibration_error_px` — yes, not yet aggregated |
| Fixation | Mean/median fixation duration, fixation count/rate | One of six features reaching AUC ≥0.90 classifying CVI (common in CP) vs. controls (2025 study, cited above in this doc). | `fixation_id`, `fix_duration_s` — yes, not yet aggregated |
| Saccade | Latency (≈ time-to-first-fixation), amplitude, direction | Same 2025 study. Amplitude/direction are exactly the two fields Gazepoint doesn't expose live (see above) — would need in-house computation from consecutive fixation POGs. | Latency: yes (`time_to_first_fixation_ms`). Amplitude/direction: not recorded |
| Task performance | Hit rate / accuracy %, mean reaction time, time-on-task | Matches the metrics used in the published Compass-based longitudinal CP study `click_grid` is modeled on. | Yes, already computed by `analysis/analyze_session.py` |
| Selection precision | Revisit / re-attempt counts | A 2026 CP oculomotor-training study (ScienceDirect, *Acta Psychologica*) tracked "fixation precision and visual exploration" pre/post intervention using gaze-driven games; this app's `attempts` field is a rough analogue. | Yes (`attempts`), not yet framed as a precision metric |
| Pupil | Mean/trend pupil diameter | Secondary priority — literature treats it mainly as an attention/cognitive-load signal, not CP-specific. | Yes, not yet aggregated |

**Planned next step (not yet started):** the user intends to pull a sample
export from Gazepoint Analysis directly (`_all_gaze.csv`, `_fixations.csv`,
`Data_Summary_export_*.csv`) to see exactly which fields/statistics it
actually produces in practice, then attempt to reverse-engineer those
derived statistics (especially the AOI/session-summary ones with no API
equivalent) from this app's own raw `gaze_stream.csv`, so the app doesn't
depend on Gazepoint Analysis at all for CP-relevant session summaries.

## Sources

- PubMed 40217776 — *Assessment of Gaze Fixations and Shifts in Children
  with Cerebral Palsy: A Comparison of Computer- and Object-Based
  Approaches* (2025) — single-target-fixation / target-target-fixation-shift
  task design and calibration failure rate (6/39 children).
- ScienceDirect / *Ophthalmology Science* — *Cerebral/Cortical Visual
  Impairment Classification and Categorization Using Eye Tracking Measures
  of Oculomotor Function* (2025) — fixation and saccade latency, frequency,
  and off-screen proportion reaching AUC ≥0.90 classifying CVI vs. controls.
- PMC4867850 — *Eye gaze performance for children with severe physical
  impairments using gaze-based assistive technology — A longitudinal study*
  — Compass software, time-on-task and accuracy metrics in children with CP.
- Gazepoint OpenGaze API manual (vendor PDF corpus, `docs/gazepoints/` in
  the top-level project) — §3.1 (ENABLE_SEND_DATA master switch), §5.9/5.10
  (LPD/RPD, pixel pupil — not used here), §5.16 (PUPILMM, mm pupil — used
  here).
- Gazepoint Analysis User Manual (vendor PDF corpus, `docs/gazepoints/
  sources/gazepoint-analysis.md` in the top-level project, Dec 2025
  revision; a 2014 edition was also checked externally) — confirms Export
  is a manual GUI action with no scripting/CLI/API hook.
- Balaskas, S. (2026). *gp3tools: An R Package for Reproducible Analysis
  and Reporting of Gazepoint GP3 Eye-Tracking Exports.* Journal of Eye
  Movement Research, 19(4), 76 — third-party tooling built specifically to
  parse manually-exported Gazepoint Analysis CSVs, corroborating that no
  live API exists for session/AOI summaries.
- ScienceDirect / *Acta Psychologica* (2026) — *Eye-gaze-driven games to
  support oculomotor skills in young adults with cerebral palsy using
  eye-tracking technology: a multiple case study* — fixation precision and
  visual exploration as pre/post intervention outcome measures in CP.
- eLife reviewed preprint (2023) — *Objective assessment of visual
  attention in toddlerhood* — accuracy + precision as general per-session
  eye-tracking data-quality proxies, alongside task-specific metrics.
