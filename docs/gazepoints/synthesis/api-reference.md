---
title: "Open Gaze API Reference"
layer: synthesis
derived_from:
  - sources/gazepoint-api.md
  - sources/gazepoint-control.md
built: 2026-08-27
---

# Open Gaze API Reference

Protocol summary and complete command table for the Open Gaze API, the interface Gazepoint Control
exposes to third-party programs. For per-field data documentation see
[data-fields-reference.md](data-fields-reference.md); for full vendor wording see
`sources/gazepoint-api.md`.

## What it is

Published in 2010 as an open alternative to proprietary eye-tracker protocols. The design
constraint is that it requires **no DLLs, libraries, or language-specific components** — just a
TCP/IP socket carrying XML. Any language with sockets can talk to it.

| Property | Value |
|---|---|
| Transport | TCP/IP socket |
| Default port | **4242** (configurable in Control Settings; must match Analysis) |
| Localhost address | `127.0.0.1` — client and server need not be on the same machine |
| Payload | XML strings |
| Delimiter | Carriage return + line feed (`\r\n`) after every record |
| Server | Gazepoint Control (must be running) |

## Message shapes

The **client** sends two tags:

| Tag | Purpose |
|---|---|
| `<SET ID="…" … />` | Write a value to a server variable |
| `<GET ID="…" />` | Read a server variable (same form, no value parameter) |

The **server** replies with four:

| Tag | Meaning |
|---|---|
| `<ACK … />` | Command succeeded |
| `<NACK … />` | Command failed |
| `<CAL … />` | Calibration progress and results |
| `<REC … />` | A data record |

Plus `<UPDATE … />`, sent to all clients when the active eye tracker changes in a multi-tracker setup.

A minimal exchange:

```xml
CLIENT: <SET ID="CALIBRATE_SHOW" STATE="1" />
SERVER: <ACK ID="CALIBRATE_SHOW" STATE="1" />
CLIENT: <GET ID="CALIBRATE_SHOW" />
SERVER: <ACK ID="CALIBRATE_SHOW" STATE="1" />
```

Actual bytes on the wire include the delimiter:
`"<SET ID=\"CALIBRATE_SHOW\" STATE=\"1\" />\r\n"`

## Typical session

1. Open a TCP socket to the server (`127.0.0.1:4242` for a local setup).
2. Enable the data records you want with the relevant `ENABLE_SEND_*` commands.
3. `<SET ID="ENABLE_SEND_DATA" STATE="1" />` to start the stream.
4. Read `<REC … />` lines as they arrive.

Only the fields you explicitly enable appear in each `<REC>`.

## Configuration commands

