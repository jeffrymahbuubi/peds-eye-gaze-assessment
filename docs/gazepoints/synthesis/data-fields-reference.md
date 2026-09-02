---
title: "Data Fields Reference — API stream and CSV export"
layer: synthesis
derived_from:
  - sources/gazepoint-api.md
  - sources/gazepoint-analysis.md
built: 2026-08-27
---

# Data Fields Reference

Every data field Gazepoint produces, cross-referenced between the two places you will meet it:
the live API `<REC />` stream and the Gazepoint Analysis CSV export. The names are largely
identical, which is convenient — but there are real differences, listed at the end.

## Coordinate conventions

Point-of-gaze X/Y values are **fractions of screen size**, not pixels:

- `(0, 0)` = top left
- `(0.5, 0.5)` = screen centre
- `(1.0, 1.0)` = bottom right

Values may be **negative or greater than 1** when gaze falls outside the screen. Pupil-centre
coordinates (`LPCX`, `RPCX`, …) use the same fractional convention but relative to the **camera
image**, not the screen.

**Which POG should you use?** For most applications, **`FPOG`** — it is the fixation-filtered
version of `BPOG` and is what the vendor recommends. `BPOG` ("best") is the average of left and
right eye when both are valid, otherwise whichever single eye is valid.

## Sequence and timing

| Field | Type | API enable | Description |
|---|---|---|---|
| `CNT` | int | `ENABLE_SEND_COUNTER` | Increments by 1 per record. Use it to detect dropped packets |
| `TIME` | float | `ENABLE_SEND_TIME` | Seconds since last system initialization or calibration. At 150 Hz it should advance by 1/150 s per record — a useful check that the host is keeping up |
| `TIME_TICK` | long long | `ENABLE_SEND_TIME_TICK` | Signed 64-bit CPU tick count for high-precision sync with other data on the same machine. Sourced from OpenCV's tick counter. Divide by `TIME_TICK_FREQUENCY` for seconds |

In the CSV export the time column is written as `TIME(DATE)`, where `DATE` is the wall-clock date
and time at which the recording started (e.g. `TIME(2024/08/22 08:28:26.460)`). That header is the
hook for synchronising with other acquisition systems such as EEG. Likewise `TIME_TICK(f)` carries
the tick frequency in its header, e.g. `TIME_TICK(f=10000000)`.

Note the subtle difference: in the **API** stream `TIME` is measured from system initialization or
calibration; in the **CSV** export it is measured from the start of the recording.

## Point of gaze

| Field | Type | Description |
|---|---|---|
| `FPOGX`, `FPOGY` | float | Fixation POG coordinates |
| `FPOGS` | float | Fixation start time, seconds |
| `FPOGD` | float | Fixation duration, seconds |
| `FPOGID` | int | Fixation ID, incrementing per new fixation |
| `FPOGV` | bool | Fixation valid flag |
| `LPOGX`, `LPOGY`, `LPOGV` | float, bool | Left eye POG and validity |
| `RPOGX`, `RPOGY`, `RPOGV` | float, bool | Right eye POG and validity |
| `BPOGX`, `BPOGY`, `BPOGV` | float, bool | Best (averaged) POG and validity |
| `APOGX`, `APOGY`, `APOGV` | float, bool | Assistive-communication POG and validity |

Enables: `ENABLE_SEND_POG_FIX`, `_POG_LEFT`, `_POG_RIGHT`, `_POG_BEST`, `_POG_AAC`.

> **`FPOGV` semantics matter.** It is TRUE **only** when at least one eye is detected **and** a
> fixation is detected. It is FALSE during blinks, when no face is in view, **and during saccades**.
> Treating FPOGV=0 as "tracking lost" will misclassify every saccade — the eye movements between
> fixations are, by definition, not fixations.

`APOG` is a moving-window average of `FPOG`, controlled by `AAC_FILTER`. The smoothing reduces
jitter to make eye-typing and similar assistive targeting practical. It is the signal used for
cursor control and Microsoft Eye Control.

## Pupil and eye position

