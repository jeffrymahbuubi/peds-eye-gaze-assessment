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

import time
from dataclasses import dataclass

from ..inputs.gazepoint_client import parse_attrs


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    n_points: int
    mean_error_px: float | None
    valid: bool


CALIBRATE_CLEAR = '<SET ID="CALIBRATE_CLEAR" />\r\n'
CALIBRATE_RESET = '<SET ID="CALIBRATE_RESET" />\r\n'
CALIBRATE_START = '<SET ID="CALIBRATE_START" STATE="1" />\r\n'
CALIBRATE_RESULT_QUERY = '<GET ID="CALIBRATE_RESULT_SUMMARY" />\r\n'

# Point layouts sent via CALIBRATE_RESET (5) / CALIBRATE_ADDPOINT (9), as
# (X, Y) fractions of screen width/height. The 5-point layout is the vendor's
# own documented default (API manual SS3.9: center + 4 corners at the 0.15/
# 0.85 margins) -- reused verbatim via CALIBRATE_RESET rather than re-added
# point by point. The 9-point layout is NOT vendor-documented anywhere in
# docs/gazepoints/ -- it's this project's own construction, extending the
# same 5 points with edge midpoints at the same 0.15/0.5/0.85 margins to form
# a 3x3 grid. Flag this if 9-point results ever need explaining to the PI.
_CALIBRATION_LAYOUTS: dict[int, list[tuple[float, float]]] = {
    5: [(0.5, 0.5), (0.85, 0.15), (0.85, 0.85), (0.15, 0.85), (0.15, 0.15)],
    9: [
        (0.5, 0.5),
        (0.85, 0.15), (0.85, 0.85), (0.15, 0.85), (0.15, 0.15),
        (0.5, 0.15), (0.85, 0.5), (0.5, 0.85), (0.15, 0.5),
    ],
}

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
    ) -> None:
        if n_points not in _CALIBRATION_LAYOUTS:
            raise ValueError(
                f"Unsupported calibration point count: {n_points} "
                f"(must be one of {sorted(_CALIBRATION_LAYOUTS)})"
            )
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

    def run(self) -> CalibrationResult:
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
        for x, y in _CALIBRATION_LAYOUTS[self.n_points]:
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