| Command | Parameters | Type | Access | Purpose |
|---|---|---|---|---|
| `ENABLE_SEND_DATA` | `STATE` | boolean | R/W | Start/stop the whole data stream |
| `ENABLE_SEND_*` | `STATE` | boolean | R/W | Enable an individual data field (see list below) |
| `CALIBRATE_START` | `STATE` | boolean | R/W | Start/stop the calibration process |
| `CALIBRATE_SHOW` | `STATE` | boolean | R/W | Show/hide the calibration window |
| `CALIBRATE_TIMEOUT` | `VALUE` | float > 0 | R/W | Duration of each calibration point, excluding animation |
| `CALIBRATE_DELAY` | `VALUE` | float ≥ 0 | R/W | Animation duration before a point's calibration begins |
| `CALIBRATE_RESULT_SUMMARY` | `AVE_ERROR`, `VALID_POINTS` | — | Read only | Average error in pixels, and count of successful points |
| `CALIBRATE_CLEAR` | `PTS` | — | R/W | Clear the internal calibration point list |
| `CALIBRATE_RESET` | `PTS` | — | R/W | Reset the point list to defaults |
| `CALIBRATE_ADDPOINT` | `X`, `Y` | float | R/W | Add a point, as a fraction of screen width/height |
| `USER_DATA` | `VALUE`, `DUR` | string, int | R/W | Embed custom data in the stream. `DUR=0` persists (default), `DUR=1` applies to one record |
| `TRACKER_DISPLAY` | `STATE`, `TRAY` | boolean | R/W | Show/hide the tracker window; `TRAY=1` minimises to system tray |
| `TIME_TICK_FREQUENCY` | `FREQ` | long long | Read only | Divisor to convert `TIME_TICK` to seconds |
| `SCREEN_SIZE` | `X`, `Y`, `WIDTH`, `HEIGHT` | integer | R/W | Get or set the tracked screen — how you target a monitor in a multi-monitor setup |
| `CAMERA_SIZE` | `WIDTH`, `HEIGHT` | integer | Read only | Camera sensor size in pixels (e.g. 752 × 480) |
| `PRODUCT_ID` | `VALUE`, `BUS`, `RATE` | string | Read only | `GP3`/`GP3HD`, `USB2`/`USB3`, `60`/`150` |
| `SERIAL_ID` | `VALUE` | string | Read only | Hardware serial number |
| `COMPANY_ID` | `VALUE` | string | Read only | Manufacturer — returns `GAZEPOINT` |
| `API_ID` | `VALUE` | string | Read only | API version |
| `TRACKER_ID` | `ACTIVE_ID`, `MAX_ID`, `SEARCH` | int, int, string | R/W (`MAX_ID` read only) | Select the active tracker; `SEARCH` ∈ `NONE`, `SIMPLE`, `CURSOR`, `GAZE` |
| `MARKER_PIX` | `VALUE`, `STATE` | float, boolean | R/W | Marker size in mm, and marker tracking on/off |
| `AAC_FILTER` | `VALUE` | integer | R/W | Moving-window average length for the AAC (assistive) POG |
| `TTL_WRITE` | `CHANNEL`, `VALUE` | integer | R/W | Channel 0–6. `VALUE` −1 = input, 0/1 = output state |

Source: `sources/gazepoint-api.md` §3.

### The ENABLE_SEND_* family

Each data field is enabled independently:

```
ENABLE_SEND_COUNTER      ENABLE_SEND_TIME         ENABLE_SEND_TIME_TICK
ENABLE_SEND_POG_FIX      ENABLE_SEND_POG_LEFT     ENABLE_SEND_POG_RIGHT
ENABLE_SEND_POG_BEST     ENABLE_SEND_POG_AAC
ENABLE_SEND_PUPIL_LEFT   ENABLE_SEND_PUPIL_RIGHT
ENABLE_SEND_EYE_LEFT     ENABLE_SEND_EYE_RIGHT
ENABLE_SEND_CURSOR       ENABLE_SEND_KB           ENABLE_SEND_BLINK
ENABLE_SEND_PUPILMM      ENABLE_SEND_DIAL         ENABLE_SEND_GSR
ENABLE_SEND_HR           ENABLE_SEND_HR_PULSE     ENABLE_SEND_HR_IBI
ENABLE_SEND_TTL          ENABLE_SEND_PIX          ENABLE_SEND_USER_DATA
```

## Calibration over the API

Trigger it with two commands:

```xml
<SET ID="CALIBRATE_SHOW"  STATE="1" />
<SET ID="CALIBRATE_START" STATE="1" />
```

The server then streams `<CAL />` records:

| Record | Sent when | Parameters |
|---|---|---|
| `CALIB_START_PT` | At the start of a point's **animation** | `PT` (1..N), `CALX`, `CALY` |
| `CALIB_RESULT_PT` | At the end of a point's **calibration** | `PT`, `CALX`, `CALY` |
| `CALIB_RESULT` | Once, at the end of the whole process | Per point `?`: `CALX?`/`CALY?` (target), `LX?`/`LY?`/`LV?` (left eye estimate + valid), `RX?`/`RY?`/`RV?` (right eye) |