| Field | Type | Description |
|---|---|---|
| `LPCX`, `LPCY` / `RPCX`, `RPCY` | float | Pupil centre in the camera image, as a fraction of image size |
| `LPD` / `RPD` | float | Pupil diameter in **pixels** |
| `LPS` / `RPS` | float | Pupil scale factor (unitless). 1 at calibration depth, < 1 when closer, > 1 when further |
| `LPV` / `RPV` | bool | Validity |
| `LEYEX/Y/Z`, `REYEX/Y/Z` | float | 3D eye position relative to the camera focal point, in **metres** |
| `LPUPILD` / `RPUPILD` | float | Pupil diameter in **metres** (same quantity as `LPMM`/`RPMM`) |
| `LPUPILV` / `RPUPILV` | bool | Validity |
| `LPMM` / `RPMM` | float | Pupil diameter in **millimetres** |
| `LPMMV` / `RPMMV` | bool | Validity |

Enables: `ENABLE_SEND_PUPIL_LEFT`, `_PUPIL_RIGHT`, `_EYE_LEFT`, `_EYE_RIGHT`, `_PUPILMM`.

> **For pupillometry, use `LPMM`/`RPMM`, not `LPD`/`RPD`.** The millimetre fields compensate for
> head movement; the pixel fields do not. Both manuals say this explicitly. If you must work in
> pixels, `LPS`/`RPS` tells you how far the participant has drifted from calibration depth, and
> marker tracking (`PIXS`) gives a precise pixels→mm factor.

## Blinks

| Field | Type | Description |
|---|---|---|
| `BKID` | int | Blink ID, incrementing per blink. **0 on every record where no blink was detected** |
| `BKDUR` | float | Duration of the *preceding* blink, seconds |
| `BKPMIN` | int | Blinks in the previous 60-second window |

Enable: `ENABLE_SEND_BLINK`.

`BKPMIN` is a rolling 60-second count measured from the start of *tracking*, not the start of the
*recording* — so the first values in a recording are typically non-zero and reflect the minute
before you hit record. Don't mistake that for a bug.

## Biometrics

| Field | Type | Description |
|---|---|---|
| `DIAL`, `DIALV` | float, bool | Self-report dial, 0 to 1 (documented as 0–100 %) |
| `GSR`, `GSRV` | int, bool | Skin resistance in **ohms**, typically 10 k to 2 M |
| `HR`, `HRV` | float, bool | Heart rate in BPM, averaged over 3 samples to suppress finger-motion artifacts |
| `HRP` | int | Heart rate pulse — unitless, proportional to an ECG signal, mostly the R peak |
| `HRIBI` (API) / `IBI` (CSV) | float | Interbeat (R–R) interval in seconds. **Unfiltered** |
| `TTL0` | int | Analog channel 0, 0–1023 |
| `TTL1` | string | API: 6 digital channel states concatenated, e.g. `111111` |
| `TTLV` | bool | Always 1 as of Biometrics V2.0 |

Enables: `ENABLE_SEND_DIAL`, `_GSR`, `_HR`, `_HR_PULSE`, `_HR_IBI`, `_TTL`.

Two cautions from the manuals. **GSR requires the sensor block to be plugged in** — unplugged, the
system measures its own internal resistances and can report plausible-looking but meaningless
values. And **`HRIBI` is unfiltered**: hand motion produces spurious peaks that are not heartbeats,
so plan on post-processing artifact removal if you are doing heart-rate-variability work.

The Analysis CSV adds derived GSR columns not present in the API stream:

| CSV column | Description |
|---|---|
| `GSR` | Ohms |
| `GSR_US` | Microsiemens |
| `GSR_US_TONIC` | Tonic component, μS |
| `GSR_US_PHASIC` | Phasic component, μS |

Conversion: `1 μS = 1 / Ω × 1,000,000`.

## Accessory inputs

| Field | Type | Description |
|---|---|---|
| `CX`, `CY` | float | Mouse cursor position as a fraction of screen size |
| `CS` | int | Cursor state: 0 idle, 1 left down, 2 right down, 3 left up, 4 right up |
| `KB` | string | Key pressed: `0`–`9`, `A`–`Z`, plus `LEFT`, `RIGHT`, `SPACE`, `RETURN`. A literal comma becomes `COMMA`; unrecognised keys become `OTHER` |
| `KBS` | int | Key state: 0 idle, 1 down, 2 up |
| `USER` | string | Arbitrary user-defined string — the standard hook for synchronisation markers |

