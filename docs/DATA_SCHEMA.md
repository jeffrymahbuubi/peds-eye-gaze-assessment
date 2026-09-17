# Data Schema

Each session writes one folder under the output root (default `sessions/`):

```
sessions/2026-07-15_P001_click_static/
  metadata.json      # subject + session + calibration + schema_version
  session.log        # human-readable timeline
  gaze_stream.csv    # per-frame gaze samples
  all_gaze.csv       # every raw <REC>, Gazepoint Analysis 62-column export layout
  fixations.csv      # one row per fixation, same layout (written at session close)
  trials.csv         # one row per trial (analysis-ready)
  events.jsonl       # discrete events (TARGET_SHOWN, HIT, TIMEOUT, MISS_CLICK)
  session_metrics.json  # rolled-up result (summary / fixation_saccade / saccades)
```

All timestamps are **nanoseconds** (`time.time_ns()` domain, UTC-based). Divide
by `1e6` for milliseconds. Coordinates are **normalized** (0–1, origin
top-left) unless the field name ends in `_px`.

## metadata.json

| field | type | notes |
|-------|------|-------|
| `subject_id` | str | subject identifier |
| `session_id` | str | folder name |
| `started_ns` | int | session start |
| `schema_version` | int | currently `1`; loaders should tolerate change |
| `gazepoint_model` | str | e.g. `GP3HD` |
| `input_mode` | str | `eye` / `gaze_switch` / `switch` |
| `calibration_error_px` | float\|null | mean calibration error (data QC) |
| `calibration_points` | int\|null | 5 or 9 |
| `tasks` | list[str] | tasks run this session |
| `notes` | str | free text |

## trials.csv

One row per completed trial.

| column | type | meaning |
|--------|------|---------|
| `trial_id` | int | 0-based index within the task |
| `task_id` | str | task identifier |
| `target_x`, `target_y` | float | target center, normalized |
| `target_radius_px` | float | hitbox radius |
| `t_target_shown_ns` | int | target onset |
| `t_first_gaze_on_target_ns` | int\|"" | first gaze inside hitbox |
| `t_click_ns` | int\|"" | selection time (blank if miss/timeout) |
| `t_end_ns` | int | trial end |
| `is_hit` | 0/1 | target selected |
| `is_timeout` | 0/1 | timed out |
| `attempts` | int | selections attempted (off-target switch presses count) |
| `reaction_time_ms` | float\|"" | `t_click - t_target_shown` |
| `time_to_first_fixation_ms` | float\|"" | `t_first_gaze_on_target - t_target_shown` |

Directly loadable with `pandas.read_csv` or R.

## gaze_stream.csv

One row per rendered frame.

| column | type | meaning |
|--------|------|---------|
| `t_ns` | int | capture time |
| `x`, `y` | float | gaze point, normalized |
| `valid` | 0/1 | tracker-reported validity |
| `fixation_id` | int\|"" | FPOGID (blank if not fixating) |
| `fix_duration_s` | float\|"" | fixation duration so far |
| `pupil_left`, `pupil_right` | float\|"" | pupil diameter (mm), v2 analysis |

## all_gaze.csv and fixations.csv

Gazepoint Analysis's own export layout, reproduced from the raw `<REC>`
stream so the session reads like an Analysis export (`gp3tools` etc.) —
`specs/SPEC-gazepoint-analysis-export-parity.md`. Off with
`recording.save_all_gaze: false`.

- **One row per `<REC>` received at device rate** (150 Hz on USB 3), not per
  rendered frame — so it has more rows than `gaze_stream.csv`.
- **62 columns in Analysis's order and spelling**: `MEDIA_ID`, `MEDIA_NAME`
  (the task id), `CNT`, `TIME(<recording start>)` (seconds from the first
  record), `TIMETICK(f=<Hz>)`, the FPOG/BPOG fields, cursor/keyboard/`USER`,
  pixel pupil (`LPCX`…`RPV`), blinks (`BKID`/`BKDUR`/`BKPMIN`), mm pupil
  (`LPMM`…`RPMMV`), biometrics (always 0 — the kit is not subscribed),
  `PIXS`/`PIXV`, `AOI` (always blank), `SACCADE_MAG`, `SACCADE_DIR`,
  `VID_FRAME` (always 0). Device values are written verbatim.
- **`SACCADE_MAG`/`SACCADE_DIR`** are filled at session close on each
  fixation's row: pixel distance and angle (0–360°, counter-clockwise from
  +x, screen-up positive) from the previous fixation's POG, scaled by the
  **tracked monitor** size in `metadata.json` (`screen_width_px` ×
  `screen_height_px`) — never by the canvas. Zero elsewhere.
- **`fixations.csv`** = the rows Analysis would export: the last `FPOGV=1`
  record of each `FPOGID`, excluding the recording's final record, with
  zero-duration fixations dropped. Both rules are golden-tested against a
  real Analysis v7.3.0 export (`tests/fixtures/gazepoint_analysis_sample/`).

Geometry fields in `metadata.json` (all additive, `null` when unknown):
`screen_width_px`/`screen_height_px` (tracked monitor, from `SCREEN_SIZE`),
`canvas_width_px`/`canvas_height_px`/`canvas_offset_x_px`/`canvas_offset_y_px`
(where the task scene sat on it), `screen_physical_width_mm`/`_height_mm`
(config, else the OS/EDID value), `viewing_distance_mm` (config). These let
`session_metrics.json`'s `saccades` block report amplitude in degrees of
visual angle as well as px.

## events.jsonl

One JSON object per line: `{"t_ns": ..., "kind": "...", ...payload}`.
Kinds: `TARGET_SHOWN`, `HIT`, `TIMEOUT`, `MISS_CLICK`.

## Versioning

`schema_version` is written into every `metadata.json`. Downstream loaders
should branch on it and tolerate older layouts (plan §8 risk mitigation).
