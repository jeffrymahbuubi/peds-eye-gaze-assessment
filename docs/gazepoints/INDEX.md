---
title: "Gazepoint GP3 HD Onboarding Corpus — Index"
device: GP3 HD (150 Hz)
built: 2026-08-27
parser: NetMind parse_pro (netmind-parse-pdf-mcp 0.1.7)
---

# Gazepoint GP3 HD Onboarding Corpus

Knowledge corpus for onboarding the **Gazepoint GP3 HD eye tracker (150 Hz)**, built from the
ten vendor PDFs in `resources/gazepoints/documents/`.

The corpus has two layers:

- **`sources/`** — one file per source PDF, verbatim. Full fidelity, traceable to the original.
  Use these when you need the exact vendor wording.
- **`synthesis/`** — derived topic files that pull scattered facts together for onboarding.
  Nothing here is new information; every claim traces to a file in `sources/`.

## Synthesis (start here)

| File | Covers |
|---|---|
| [synthesis/gp3-hd-specifications.md](synthesis/gp3-hd-specifications.md) | GP3 HD specs, how they differ from the 60 Hz GP3, biometrics module specs, host requirements |
| [synthesis/setup-and-calibration.md](synthesis/setup-and-calibration.md) | End-to-end runbook: unbox → mount → position → install → calibrate |
| [synthesis/api-reference.md](synthesis/api-reference.md) | Open Gaze API protocol and the complete configuration-command table |
| [synthesis/data-fields-reference.md](synthesis/data-fields-reference.md) | Every data field, cross-referenced between the API `<REC>` stream and the Analysis CSV export |
| [synthesis/troubleshooting.md](synthesis/troubleshooting.md) | All troubleshooting guidance consolidated, by symptom |

## Sources (verbatim)

| File | Source PDF | Pages | Revision |
|---|---|---|---|
| [sources/gazepoint-quick-start.md](sources/gazepoint-quick-start.md) | gazepoint_quick_start.pdf | 3 | not stated |
| [sources/gp3-placement-and-positioning.md](sources/gp3-placement-and-positioning.md) | GP3_Placement_and_Positioning.pdf | 1 | not stated |
| [sources/gazepoint-vesa-mount.md](sources/gazepoint-vesa-mount.md) | gazepoint_vesa_mount.pdf | 4 | not stated |
| [sources/gazepoint-laptop-mount.md](sources/gazepoint-laptop-mount.md) | gazepoint_laptop_mount.pdf | 2 | not stated |
| [sources/gazepoint-control.md](sources/gazepoint-control.md) | Gazepoint Control.pdf | 14 | March 10, 2025 |
| [sources/gazepoint-analysis.md](sources/gazepoint-analysis.md) | Gazepoint Analysis.pdf | 27 | December 9, 2025 |
| [sources/gazepoint-api.md](sources/gazepoint-api.md) | Gazepoint API.pdf | 30 | March 11, 2025 |
| [sources/gazepoint-biometrics.md](sources/gazepoint-biometrics.md) | Gazepoint Biometrics.pdf | 11 | December 3, 2023 |
| [sources/gazepoint-remote-viewer.md](sources/gazepoint-remote-viewer.md) | Gazepoint Remote Viewer.pdf | 9 | February 2, 2020 |
| [sources/gazepoint-mobile.md](sources/gazepoint-mobile.md) | Gazepoint Mobile.pdf | 14 | Reference Guide V4 |

## The product family, in one paragraph

**GP3** and **GP3 HD** are the desktop eye trackers; the HD samples at 150 Hz over USB 3.0, the
standard GP3 at 60 Hz over USB 2.0. **GP3-Mobile** is a separate stand-mounted rig for phone/tablet
studies. **Gazepoint Control** is the capture application and API server — it must be running for
anything else to receive data. **Gazepoint Analysis** is the recording and analysis application
(Standard / Professional / UX editions). **Gazepoint Biometrics** is an optional hardware module
adding GSR/EDA, heart rate, a self-report dial, and TTL I/O. **Remote Viewer** is an add-on that
streams the Analysis display to observers on another machine.

## Provenance and caveats

- All ten PDFs were parsed with NetMind's `parse_pro` engine, which recovered the specification
  tables and figure captions with correct row/column structure.
- **Identifier corrections.** NetMind reliably mangles underscores in code identifiers — it read
  `TIME_TICK` as `TIME tick`, `VALID_POINTS` as `VALIDPOINTS`, `CALIBRATE_SHOW` as `CALIBRATEShow`,
  `AOI_EXPORT` as `AOIXPORT`, and `NSURLSession WebSocket` as `NSIROLSession WSocket`. Because exact
  identifier spelling is the entire value of an API corpus, every affected token was cross-checked
  against an independent `pdftotext` extraction and corrected — **39 occurrences across three
  files**, concentrated in the API manual. Each correction is itemised in that file's
  `parser_corrections` frontmatter, so the edits are auditable rather than silent. A verification
  pass confirms every `SCREAMING_SNAKE` identifier present in the PDF text layer is present in the
  corpus. This is the one respect in which `sources/` is not byte-verbatim.
- **Figures are not extracted.** Each image is marked `[FIGURE]` with its original caption retained
  where the document had one. Several procedures (mount assembly, Control UI) reference figures
  that are not reproduced here — consult the source PDF when a step is visual.
- Page headers, footers, and copyright lines were dropped by the parser as page furniture.
- Revision dates are the vendor's own "Revised …" line. Note the spread: Remote Viewer's manual
  dates from 2020 and Biometrics from 2023, so those are likelier to lag the shipping software
  than Control, Analysis, or the API doc.
- **One unresolved conflict between sources** regarding USB hubs — see
  [synthesis/setup-and-calibration.md](synthesis/setup-and-calibration.md#usb-connection-conflict).