Enables: `ENABLE_SEND_CURSOR`, `_KB`, `_USER_DATA`.

On a multi-monitor system the cursor origin `(0,0)` is the **primary** display, so `CX`/`CY` can go
below 0 or above 1 when the cursor is on a secondary screen.

Keyboard caveat: when typing quickly, Windows may report key release and the next key press out of
order, depending on press-and-hold settings. Press-and-hold yields a down, a delay, then repeated
down events. An idle `KBS` pairs with a blank `KB`; the Analysis export clears it to an empty string.

`USER` requires the API to set — see `USER_DATA` in [api-reference.md](api-reference.md). This is
the intended mechanism for aligning gaze data with an external acquisition system.

## Marker tracking

| Field | Type | Description |
|---|---|---|
| `PIXX`, `PIXY` | float | Marker position in the camera image, as a fraction of image size |
| `PIXS` | float | Scale factor: multiply a pixel measurement by `PIXS` to get millimetres |
| `PIXV` | bool | Validity |

Enable: `ENABLE_SEND_PIX`. Requires a printed marker of known size worn by the participant, with
the size declared via `MARKER_PIX`. The CSV export carries `PIXS` and `PIXV` only.

## CSV-only fields

These are computed by Gazepoint Analysis during export and have no API stream equivalent.

| CSV column | Type | Description |
|---|---|---|
| `SACCADE_MAG` | float | Saccade magnitude — distance between two fixations, in **pixels** |
| `SACCADE_DIR` | float | Saccade direction — angle between fixations, in **degrees from horizontal** |
| `VID_FRAME` | int | Video playback frame number at the time of the record |
| `MEDIA_ID`, `MEDIA_NAME` | int, string | Media item identity |
| `WEB_ID`, `WEB_TITLE`, `WEB_URL` | int, string, string | Web page item identity |
| `AOI` | string | Names of all visible AOIs containing the fixation POG, dash-joined, e.g. `AD1-FACE2-LEYE` |
| `AOINAME(X/Y/W/H)` | float or int | Position and size of a named AOI, as percent or pixels. 0 when the AOI is not visible |
| `AOINAME(Viewed)` | bool | Whether the AOI is currently viewed |

Both saccade fields read **0** on every record until the last valid record of a fixation, at which
point the magnitude and direction *from the previous fixation* are written. Do not read them as
per-sample values.

Because the tracker samples faster than video plays (150 Hz vs typically 30 Hz), expect several
consecutive records to share the same `VID_FRAME`.

`AOINAME(Viewed)` differs by file: in `_all_gaze.csv` it is 1 when that record's gaze fell inside
the AOI; in `_fixations.csv` it is 1 when the *fixation* is on the AOI. The all-gaze version is
what drives the summary statistics.

## Export file layout

Exporting from Analysis produces, per selected recording:

| File | Contents |
|---|---|
| `{RECORDING_NAME}_all_gaze.csv` | Every data record — the most detailed view |
| `{RECORDING_NAME}_fixations.csv` | One row per fixation |
| `Data_Summary_export_{DATETIME_LABEL}.csv` | AOI statistics per user plus averages across users |

Columns are individually selectable at export time. If biometrics data is present, each signal is
averaged over each AOI's duration and appears in the summary file.

### AOI summary statistics

`Media ID`, `Media Name`, `Media Duration` (`U` when user-controlled), `AOI ID`, `AOI Name`,
`AOI Start (sec)`, `AOI Duration`, `Viewers (#)`, `Total Viewers (#)`,
`Ave Time to 1st View (sec)` — **−1 if never viewed** — `Ave Time Viewed (sec)`,
`Ave Time Viewed (%)`, `Ave Fixations (#)`, `Revisitors (#)`, `Average Revisits (#)`,
`Average Clicks (#)`, `Ave Dial (0-1)`, `Ave GSR (kOhm)`, `Ave Heart Rate (BPM)`,
`Ave Interbeat Interval(s)`, `Ave Left Pupil (mm)`, `Ave Right Pupil (mm)`.

A *revisit* is a participant looking at an AOI, looking away, then looking back. Most averages are
computed over the subjects who actually viewed the AOI, not all subjects — `Average Clicks (#)` is
the exception, averaged over all.

Note `Ave GSR` is reported in **kΩ** here, while the per-record `GSR` field is in **Ω**.
