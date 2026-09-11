"""GUI application wiring (plan section 3.1 + Prompts 3/4).

Builds the QApplication, the gaze source (live Gazepoint or paced replay), the
task, the recorder, and a 60 Hz update loop that ties them together. Kept in its
own module so importing it (and thus PySide6) is opt-in — the headless pipeline
in :mod:`src.engine.task_runner` never touches this file.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QTimer, QUrl
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QApplication, QDialog

from .data.exporter import write_session_metrics
from .data.recorder import SessionRecorder
from .data.schema import SessionMetadata
from .engine.calibration import (
    Calibration,
    CalibrationFileError,
    CalibrationResult,
    calibration_timing_log_path,
    load_calibration_result,
    save_calibration_result,
)
from .engine.config import CONFIG_ROOT, deep_merge, load_task_config, load_theme
from .engine.gaze_diagnostics import GazeDropoutLog, gaze_dropout_log_path
from .engine.feedback import FeedbackBus
from .engine.latency import LatencyTracker
from .engine.sample_rate import SampleRateTracker
from .engine.session_naming import next_session_id
from .engine.task_runner import build_task
from .inputs.base import Pointer
from .inputs.eye_input import DwellConfig, EyeInput, SmoothingConfig
from .inputs.gazepoint_client import GazepointClient
from .inputs.switch_input import SwitchInput
from .ui.main_window import MainWindow, TaskRunView
from .ui.settings_registry import initial_live_values
from .ui.task_settings_dialog import TaskSettingsDialog


class GuiFeedback(FeedbackBus):
    """Feedback that drives on-canvas particles and short hit/miss sound cues.

    Sound loading is best-effort: a missing asset or a task/theme with no
    `sounds` block just means silence, never a crash (matches the tolerant
    style used elsewhere on this startup path, e.g. Calibration's stub mode).
    """

    # Deliberately below full volume: these cues need to never add to
    # sensory overstimulation for a child with sensory sensitivity, which
    # weighed into how the sound assets themselves were designed/generated
    # (SPEC-2026-09-02.md item 4 — short, soft, non-startling cues).
    _VOLUME = 0.6

    def __init__(self, canvas, theme: dict | None = None, feedback_cfg: dict | None = None) -> None:
        self.canvas = canvas
        theme = theme or {}
        feedback_cfg = feedback_cfg or {}
        self._hit_sound = (
            self._load_sound(theme, "hit") if feedback_cfg.get("hit_sound", True) else None
        )
        self._miss_sound = (
            self._load_sound(theme, "miss") if feedback_cfg.get("miss_sound", True) else None
        )

    @staticmethod
    def _load_sound(theme: dict, key: str) -> QSoundEffect | None:
        rel_path = theme.get("sounds", {}).get(key)
        if not rel_path:
            return None
        path = CONFIG_ROOT / rel_path
        if not path.exists():
            return None
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(path)))
        effect.setVolume(GuiFeedback._VOLUME)
        return effect

    def on_target_shown(self, x: float, y: float) -> None:
        pass

    def on_hit(self, x: float, y: float) -> None:
        self.canvas.burst(x, y)
        if self._hit_sound is not None:
            self._hit_sound.play()

    def on_miss(self, x: float, y: float) -> None:
        if self._miss_sound is not None:
            self._miss_sound.play()

    def on_progress(self, x: float, y: float, progress: float) -> None:
        pass


class AssessmentApp:
    def __init__(
        self,
        task_id: str,
        replay_path: str | None,
        subject_id: str,
        calibration_file: str | None = None,
        structural_overrides: dict | None = None,
        client: GazepointClient | None = None,
        preset_calibration_result: CalibrationResult | None = None,
        embedded: bool = False,
        on_finished: Callable[[], None] | None = None,
        assessment_date: str = "",
        sex: str = "",
        notes: str = "",
    ) -> None:
        """Build one task run.

        ``client``/``preset_calibration_result`` let a caller that already
        owns a connected :class:`GazepointClient` and a completed
        calibration (the Setup tab's dashboard, SPEC-ui-setup-task-
        selection.md S3.1.7) hand both in directly instead of this class
        connecting/calibrating again on every task run -- "nothing gets
        relaunched" was the explicit design decision. ``embedded`` builds a
        plain :class:`~src.ui.main_window.TaskRunView` (for the dashboard's
        ``QStackedWidget``) instead of a fullscreen
        :class:`~src.ui.main_window.MainWindow`, and routes end-of-task to
        ``on_finished`` instead of quitting the whole application. All four
        default to the exact standalone-launch behavior this class always
        had (own client, own calibration, own top-level window, quit on
        end) when omitted, so ``python -m src.main --task X --gui`` is
        unaffected.
        """
        self.config = load_task_config(task_id)
        self.task_id = task_id
        if structural_overrides:
            # Pre-launch-only structural params (grid size, radius, trial
            # count, ...) collected via TaskSettingsDialog -- SPEC-live-
            # settings-panel.md section 5.3. Reuses the exact merge a task
            # YAML's own `overrides:` block already goes through.
            self.config["task"] = deep_merge(self.config["task"], structural_overrides)
        theme_name = self.config.get("task", {}).get("theme") or self.config.get("theme", {}).get("name", "forest")
        self.theme = load_theme(theme_name)
        self.input_mode = self.config.get("input", {}).get("mode", "eye")

        # A run-index suffix (SPEC-ui-setup-task-selection.md S3.1.8) so a
        # same-day re-run of the same task for the same subject -- which the
        # dashboard's embed-in-place Run explicitly supports -- gets its own
        # directory instead of silently reusing (and overwriting) a prior
        # run's (SessionRecorder creates its directory with exist_ok=True).
        # Computed up front (not after calibration, as before) because an
        # auto-saved calibration.json needs the session dir to already be
        # known before Calibration.run() executes.
        output_root = self.config.get("recording", {}).get("output_root", "sessions")
        session_id = next_session_id(output_root, subject_id, task_id)
        session_dir = Path(output_root) / session_id

        # A --calibration-file is loaded and subject-checked before touching
        # the device at all, so a bad path or subject mismatch fails fast
        # without opening a socket or showing any calibration UI
        # (SPEC-2026-09-02.md item 7, Goal 1).
        preset_calibration = preset_calibration_result
        if calibration_file is not None:
            saved = load_calibration_result(calibration_file)
            if saved.subject_id != subject_id:
                raise CalibrationFileError(
                    f"Calibration file subject_id {saved.subject_id!r} does not match "
                    f"--subject {subject_id!r} ({calibration_file})"
                )
            preset_calibration = saved.result

        gp_cfg = self.config.get("gazepoint", {})
        # An externally-provided client is already connected (and possibly
        # already streaming, from a prior task run in the same dashboard
        # session) -- connect()/start_streaming() must not be called again
        # on it: connect() unconditionally reopens the socket and re-sends
        # every ENABLE_SEND_* command, which would be wasteful at best and
        # disruptive to an in-progress stream at worst. This class never
        # owns (and must never .stop()) a client it didn't create itself.
        self._owns_client = client is None
        if client is not None:
            self.client = client
        else:
            # `enable` here is the gazepoint.enable.* block (default.yaml keys:
            # time/pog_fix/pog_best/pupil_left/pupil_right/cursor) -- wiring it
            # through lets a therapist disable a data field via YAML instead of
            # it silently doing nothing (GazepointClient defaults to all-True
            # when enable=None, which is why this was harmless until now).
            self.client = GazepointClient(replay_path=replay_path, enable=gp_cfg.get("enable"))
            self.client.connect(host=gp_cfg.get("host", "127.0.0.1"), port=int(gp_cfg.get("port", 4242)))

        # Calibration must run before start_streaming(): it reads the socket
        # directly to poll CALIBRATE_RESULT_SUMMARY, and once the background
        # reader thread is consuming the same socket it will race for (and
        # can silently swallow) that response. A preset result (whether from
        # --calibration-file or handed in directly by the dashboard) skips
        # this device interaction entirely -- there's nothing to poll for.
        cal_cfg = self.config.get("calibration", {})
        if preset_calibration is not None:
            cal = preset_calibration
            # Recorded into THIS run's own session dir too, even though it
            # wasn't measured this run -- every session directory carries its
            # own self-contained calibration record, matching the fresh-
            # calibration branch below, and lets --calibration-file work
            # against any individual run's folder later.
            session_dir.mkdir(parents=True, exist_ok=True)
            save_calibration_result(session_dir / "calibration.json", subject_id, cal)
        else:
            calibration = Calibration(
                self.client,
                n_points=int(cal_cfg.get("points", 5)),
                enabled=bool(cal_cfg.get("enabled", True)),
                show=bool(cal_cfg.get("show", True)),
                point_timeout_s=cal_cfg.get("timeout_s"),
                point_delay_s=cal_cfg.get("delay_s"),
                timing_log_path=calibration_timing_log_path(output_root),
            )
            cal = calibration.run()
            if not calibration.is_stub:
                # A real calibration just ran (not the no-hardware/disabled
                # stub) -- auto-save it so a later launch can reuse it via
                # --calibration-file. No separate save flag, per the user's
                # 2026-09-04 design decision.
                session_dir.mkdir(parents=True, exist_ok=True)
                save_calibration_result(session_dir / "calibration.json", subject_id, cal)

        self.client.start_streaming()  # idempotent (GazepointClient no-ops if already streaming)

        # Single source of truth for every live-settings-panel field's
        # starting value (SPEC-live-settings-panel.md section 5.1) -- used
        # both to seed the operator panel's controls and to initialize the
        # live objects below, so the two can never drift apart.
        self._live_values = initial_live_values(self.config)
        lv = self._live_values

        self.eye = EyeInput(
            self.client,
            DwellConfig(
                threshold_ms=float(lv["dwell.threshold_ms"]),
                refractory_ms=float(lv["dwell.refractory_ms"]),
            ),
            SmoothingConfig(
                enabled=bool(lv["dwell.smoothing.enabled"]),
                alpha=float(lv["dwell.smoothing.alpha"]),
            ),
        )
        self.switch = SwitchInput()

        self._embedded = embedded
        self._on_finished = on_finished
        if embedded:
            # No top-level window at all -- the caller (DashboardWindow)
            # inserts .view into its own QStackedWidget page.
            self.window = None
            self.view = TaskRunView(theme=self.theme, task_id=task_id, initial_settings=lv)
        else:
            self.window = MainWindow(
                theme=self.theme,
                task_id=task_id,
                initial_settings=lv,
                fullscreen=bool(self.config.get("app", {}).get("fullscreen", True)),
            )
            self.view = self.window.view
        self.canvas = self.view.canvas
        self.operator_panel = self.view.operator_panel
        self.canvas.show_cursor = bool(lv["dwell.visual_cursor"])
        self.canvas.show_progress_ring = bool(lv["dwell.progress_ring"])
        self.canvas.show_instant_feedback = bool(lv["dwell.instant_feedback"])

        self.metadata = SessionMetadata(
            subject_id=subject_id,
            session_id=session_id,
            started_ns=time.time_ns(),
            input_mode=self.input_mode,
            tasks=[task_id],
            assessment_date=assessment_date,
            sex=sex,
            notes=notes,
        )
        self.recorder = SessionRecorder(self.metadata, output_root=output_root)
        self.recorder.open()

        # Human-readable session narrative (SPEC-result-logic.md §8.3's
        # Session Log panel) -- connect()/calibrate() above both had to run
        # before the recorder existed (calibration polls the socket directly
        # and must not race the client's own reader thread against a log
        # write), so their lines are recorded here, right after open(), not
        # at the point each thing actually happened.
        self.recorder.log(f"Session started: {session_id}")
        if self._owns_client:
            self.recorder.log("Connected to Gazepoint Control.")
        if cal.valid:
            error_txt = f"{cal.mean_error_px:.1f}px" if cal.mean_error_px is not None else "n/a"
            self.recorder.log(f"Calibration measured — {cal.n_points} points, mean error {error_txt}, valid.")
        else:
            self.recorder.log(f"Calibration measured — {cal.n_points} points, invalid or unmeasured.")

        self.metadata.calibration_points = cal.n_points
        self.metadata.calibration_error_px = cal.mean_error_px

        self.feedback = GuiFeedback(
            self.canvas, self.theme, self.config.get("task", {}).get("feedback", {})
        )
        self.task = build_task(task_id, self.config, recorder=self.recorder, feedback=self.feedback)
        app_cfg = self.config.get("app", {})
        self.recorder.log(
            f"Running {task_id} ({len(self.task.targets)} trials) at "
            f"{int(app_cfg.get('screen_width_px', 1920))}x{int(app_cfg.get('screen_height_px', 1080))}."
        )
        # Fetched once, not per frame -- the task's persistent on-screen
        # layout description (ported from resources/diki, see
        # SPEC-diki-design-audit.md S3.1). Default {"mode": "single"} for
        # tasks not yet ported to a dedicated scene.
        self._scene = self.task.scene_spec()

        self._paused = False
        self._wire_operator()
        self._install_key_handler()

        self._fps_frames = 0
        self._fps_last_ns = time.time_ns()
        self._fps = 0.0

        # Gaze-to-feedback latency (plan risk table / gap F): only meaningful
        # against a live tracker, never a replay fixture (see
        # GazepointClient.is_live).
        self._latency = LatencyTracker(window_size=int(self.config.get("app", {}).get("target_fps", 60)))
        self._device_rate = SampleRateTracker()

        # Dropout / off-canvas diagnostic (SPEC-gaze-cursor-redesign.md S6).
        # Live device only: a replay fixture's dropouts are the fixture's, not
        # the tracker's, and would pollute the aggregate the fade threshold is
        # meant to be read from.
        self._dropout_log = (
            GazeDropoutLog(
                gaze_dropout_log_path(output_root),
                raw_probe=getattr(self.client, "last_raw_pog", None),
                task_id=task_id,
            )
            if self.client.is_live
            else None
        )

        fps = int(self.config.get("app", {}).get("target_fps", 60))
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(int(1000 / fps))

    # -- wiring ------------------------------------------------------------

    def _wire_operator(self) -> None:
        panel = self.operator_panel
        panel.pause_toggled.connect(self._set_paused)
        panel.skip_requested.connect(self._skip_trial)
        panel.end_requested.connect(self._shutdown)
        panel.setting_changed.connect(self._apply_setting)

    def _install_key_handler(self) -> None:
        original = self.canvas.keyPressEvent

        def handler(event):
            if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.switch.press()
            elif event.key() == Qt.Key.Key_Escape:
                self._shutdown()
            else:
                original(event)

        self.canvas.keyPressEvent = handler
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.canvas.setFocus()

    # -- operator actions --------------------------------------------------

    def _set_paused(self, paused: bool) -> None:
        self._paused = paused

    def _skip_trial(self) -> None:
        # Force a timeout on the current trial by rewinding its start time.
        self.task._trial_start_ns = 0  # noqa: SLF001 - deliberate operator override

    def _apply_setting(self, key: str, value: object) -> None:
        """Apply one live-settings-panel change to the object that actually
        consumes it (SPEC-live-settings-panel.md section 5.1).

        Every key here is read fresh every frame/paint by its target object,
        so the change takes effect on the very next tick -- including within
        the trial already in progress (deliberate; see the SPEC's section
        5.5 on why a SETTING_CHANGED event is logged alongside every change).
        """
        old_value = self._live_values.get(key)
        self._live_values[key] = value

        if key == "dwell.threshold_ms" and self.task.dwell is not None:
            self.task.dwell.config = replace(self.task.dwell.config, threshold_ms=float(value))
        elif key == "dwell.refractory_ms" and self.task.dwell is not None:
            self.task.dwell.config = replace(self.task.dwell.config, refractory_ms=float(value))
        elif key == "dwell.jitter_tolerance_px":
            self.task.jitter_px = float(value)
        elif key == "dwell.visual_cursor":
            self.canvas.show_cursor = bool(value)
        elif key == "dwell.progress_ring":
            self.canvas.show_progress_ring = bool(value)
        elif key == "dwell.instant_feedback":
            self.canvas.show_instant_feedback = bool(value)
        elif key == "dwell.smoothing.enabled":
            self.eye.smoother.config = replace(self.eye.smoother.config, enabled=bool(value))
            # Drop the running EMA so the next sample doesn't blend toward a
            # stale average from before the change (SPEC section 5.4).
            self.eye.smoother.reset()
        elif key == "dwell.smoothing.alpha":
            self.eye.smoother.config = replace(self.eye.smoother.config, alpha=float(value))
            self.eye.smoother.reset()
        elif key == "task.timeout_ms":
            self.task.timeout_ns = int(float(value) * 1e6)
        elif key == "task.inter_trial_interval_ms":
            self.task.iti_ns = int(float(value) * 1e6)
        elif key == "motion.speed_frac_per_s" and hasattr(self.task, "speed"):
            self.task.speed = float(value)

        self.recorder.record_event(
            "SETTING_CHANGED", time.time_ns(), key=key, old_value=old_value, new_value=value
        )
        self.recorder.log(f"Setting changed: {key} {old_value!r} -> {value!r}")

    # -- main loop ---------------------------------------------------------

    def _sync_gaze_geometry(self) -> None:
        """Feed the task the real tracked-screen geometry (SPEC-gui-audit-
        2026-09-10.md item 5) so pointer conversion doesn't assume the
        canvas fills the tracked monitor -- the confirmed cause of gaze
        undershooting targets away from center (worst on whichever edge is
        furthest from the canvas's on-screen position).

        A no-op (``BaseTask`` keeps its today-identical canvas-relative
        fallback) whenever ``SCREEN_SIZE`` wasn't reported -- replay mode,
        an unanswered query, or before any connect has happened.
        """
        info = self.client.device_info
        if info is None or not info.screen_width or not info.screen_height:
            return
        canvas_origin = self.canvas.mapToGlobal(QPoint(0, 0))
        offset_x = canvas_origin.x() - (info.screen_x or 0)
        offset_y = canvas_origin.y() - (info.screen_y or 0)
        self.task.set_gaze_geometry(info.screen_width, info.screen_height, offset_x, offset_y)

    def _tick(self) -> None:
        if self._paused:
            return
        t_ns = time.time_ns()
        # Keep hit-testing in sync with whatever the canvas actually renders
        # at (fullscreen resolution, a resized window, ...) instead of the
        # configured screen_width_px/height_px default.
        self.task.set_screen_size(self.canvas.width(), self.canvas.height())
        self._sync_gaze_geometry()
        pointer = self.eye.poll(t_ns)
        if self.input_mode != "eye":
            pointer = Pointer(
                x=pointer.x, y=pointer.y, valid=pointer.valid, clicked=self.switch.consume_click()
            )

        sample = self.eye.latest_sample()
        if sample is not None and self.config.get("recording", {}).get("save_gaze_stream", True):
            self.recorder.record_gaze(sample)
        if sample is not None and self.client.is_live:
            self._record_latency(sample.t_ns, t_ns)
            self._device_rate.update(sample.t_ns, t_ns)

        result = self.task.update(t_ns, pointer)

        if self._dropout_log is not None:
            self._dropout_log.observe(t_ns, pointer.valid, result.cursor_xy_norm)

        self.canvas.set_frame(
            target_xy_norm=result.target_xy_norm,
            target_radius_px=(result.target.radius_px if result.target else 90.0),
            # The task's own corrected canvas-normalized pointer, NOT the raw
            # monitor-normalized pointer.x/y -- feeding the raw value here was
            # the confirmed cause of the cursor silently vanishing off-center
            # (SPEC-gui-audit-2026-09-10.md S6).
            cursor_xy_norm=result.cursor_xy_norm,
            cursor_valid=pointer.valid,
            dwell_progress=result.dwell_progress,
            selectable=result.selectable,
            layout_slots=self.task.layout_slots,
            on_target=result.on_target,
            scene=self._scene,
            active_slot=(result.target.slot_index if result.target else -1),
        )

        self._update_fps(t_ns)
        # Tallied from the task's own completed-trial records rather than
        # tracked separately, so this can never drift from what trials.csv
        # ends up with (SPEC-diki-design-audit.md S8 -- diki's LiveCounterPanel
        # hit/timeout counts, ported here).
        hits = sum(1 for t in self.task.trials if t.is_hit)
        timeouts = sum(1 for t in self.task.trials if t.is_timeout)
        self.operator_panel.update_status(
            self._fps,
            pointer.valid,
            result.trial_index,
            len(self.task.targets),
            connected=self.client.is_connected(),
            hits=hits,
            timeouts=timeouts,
            device_rate_hz=self._device_rate.rate_hz if self.client.is_live else None,
        )

        if self.task.is_done:
            self._shutdown()

    def _update_fps(self, t_ns: int) -> None:
        self._fps_frames += 1
        if t_ns - self._fps_last_ns >= 1_000_000_000:
            self._fps = self._fps_frames * 1e9 / (t_ns - self._fps_last_ns)
            self._fps_frames = 0
            self._fps_last_ns = t_ns

    def _record_latency(self, sample_t_ns: int, t_ns: int) -> None:
        summary = self._latency.add_sample(sample_t_ns, t_ns)
        if summary is not None:
            self.recorder.record_event(
                "LATENCY_SAMPLE",
                t_ns,
                latency_ms_mean=round(summary.mean_ms, 2),
                latency_ms_min=round(summary.min_ms, 2),
                latency_ms_max=round(summary.max_ms, 2),
                n_samples=summary.n_samples,
            )

    def _shutdown(self) -> None:
        if getattr(self, "_shutdown_done", False):
            return  # End button + task.is_done can both fire in the same tick
        self._shutdown_done = True
        self.timer.stop()
        if self._dropout_log is not None:
            # Flush a dropout still open at the end, so one that never
            # recovered is recorded rather than silently lost.
            self._dropout_log.close(time.time_ns())
        trials_path = self.recorder.write_trials(self.task.trials)
        self.recorder.log(f"Wrote {len(self.task.trials)} trials -> {trials_path}")
        self.recorder.close()
        write_session_metrics(self.recorder.session_dir)
        if self._owns_client:
            self.client.stop()
        if self._embedded:
            if self._on_finished is not None:
                self._on_finished()
        else:
            QApplication.quit()


def run_gui(
    task_id: str,
    replay_path: str | None = None,
    subject_id: str = "P000",
    calibration_file: str | None = None,
    skip_task_settings_dialog: bool = False,
) -> int:
    app = QApplication.instance() or QApplication([])

    structural_overrides: dict | None = None
    if not skip_task_settings_dialog:
        # Structural/layout task params (grid size, radius, trial count, ...)
        # are collected here, before AssessmentApp/build_targets() run --
        # SPEC-live-settings-panel.md section 5.3. "Start task" with no
        # changes reproduces today's YAML-only behavior exactly.
        preview_config = load_task_config(task_id)
        dialog = TaskSettingsDialog(task_id, preview_config)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            print("Task launch cancelled.", file=sys.stderr)
            return 0
        structural_overrides = dialog.overrides()

    try:
        assessment = AssessmentApp(
            task_id=task_id,
            replay_path=replay_path,
            subject_id=subject_id,
            calibration_file=calibration_file,
            structural_overrides=structural_overrides,
        )
    except CalibrationFileError as exc:
        print(f"Calibration file error: {exc}", file=sys.stderr)
        return 2
    assessment.window.show()
    return app.exec()
