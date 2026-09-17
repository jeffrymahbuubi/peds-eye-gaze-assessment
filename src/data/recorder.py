"""Per-session data recorder.

Writes one directory per session::

    sessions/
      2026-07-15_P001_S1/
        metadata.json      # subject, calibration error, schema version
        session.log        # human-readable timeline
        gaze_stream.csv    # per-frame gaze samples
        all_gaze.csv       # every raw <REC>, Gazepoint Analysis export layout (optional)
        trials.csv         # one row per trial
        events.jsonl       # discrete events (DWELL_START, TARGET_SHOWN, ...)

The recorder is deliberately GUI-free and streams to disk incrementally so a
crash mid-session still leaves usable partial data.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from .analysis_export import ALL_GAZE_FILENAME, all_gaze_header, rec_to_all_gaze_row
from .schema import GazeSample, SessionMetadata, TrialRecord

_GAZE_HEADER = [
    "t_ns",
    "x",
    "y",
    "valid",
    "fixation_id",
    "fix_duration_s",
    "pupil_left",
    "pupil_right",
]


class SessionRecorder:
    """Streams gaze samples, trials and events to a session directory."""

    def __init__(self, metadata: SessionMetadata, output_root: str | Path = "sessions") -> None:
        self.metadata = metadata
        self.session_dir = Path(output_root) / metadata.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self._gaze_file: TextIO | None = None
        self._gaze_writer: csv.DictWriter | None = None
        self._events_file: TextIO | None = None
        self._log_file: TextIO | None = None
        self._closed = False
        # Flush the gaze CSV at least this often so a hard crash (SIGKILL, power
        # loss) leaves at most ~this many buffered samples on the floor.
        self._gaze_flush_every = 60
        self._gaze_since_flush = 0

        # Optional second per-sample file in Gazepoint Analysis's own export
        # layout (SPEC-gazepoint-analysis-export-parity.md S5): one row per
        # raw <REC> received, not per GUI frame -- opened by open_all_gaze().
        self._all_gaze_file: TextIO | None = None
        self._all_gaze_writer: Any = None  # csv.writer instance
        self._all_gaze_media_name = ""
        self._all_gaze_time_origin_s: float | None = None
        self._all_gaze_since_flush = 0

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> SessionRecorder:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def open(self) -> None:
        self._gaze_file = (self.session_dir / "gaze_stream.csv").open(
            "w", newline="", encoding="utf-8"
        )
        self._gaze_writer = csv.DictWriter(self._gaze_file, fieldnames=_GAZE_HEADER)
        self._gaze_writer.writeheader()

        self._events_file = (self.session_dir / "events.jsonl").open(
            "w", encoding="utf-8"
        )
        self._log_file = (self.session_dir / "session.log").open("w", encoding="utf-8")

    def open_all_gaze(self, media_name: str, tick_frequency: int | None) -> None:
        """Start ``all_gaze.csv`` (Gazepoint Analysis layout). Call after
        :meth:`open`. ``media_name`` fills the ``MEDIA_NAME`` column (the
        task id -- our analogue of Analysis's stimulus name); ``tick_frequency``
        is the device's ``TIME_TICK_FREQUENCY`` for the ``TIMETICK(f=..)``
        header, 0 when unknown."""
        if self._all_gaze_file is not None:
            return
        self._all_gaze_media_name = media_name
        self._all_gaze_file = (self.session_dir / ALL_GAZE_FILENAME).open(
            "w", newline="", encoding="utf-8"
        )
        self._all_gaze_writer = csv.writer(self._all_gaze_file)
        self._all_gaze_writer.writerow(all_gaze_header(datetime.now(), tick_frequency))

    # -- writers -----------------------------------------------------------

    def record_raw(self, t_ns: int, attrs: dict[str, str]) -> None:
        """Append one raw ``<REC>`` to ``all_gaze.csv``; a no-op unless
        :meth:`open_all_gaze` was called, so callers need not branch.

        ``TIME`` is rewritten relative to the first record (the export's
        convention), from the device's own ``TIME`` when present, else from
        ``t_ns`` -- the two are never mixed within one file.
        """
        if self._all_gaze_writer is None:
            return
        device_time = _parse_float(attrs.get("TIME"))
        now_s = device_time if device_time is not None else t_ns / 1e9
        if self._all_gaze_time_origin_s is None:
            self._all_gaze_time_origin_s = now_s
        row = rec_to_all_gaze_row(
            attrs,
            time_s=now_s - self._all_gaze_time_origin_s,
            media_name=self._all_gaze_media_name,
        )
        self._all_gaze_writer.writerow(list(row.values()))
        self._all_gaze_since_flush += 1
        if self._all_gaze_since_flush >= self._gaze_flush_every:
            self._all_gaze_file.flush()
            self._all_gaze_since_flush = 0

    def record_gaze(self, sample: GazeSample) -> None:
        if self._gaze_writer is None:
            raise RuntimeError("Recorder is not open; call open() or use as context manager.")
        self._gaze_writer.writerow(sample.as_row())
        self._gaze_since_flush += 1
        if self._gaze_since_flush >= self._gaze_flush_every:
            self._gaze_file.flush()
            self._gaze_since_flush = 0

    def record_event(self, kind: str, t_ns: int, **payload: Any) -> None:
        if self._events_file is None:
            raise RuntimeError("Recorder is not open.")
        event = {"t_ns": t_ns, "kind": kind, **payload}
        self._events_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        # Events are low-frequency and high-value; flush each one so the trial
        # timeline survives a crash.
        self._events_file.flush()

    def log(self, message: str) -> None:
        if self._log_file is None:
            raise RuntimeError("Recorder is not open.")
        self._log_file.write(message.rstrip("\n") + "\n")
        self._log_file.flush()

    def write_trials(self, trials: list[TrialRecord]) -> Path:
        path = self.session_dir / "trials.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=TrialRecord.csv_header())
            writer.writeheader()
            for trial in trials:
                writer.writerow(trial.as_row())
        return path

    def write_metadata(self) -> Path:
        path = self.session_dir / "metadata.json"
        path.write_text(
            json.dumps(self.metadata.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    # -- teardown ----------------------------------------------------------

    def close(self) -> None:
        if self._closed:
            return
        # metadata is (re)written on close so late fields (calibration error,
        # task list) are captured.
        self.write_metadata()
        for fh in (self._gaze_file, self._all_gaze_file, self._events_file, self._log_file):
            if fh is not None:
                fh.flush()
                fh.close()
        self._closed = True


def _parse_float(raw: str | None) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except ValueError:
        return None
