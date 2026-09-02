# Gazepoint Driver Setup (not included in this repo)

This repo does **not** include the Gazepoint driver/software installer. It's a
~200 MB proprietary vendor binary, not source code, so it doesn't belong in
version control — install it separately on each machine that runs this app.

## Download

- Official download page: <https://gazept.com/downloads/>
- A **password is required** and is issued by Gazepoint at the time of
  hardware purchase (see `docs/gazepoints/sources/gazepoint-control.md` and
  `gazepoint-biometrics.md` in this repo). It is **not stored in this repo,
  in this project's files, or anywhere in version control** — it's tied to
  the hardware purchase, not to the codebase, and must never be committed.
  If you don't have it, check the original purchase/order confirmation
  email from Gazepoint, or ask the PI / whoever ordered the GP3HD.
- The version used during development of this prototype was **Gazepoint
  7.3.0** (`Gazepoint_7.3.0.exe`). Install that version or a newer compatible
  one, using the installer's default options.

### Mirror (no vendor password needed)

The exact installer used for this project (`Gazepoint_7.3.0.exe`) is also
mirrored on Google Drive for convenience when setting up a new machine:

<https://drive.google.com/drive/u/1/folders/139tZCs8GnjL-AQKpE62YyHi7p09Spvth>

This link is tied to a personal Google account — make sure you're signed in
with an account that has access (or that the folder is shared with the
account you'll use on the new laptop) before relying on it.

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
