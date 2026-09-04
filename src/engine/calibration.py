"""Gazepoint calibration flow (plan section 5.4 / risk table).

Wraps the OpenGaze calibration commands. The real calibration UI is rendered
by Gazepoint Control; here we trigger it and poll ``CALIBRATE_RESULT_SUMMARY``
for the resulting per-point error so it can be stored in ``metadata.json`` for
data-quality filtering. Without hardware the class runs in a no-op stub mode.

Calibration is asynchronous on the device: ``CALIBRATE_START``'s ACK only
confirms the command was received, not that calibration finished (the child
still has to look at each animated point in turn). The result must be polled
for after starting it (API manual §3.7). This also means :meth:`run` must be
called *before* :meth:`GazepointClient.start_streaming`, while nothing else is
reading the socket -- otherwise the background reader thread's ``recv()``
races with this class's own ``recv()`` for the same bytes and can silently
swallow the calibration response.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..inputs.gazepoint_client import parse_attrs


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    n_points: int
    mean_error_px: float | None
    valid: bool


class CalibrationFileError(Exception):
    """A --calibration-file was missing, malformed, or didn't match the subject.

    Raised instead of falling back to a fresh calibration so a bad path or a
    subject mismatch fails fast and loud (SPEC-2026-09-02.md item 7, Goal 1).
    """


@dataclass(frozen=True, slots=True)
class SavedCalibration:
    """A calibration record loaded from a ``calibration.json`` file."""

    subject_id: str
    result: CalibrationResult
    calibrated_at: str


def save_calibration_result(path: str | Path, subject_id: str, result: CalibrationResult) -> None:
    """Write ``result`` to ``path`` for later reuse via ``--calibration-file``."""
    payload = {
        "subject_id": subject_id,
        "n_points": result.n_points,
        "mean_error_px": result.mean_error_px,
        "valid": result.valid,
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_calibration_result(path: str | Path) -> SavedCalibration:
    """Load a calibration record written by :func:`save_calibration_result`.

    Raises :class:`CalibrationFileError` on any problem (missing file,
    invalid JSON, missing/malformed fields) -- deliberately no silent
    fallback to a fresh calibration (SPEC-2026-09-02.md item 7, Goal 1: "hard
    error" was the user's explicit choice over silently proceeding).
    """
    p = Path(path)
    if not p.exists():
        raise CalibrationFileError(f"Calibration file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CalibrationFileError(f"Calibration file is not valid JSON: {p} ({exc})") from exc
    try:
        subject_id = str(data["subject_id"])
        mean_error_px = data.get("mean_error_px")
        result = CalibrationResult(
            n_points=int(data["n_points"]),
            mean_error_px=float(mean_error_px) if mean_error_px is not None else None,
            valid=bool(data["valid"]),
        )
        calibrated_at = str(data["calibrated_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CalibrationFileError(f"Calibration file is missing/invalid fields: {p} ({exc})") from exc
    return SavedCalibration(subject_id=subject_id, result=result, calibrated_at=calibrated_at)


CALIBRATE_CLEAR = '<SET ID="CALIBRATE_CLEAR" />\r\n'
CALIBRATE_RESET = '<SET ID="CALIBRATE_RESET" />\r\n'
CALIBRATE_START = '<SET ID="CALIBRATE_START" STATE="1" />\r\n'
CALIBRATE_RESULT_QUERY = '<GET ID="CALIBRATE_RESULT_SUMMARY" />\r\n'

# Point layouts sent via CALIBRATE_RESET (5) / CALIBRATE_ADDPOINT (9), as
# (X, Y) fractions of screen width/height, as one ordered pool rather than a
# per-count dict: the first N points are used for an N-point calibration.
# This reproduces two known-good layouts exactly as prefixes -- the vendor's
# own documented 5-point default (API manual SS3.9: center + 4 corners at the
# 0.15/0.85 margins; POOL[:5]) and this project's own 9-point extension
# (edge midpoints at the same margins, forming a 3x3 grid; POOL[:9]) -- so
# neither one's behavior changes by adding this. Point counts below 5 (or
# between 5 and 9) have NO vendor precedent at all (SPEC-2026-09-02.md item
# 7 Goal 2: Control's own sub-5-point "quick" mode is a local UI feature with
# no API equivalent, confirmed by an exhaustive search of the API manual --
# any point count sent via CALIBRATE_ADDPOINT runs the same regression the
# 5/9-point modes use, just with fewer points). This project's own choice:
# center-then-corners-then-edge-midpoints ordering, so a low N still anchors
# the widest field of view first rather than clustering points arbitrarily.
# Counts beyond 9 have no layout defined here (deliberately out of scope --
# see the Goal 2 SPEC section for why).
_CALIBRATION_POINT_POOL: list[tuple[float, float]] = [
    (0.5, 0.5),
    (0.85, 0.15), (0.85, 0.85), (0.15, 0.85), (0.15, 0.15),
    (0.5, 0.15), (0.85, 0.5), (0.5, 0.85), (0.15, 0.5),
]


def _layout_for(n_points: int) -> list[tuple[float, float]]:
    """The first ``n_points`` points of :data:`_CALIBRATION_POINT_POOL`.

    Raises ``ValueError`` outside ``1..len(_CALIBRATION_POINT_POOL)`` -- no
    vendor or project precedent exists for a layout beyond 9 points, and 0
    points isn't a calibration at all.
    """
    if not 1 <= n_points <= len(_CALIBRATION_POINT_POOL):
        raise ValueError(
            f"Unsupported calibration point count: {n_points} "
            f"(must be 1-{len(_CALIBRATION_POINT_POOL)} -- no vendor-documented "
            f"layout exists beyond this project's existing 9-point extension)"
        )
    return _CALIBRATION_POINT_POOL[:n_points]


_POLL_INTERVAL_S = 0.5


class Calibration:
    """Drive the Gazepoint calibration and capture its error summary."""

    def __init__(
        self,
        client=None,
        n_points: int = 5,
        timeout_s: float | None = None,
        enabled: bool = True,
        show: bool = True,
        point_timeout_s: float | None = None,
        point_delay_s: float | None = None,
        preset_result: CalibrationResult | None = None,
    ) -> None:
        # A preset result (from --calibration-file) means run() returns it
        # immediately without touching the socket at all -- skip point-count
        # validation and the device-timing math below entirely, since none of
        # it applies to a reused record.
        self._preset_result = preset_result
        if preset_result is not None:
            self._layout = None  # never consulted: run() returns preset_result directly
            self._client = client
            self.n_points = preset_result.n_points
            self.enabled = enabled
            self.show = show
            self.point_timeout_s = point_timeout_s
            self.point_delay_s = point_delay_s
            self._timeout_s = timeout_s or 0.0
            return

        self._layout = _layout_for(n_points)  # raises ValueError if out of range
        self._client = client
        self.n_points = n_points
        self.enabled = enabled
        self.show = show
        # Device-side per-point timing (CALIBRATE_DELAY / CALIBRATE_TIMEOUT,
        # API manual SS3.5/SS3.6). None means "leave Gazepoint Control's own
        # configured value alone" -- these are NOT the same as timeout_s
        # below, which is purely our own polling deadline.
        self.point_timeout_s = point_timeout_s
        self.point_delay_s = point_delay_s

        # Our own poll-loop deadline (see _poll_for_result), distinct from
        # the device's CALIBRATE_TIMEOUT above. Generous default: real
        # calibration takes roughly (CALIBRATE_DELAY + CALIBRATE_TIMEOUT) per
        # point, ~1.75s at device defaults; scale that estimate using
        # point_delay_s/point_timeout_s when the caller overrides them, with
        # a safety margin, so a longer configured per-point time doesn't get
        # truncated by our own poll giving up first.
        per_point_s = (self.point_delay_s if self.point_delay_s is not None else 0.5) + (
            self.point_timeout_s if self.point_timeout_s is not None else 1.25
        )
        self._timeout_s = timeout_s if timeout_s is not None else max(10.0, n_points * per_point_s * 1.75)

    @property
    def is_stub(self) -> bool:
        """True if :meth:`run` will skip the device (no socket, or disabled).

        Mirrors the condition inside :meth:`run` -- used by callers (e.g.
        ``AssessmentApp``) to decide whether a completed run represents a
        real, freshly-measured calibration worth auto-saving to
        ``calibration.json``. Not meaningful when ``preset_result`` was given
        (that path is a reuse, not a stub or a fresh measurement); callers
        should branch on the presence of a preset result before consulting
        this property.
        """
        sock = getattr(self._client, "_sock", None) if self._client is not None else None
        return sock is None or not self.enabled

    def run(self) -> CalibrationResult:
        if self._preset_result is not None:
            return self._preset_result
        sock = getattr(self._client, "_sock", None) if self._client is not None else None
        if sock is None or not self.enabled:
            # Stub mode (no hardware, replay mode, or calibration.enabled:
            # false in config): report unmeasured, skip the device entirely.
            return CalibrationResult(n_points=self.n_points, mean_error_px=None, valid=False)

        if self.point_delay_s is not None:
            sock.sendall(f'<SET ID="CALIBRATE_DELAY" VALUE="{self.point_delay_s}" />\r\n'.encode("ascii"))
        if self.point_timeout_s is not None:
            sock.sendall(f'<SET ID="CALIBRATE_TIMEOUT" VALUE="{self.point_timeout_s}" />\r\n'.encode("ascii"))

        self._configure_points(sock)
        show_state = 1 if self.show else 0
        sock.sendall(f'<SET ID="CALIBRATE_SHOW" STATE="{show_state}" />\r\n'.encode("ascii"))
        sock.sendall(CALIBRATE_START.encode("ascii"))
        return self._poll_for_result(sock)

    def _configure_points(self, sock) -> None:
        if self.n_points == 5:
            # The vendor's own default matches this layout exactly (API
            # manual SS3.9) -- reuse it rather than re-adding points one by one.
            sock.sendall(CALIBRATE_RESET.encode("ascii"))
            return
        sock.sendall(CALIBRATE_CLEAR.encode("ascii"))
        for x, y in self._layout:
            sock.sendall(f'<SET ID="CALIBRATE_ADDPOINT" X="{x}" Y="{y}" />\r\n'.encode("ascii"))

    def _poll_for_result(self, sock) -> CalibrationResult:
        """Poll ``CALIBRATE_RESULT_SUMMARY`` until all points are calibrated
        or ``self._timeout_s`` elapses, returning the best result seen."""
        original_timeout = sock.gettimeout()
        sock.settimeout(0.2)
        buffer = ""
        best: CalibrationResult | None = None
        deadline = time.monotonic() + self._timeout_s
        next_query = 0.0  # query immediately on the first loop iteration
        try:
            while time.monotonic() < deadline:
                if time.monotonic() >= next_query:
                    sock.sendall(CALIBRATE_RESULT_QUERY.encode("ascii"))
                    next_query = time.monotonic() + _POLL_INTERVAL_S
                try:
                    chunk = sock.recv(4096)
                except TimeoutError:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buffer += chunk.decode("ascii", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    parsed = parse_attrs(line)
                    if parsed is None:
                        continue
                    tag, attrs = parsed
                    if tag != "ACK" or attrs.get("ID") != "CALIBRATE_RESULT_SUMMARY":
                        continue  # ignore CALIB_START_PT/CALIB_RESULT_PT progress records
                    valid_points = int(attrs.get("VALID_POINTS") or 0)
                    ave_error = attrs.get("AVE_ERROR")
                    mean_error_px = float(ave_error) if ave_error else None
                    best = CalibrationResult(
                        n_points=self.n_points, mean_error_px=mean_error_px, valid=valid_points > 0
                    )
                    if valid_points >= self.n_points:
                        return best
        finally:
            sock.settimeout(original_timeout)
        return best or CalibrationResult(n_points=self.n_points, mean_error_px=None, valid=False)
