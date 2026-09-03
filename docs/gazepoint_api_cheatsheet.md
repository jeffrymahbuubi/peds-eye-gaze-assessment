# Gazepoint OpenGaze API — Cheatsheet

Working notes for the GP3HD integration (plan §5.1). The authoritative source is
the *Gazepoint Open Gaze API* PDF; this summarizes what v1 uses.

## Connection

- Gazepoint Control (Windows app) must be running; it hosts a TCP server on
  `127.0.0.1:4242`.
- Protocol is line-based XML over TCP. Each message ends with `\r\n`.

## Subscribing to data (SET ... ENABLE_SEND_*)

Send these to turn on the data records we need:

```
<SET ID="ENABLE_SEND_TIME" STATE="1" />
<SET ID="ENABLE_SEND_POG_FIX" STATE="1" />
<SET ID="ENABLE_SEND_POG_BEST" STATE="1" />
<SET ID="ENABLE_SEND_PUPILMM" STATE="1" />
<SET ID="ENABLE_SEND_CURSOR" STATE="1" />
```

**Correction (2026-09-02):** pupil diameter (`LPMM`/`RPMM`, millimeters) is
gated by the single `ENABLE_SEND_PUPILMM` command above (API manual §5.16),
not by `ENABLE_SEND_PUPIL_LEFT`/`ENABLE_SEND_PUPIL_RIGHT` as an earlier
version of this doc said — those two instead gate the *pixel*-based
`LPD`/`RPD` fields (§5.9/5.10), which this client does not read. The code's
`gazepoint.enable.pupil_left`/`pupil_right` config keys both map to the one
`ENABLE_SEND_PUPILMM` call (see `_ENABLE_RECORDS` in
`src/inputs/gazepoint_client.py`), kept as two keys only so they stay
independent on/off switches in `configs/default.yaml`.

`enable_command(record_id, state)` in `src/inputs/gazepoint_client.py` builds
these.

**Then start the stream itself** — the calls above only select which fields
*would* appear; the server does not send any `<REC .../>` until you also do:

```
<SET ID="ENABLE_SEND_DATA" STATE="1" />
```

(OpenGaze API manual §3.1 — this is a separate master switch, easy to miss.)

## Data records (REC)

The server then streams one `<REC .../>` per sample, e.g.:

```
<REC TIME="123.456" FPOGX="0.51" FPOGY="0.42" FPOGS="10.1" FPOGD="0.234"
     FPOGID="45" FPOGV="1" BPOGX="0.52" BPOGY="0.41" BPOGV="1"
     LPMM="3.1" RPMM="3.2" CX="0.5" CY="0.4" />
```

Fields used:

| attr | meaning |
|------|---------|
| `TIME` | seconds since tracker start |
| `FPOGX/Y` | fixation point of gaze, normalized 0–1 |
| `FPOGS` | fixation start time |
| `FPOGD` | fixation duration (s) |
| `FPOGID` | fixation id (increments per fixation) |
| `FPOGV` | fixation valid (0/1) |
| `BPOGX/Y` | best point of gaze (smoothed), normalized |
| `BPOGV` | best POG valid (0/1) |
| `LPMM/RPMM` | left/right pupil diameter (mm) |
| `CX/CY` | cursor position |

**Pointer choice:** we use `BPOG` when `BPOGV=1`, else fall back to `FPOG`.
Dwell selection keys off the fixation (`FPOGID`/`FPOGD`) staying on target.

## Calibration

```
<SET ID="CALIBRATE_CLEAR" />
<SET ID="CALIBRATE_SHOW" STATE="1" />
<SET ID="CALIBRATE_START" STATE="1" />
<GET ID="CALIBRATE_RESULT_SUMMARY" />
```

The result summary carries per-point accuracy; store the mean in
`metadata.calibration_error_px` for data-quality filtering. (Real parsing lands
when hardware is on-site — Phase 1.)

## Replay (no hardware)

`ReplayGazeSource` reads a `.jsonl` fixture. Each line is either a raw REC
attribute dict (has `FPOGX`) or a normalized sample dict
(`{"t_ns","x","y","valid",...}`). See `tools/make_replay_fixture.py`.
