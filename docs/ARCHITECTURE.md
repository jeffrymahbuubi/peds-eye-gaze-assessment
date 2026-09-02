# Architecture

## Layering

```
┌─────────────────────────────────────────────┐
│ Presentation (PySide6)  src/ui/, src/app.py  │  <- gui extra only
└───────────────┬───────────────┬──────────────┘
                │               │
        ┌───────┴──────┐  ┌─────┴──────────────┐
        │ Task Engine  │  │ Input Manager      │
        │ src/tasks/   │◄─┤ EyeInput / Switch  │
        │ src/engine/  │  │ src/inputs/        │
        └───────┬──────┘  └────────────────────┘
                │
        ┌───────┴──────────┐   ┌──────────────┐
        │ Data Recorder    │──►│ sessions/... │
        │ src/data/        │   │ CSV + JSON   │
        └──────────────────┘   └──────────────┘
```

## Key design rule: GUI-free core

Everything below the presentation layer has **no Qt import**. This is what makes
the whole pipeline testable and lets ~80% of development happen with no eye
tracker (plan risk table). Concretely:

- `src/inputs/` — gaze parsing, replay, dwell logic, switch latch.
- `src/tasks/` — per-frame trial state machine, four task variants.
- `src/engine/` — config, feedback interface, calibration, task runner.
- `src/data/` — schema (dataclasses), streaming recorder, exporter.

Only `src/ui/` and `src/app.py` import `PySide6`. Tests never import them.

## Time model

All timestamps are nanoseconds in the `time.time_ns()` domain. The headless
pipeline advances a **virtual clock** (frame × 1/fps) and asks
`ReplayGazeSource.sample_at(elapsed_s)` for the gaze active at that instant — no
wall clock, no threads → fully reproducible runs and tests.

The live GUI uses a 60 Hz `QTimer` and real `time.time_ns()`, while the
`GazepointClient` reads the socket on a background thread and hands the newest
sample to the main thread under a lock.

## Frame loop (both headless and GUI)

```
t_ns = clock()
pointer = eye.poll(t_ns)          # gaze position (+switch click in switch mode)
recorder.record_gaze(sample)
result = task.update(t_ns, pointer)   # dwell/hit-test, trial state machine
canvas.set_frame(result...)       # GUI only
```

`BaseTask.update` owns the trial state machine
(`SHOW_TARGET → WAIT_INPUT → HIT/MISS/TIMEOUT → ITI → NEXT`) and, in eye mode,
feeds on-target hit-tests to a `DwellSelector`.

## Dwell selection

`DwellSelector` (`src/inputs/eye_input.py`) is a pure temporal accumulator:

- accumulate while on-target; trigger at `threshold_ms`;
- `refractory_ms` window blocks immediate re-trigger;
- `hold_grace_ms` tolerates brief drop-outs (child gaze is noisy);
- spatial jitter tolerance is applied by the task by widening the hitbox
  (`jitter_tolerance_px`).

## Extending

- **New task**: subclass `BaseTask`, implement `build_targets()` (and
  `target_position()` if it moves), register it in
  `engine/task_runner.py:TASK_REGISTRY`, add a `configs/tasks/<id>.yaml`.
- **New input**: implement something with `latest() -> GazeSample | None` (gaze)
  or feed `SwitchInput.press()` (switch); no engine change needed.
- **New tracker**: replace `GazepointClient` with any class exposing
  `latest()`; coordinates must be normalized (0–1).
