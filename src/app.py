"""GUI application wiring (plan section 3.1 + Prompts 3/4).

Builds the QApplication, the gaze source (live Gazepoint or paced replay), the
task, the recorder, and a 60 Hz update loop that ties them together. Kept in its
own module so importing it (and thus PySide6) is opt-in — the headless pipeline
in :mod:`src.engine.task_runner` never touches this file.
"""

from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QApplication, QDialog

from .data.recorder import SessionRecorder
from .data.schema import SessionMetadata
from .engine.calibration import (
    Calibration,
    CalibrationFileError,
    load_calibration_result,
    save_calibration_result,
)
from .engine.config import CONFIG_ROOT, deep_merge, load_task_config, load_theme
from .engine.feedback import FeedbackBus
from .engine.latency import LatencyTracker
from .engine.task_runner import build_task
from .inputs.base import Pointer
from .inputs.eye_input import DwellConfig, EyeInput, SmoothingConfig
from .inputs.gazepoint_client import GazepointClient
from .inputs.switch_input import SwitchInput
from .ui.main_window import MainWindow
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
    ) -> None:
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

        # Computed up front (not after calibration, as before) because an
        # auto-saved calibration.json needs the session dir to already be
        # known before Calibration.run() executes.
        session_id = time.strftime("%Y-%m-%d_") + f"{subject_id}_{task_id}"
        output_root = self.config.get("recording", {}).get("output_root", "sessions")
        session_dir = Path(output_root) / session_id

        # A --calibration-file is loaded and subject-checked before touching
        # the device at all, so a bad path or subject mismatch fails fast
        # without opening a socket or showing any calibration UI
        # (SPEC-2026-09-02.md item 7, Goal 1).
        preset_calibration = None
        if calibration_file is not None:
            saved = load_calibration_result(calibration_file)
            if saved.subject_id != subject_id:
                raise CalibrationFileError(
                    f"Calibration file subject_id {saved.subject_id!r} does not match "
                    f"--subject {subject_id!r} ({calibration_file})"
                )
            preset_calibration = saved.result

        gp_cfg = self.config.get("gazepoint", {})
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
        # can silently swallow) that response.
        cal_cfg = self.config.get("calibration", {})
        if preset_calibration is not None:
            # --calibration-file wins over calibration.enabled: false -- it's
            # a separate, explicit request to reuse a real prior measurement,
            # not the config's own dev/no-hardware stub toggle.
            calibration = Calibration(self.client, preset_result=preset_calibration)
            cal = calibration.run()
        else:
            calibration = Calibration(
                self.client,
                n_points=int(cal_cfg.get("points", 5)),
                enabled=bool(cal_cfg.get("enabled", True)),
                show=bool(cal_cfg.get("show", True)),
                point_timeout_s=cal_cfg.get("timeout_s"),
                point_delay_s=cal_cfg.get("delay_s"),
            )
            cal = calibration.run()
            if not calibration.is_stub:
                # A real calibration just ran (not the no-hardware/disabled
                # stub) -- auto-save it so a later launch can reuse it via
                # --calibration-file. No separate save flag, per the user's
                # 2026-09-04 design decision.
                session_dir.mkdir(parents=True, exist_ok=True)
                save_calibration_result(session_dir / "calibration.json", subject_id, cal)

        self.client.start_streaming()

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

        self.window = MainWindow(
            theme=self.theme,
            task_id=task_id,
            initial_settings=lv,
            fullscreen=bool(self.config.get("app", {}).get("fullscreen", True)),
        )
        self.canvas = self.window.canvas
        self.canvas.show_cursor = bool(lv["dwell.visual_cursor"])
        self.canvas.show_progress_ring = bool(lv["dwell.progress_ring"])
        self.canvas.show_instant_feedback = bool(lv["dwell.instant_feedback"])

        self.metadata = SessionMetadata(
            subject_id=subject_id,
            session_id=session_id,
            started_ns=time.time_ns(),
            input_mode=self.input_mode,
            tasks=[task_id],
        )
        self.recorder = SessionRecorder(self.metadata, output_root=output_root)
        self.recorder.open()

        self.metadata.calibration_points = cal.n_points
        self.metadata.calibration_error_px = cal.mean_error_px

        self.feedback = GuiFeedback(
            self.canvas, self.theme, self.config.get("task", {}).get("feedback", {})
        )
        self.task = build_task(task_id, self.config, recorder=self.recorder, feedback=self.feedback)

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

        fps = int(self.config.get("app", {}).get("target_fps", 60))
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(int(1000 / fps))

    # -- wiring ------------------------------------------------------------

    def _wire_operator(self) -> None:
        panel = self.window.operator_panel
        panel.pause_toggled.connect(self._set_paused)
        panel.skip_requested.connect(self._skip_trial)
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

    def _tick(self) -> None:
        if self._paused:
            return
        t_ns = time.time_ns()
        # Keep hit-testing in sync with whatever the canvas actually renders
        # at (fullscreen resolution, a resized window, ...) instead of the
        # configured screen_width_px/height_px default.
        self.task.set_screen_size(self.canvas.width(), self.canvas.height())
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

        result = self.task.update(t_ns, pointer)

        self.canvas.set_frame(
            target_xy_norm=result.target_xy_norm,
            target_radius_px=(result.target.radius_px if result.target else 90.0),
            cursor_xy_norm=(pointer.x, pointer.y),
            cursor_valid=pointer.valid,
            dwell_progress=result.dwell_progress,
            selectable=result.selectable,
            layout_slots=self.task.layout_slots,
            on_target=result.on_target,
        )

        self._update_fps(t_ns)
        self.window.operator_panel.update_status(
            self._fps,
            pointer.valid,
            result.trial_index,
            len(self.task.targets),
            connected=self.client.is_connected(),
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
        self.timer.stop()
        self.recorder.write_trials(self.task.trials)
        self.recorder.close()
        self.client.stop()
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