`CALIB_RESULT` is what you want for programmatic quality assessment — it gives the estimated
point-of-gaze at every calibration target for each eye separately, plus a per-eye validity flag.
For a single quality number, `CALIBRATE_RESULT_SUMMARY` returns average error in pixels and the
count of valid points.

## Multiple eye trackers

Several trackers can share one machine, each below its own screen and calibrated on it. Use
`TRACKER_ID` to select the active one or enable automatic switching. On a switch, every connected
client receives:

```xml
<UPDATE ACTIVE_ID="1" MAX_ID="2" X="0" Y="0" WIDTH="1920" HEIGHT="1080" >
```

## Sample code and integrations

Bundled with the installer at `C:\Program Files (x86)\Gazepoint\Gazepoint\demo\`
(32-bit: `C:\Program Files\Gazepoint\Gazepoint\demo\`). Copy the folder elsewhere — e.g. the
desktop or `C:\temp\` — before compiling, since Windows blocks writes inside `Program Files`.

| Item | Description |
|---|---|
| `GPClient` class | MFC class in `\Demo\Include\` wrapping all API tasks; used by every Gazepoint app |
| C++ `apiclient` | Enumerates API commands so you can fire them one at a time — the best way to watch the protocol |
| C++ template | Minimal connect / send / print-incoming-data skeleton |
| Matlab | Sample source demonstrating API use |
| C#, Python | Example code also provided in the demo folder |
| Fruit Ninja Eyeblades | Full demo shipped as a Visual Studio project |

**Lab Streaming Layer.** `Gazepoint/demo/lsl/LSLGazepoint.py` streams Control's data to an LSL
recorder. Requires PyLSL. It opens two streams: `GazepointEyeTracker` (fixation-filtered
point-of-gaze) and `GazepointBiometrics` (dial, GSR, heart rate). Start Control first, then run the
script.

## Version history

| Version | Changes |
|---|---|
| 2.0 | Replaced GPI with the simpler `USER` field; added `CALIBRATE_CLEAR`/`ADDPOINT`/`RESET`; removed `CALIBRATE_FAST`, `TRACK_WINDOW`, and `MFG_ID` from `API_ID` |
| 2.1 | Blink tracking fields |
| 2.2 | Updated mouse button tracking states |
| 2.3 | Multi-tracker commands |
| 2.4 | `USER_DATA` single-record mode; biometrics system, pupil in mm, dial, heart rate, GSR, marker tracking |
| 2.5 | `TRACKER_DISPLAY` can minimise to system tray |
| 2.6 | Heart rate pulse signal; GSR and HR changed float → int |
| 2.7 | `APOG` — filtered FPOG for assistive communication (e.g. Microsoft Eye Control) |
| 2.8 | HR changed int → float; added `HRIBI`; `TTL1` now carries 6 digital states in one record; added `TTL_WRITE`; added keyboard keystroke tracking |

Note the type churn on `HR` and `GSR` across 2.6 and 2.8 — worth pinning the API version
(`API_ID`) if you write a parser against them.

## Direct serial access to the biometrics module

Normally Control reads the biometrics hardware and merges it into the API stream, synchronised with
everything else — which is the recommended path, since Control adds validity checks. Direct access
over the virtual COM port at **115,000 baud** is possible:

| Command | Effect |
|---|---|
| `q` | Query system version — e.g. `<ACK ID="GAZEPOINT" VER="2.0" />` |
| `v <#>` | Select response format: `1` = V1.x string, `2` = V2.x string, `3` = V2.x compact |
| `s` | Send a single data string |
| `r` | Send a continuous stream |
| `e` | End the stream |
| `t <ch> <val>` | Set TTL I/O. `<ch>` 0–7; `<val>` 0/1 switches the channel to an output at that value, −1 resets it to an input |

In the V2.x string, `T` is timestamp, `D` dial, `B` beats per minute, `H` heart rate pulse,
`HV` heart-rate valid, `I` interbeat interval, `G` GSR, `T0` the analog channel, `T1` the digital
channels. Source: `sources/gazepoint-biometrics.md` §6.
