# Pediatric Eye-Gaze Assessment Tool (v0.1)

兒童眼控電腦操作能力評估工具 — prototype.

A Windows-oriented tool for assessing children's eye-control computer operation
ability, designed to reduce the Compass floor effect for young beginners. It
supports **gaze dwell selection** (Gazepoint GP3HD) and **switch input**
(keyboard now, USB-HID/GPIO later), rich audiovisual feedback, and structured
data export for reliability/validity analysis.

See `../303bfbea-eye_gaze_assessment_v1_plan.md` for the full design plan.

## Highlights of this prototype

- **Runs with no eye tracker.** A deterministic *replay mode* reads a gaze
  fixture (`.jsonl`) so ~80% of development and all tests run headless.
- **Four tasks** implemented: `click_static`, `click_grid`, `follow_moving`,
  `scanning` (plan §5.5).
- **GUI-free core.** Inputs, dwell logic, task state machine, and data recording
  have no Qt dependency and are unit-tested. Only `src/ui/` and `src/app.py`
  import PySide6.
- **Therapist-editable YAML config** for target size, trial count, timeout,
  dwell threshold, theme (plan US-02).
- **Structured output** per session: `metadata.json`, `trials.csv`,
  `gaze_stream.csv`, `events.jsonl` (plan §5.7).

## Architecture

```
Presentation (PySide6)         src/ui/, src/app.py         [gui extra only]
        │
Task Engine ── Input Manager   src/tasks/, src/engine/, src/inputs/
        │
Data Recorder ── Storage       src/data/  → sessions/<id>/
```

Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the data
contract in [`docs/DATA_SCHEMA.md`](docs/DATA_SCHEMA.md).

## Install

```bash
# core (headless pipeline + tests) — no Qt needed
pip install -e ".[dev]"

# full GUI (Windows target)
pip install -e ".[gui,dev]"
```

## Run the headless replay demo (no hardware)

```bash
# regenerate the fixture (optional — one is committed)
python tools/make_replay_fixture.py tests/fixtures/gaze_replay.jsonl

# run a full "calibrate → task → export" loop against the fixture
python -m src.main --task click_static --replay tests/fixtures/gaze_replay.jsonl

# → sessions/replay_click_static_REPLAY/{trials.csv, gaze_stream.csv, ...}
```

Any of the four tasks works: `--task click_grid|follow_moving|scanning`.

## Run the GUI (needs the `gui` extra)

```bash
# with a paced replay (simulated tracker)
python -m src.main --task click_static --gui --replay tests/fixtures/gaze_replay.jsonl

# with a real Gazepoint GP3HD (Gazepoint Control running on 127.0.0.1:4242)
python -m src.main --task click_static --gui
```

Operator controls (right panel): pause/resume, skip trial, and a live dwell-
threshold slider — no restart needed to adapt to a child.

## Tests & lint

```bash
pytest        # 46 tests, all headless
ruff check .
```

## Analysis

`analysis/analyze_session.py` reads a session's `trials.csv`/`gaze_stream.csv`
and prints an RT summary + writes a gaze heatmap (see `docs/DATA_SCHEMA.md`).

## Development phases

Tracked in the plan (§6). This prototype covers Phase 0–3 core + the Phase 2
demo milestone ("calibrate → task → export") in headless form, plus the GUI
scaffold for Phase 3.
