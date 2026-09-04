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

Requires **Python >= 3.11** (see `pyproject.toml`); developed and tested on
**3.12** (pinned in `.python-version`).

```bash
# core (headless pipeline + tests) — no Qt needed
pip install -e ".[dev]"

# full GUI (Windows target)
pip install -e ".[gui,dev]"
```

### With `uv` (recommended — matches the dev environment exactly)

```bash
# uv reads .python-version automatically, so this creates a 3.12 venv
uv venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# core (headless pipeline + tests)
uv pip install -e ".[dev]"

# full GUI (Windows target)
uv pip install -e ".[gui,dev]"
```

If a specific machine doesn't have Python 3.12 installed, `uv venv --python 3.12`
will fetch and use it automatically without touching the system Python.

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

## Editing a config file locally without it showing up in `git status`

During experimentation you'll often want to hand-edit a tracked config file
(`configs/default.yaml`, a task file under `configs/tasks/`, a theme, ...) to
try different settings, without every tweak becoming a pending change to
commit or accidentally get pushed. Git's `skip-worktree` flag does this: the
file stays fully tracked (so a fresh clone still gets it with real content),
but local edits are hidden from `git status`/`git diff`/`git add -A` until
you explicitly turn tracking back on.

```bash
# Start freely editing a file locally — its future edits won't show up in git status
git update-index --skip-worktree configs/default.yaml

# Confirm which files currently have it set (look for a leading "S")
git ls-files -v | grep '^S'

# When you DO want a change in this file to actually ship, turn tracking back
# on first, otherwise `git add`/`git commit` will silently ignore your edits
git update-index --no-skip-worktree configs/default.yaml
```

Works the same way for any other tracked config (`configs/tasks/click_static.yaml`,
`configs/themes/forest.yaml`, etc.) — just substitute the path.

**Caveats:**
- This is a **local, per-clone git setting** — it is not committed or shared.
  Set it again on any other machine (e.g. the other laptop) where you want
  the same free-editing behavior.
- It's easy to forget it's on. If you make a config change you *do* want to
  ship and `git status` doesn't show it, check `git ls-files -v | grep '^S'`
  first — the file is probably still marked skip-worktree.
- `configs/default.yaml` currently has this set (as of 2026-09-03), reverted
  to its last committed value (`calibration.enabled: true`) beforehand.

## Adjusting target speed and pacing between trials

A physician testing the tool asked whether the moving target can go slower,
and whether there can be more of a pause between targets. Both are already
configurable per task in `configs/tasks/*.yaml` — this just spells out where.

**How fast the `follow_moving` target moves**, in `follow_moving.yaml`:

```yaml
motion:
  speed_frac_per_s: 0.20   # fraction of screen width the target crosses per second
  select_window_ms: 2500   # how long the target stays selectable once it's reachable
```

Lower `speed_frac_per_s` (e.g. `0.10`) for a slower-moving target. This only
applies to `follow_moving` — the other three tasks show a stationary target
per trial, so there's no "movement speed" to tune for them.

**The pause between one target and the next**, in every task's YAML:

```yaml
inter_trial_interval_ms: 800   # click_static/click_grid: 800, scanning: 900, follow_moving: 1000
```

Raise this (e.g. to `1500`) for a longer breather between targets. There's no
separate "appear" animation — the next target simply pops in the instant this
interval elapses, so this pause is the only adjustable gap between targets.

**How long a trial waits before giving up** is a separate, also per-task
setting that may be worth checking at the same time:

```yaml
timeout_ms: 8000   # click_static default; varies per task (see each task's YAML)
```

Edit `configs/tasks/<task>.yaml` (or use the `git update-index --skip-worktree`
trick above to try values without them showing up as a pending change), then
re-run the task to feel the new pacing. Full diagnosis behind these settings:
`docs/specs/SPEC-2026-09-02.md`, item 5.

## Tests & lint

```bash
pytest        # 80 tests, all headless
ruff check .
```

## Analysis

`analysis/analyze_session.py` reads a session's `trials.csv`/`gaze_stream.csv`
and prints an RT summary + writes a gaze heatmap (see `docs/DATA_SCHEMA.md`).

## Development phases

Tracked in the plan (§6). This prototype covers Phase 0–3 core + the Phase 2
demo milestone ("calibrate → task → export") in headless form, plus the GUI
scaffold for Phase 3.
