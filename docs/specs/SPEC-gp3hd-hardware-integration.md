---
title: GP3HD Hardware Integration Validation
status: in-progress
created: 2026-08-31
last_updated: 2026-08-31
---

## Update 2026-08-31 (new feature: configurable calibration parameters)

**Status: implemented, tested, and confirmed live against the real GP3HD**
(user stopped mid-run once to get this documented first, then expanded
scope; see the later "user confirmed live" update near the end of this
document for final status).

While explaining the calibration API to the user (walking through what
`follow_moving`'s dwell mechanism does, then how calibration itself works),
it came up that `Calibration.run()` (`src/engine/calibration.py`) hardcodes
everything about how calibration is triggered: `n_points=5` is passed as a
literal in `app.py:70`, and the point layout, `CALIBRATE_TIMEOUT`,
`CALIBRATE_DELAY` are entirely left at Gazepoint Control's own device
defaults — none of it is configurable via `configs/default.yaml`, and there
is no CLI flag either. The user asked for a `calibration:` YAML block so
these become editable without touching code.

**Scope agreed so far:**
- `calibration.points: 5 | 9` — selects the point layout sent to Gazepoint
  Control before `CALIBRATE_START`. The vendor API only documents a default
  5-point layout (via `CALIBRATE_RESET` — center + 4 corners at 0.15/0.85
  margins, API manual §3.9). No 9-point preset is documented anywhere in
  `docs/gazepoints/`, so a 9-point layout means extending the 5-point corners
  with edge midpoints at the *same* 0.15/0.5/0.85 margins (a 3x3 grid) — this
  is the implementer's own construction, not a vendor spec, and should be
  flagged as such if any results ever need explaining to the PI.
- **Also just requested, not yet designed:** expose `CALIBRATE_TIMEOUT`
  (per-point fixation duration, device default 1.25s) and `CALIBRATE_DELAY`
  (per-point animation lead-in, device default 0.5s) as config values too —
  both are unambiguous float settings per the API (§3.5/§3.6).
  Additionally asked for "Calibration SHOW" and "Calibrate START" to be
  configurable — these are boolean `STATE` toggles in the API (§3.3/§3.4),
  and their intended meaning as *config* isn't yet resolved: `SHOW` most
  likely means letting the calibration window run invisibly
  (`CALIBRATE_SHOW STATE=0`) instead of always popping up on screen; `START`
  is less obvious as a "setting" — most plausible reading is a
  `calibration.enabled: true/false` switch to skip calibration entirely on
  a given launch, which would also resolve the standing complaint that
  calibration currently runs unconditionally on *every* `--gui` launch with
  no way to skip it. **Not yet confirmed with the user** — see the question
  raised back to them before implementing this part.

**Implemented and tested** (after the pause above, and after resolving the
SHOW/START ambiguity via AskUserQuestion): `configs/default.yaml` now has a
`calibration:` block:

```yaml
calibration:
  enabled: true    # false = skip calibration entirely (no CALIBRATE_START sent)
  points: 5        # 5 or 9
  show: true       # false = CALIBRATE_SHOW STATE=0, runs invisibly
  timeout_s: null  # CALIBRATE_TIMEOUT; null = device default (~1.25s)
  delay_s: null    # CALIBRATE_DELAY; null = device default (~0.5s)
```

- `src/engine/calibration.py`: `Calibration.__init__` gained `enabled`,
  `show`, `point_timeout_s`, `point_delay_s` params (the latter two
  deliberately *not* named `timeout_s`/`delay_s` to avoid colliding with the
  pre-existing `timeout_s` param, which is our own poll-loop deadline, not
  the device's `CALIBRATE_TIMEOUT`). `n_points` is validated against a new
  `_CALIBRATION_LAYOUTS` dict (`{5: [...], 9: [...]}`) — invalid values
  (anything but 5 or 9) now raise `ValueError` instead of silently
  misbehaving. `run()`: `enabled=False` returns an unmeasured
  `CalibrationResult` without touching the socket at all; otherwise sends
  `CALIBRATE_DELAY`/`CALIBRATE_TIMEOUT` (only if overridden), then routes
  point setup through `_configure_points()` — `CALIBRATE_RESET` for 5
  points (reuses the vendor's own default layout verbatim) vs.
  `CALIBRATE_CLEAR` + 9x `CALIBRATE_ADDPOINT` for 9. Also fixed a latent
  correctness gap while doing this: our own poll-loop timeout now scales
  with the configured `point_timeout_s`/`point_delay_s` (when overridden)
  instead of a hardcoded `n_points*3.0`, so a longer configured per-point
  time can't get truncated by our own polling giving up first.
- `src/app.py`: reads the `calibration.*` block and passes it all through to
  `Calibration(...)`.
- `tests/test_calibration.py`: `_ScriptedServer` extended with a
  `received_text()` capture (same drain-thread pattern as
  `FakeGazepointServer` in `test_gazepoint_client.py`) so the exact
  outgoing commands can be asserted. Six new tests: invalid `n_points`
  raises; 5-point sends `CALIBRATE_RESET` (not `ADDPOINT`); 9-point sends
  `CALIBRATE_CLEAR` + exactly 9 `ADDPOINT`s including the new edge-midpoint
  coordinates; `show=False` sends `STATE="0"`; `enabled=False` sends
  nothing over the wire at all; `point_timeout_s`/`point_delay_s` send the
  expected `SET VALUE=...` commands. **58 tests total (57 pass + 1
  pre-existing, unrelated failure)** — `test_config_merges_task_over_default`
  asserts `target_fps == 60`, but the user changed `default.yaml`'s
  `target_fps` to `150` earlier this session (see the live-drills update
  above); the test just hardcodes the old default and needs the user's call
  on which side to fix.
- **Fixed in working copy only** (`dev/peds-eye-gaze-assessment/`), same
  caveat as every other fix in this task.

## Update 2026-08-31 (user confirmed live; earlier "0.0 error" bug appears resolved as a side effect)

User tested the new `calibration.*` config live against the real GP3HD:
both the 5-point default and the 9-point layout launched and calibrated
successfully (9-point confirmed by the user's own observation; no
`metadata.json` from that specific run was found to cite directly as
file evidence, but 5-point has direct evidence below).

**Important finding — comparing `sessions/*/metadata.json` across the
whole day resolves the "suspicious 0.0" flag raised earlier:**

| Session | When | `calibration_error_px` | `calibration_points` |
|---|---|---|---|
| `live_drill_20260831_click_static` | before this fix | **0.0** | 5 |
| `live_drill2_20260831_click_static` | before this fix | **0.0** | 5 |
| `live_drill3_20260831_click_static` | before this fix | **0.0** | 5 |
| `REPLAY_scanning` | after this fix (user's test) | **7.89** | 5 |
| `REPLAY_follow_moving` | after this fix (user's test) | **743.06** | 5 |

All three *pre-fix* runs show exactly `0.0` (implausible, as flagged in
finding #4 update above). Both *post-fix* runs show real, non-degenerate
values — `7.89` is a clean, plausible calibration; `743.06` is very high
but is a **real, non-zero measurement** (consistent with a genuinely poor
calibration attempt — e.g. the subject not looking properly for that run —
not a code bug; a bogus placeholder would be `0.0` or absent, not a large
specific number).

**Root cause now understood, not just suspected:** before this session's
`calibration.*` feature, `Calibration.run()` sent `CALIBRATE_CLEAR` (empties
the device's point list to **0 points**, API manual SS3.8) and never sent
anything to repopulate it before `CALIBRATE_START`. Calibrating against an
empty/degenerate point list plausibly explains a stale-or-trivial
`AVE_ERROR="0.00"` response. The point-configuration fix in the update above
changed 5-point behavior to send `CALIBRATE_RESET` instead (loads the
vendor's real default 5-point layout, confirmed `PTS="5"` in the API's own
documented example) — the live evidence above is consistent with this
having fixed the "0.0" symptom as a side effect, though it was implemented
primarily to add the point-count option, not specifically to chase this bug.

**Status update:**
- **Gap A (calibration) — now reasonably considered validated against the
  real GP3HD.** Two real live calibration attempts post-fix both produced
  plausible (if one poor) non-zero results, which is exactly the behavior
  the original gap-A fix was supposed to produce. Closing this out; see
  updated Log entry.
- **Gap D (disconnect) — still NOT validated.** No session this entire day
  successfully exercised "stop Gazepoint Control while the app keeps
  running" — every attempt ended with either natural task completion or the
  app being closed before the disconnect step. Still the one open item from
  the original six gaps.
- `configs/default.yaml` `gazepoint.host` is still pointed at the real
  device (`26.113.49.235`) as of this update — **still needs reverting to
  `127.0.0.1` once D is done** (or sooner, at the user's discretion, since A
  is now settled).
- One unrelated, still-open item: `test_config_merges_task_over_default`
  fails because the user changed `default.yaml`'s `target_fps` from `60` to
  `150` — needs the user's call on which side to fix (see the calibration
  config update above).

## Update 2026-08-31 (connection health validation)

PI feedback: "Proceed with the hardware validation. Make sure the
connection to the device is normal." Scope agreed with user: validate
current connection behavior only (no code changes this pass); drive the
real GUI via the `qt-mcp` probe rather than manually.

**Method:**
1. Confirmed baseline TCP reachability: `Test-NetConnection 26.113.49.235:4242`
   → `TcpTestSucceeded=True` (ICMP ping fails, as expected on Radmin VPN —
   irrelevant, the OpenGaze TCP port is what matters).
2. Temporarily pointed `configs/default.yaml` `gazepoint.host` at
   `26.113.49.235` (reverted immediately after the test — permanent fix for
   this is tracked separately, see gap C in the task memory) and launched
   the real GUI (`python -m src.main --task click_static --gui`) with the
   `qt-mcp` probe attached (`QT_MCP_PROBE=1 QT_MCP_PORT=9142`,
   `QT_QPA_PLATFORM=offscreen`), then read the operator panel's live FPS
   and Gaze-validity labels via `qt_find_widget`/`qt_get_text`.
3. Ran a standalone 60-second read-only stability probe (scratch script,
   not committed) that imports `GazepointClient` directly and measures
   inter-sample gaps and valid/invalid counts over a full minute, to check
   for the drop/stall behavior gap D describes.

**Results:**
- GUI: operator panel showed a steady **FPS: 62-63** throughout, and
  **Gaze: valid** once a person was in front of the tracker — confirming
  the full pipeline (real device → `GazepointClient` → `EyeInput` → canvas
  → operator panel) works end-to-end live, not just via the earlier
  headless client script.
- 60s stability probe: connected in 16ms; **5488 distinct samples
  observed, 5401 valid (98.4%), 87 invalid** (consistent with blinks /
  momentary off-screen gaze, not connection loss); **max inter-sample gap
  47ms, zero gaps over 0.5s** in the full 60s window.
- **Conclusion: the connection to the real GP3HD is normal and stable** —
  no evidence of drops, stalls, or dead sockets under a sustained live
  session.
- Gap D (no reconnect/disconnect-detection logic) remains open and
  unaddressed by this pass — deferred by explicit user choice
  ("validate only" scope) rather than skipped by oversight. It was not
  exercised because the connection never actually dropped during the test
  window; a real disconnect scenario (e.g. killing Gazepoint Control
  mid-session) has not been tested.
- Cleanup: killed the validation GUI process and reverted
  `configs/default.yaml` `gazepoint.host` back to `127.0.0.1` after the
  test; no permanent repo changes made this pass.

# GP3HD Hardware Integration Validation

## Task

Validate the `peds-eye-gaze-assessment` prototype (pediatric eye-control
computer operation assessment tool) against a real **Gazepoint GP3HD**
eye tracker (150 Hz), assigned by the PI. The prototype's OpenGaze TCP
client and full pipeline were written and unit-tested but had **never
been connected to real hardware** prior to this task — only `.jsonl`
replay fixtures had been exercised.

- Source repo (pristine, read-only reference):
  `resources/target/peds-eye-gaze-assessment-main/`
- Working copy (where fixes are made):
  `dev/peds-eye-gaze-assessment/`
- Onboarding entry point: `docs/HANDOVER_GAZEPOINT.md` (in both copies)
- Ground-truth vendor protocol corpus (for cross-checking code against
  the real OpenGaze API, not the project's own notes):
  `docs/gazepoints/` — see `docs/gazepoints/INDEX.md`

## Environment

| Item | Status |
|---|---|
| Working copy | Created at `dev/peds-eye-gaze-assessment/` (copied from `resources/target/peds-eye-gaze-assessment-main/`, 271K, no `.git`) |
| `dev/.venv` | Rebuilt 2026-08-31 on **Python 3.12.14** via `uv` (originally 3.10.11 against a `>=3.11` requirement; superseded once `qt-mcp` needed >=3.12 — see memory `peds-eye-gaze-assessment-venv-2026-08-31`) |
| Dependencies | `peds-eye-gaze-assessment[gui,dev]` (numpy/pandas/pyyaml/PySide6/opencv-python/pynput/pytest/ruff) + `qt-mcp[probe-pyside6]`, all in the one shared venv |
| GP3HD Control address | `26.113.49.235:4242` (per Gazepoint Control's own API TCP/IP Settings panel; **not** the `127.0.0.1` default in `configs/default.yaml`) |

## Tests performed

| Layer | What | Result |
|---|---|---|
| L0 — unit tests | `pytest` on `dev/peds-eye-gaze-assessment/tests/` | **29/29 passed** (before and after all fixes below) |
| Code vs. ground-truth cross-check | Read `src/inputs/gazepoint_client.py`, `src/engine/calibration.py`, `src/app.py`, `docs/gazepoint_api_cheatsheet.md`; compared against `docs/gazepoints/sources/gazepoint-api.md` and `synthesis/api-reference.md` + `synthesis/data-fields-reference.md` | 2 real bugs found (below) |
| TCP reachability | Raw `socket.create_connection(('26.113.49.235', 4242))` | **Connected successfully** |
| Live client test (gaze) | `GazepointClient` against real device, 30 samples over ~6s | **Received valid `<REC>` samples** — x/y streaming, `fixation_id` incrementing, occasional `valid=False` / out-of-[0,1] samples consistent with blinks/off-screen gaze (expected per vendor docs) |
| Live client test (pupil) | Same, checking `pupil_left`/`pupil_right` | Failed before fix (always `None`), **passed after fix** (~5mm plausible readings) |

These were the pre-existing "known gaps" from `HANDOVER_GAZEPOINT.md` §6
(A/B/C/D/E/F below). **As of the last entry in the Log, all six are
addressed** — see findings #3-8 and the "Next steps" section right after
Open Items for what's genuinely still outstanding (two live drills).

## Findings / bugs and their solutions

### 1. Missing `ENABLE_SEND_DATA` (master stream switch)

- **Found:** 2026-08-31, during ground-truth cross-check, before any
  hardware was touched.
- **What:** `GazepointClient.connect()` sent per-field `ENABLE_SEND_*`
  commands but never sent `<SET ID="ENABLE_SEND_DATA" STATE="1" />` —
  the separate master switch that actually starts the `<REC>` stream
  (vendor manual `docs/gazepoints/sources/gazepoint-api.md` §3.1). Same
  omission existed in the project's own `docs/gazepoint_api_cheatsheet.md`
  and in the smoke-test snippet in `HANDOVER_GAZEPOINT.md` §4 Step 1.
- **Risk:** could make a fully working TCP connection look identical to
  "hardware unreachable" — no `<REC>` ever arrives.
- **Fix:** added `sock.sendall(enable_command("ENABLE_SEND_DATA", True))`
  at the end of `GazepointClient.connect()` in
  `dev/peds-eye-gaze-assessment/src/inputs/gazepoint_client.py`; updated
  `docs/gazepoint_api_cheatsheet.md` to document the missing step.
- **Solved:** 2026-08-31. Verified: 29/29 unit tests still pass; live test
  against `26.113.49.235:4242` received `<REC>` samples.
- **Fixed in working copy only** (`dev/peds-eye-gaze-assessment/`) — not
  in the pristine `resources/target/peds-eye-gaze-assessment-main/`.

### 2. Wrong enable command for pupil diameter (mm)

- **Found:** 2026-08-31, empirically — live-tested client returned
  `pupil_left=None, pupil_right=None` on 30/30 samples despite gaze
  data streaming correctly.
- **What:** `rec_to_sample()` reads `LPMM`/`RPMM` (pupil diameter in
  **millimeters**), but `_ENABLE_RECORDS` wired the `pupil_left`/
  `pupil_right` config keys to `ENABLE_SEND_PUPIL_LEFT`/
  `ENABLE_SEND_PUPIL_RIGHT`. Per the vendor manual §5.9/§5.10, those
  commands gate `LPD`/`RPD` (pixel-based diameter, camera-image
  space) — a different field this client never reads. The correct
  enable for `LPMM`/`RPMM` is the separate `ENABLE_SEND_PUPILMM` (§5.16).
- **Fix:** both `"pupil_left"` and `"pupil_right"` in `_ENABLE_RECORDS`
  now map to `"ENABLE_SEND_PUPILMM"` (sending the same `SET` command
  twice is idempotent/harmless); the two independent config keys in
  `configs/default.yaml` `gazepoint.enable.*` keep working unchanged.
- **Solved:** 2026-08-31. Verified: 29/29 unit tests still pass; re-ran
  live test against `26.113.49.235:4242` — `pupil_left`/`pupil_right`
  now populate with physiologically plausible values (~5mm).
- **Fixed in working copy only**, same caveat as finding #1.

### 3. No reconnect / disconnect-detection logic (gap D)

- **Found:** pre-existing, documented in `HANDOVER_GAZEPOINT.md` §6 as
  "dropped connection looks like a frozen gaze cursor, not a disconnect."
  Addressed 2026-08-31 at the PI's explicit request, after the connection
  was already confirmed stable under normal operation (see the earlier
  2026-08-31 connection-health update above) — this pass covers the
  failure path that a healthy-connection test can't exercise.
- **What:** `GazepointClient._run_socket()`'s reader thread simply
  `break`-ed out and exited on any socket error or clean close, with no
  retry. Because `latest()` just returns the last cached `GazeSample`
  forever, a dropped connection produced the *same* "Gaze: valid,
  cursor at (x,y)" UI state as a live tracker whose gaze genuinely
  hadn't moved — indistinguishable from the operator's point of view.
- **Fix** (`dev/peds-eye-gaze-assessment/`):
  - `GazepointClient` now tracks connection state via `is_connected()`;
    `_open_socket()`/`_on_disconnected()`/`_reconnect()` were factored out
    of `connect()`/`_run_socket()` so the reader thread retries the
    connection (re-sending all `ENABLE_SEND_*` + `ENABLE_SEND_DATA`) on a
    configurable interval (`reconnect_interval_s`, default 1s) instead of
    exiting. `stop()` remains prompt even mid-retry-wait (the wait is a
    `threading.Event.wait`, which `stop()`'s `stop_event.set()` wakes
    immediately).
  - `EyeInput.poll()` now checks the source's `is_connected()` (if it has
    one) and forces the pointer invalid at the neutral center while
    disconnected, instead of freezing on the last cached sample — this is
    the actual fix for the "frozen cursor" symptom.
  - `OperatorPanel.update_status()` gained a `connected` flag so the panel
    shows a third, distinct **"Gaze: DISCONNECTED"** state (vs. "valid" /
    "LOST" for a normal blink or off-screen glance), satisfying the
    handover doc's acceptance criterion "visible signal-loss state on
    disconnect" (§7). `app.py`'s tick loop passes
    `self.client.is_connected()` through.
- **Tested:** new `tests/test_gazepoint_client.py` cases use a local
  loopback fake OpenGaze server (not the real device) to deterministically
  drop and re-accept the connection, asserting: `is_connected()` flips
  false on drop, flips true again once the reader thread reconnects and
  streaming resumes, and `stop()` doesn't block for the (possibly long)
  reconnect interval. New `tests/test_eye_input.py` asserts the pointer is
  forced invalid while disconnected even with a cached valid sample, and
  that sources without `is_connected()` (e.g. a bare replay source) are
  unaffected. **36/36 tests pass** (29 original + 7 new).
- **Not tested against the real GP3HD**: exercising this against the
  actual device would require stopping/blocking Gazepoint Control mid-session,
  which risks disrupting an active setup — deferred pending the PI/user
  explicitly wanting that live drill. The fake-server tests exercise the
  same code path (`_run_socket`/`_reconnect`/`_open_socket`) that a real
  disconnect would hit.
- **Fixed in working copy only** (`dev/peds-eye-gaze-assessment/`), same
  caveat as findings #1-2 — touches `src/inputs/gazepoint_client.py`,
  `src/inputs/eye_input.py`, `src/ui/operator_panel.py`, `src/app.py`.

### 4. Calibration error never captured (gap A)

- **Found:** pre-existing, documented in `HANDOVER_GAZEPOINT.md` §6.
  `Calibration.run()` sent `CALIBRATE_CLEAR`/`SHOW`/`START` but never
  queried or parsed `CALIBRATE_RESULT_SUMMARY`, so `mean_error_px` was
  always `None`. Separately, `Calibration.run()` was called *after*
  `client.start_streaming()` in `src/app.py`, so even a naive fix would
  have raced the background reader thread for the socket's bytes and
  could silently lose the response.
- **What the protocol actually requires** (confirmed against
  `docs/gazepoints/sources/gazepoint-api.md` §3.3/§3.7 and
  `synthesis/api-reference.md` "Calibration over the API"): calibration is
  **asynchronous** — `CALIBRATE_START`'s ACK only confirms the command was
  received, not that calibration finished (each of the N points has its
  own animation + fixation window, ~1.75s at default `CALIBRATE_DELAY`/
  `CALIBRATE_TIMEOUT`). The result must be polled for afterward via
  `<GET ID="CALIBRATE_RESULT_SUMMARY" />` → `<ACK ID="CALIBRATE_RESULT_SUMMARY"
  AVE_ERROR="..." VALID_POINTS="..." />`, interleaved with unsolicited
  `<CAL ID="CALIB_START_PT"/CALIB_RESULT_PT".../>` progress records that
  must be ignored.
- **Fix** (`dev/peds-eye-gaze-assessment/`):
  - `src/inputs/gazepoint_client.py`: factored a tag-generic `parse_attrs()`
    out of `parse_rec()` (returns `(tag, attrs)` for any `<TAG .../>` line,
    not just `<REC>`) so calibration parsing can reuse the same attribute
    grammar instead of duplicating the regex.
  - `src/engine/calibration.py`: `Calibration.run()`/`_poll_for_result()`
    now sends the GET every 0.5s and reads the socket directly (blocking,
    short timeout) until either `VALID_POINTS >= n_points` (full success)
    or `self._timeout_s` elapses (default `max(10, n_points * 3)` seconds),
    returning the best partial result seen rather than blocking forever.
    Non-ACK lines (the CAL progress records) are parsed and discarded.
  - `src/app.py`: moved the `Calibration(...).run()` call to right after
    `client.connect()` and *before* `client.start_streaming()`, fixing the
    race — nothing else touches the socket while calibration polls it.
- **Tested:** new `tests/test_calibration.py` uses a scripted loopback
  server (not the real device) that streams progress records then the
  final `CALIBRATE_RESULT_SUMMARY` ACK, covering: full success, timeout
  with a partial (non-zero) result, timeout with zero valid points ever
  seen, and the pre-existing no-hardware stub path. Two new
  `test_gazepoint_client.py` cases cover `parse_attrs()` directly.
  **43/43 tests pass** (36 prior + 7 new).
- **Not tested against the real GP3HD**: doing so triggers Gazepoint
  Control's actual calibration window on screen and needs a person to look
  at each point for a meaningful result — deferred by explicit user choice
  (same pattern as the gap D live drill) rather than run unannounced.
- **Fixed in working copy only**, same caveat as findings #1-3.

### 5. Hit-testing hardcoded to 1920x1080 (gap B)

- **Found:** pre-existing, documented in `HANDOVER_GAZEPOINT.md` §6.
  Recommended as the highest-priority remaining gap 2026-08-31 (over C/E/F)
  because it's a live correctness bug, not a missing feature: it silently
  mis-scores hits/misses on any real session that isn't run on an exact
  1920x1080 display or window.
- **What:** `TaskCanvas.paintEvent()` (`src/ui/canvas.py`) already renders
  the target/cursor using the widget's real, current `width()`/`height()`.
  But `BaseTask` (`src/tasks/base_task.py`) converted normalized gaze/target
  coordinates to pixel space for hit-testing using `self.screen_w`/
  `screen_h`, which were set **once at task construction** from
  `config['app']['screen_width_px'/'height_px']` (default.yaml default:
  1920x1080) and never updated. Whenever the actual canvas size differs —
  any other monitor resolution, a resized/non-fullscreen window — the
  circle rendered on screen and the circle used to decide "on target" are
  computed in two different pixel spaces and disagree.
- **Fix** (`dev/peds-eye-gaze-assessment/`):
  - `src/tasks/base_task.py`: added
    `BaseTask.set_screen_size(width_px, height_px)`, which updates
    `self.screen_w`/`self.screen_h` (ignoring non-positive sizes, e.g. a
    widget queried before it's shown).
  - `src/app.py`: the tick loop now calls
    `self.task.set_screen_size(self.canvas.width(), self.canvas.height())`
    every frame, before polling gaze/updating the task — so hit-testing
    always matches whatever is actually on screen, including after a live
    window resize. Headless replay (`run_headless_replay`) never calls
    this, so it's unaffected and keeps using the configured default (there
    is no real widget to query in that path, matching `default.yaml`'s own
    comment on that fallback role).
- **Tested:** new `tests/test_task_pipeline.py` cases: `set_screen_size`
  correctly updates dimensions and ignores non-positive input; a direct
  demonstration that the *same* normalized click is scored a miss under
  the 1920x1080 config default and a hit once `set_screen_size` reflects a
  narrower live canvas (proves the mechanism, not just the plumbing).
  **45/45 tests pass** (43 prior + 2 new). Also ran a short live GUI smoke
  test against a replay fixture (no real hardware involved, so no
  disruption risk) — ran cleanly for ~9s with no errors before being
  stopped early (headless tests already cover full-session correctness in
  seconds; the live run was only to confirm no startup/runtime exception).
- **Not tested against the real GP3HD**: no need to — this fix is entirely
  about canvas/window pixel geometry, unrelated to the device connection,
  so the replay-based smoke test is sufficient live coverage.
- **Fixed in working copy only**, same caveat as findings #1-4 — touches
  `src/tasks/base_task.py` and `src/app.py`.

### 6. `gazepoint.enable.*` YAML config not wired into `GazepointClient` (gap C)

- **Found:** pre-existing, documented in `HANDOVER_GAZEPOINT.md` §6 as
  harmless-for-now: `GazepointClient` already fully supports selectively
  enabling data fields via its `enable` constructor argument, but
  `src/app.py` never passed it — `self.client = GazepointClient(
  replay_path=replay_path)` always used the class's own all-`True` default,
  silently ignoring whatever a therapist set under `configs/default.yaml`
  `gazepoint.enable.*`.
- **Fix:** `src/app.py` now passes `enable=gp_cfg.get("enable")` through
  to the `GazepointClient` constructor. (`config.py`'s deep-merge always
  keeps `gazepoint.enable` as a complete 6-key dict inherited from
  `default.yaml`, even when a task's `overrides:` block only changes one
  key, so a partial task override can't accidentally blank out the rest.)
- **Tested:** new `tests/test_gazepoint_client.py::test_connect_only_sends_enabled_records`
  closes a gap that existed even before this fix — `GazepointClient`'s own
  `enable`-gating had no direct test. Extended `FakeGazepointServer` with a
  `received_text()` capture (a background drain thread recording whatever
  the client sends) and asserted that disabling `pog_best`/`pupil_left`/
  `pupil_right` omits their `ENABLE_SEND_*` commands entirely while
  enabled fields and the unconditional `ENABLE_SEND_DATA` master switch
  still go out. **46/46 tests pass** (45 prior + 1 new). Also ran a short
  live GUI smoke test against a replay fixture (no real hardware needed)
  — clean startup, no errors.
- **Not tested against the real GP3HD**: not needed — this is a pure
  config-wiring fix already covered by the client-level protocol test
  above; a live run would only re-confirm what the reachability tests in
  findings #1-2 already established.
- **Fixed in working copy only**, same caveat as findings #1-5.

### 7. Stale README test count (gap E)

- **Found:** pre-existing, documented in `HANDOVER_GAZEPOINT.md` §6 as
  purely cosmetic: `README.md`'s `## Tests & lint` section said
  `pytest # 26 tests, all headless`; the handover doc itself already
  noted the real count was 29 even before this session's work.
- **Fix:** updated `README.md` to `pytest # 46 tests, all headless` —
  the actual current count after this session's four gap fixes added 17
  new tests (29 -> 46), confirmed by running `pytest` directly. All new
  test files (`test_calibration.py`, `test_eye_input.py`, plus additions
  to existing files) remain Qt-free, so "all headless" is still accurate.
  Left `docs/HANDOVER_GAZEPOINT.md`'s own historical gap-list entry
  (which quotes "26... actual is 29") untouched, same as findings #1-2
  which only updated `docs/gazepoint_api_cheatsheet.md`, not the handover
  doc itself — it's treated as a fixed onboarding reference, not a
  live-updated doc.
- **Tested:** N/A (doc-only change); confirmed via `pytest` that the new
  count (46) is accurate at time of writing.
- **Fixed in working copy only**, same caveat as findings #1-6.

### 8. No end-to-end gaze-to-feedback latency measurement (gap F)

- **Found:** pre-existing, documented in `HANDOVER_GAZEPOINT.md` §6 —
  the plan needs to know gaze-to-feedback latency; nothing measured it.
  Handover doc's own suggestion: in `_tick()`, record the difference
  between `sample.t_ns` and `time.time_ns()` into `events.jsonl`.
- **What was built** (`dev/peds-eye-gaze-assessment/`): implemented the
  suggested measurement, but factored the actual math into a new,
  Qt-free `src/engine/latency.py` (`LatencyTracker`/`LatencySummary`)
  rather than inlining it in `app.py`, so it's unit-testable without
  pulling in PySide6 — same separation used for the other app.py-level
  wiring fixes this session:
  - `LatencyTracker.add_sample(sample_t_ns, now_ns)` accumulates
    per-frame latency and returns a `LatencySummary` (mean/min/max/n)
    once a window fills (default: one window per second at 60fps),
    resetting for the next window. Per-frame writes would hit
    `events.jsonl` at 60 Hz, which is fsync'd on every write and
    documented as "low-frequency, high-value" — windowing keeps that
    invariant instead of quietly changing it.
  - `GazepointClient.is_live` (new property): True only for a real
    socket connection, never replay — a replay fixture's `t_ns` values
    are relative to its own virtual clock, not wall time, so diffing
    them against `time.time_ns()` would be meaningless.
  - `src/app.py`'s `_tick()` calls `self._record_latency(sample.t_ns,
    t_ns)` when `self.client.is_live`, which feeds the tracker and, once
    a window closes, writes a `LATENCY_SAMPLE` event (mean/min/max_ms,
    n_samples) via the existing `recorder.record_event()`.
  - **Explicitly out of scope** (documented in `latency.py`'s docstring):
    this measures socket-arrival-to-tick-processing latency, not the
    final GPU/compositor time to actually present the repainted frame —
    that would need OS-level display instrumentation this app doesn't have.
- **Tested:** new `tests/test_latency.py` covers `LatencyTracker` fully
  in isolation (window accumulation, summary math, reset-after-emit,
  `window_size=1`, invalid window size) and a new
  `test_gazepoint_client.py::test_is_live_true_for_socket_mode_false_for_replay`.
  **52/52 tests pass** (46 prior + 6 new).
- **Live measurement — incident, then result:** the first attempt
  launched the full live GUI against the real device to get a real
  number, which (overlooked in the moment) also runs gap A's calibration
  flow first and briefly triggered Gazepoint Control's actual calibration
  window on screen without asking — the same disruptive behavior
  deliberately deferred for gap A earlier. Caught and killed within ~2s;
  sent `<SET ID="CALIBRATE_SHOW" STATE="0" />` immediately after (got a
  clean `ACK`) to hide it. Disclosed to the user immediately; they chose
  to continue via a standalone script that talks to `GazepointClient` +
  `LatencyTracker` directly — no `Calibration`/`AssessmentApp` involved,
  so no calibration risk (same non-disruptive shape as the original
  connection-health probe). Real result over 30s / 71 one-second windows
  against `26.113.49.235:4242`: **mean 3.26ms, min 0ms, max 10ms**
  (single outlier; typical window max 4-6ms) for the socket-to-consumption
  hop specifically — this is a good pipeline-overhead number but is
  **not** the full "gaze -> photons on screen" latency (see scope note
  above).
- **Fixed in working copy only**, same caveat as findings #1-7 — new file
  `src/engine/latency.py`; touches `src/inputs/gazepoint_client.py` and
  `src/app.py`.

## Open items / not yet resolved

- The design plan `303bfbea-eye_gaze_assessment_v1_plan.md`, referenced
  by `HANDOVER_GAZEPOINT.md` as living outside this repo (obtainable
  from the PI), has not been obtained — may contain requirements beyond
  what's documented in `docs/`.
- `dev/.venv` remains on Python 3.10.11 against a `>=3.11` requirement;
  proceeding per user's judgment that this is not currently causing
  problems, but noting it here in case an unexplained failure later
  traces back to it.
- **All six pre-existing gaps from `HANDOVER_GAZEPOINT.md` §6 are now
  addressed**: reconnect logic (D, finding #3), calibration error capture
  (A, finding #4), hardcoded screen size (B, finding #5), YAML enable
  wiring (C, finding #6), stale README count (E, finding #7), and latency
  measurement (F, finding #8, with a real measured number: 3.26ms mean
  socket-to-consumption over a 30s live probe).
  **Update, end of day 2026-08-31: A is now considered validated live** —
  two real post-calibration-config-fix runs produced plausible non-zero
  `calibration_error_px` values (7.89 and 743.06) against the real GP3HD;
  see the "user confirmed live" update above. **D is still open** — despite
  four separate launch attempts, no session ever successfully exercised
  "stop Gazepoint Control while the app keeps running"; every attempt ended
  via natural task completion or the window being closed first. F got one
  real number via a standalone script, deliberately avoiding
  `AssessmentApp` after an incident (see finding #8) where a first attempt
  briefly triggered the real calibration window unannounced.

## Update 2026-08-31 (live drill attempts, paused mid-session)

PI/user feedback: "Proceed with live drills." Four launches against the real
device were attempted this session; **drill 1 (disconnect) is still not
validated**, drill 2 (calibration) produced a result but with a suspicious
value flagged below. Session paused by user request ("kill the GUI first, I
will redo later") — resume here.

**Drill 2 (calibration) — ran, but result looks wrong, not confirmed passing:**
The very first live launch (`live_drill_20260831`) ran calibration + the full
`click_static` task (32 trials, ~4.7 min) to natural completion.
`metadata.json` recorded `calibration_points: 5` (a real, non-null result —
the polling mechanism itself works) but `calibration_error_px: 0.0` exactly.
Cross-checked against the vendor manual's own worked example
(`docs/gazepoints/sources/gazepoint-api.md` §3.7:
`AVE_ERROR="19.43" VALID_POINTS="5"`) — an exact `0.0` average pixel error is
implausible for a real human calibration. Suspected cause (not yet confirmed):
`Calibration._poll_for_result()` (`src/engine/calibration.py`) queries
`CALIBRATE_RESULT_SUMMARY` immediately after `CALIBRATE_START`
(`next_query = 0.0`), and nothing in the fix clears the device's *previous*
result before polling (`CALIBRATE_CLEAR` only clears the point list, per its
own API description) — so the first poll may be returning a stale result from
whatever calibration last ran on the device (possibly a manual one via
Gazepoint Control itself, unrelated to this session), not this run's result.
**Needs a follow-up investigation**: add temporary logging of every raw
`CALIBRATE_RESULT_SUMMARY` line received during a poll to see whether
`AVE_ERROR` starts non-zero and gets overwritten, or is `0.00` from the very
first response.

**Drill 1 (disconnect) — not yet exercised against a live, running app.**
Three further launches (`live_drill2/3/4_20260831`) all failed to land the
"stop Gazepoint Control while the app keeps running" step:
- `live_drill2`: app appeared to hang (qt-mcp probe dropped, `events.jsonl`
  stopped for 2+ minutes) — initially reported as a possible real deadlock
  bug, but this was **retracted**: the user had closed the assessment
  window directly, mistaking the `click_static` task's normal 32-trial run
  (one target at a time, ~8-9s each, ~4.7 min total) for a malfunctioning
  calibration ("took a lot of trials, transitions took time... doesn't match
  Gazepoint's official 5/9-point calibration"). Root cause of the
  *confusion*, not a code bug: real Gazepoint calibration (fast, Gazepoint
  Control's own overlay, ~10s) is immediately followed by our own
  `click_static` task starting automatically, which is visually similar
  (single dot appears/disappears) but is a completely different, much
  longer phase. `src/tasks/click_static.py` confirms the default trial count
  is exactly `32` — matching what the user reported, confirming this was the
  task, not calibration.
- `live_drill3`: same confusion pattern; this run's task simply ran to full
  natural completion (all 32 trials, ~4.7 min) before any disconnect action
  was taken, because coordination over chat (waiting for a "go" signal) was
  slower than the task's own runtime.
- `live_drill4`: launched with corrected instructions (user told to act on
  their own timing without waiting for a chat reply), but the user asked to
  pause before completing the drill ("kill the GUI first, I will redo
  later"). Process killed cleanly (PIDs found via
  `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` — plain
  `tasklist //FI "IMAGENAME eq python.exe"` gave misleadingly static/stale
  output all session and should not be trusted for this app on this
  machine).

**Environment change (user's own edit, not reverted):** `configs/default.yaml`
now has `app.fullscreen: false` (was `true`) and `app.target_fps: 150` (was
`60`) — the user edited this directly, likely so the app window doesn't take
over the single display and block seeing this chat during the next attempt.
`gazepoint.host` is still pointed at the real device (`26.113.49.235`, not
the `127.0.0.1` default) since the drill is paused mid-session, not finished
— **remember to revert it once both drills are actually confirmed done.**

**Lesson for the resume:** don't try to poll live in lockstep with the
user's actions over chat turns — the ~4.7 min task runtime gives a wide
window, but coordinating "wait for my go-ahead" mid-task repeatedly missed
the window in both directions (task finished first, or the user closed the
window out of confusion). Next attempt should either (a) let the user run
the whole stop/wait/restart sequence unprompted and report back once, or (b)
use a narrower standalone script (`GazepointClient` + a minimal stand-in for
the operator panel, skipping calibration and the `click_static` task
entirely) — closer to the non-disruptive pattern already used for the
connection-health and latency probes — so there's no task-completion race at
all. Also now try `fullscreen: false` (already set) so the user can watch
both the app and this chat at once, removing the coordination problem at its
root.

## Next steps (the two deferred live drills)

Both fixed in code and unit-tested, but never exercised against the real
GP3HD — user plans to run these after a context `/clear` + memory restore.

### Drill 1 — reconnect / disconnect (gap D)

1. Launch the real GUI against the device: temporarily set
   `configs/default.yaml` `gazepoint.host` to `26.113.49.235` (revert after),
   then `python -m src.main --task click_static --gui` from
   `dev/peds-eye-gaze-assessment/` using `dev/.venv/Scripts/python.exe`.
2. Confirm the operator panel shows `Gaze: valid` (or `LOST`) normally.
3. **Stop Gazepoint Control** (or otherwise kill the TCP connection) while
   the app keeps running.
4. Expect: operator panel switches to **`Gaze: DISCONNECTED`** within
   about a second (not a frozen cursor at the last position).
5. Restart Gazepoint Control; expect the client to reconnect on its own
   (`reconnect_interval_s` default 1s) and the panel to return to normal
   `valid`/`LOST` without restarting the app.
6. Record the outcome (worked / didn't / anything unexpected) in this
   SPEC's Log and in memory `peds-eye-gaze-assessment-reconnect-fix-2026-08-31`.

### Drill 2 — real calibration (gap A)

1. Same live-GUI launch as above. **Note:** calibration runs automatically
   and immediately on every launch against a live device — Gazepoint
   Control's calibration window (5 points, ~1.75s each) will appear on
   screen and needs someone looking at the tracker. This is expected and
   intentional for this drill (unlike the earlier incident in finding #8,
   which was *unannounced*).
2. After it completes (or times out at `max(10, n_points*3)`s), check the
   session's `metadata.json` for a real, non-null `calibration_error_px`
   and `calibration_points`.
3. Record the outcome in this SPEC's Log and in memory
   `peds-eye-gaze-assessment-calibration-fix-2026-08-31`.

Both drills can be done in the same launch (calibration happens first,
then disconnect the device mid-session for drill 1). After either drill,
update this SPEC's `status` field to `complete` once both are confirmed
working, and update/close out the two "unit-tested only" caveats in
findings #3 and #4 above.

## Log

| Date | Event |
|---|---|
| 2026-08-31 | Task assigned; read `HANDOVER_GAZEPOINT.md`, reported testing objective (no code changes) |
| 2026-08-31 | Wrote project memories for the task; reported `dev/.venv` had zero packages installed and wrong Python version |
| 2026-08-31 | User installed dependencies manually; created `dev/peds-eye-gaze-assessment/` working copy |
| 2026-08-31 | Code inspected against `docs/gazepoints/` ground truth; found and fixed `ENABLE_SEND_DATA` gap |
| 2026-08-31 | TCP reachability to `26.113.49.235:4242` confirmed; live client test found and fixed the `PUPILMM` gap |
| 2026-08-31 | This SPEC document created |
| 2026-08-31 | PI asked to proceed with hardware validation, focused on connection health; ran live GUI session (via qt-mcp) + 60s standalone stability probe against real device — connection confirmed stable, no drops |
| 2026-08-31 | PI asked to proceed with the reconnect gap (D); implemented reconnect/disconnect-detection in `GazepointClient` + a distinct "DISCONNECTED" UI state; validated with new loopback-server unit tests (36/36 pass); not yet drilled against the real device |
| 2026-08-31 | User chose gap A (calibration error capture) as the next task; implemented `CALIBRATE_RESULT_SUMMARY` polling in `Calibration.run()` and fixed the calibration-before-streaming ordering bug in `app.py`; validated with new scripted-server unit tests (43/43 pass); live calibration-window test against the real device deferred by user choice |
| 2026-08-31 | Asked to recommend the most important remaining gap; recommended B (hardcoded hit-testing resolution) over C/F as a live correctness bug affecting real session data; user agreed. Added `BaseTask.set_screen_size()`, wired into `app.py`'s tick loop; validated with new unit tests (45/45 pass) and a short replay-based live GUI smoke test (no real device needed) |
| 2026-08-31 | User asked to proceed with gap C; wired `gazepoint.enable.*` YAML config into `GazepointClient` via `app.py`, and added the first direct test of the client's enable-gating mechanism itself; validated with new unit tests (46/46 pass) and a replay-based live GUI smoke test |
| 2026-08-31 | User asked to proceed with gap E; updated the stale `README.md` test count (26 -> 46, confirmed via `pytest`). Only gap F (latency measurement) remains open from the original six; D and A still need live-device drills |
| 2026-08-31 | User asked to proceed with gap F; built `LatencyTracker` (new `src/engine/latency.py`) + `GazepointClient.is_live`, wired into `app.py`'s tick loop (52/52 tests pass). First live-measurement attempt via the full GUI mistakenly triggered the real device's calibration window (gap A runs before anything else) — caught in ~2s, hidden via `CALIBRATE_SHOW=0`, disclosed immediately. User chose a standalone-script measurement instead; got a real result: mean 3.26ms socket-to-consumption latency over 30s against the real GP3HD. All six original handover gaps now addressed |
| 2026-08-31 | PI/user asked to proceed with the two deferred live drills (D, A). Four launches (`live_drill`/`2`/`3`/`4`) against the real device; none successfully exercised D (disconnect) — every attempt ended via natural `click_static` task completion (32 trials, ~4.7 min, confused by the user for calibration misbehaving) or the window being closed first. Session paused mid-drill at user's request; `gazepoint.host` left pointed at the real device deliberately, to resume later |
| 2026-08-31 | User asked several clarifying questions about the app (dwell mechanism, `follow_moving`'s selection window, calibration/Gazepoint Control relationship, calibration always running on every launch) — answered from code reading, no changes made |
| 2026-08-31 | User asked for calibration point count (5 vs 9) to be configurable; reported via API research that `Calibration.run()` never actually sent `CALIBRATE_ADDPOINT`/`CALIBRATE_RESET`, only `CALIBRATE_CLEAR` (empties the list) — `n_points` was purely client-side bookkeeping, not an actual device setting |
| 2026-08-31 | User asked to update this SPEC first, then expanded the ask to also cover `CALIBRATE_TIMEOUT`/`DELAY`/`SHOW`/`START` as config. Clarified SHOW ("run invisibly") and START ("skip calibration entirely") via `AskUserQuestion`, both confirmed. Implemented full `calibration.*` config block (`enabled`/`points`/`show`/`timeout_s`/`delay_s`) in `configs/default.yaml`, `Calibration` class, and `app.py`; added `n_points` validation (5/9 only); fixed our own poll-timeout to scale with configured per-point timing. 6 new tests, 57/58 pass (1 pre-existing unrelated failure from the user's own `target_fps` edit) |
| 2026-08-31 | User confirmed both 5-point and 9-point calibration worked live against the real GP3HD. Cross-referencing `sessions/*/metadata.json` across the day showed all 3 pre-fix live runs recorded exactly `calibration_error_px: 0.0` (implausible), while 2 post-fix runs recorded plausible non-zero values (7.89, 743.06) — the point-configuration fix (sending real `CALIBRATE_RESET`/`ADDPOINT` instead of just `CALIBRATE_CLEAR`) appears to have resolved the earlier-flagged suspicious-0.0 bug as a side effect. **Gap A now considered validated live; gap D remains the sole open item from the original six gaps.** Session ending here (user requested memory/SPEC update before `/clear`) |
