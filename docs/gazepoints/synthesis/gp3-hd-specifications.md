---
title: "GP3 HD Specifications"
layer: synthesis
device: GP3 HD (150 Hz)
derived_from:
  - sources/gazepoint-control.md
  - sources/gazepoint-biometrics.md
  - sources/gazepoint-api.md
  - sources/gazepoint-mobile.md
built: 2026-08-27
---

# GP3 HD Specifications

All figures below are the vendor's, from the specification tables in the Control and Biometrics
manuals. The **GP3 HD** column is the device this project onboards.

## Eye tracker

| Specification | GP3 | **GP3 HD** |
|---|---|---|
| Sampling rate | 60 Hz | **150 Hz** |
| Accuracy | 0.5 – 1 degree | 0.5 – 1 degree |
| Spatial resolution (RMS) | 0.1 | 0.1 |
| Eye tracking mode | Binocular | Binocular |
| Operating distance | 50 cm – 80 cm | 50 cm – 80 cm |
| Tracking range (head box) | 25 cm x 11 cm | **35 cm x 22 cm** |
| Calibration | 5 or 9 point | 5 or 9 point |
| Tracking recovery time | < 50 ms | **< 20 ms** |
| System latency | < 50 ms (end to end, event to API output) | < 50 ms (end to end, event to API output) |
| Data connection | USB 2.0 | **USB 3.0** |
| Dimensions | 235 mm x 43 mm x 47 mm | 235 mm x 43 mm x 47 mm |
| Weight | 115 g | 123 g |
| Eyewear compatibility | Works with most glasses and contact lenses | Works with most glasses and contact lenses |

Source: `sources/gazepoint-control.md` §2.

### What the HD actually buys you

Four things differ, and only four:

1. **150 Hz instead of 60 Hz** — 2.5× the temporal resolution. This is the headline difference and
   the reason to care about saccade-level analysis.
2. **USB 3.0 instead of USB 2.0** — not a bonus but a *requirement*; see the warning below.
3. **A head box roughly 2.8× larger by area** (35 × 22 cm vs 25 × 11 cm) — participants can move
   more before tracking is lost.
4. **Tracking recovery under 20 ms instead of 50 ms** — faster reacquisition after a blink or
   look-away.

Accuracy, spatial resolution, operating distance, physical size, and eyewear tolerance are
identical. The HD is not a more *accurate* tracker; it is a *faster* one with more headroom.

> **The 150 Hz trap.** The GP3 HD only reaches 150 Hz on a **USB 3.0** port. On USB 2.0 it will
> connect and work — just not at full rate. Confirm the negotiated bus in the Gazepoint Control
> status bar (bottom right, the *Information* field, which reports USB2 or USB3), or query
> `PRODUCT_ID` over the API, which returns `VALUE`, `BUS`, and `RATE`. Expect
> `VALUE="GP3HD" BUS="USB3" RATE="150"`. A frame rate readout near 150 Hz (~6.7 ms) confirms it;
> ~62 Hz (~16.6 ms) means you are on the slow path.
> Source: `sources/gazepoint-control.md` §4.1, §6.5; `sources/gazepoint-api.md` §3.16.

Note also that the *Update Rate* control in Gazepoint Control offers both 60 Hz and 150 Hz, but on
a standard GP3 only 60 Hz is available.

## Host machine requirements

| Requirement | Specification |
|---|---|
| Processor | Intel i5 (i7 recommended) |
| Memory | 4 GB (8 GB recommended) |
| OS | Windows 8 / 10 / 11, 64-bit |

Source: `sources/gazepoint-control.md` §2.

Take the "recommended" column seriously at 150 Hz: the Control manual warns that a frame rate
below the nominal value means the host needs more CPU. Remote Viewer separately asks for an i7 if
you intend to run capture, analysis, and observer streaming on one machine.

## Biometrics module (optional hardware)

| Specification | GSR / EDA | Heart Rate | Self-Report Dial | TTL |
|---|---|---|---|---|
| Sampling rate | 60 Hz / 150 Hz | 60 Hz / 150 Hz | 60 Hz / 150 Hz | 60 Hz / 150 Hz |
| Input range | 10 kΩ – 10 MΩ (equivalently 0.1 μS – 100 μS) | 35 – 170 BPM | 0 % – 100 % | 0 V – 5 V |
| Sensitivity (ADC) | 10 bit, 4-stage auto gain | 10 bit, 2-stage auto gain | 10 bit | 10 bit |
| Input protection | Current limiting | Optical | N/A | 10k pullup |
| Frequency range | DC to 10 Hz | N/A | N/A | N/A |

Module-wide: **USB 2.0**, 30 mA power draw, Intel i5, 4 GB RAM, Windows 8/10/11 64-bit.
Source: `sources/gazepoint-biometrics.md` §2.

The biometrics sampling rate follows the tracker, so on a GP3 HD these channels also run at 150 Hz.
Two details worth internalising: the GSR input range is one quantity expressed two ways
(resistance and conductance, related by `1 μS = 1 / Ω × 1,000,000`), and the TTL block is
**7 channels** — channel 0 is a 10-bit analog input mapping 0–5 V onto 0–1023, and channels 1–6 are
digital. All channels are internally pulled high.

## GP3-Mobile (different product — for contrast)

Listed only to prevent confusion with the desktop GP3 HD; this project does not use it.

| Specification | GP3-Mobile |
|---|---|
| Sampling rate | 60 Hz or 150 Hz |
| Accuracy | 0.5° – 1° |
| Operating distance | 38 cm – 56 cm |
| Tracking range (head box) | 23 cm x 18 cm |
| Calibration | 5 point, via www.gp3mobile.com |
| Data connection | USB 3.0 × 2 |
| Dimensions | 23 cm x 28 cm x 16 cm |
| Weight | 1150 g |
| Supported device size | Max 15 inch screen width, 8 inch screen height |
| Processor / Memory / OS | Intel i5 or i7 or AMD Ryzen 7 / 8 GB / Windows 10 or 11 64-bit |

Source: `sources/gazepoint-mobile.md`. Note the shorter operating distance (38–56 cm vs 50–80 cm)
and the heavier host requirements — it is a stand-mounted rig, not a desk-mounted sensor.

## Identifying the device programmatically

Over the Open Gaze API:

```xml
<GET ID="PRODUCT_ID" />
<ACK ID="PRODUCT_ID" VALUE="GP3" BUS="USB2" RATE="60" />
```

`VALUE` is `GP3` or `GP3HD`, `BUS` is `USB2` or `USB3`, `RATE` is `60` or `150`. Related read-only
identifiers: `SERIAL_ID`, `COMPANY_ID` (returns `GAZEPOINT`), `API_ID` (API version),
`CAMERA_SIZE` (e.g. 752 × 480). See `synthesis/api-reference.md`.
