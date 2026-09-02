# Data Schema

Each session writes one folder under the output root (default `sessions/`):

```
sessions/2026-07-15_P001_click_static/
  metadata.json      # subject + session + calibration + schema_version
  session.log        # human-readable timeline
  gaze_stream.csv    # per-frame gaze samples
  trials.csv         # one row per trial (analysis-ready)
  events.jsonl       # discrete events (TARGET_SHOWN, HIT, TIMEOUT, MISS_CLICK)
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

## events.jsonl

One JSON object per line: `{"t_ns": ..., "kind": "...", ...payload}`.
Kinds: `TARGET_SHOWN`, `HIT`, `TIMEOUT`, `MISS_CLICK`.

## Versioning

`schema_version` is written into every `metadata.json`. Downstream loaders
should branch on it and tolerate older layouts (plan §8 risk mitigation).
