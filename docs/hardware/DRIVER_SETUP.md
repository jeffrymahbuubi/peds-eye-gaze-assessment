# Gazepoint Driver Setup (not included in this repo)

This repo does **not** include the Gazepoint driver/software installer. It's a
~200 MB proprietary vendor binary, not source code, so it doesn't belong in
version control — install it separately on each machine that runs this app.

## Download

- Official download page: <https://gazept.com/downloads/>
- A **password is required** and is issued by Gazepoint at the time of
  hardware purchase (see `docs/gazepoints/sources/gazepoint-control.md` and
  `gazepoint-biometrics.md` in this repo).
- The version used during development of this prototype was **Gazepoint
  7.3.0** (`Gazepoint_7.3.0.exe`). Install that version or a newer compatible
  one, using the installer's default options.

## After installing

1. Launch **Gazepoint Control** and leave it running in the background. It
   opens an OpenGaze TCP server on `127.0.0.1:4242` that this app connects to.
2. Connect the GP3HD tracker and complete calibration in Gazepoint Control
   before running the app (see
   `docs/gazepoints/synthesis/setup-and-calibration.md`).
3. Run the app with `python -m src.main --task click_static --gui` (see the
   repo `README.md`).

For the wire protocol this app speaks to Gazepoint Control, see
[`../gazepoint_api_cheatsheet.md`](../gazepoint_api_cheatsheet.md) and
[`../HANDOVER_GAZEPOINT.md`](../HANDOVER_GAZEPOINT.md). For the full vendor
manuals this project's docs were distilled from, see
[`../gazepoints/`](../gazepoints/).
