"""Tests for Calibration.run()'s CALIBRATE_RESULT_SUMMARY polling (gap A),
plus the --calibration-file reuse mechanism (SPEC-2026-09-02.md item 7,
Goal 1): preset-result short-circuiting, Calibration.is_stub, and the
save/load_calibration_result file format.
"""

from __future__ import annotations

import json
import socket
import threading
import time

import pytest

from src.engine.calibration import (
    Calibration,
    CalibrationFileError,
    CalibrationResult,
    calibration_timing_log_path,
    load_calibration_result,
    per_point_errors_px,
    save_calibration_result,
)


class _ScriptedServer:
    """Accepts one connection and, in a background thread, sends a scripted
    sequence of raw lines at given delays -- simulating Gazepoint Control
    streaming CAL progress records and eventually the RESULT_SUMMARY ACK.
    Also records whatever the client sends (SET/GET commands), like
    FakeGazepointServer in test_gazepoint_client.py, so tests can assert on
    the exact calibration-setup commands sent.
    """

    def __init__(self, script: list[tuple[float, str]]) -> None:
        self._script = script
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        self.port = listener.getsockname()[1]
        self._listener = listener
        self._conn: socket.socket | None = None
        self._received = bytearray()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        conn, _ = self._listener.accept()
        self._conn = conn
        conn.settimeout(0.2)
        threading.Thread(target=self._drain, args=(conn,), daemon=True).start()
        for delay_s, line in self._script:
            time.sleep(delay_s)
            try:
                conn.sendall(line.encode("ascii"))
            except OSError:
                return

    def _drain(self, conn: socket.socket) -> None:
        while True:
            try:
                chunk = conn.recv(4096)
            except TimeoutError:
                continue
            except OSError:
                return
            if not chunk:
                return
            self._received.extend(chunk)

    def received_text(self) -> str:
        return bytes(self._received).decode("ascii", errors="ignore")

    def send_now(self, text: str) -> None:
        """Push raw text immediately, outside the timed script.

        Lets a test seed the client's receive buffer with data that predates
        the call under test -- e.g. a previous calibration's leftover replies
        (SPEC-gui-audit-2026-09-10.md S9).
        """
        deadline = time.monotonic() + 2.0
        while self._conn is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert self._conn is not None, "client never connected"
        self._conn.sendall(text.encode("ascii"))

    def connect_client_socket(self) -> socket.socket:
        return socket.create_connection(("127.0.0.1", self.port), timeout=2.0)

    def close(self) -> None:
        self._thread.join(timeout=2.0)
        if self._conn is not None:
            self._conn.close()
        self._listener.close()


class _StubClient:
    """Stand-in for GazepointClient exposing only what Calibration.run() uses."""

    def __init__(self, sock: socket.socket | None) -> None:
        self._sock = sock


def test_run_returns_unmeasured_when_no_socket():
    result = Calibration(client=_StubClient(None), n_points=5).run()
    assert result.valid is False
    assert result.mean_error_px is None


def test_run_returns_unmeasured_when_no_client():
    result = Calibration(client=None, n_points=5).run()
    assert result.valid is False
    assert result.mean_error_px is None


def test_run_polls_through_progress_records_to_final_result():
    script = [
        (0.05, '<CAL ID="CALIB_START_PT" PT="1" CALX="0.5" CALY="0.5" />\r\n'),
        (0.10, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="45.0" VALID_POINTS="1" />\r\n'),
        (0.10, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="22.0" VALID_POINTS="3" />\r\n'),
        (0.10, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="19.43" VALID_POINTS="5" />\r\n'),
    ]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        result = Calibration(client=_StubClient(sock), n_points=5, timeout_s=5.0).run()
        assert result.valid is True
        assert result.n_points == 5
        assert result.mean_error_px == pytest.approx(19.43)
    finally:
        server.close()


def test_run_captures_calib_result_per_point_breakdown():
    # CALIB_RESULT is pushed once, unprompted, at the end of calibration
    # (API manual S4.3) -- distinct from the polled CALIBRATE_RESULT_SUMMARY.
    script = [
        (
            0.05,
            '<CAL ID="CALIB_RESULT" CALX1="0.50000" CALY1="0.50000" '
            'LX1="0.50229" LY1="0.50279" LV1="1" RX1="0.51467" RY1="0.50870" RV1="1" '
            'CALX2="0.85000" CALY2="0.15000" LX2="0.84943" LY2="0.14930" LV2="1" '
            'RX2="0.84600" RY2="0.14763" RV2="0" />\r\n',
        ),
        (0.10, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="19.43" VALID_POINTS="2" />\r\n'),
    ]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        result = Calibration(client=_StubClient(sock), n_points=2, timeout_s=2.0).run()
        assert result.per_point == (
            {
                "point": 1,
                "target_x": 0.5,
                "target_y": 0.5,
                "left": {"x": 0.50229, "y": 0.50279, "valid": True},
                "right": {"x": 0.51467, "y": 0.5087, "valid": True},
            },
            {
                "point": 2,
                "target_x": 0.85,
                "target_y": 0.15,
                "left": {"x": 0.84943, "y": 0.1493, "valid": True},
                "right": {"x": 0.846, "y": 0.14763, "valid": False},
            },
        )
    finally:
        server.close()


def test_run_captures_calib_result_that_arrives_after_the_satisfying_summary_ack():
    """SPEC-gui-audit-2026-09-10.md item 2a: CALIB_RESULT (per the vendor
    manual, pushed at the very end of calibration) can arrive after the
    CALIBRATE_RESULT_SUMMARY ACK that already satisfies VALID_POINTS ==
    n_points -- returning the instant that ACK alone is seen used to
    silently drop a CALIB_RESULT that was only moments away, reproducing
    the reported "sometimes available, sometimes not" symptom. The grace
    window must catch it instead."""
    script = [
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="19.43" VALID_POINTS="2" />\r\n'),
        (
            0.15,  # arrives within the grace window, after the satisfying ACK above
            '<CAL ID="CALIB_RESULT" CALX1="0.50000" CALY1="0.50000" '
            'LX1="0.50229" LY1="0.50279" LV1="1" RX1="0.51467" RY1="0.50870" RV1="1" '
            'CALX2="0.85000" CALY2="0.15000" LX2="0.84943" LY2="0.14930" LV2="1" '
            'RX2="0.84600" RY2="0.14763" RV2="0" />\r\n',
        ),
    ]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        result = Calibration(client=_StubClient(sock), n_points=2, timeout_s=2.0).run()
        assert result.valid is True
        assert result.mean_error_px == pytest.approx(19.43)
        assert result.per_point is not None
        assert len(result.per_point) == 2
        assert result.per_point[0]["target_x"] == 0.5
    finally:
        server.close()


def test_run_gives_up_waiting_for_a_calib_result_that_never_arrives():
    """The wait must be bounded -- a summary-satisfied result with no
    CALIB_RESULT ever coming (e.g. an older firmware, or it genuinely never
    fires) must still return without waiting out the full poll timeout.

    Since S9 this returns after _min_calibration_s plus the grace window
    rather than immediately: an instantly-satisfied summary cannot be
    distinguished from Gazepoint Control's retained previous calibration any
    other way. Here that gate is the 0.7 x timeout cap (7.0s of the 10s
    timeout), so the call still returns before the deadline rather than
    running it out."""
    script = [
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="19.43" VALID_POINTS="5" />\r\n'),
    ]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        start = time.monotonic()
        result = Calibration(client=_StubClient(sock), n_points=5, timeout_s=10.0).run()
        elapsed = time.monotonic() - start
        assert result.valid is True
        assert result.per_point is None
        assert 7.0 <= elapsed < 9.5  # gated, then bounded -- not the 10s timeout
    finally:
        server.close()


def test_run_returns_none_per_point_when_calib_result_never_sent():
    script = [
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="19.43" VALID_POINTS="5" />\r\n'),
    ]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        result = Calibration(client=_StubClient(sock), n_points=5, timeout_s=2.0).run()
        assert result.per_point is None
    finally:
        server.close()


def test_run_returns_partial_result_on_timeout():
    script = [
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="30.0" VALID_POINTS="2" />\r\n'),
        # Server goes quiet after this -- never reaches n_points=5.
    ]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        result = Calibration(client=_StubClient(sock), n_points=5, timeout_s=1.0).run()
        assert result.valid is True  # some valid points were seen
        assert result.mean_error_px == pytest.approx(30.0)
        assert result.n_points == 5  # reports the *requested* count, not observed
    finally:
        server.close()


def test_run_returns_invalid_when_never_any_valid_points():
    server = _ScriptedServer([])  # server accepts but sends nothing at all
    try:
        sock = server.connect_client_socket()
        result = Calibration(client=_StubClient(sock), n_points=5, timeout_s=0.5).run()
        assert result.valid is False
        assert result.mean_error_px is None
    finally:
        server.close()


def _wait_until(predicate, timeout_s: float = 2.0, interval_s: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return predicate()


def test_zero_points_raises():
    with pytest.raises(ValueError):
        Calibration(client=None, n_points=0)


def test_more_than_nine_points_raises():
    # No vendor or project precedent exists for a layout beyond the 9-point
    # pool (SPEC-2026-09-02.md item 7 Goal 2) -- deliberately out of scope.
    with pytest.raises(ValueError):
        Calibration(client=None, n_points=10)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 6, 7, 8])
def test_sub_5_and_between_5_9_points_send_clear_then_n_addpoints(n):
    # Goal 2: point counts other than the two vendor/project-precedented ones
    # (5, 9) now work, via CALIBRATE_CLEAR + N CALIBRATE_ADDPOINT commands --
    # the same mechanism 9-point calibration already used.
    server = _ScriptedServer([
        (0.05, f'<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="10.0" VALID_POINTS="{n}" />\r\n'),
    ])
    try:
        sock = server.connect_client_socket()
        Calibration(client=_StubClient(sock), n_points=n, timeout_s=2.0).run()
        assert _wait_until(lambda: server.received_text().count("CALIBRATE_ADDPOINT") == n)
        sent = server.received_text()
        assert 'ID="CALIBRATE_CLEAR"' in sent
        assert 'ID="CALIBRATE_RESET"' not in sent
    finally:
        server.close()


def test_1_point_layout_is_just_the_center():
    server = _ScriptedServer([
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="10.0" VALID_POINTS="1" />\r\n'),
    ])
    try:
        sock = server.connect_client_socket()
        Calibration(client=_StubClient(sock), n_points=1, timeout_s=2.0).run()
        assert _wait_until(lambda: "CALIBRATE_ADDPOINT" in server.received_text())
        sent = server.received_text()
        assert sent.count("CALIBRATE_ADDPOINT") == 1
        assert 'X="0.5" Y="0.5"' in sent
    finally:
        server.close()


def test_4_point_layout_is_center_plus_first_three_corners():
    # Pool order is center-first (matching the vendor's own 5/9-point
    # ordering), so n=4 takes the center + the first 3 of the 4 corners --
    # not "4 corners, no center." The 4th corner (0.15, 0.15) is pool[4],
    # i.e. only included once n >= 5.
    server = _ScriptedServer([
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="10.0" VALID_POINTS="4" />\r\n'),
    ])
    try:
        sock = server.connect_client_socket()
        Calibration(client=_StubClient(sock), n_points=4, timeout_s=2.0).run()
        assert _wait_until(lambda: server.received_text().count("CALIBRATE_ADDPOINT") == 4)
        sent = server.received_text()
        for x, y in [(0.5, 0.5), (0.85, 0.15), (0.85, 0.85), (0.15, 0.85)]:
            assert f'X="{x}" Y="{y}"' in sent
        assert 'X="0.15" Y="0.15"' not in sent  # the 4th corner, excluded at n=4
    finally:
        server.close()


def test_5_points_sends_calibrate_reset_not_addpoint():
    server = _ScriptedServer([
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="10.0" VALID_POINTS="5" />\r\n'),
    ])
    try:
        sock = server.connect_client_socket()
        Calibration(client=_StubClient(sock), n_points=5, timeout_s=2.0).run()
        assert _wait_until(lambda: "CALIBRATE_RESET" in server.received_text())
        sent = server.received_text()
        assert "CALIBRATE_ADDPOINT" not in sent
        assert 'ID="CALIBRATE_START" STATE="1"' in sent
    finally:
        server.close()


def test_9_points_sends_clear_then_nine_addpoints():
    server = _ScriptedServer([
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="10.0" VALID_POINTS="9" />\r\n'),
    ])
    try:
        sock = server.connect_client_socket()
        Calibration(client=_StubClient(sock), n_points=9, timeout_s=2.0).run()
        assert _wait_until(lambda: server.received_text().count("CALIBRATE_ADDPOINT") == 9)
        sent = server.received_text()
        assert 'ID="CALIBRATE_CLEAR"' in sent
        assert 'ID="CALIBRATE_RESET"' not in sent
        # Edge-midpoint additions beyond the 5-point default, at the same margins.
        assert 'X="0.5" Y="0.15"' in sent
        assert 'X="0.15" Y="0.5"' in sent
    finally:
        server.close()


def test_show_false_sends_state_zero():
    server = _ScriptedServer([
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="10.0" VALID_POINTS="5" />\r\n'),
    ])
    try:
        sock = server.connect_client_socket()
        Calibration(client=_StubClient(sock), n_points=5, timeout_s=2.0, show=False).run()
        assert _wait_until(lambda: "CALIBRATE_SHOW" in server.received_text())
        assert 'ID="CALIBRATE_SHOW" STATE="0"' in server.received_text()
    finally:
        server.close()


def test_enabled_false_skips_device_entirely():
    server = _ScriptedServer([])
    try:
        sock = server.connect_client_socket()
        result = Calibration(client=_StubClient(sock), n_points=5, enabled=False).run()
        assert result.valid is False
        assert result.mean_error_px is None
        time.sleep(0.1)
        assert server.received_text() == ""
    finally:
        server.close()


def test_point_timeout_and_delay_send_set_commands():
    server = _ScriptedServer([
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="10.0" VALID_POINTS="5" />\r\n'),
    ])
    try:
        sock = server.connect_client_socket()
        Calibration(
            client=_StubClient(sock), n_points=5, timeout_s=2.0,
            point_timeout_s=2.5, point_delay_s=1.0,
        ).run()
        assert _wait_until(lambda: "CALIBRATE_TIMEOUT" in server.received_text())
        sent = server.received_text()
        assert 'ID="CALIBRATE_TIMEOUT" VALUE="2.5"' in sent
        assert 'ID="CALIBRATE_DELAY" VALUE="1.0"' in sent
    finally:
        server.close()


# -- preset_result / is_stub (--calibration-file reuse) --------------------


def test_preset_result_returned_without_touching_socket():
    server = _ScriptedServer([])  # would hang/timeout if Calibration.run() ever queried it
    try:
        sock = server.connect_client_socket()
        preset = CalibrationResult(n_points=9, mean_error_px=12.5, valid=True)
        result = Calibration(client=_StubClient(sock), preset_result=preset).run()
        assert result == preset
        time.sleep(0.1)
        assert server.received_text() == ""  # no CALIBRATE_* commands sent at all
    finally:
        server.close()


def test_preset_result_works_with_no_client_at_all():
    preset = CalibrationResult(n_points=5, mean_error_px=8.0, valid=True)
    result = Calibration(client=None, preset_result=preset).run()
    assert result == preset


def test_preset_result_skips_n_points_validation():
    # n_points=15 is out of the 1-9 pool range and would normally raise --
    # a preset result bypasses that check since no device points are sent.
    preset = CalibrationResult(n_points=15, mean_error_px=5.0, valid=True)
    calibration = Calibration(client=None, n_points=5, preset_result=preset)
    assert calibration.n_points == 15
    assert calibration.run() == preset


def test_is_stub_true_when_no_socket():
    assert Calibration(client=_StubClient(None), n_points=5).is_stub is True


def test_is_stub_true_when_disabled():
    server = _ScriptedServer([])
    try:
        sock = server.connect_client_socket()
        assert Calibration(client=_StubClient(sock), n_points=5, enabled=False).is_stub is True
    finally:
        server.close()


def test_is_stub_false_with_real_socket_and_enabled():
    server = _ScriptedServer([])
    try:
        sock = server.connect_client_socket()
        assert Calibration(client=_StubClient(sock), n_points=5, enabled=True).is_stub is False
    finally:
        server.close()


# -- save_calibration_result / load_calibration_result ---------------------


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "calibration.json"
    result = CalibrationResult(n_points=9, mean_error_px=17.25, valid=True)
    save_calibration_result(path, "P042", result)

    saved = load_calibration_result(path)
    assert saved.subject_id == "P042"
    assert saved.result == result
    assert saved.calibrated_at  # a non-empty ISO timestamp string


def test_save_then_load_round_trips_per_point(tmp_path):
    path = tmp_path / "calibration.json"
    per_point = (
        {
            "point": 1,
            "target_x": 0.5,
            "target_y": 0.5,
            "left": {"x": 0.502, "y": 0.503, "valid": True},
            "right": {"x": 0.515, "y": 0.509, "valid": True},
        },
    )
    result = CalibrationResult(n_points=1, mean_error_px=5.0, valid=True, per_point=per_point)
    save_calibration_result(path, "P042", result)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["per_point"] == list(per_point)

    saved = load_calibration_result(path)
    assert saved.result.per_point == per_point


def test_load_calibration_file_without_per_point_key_still_loads(tmp_path):
    # Older calibration.json files predate the per_point field -- its absence
    # is not an error (unlike the required fields below).
    path = tmp_path / "calibration.json"
    path.write_text(
        json.dumps(
            {
                "subject_id": "P001",
                "n_points": 5,
                "mean_error_px": 10.0,
                "valid": True,
                "calibrated_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    saved = load_calibration_result(path)
    assert saved.result.per_point is None


def test_save_writes_none_mean_error_as_null(tmp_path):
    path = tmp_path / "calibration.json"
    result = CalibrationResult(n_points=5, mean_error_px=None, valid=False)
    save_calibration_result(path, "P001", result)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["mean_error_px"] is None

    saved = load_calibration_result(path)
    assert saved.result.mean_error_px is None
    assert saved.result.valid is False


# -- per_point_errors_px (SPEC-result-logic.md §8.1) -------------------------

_SAMPLE_PER_POINT = (
    {
        "point": 1,
        "target_x": 0.5,
        "target_y": 0.5,
        "left": {"x": 0.50229, "y": 0.50279, "valid": True},
        "right": {"x": 0.51467, "y": 0.5087, "valid": True},
    },
    {
        "point": 2,
        "target_x": 0.85,
        "target_y": 0.15,
        "left": {"x": 0.84943, "y": 0.1493, "valid": True},
        "right": {"x": 0.846, "y": 0.14763, "valid": False},
    },
)


def test_per_point_errors_px_computes_euclidean_distance_in_pixel_space():
    rows = per_point_errors_px(_SAMPLE_PER_POINT, screen_width_px=1920, screen_height_px=1080)
    assert len(rows) == 2
    assert rows[0]["point"] == 1
    assert rows[0]["left_error_px"] == pytest.approx(5.33, abs=0.05)
    assert rows[0]["right_error_px"] == pytest.approx(29.69, abs=0.05)
    # An eye with valid=False still has a real estimate to compute a distance
    # against -- validity and "was an error computed" are separate concerns.
    assert rows[1]["right"]["valid"] is False
    assert rows[1]["right_error_px"] == pytest.approx(8.10, abs=0.05)


def test_per_point_errors_px_missing_eye_is_none():
    per_point = (
        {"point": 1, "target_x": 0.5, "target_y": 0.5, "left": {"x": 0.5, "y": 0.5, "valid": True}, "right": None},
    )
    rows = per_point_errors_px(per_point, screen_width_px=1920, screen_height_px=1080)
    assert rows[0]["left_error_px"] == pytest.approx(0.0)
    assert rows[0]["right_error_px"] is None


def test_per_point_errors_px_empty_or_none_input():
    assert per_point_errors_px(None, 1920, 1080) == []
    assert per_point_errors_px((), 1920, 1080) == []


def test_load_missing_file_raises_calibration_file_error(tmp_path):
    with pytest.raises(CalibrationFileError, match="not found"):
        load_calibration_result(tmp_path / "does_not_exist.json")


def test_load_malformed_json_raises_calibration_file_error(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(CalibrationFileError, match="not valid JSON"):
        load_calibration_result(path)


def test_load_missing_fields_raises_calibration_file_error(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps({"subject_id": "P001"}), encoding="utf-8")
    with pytest.raises(CalibrationFileError, match="missing/invalid fields"):
        load_calibration_result(path)


# -- S7 calibration timing diagnostic ------------------------------------


def test_timing_log_records_a_calib_result_that_arrived_inside_the_grace_window(tmp_path):
    """SPEC-gui-audit-2026-09-10.md S7: the diagnostic must record how the
    ACK-vs-CALIB_RESULT race actually resolved, and how large the gap was --
    that measured gap across point counts is what decides whether 0.75s is the
    right grace window, instead of guessing at a new constant."""
    log_path = tmp_path / "_diagnostics" / "calibration_timing.jsonl"
    script = [
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="19.43" VALID_POINTS="2" />\r\n'),
        (
            0.15,  # after the satisfying ACK, but inside the grace window
            '<CAL ID="CALIB_RESULT" CALX1="0.50000" CALY1="0.50000" '
            'LX1="0.50229" LY1="0.50279" LV1="1" RX1="0.51467" RY1="0.50870" RV1="1" '
            'CALX2="0.85000" CALY2="0.15000" LX2="0.84943" LY2="0.14930" LV2="1" '
            'RX2="0.84600" RY2="0.14763" RV2="0" />\r\n',
        ),
    ]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        Calibration(
            client=_StubClient(sock), n_points=2, timeout_s=2.0, timing_log_path=log_path
        ).run()
    finally:
        server.close()

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["outcome"] == "calib_result_after_ack"
    assert record["n_points"] == 2
    assert record["per_point_captured"] is True
    # The gap is the whole point of the diagnostic: positive (it arrived after
    # the ACK) and inside the window that caught it.
    assert 0 < record["gap_s"] < record["grace_s"]


def test_timing_log_records_a_calib_result_that_never_arrived(tmp_path):
    """The 'never arrived' case must be recorded too -- a log of only the
    successes would make the grace window look adequate no matter how often it
    actually times out."""
    log_path = tmp_path / "_diagnostics" / "calibration_timing.jsonl"
    script = [(0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="19.43" VALID_POINTS="5" />\r\n')]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        Calibration(
            client=_StubClient(sock), n_points=5, timeout_s=10.0, timing_log_path=log_path
        ).run()
    finally:
        server.close()

    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["outcome"] == "calib_result_never"
    assert record["gap_s"] is None
    assert record["t_calib_result_s"] is None
    assert record["per_point_captured"] is False
    assert record["n_points"] == 5


def test_timing_log_appends_across_runs_and_is_off_by_default(tmp_path):
    """Records accumulate in one file (the question they answer is only
    answerable across many runs), and no path means no file is written at
    all -- the diagnostic must not create files for callers that never asked
    for it."""
    log_path = tmp_path / "_diagnostics" / "calibration_timing.jsonl"
    script = [(0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="10.0" VALID_POINTS="4" />\r\n')]
    for _ in range(2):
        server = _ScriptedServer(script)
        try:
            sock = server.connect_client_socket()
            Calibration(
                client=_StubClient(sock), n_points=4, timeout_s=10.0, timing_log_path=log_path
            ).run()
        finally:
            server.close()
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 2

    # No timing_log_path -> nothing written anywhere.
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        Calibration(client=_StubClient(sock), n_points=4, timeout_s=10.0).run()
    finally:
        server.close()
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_calibration_timing_log_path_is_shared_not_per_session(tmp_path):
    """Both callers (the dashboard's Setup page and app.py's own CLI launch
    path) must resolve to the same file, or the point counts get split across
    files and can't be compared."""
    assert calibration_timing_log_path(tmp_path) == tmp_path / "_diagnostics" / "calibration_timing.jsonl"


# -- S9 stale-result bug (leftover replies from a previous calibration) ---


def test_run_ignores_stale_replies_left_over_from_a_previous_calibration():
    """SPEC-gui-audit-2026-09-10.md S9: the reported bug, reproduced exactly.

    _poll_for_result polls CALIBRATE_RESULT_SUMMARY every _POLL_INTERVAL_S and
    returns on the first satisfying reply, so a real (~10s) calibration leaves
    a queue of later replies unread -- every one of them reporting the finished
    calibration as fully valid. Against the real GP3 HD this made each
    calibration after the first return in ~60ms with the PREVIOUS run's numbers
    while the child was still being calibrated on screen.

    Here the socket already holds such stale replies before run() is called;
    the new calibration must ignore them and report its own result, not the
    stale 99.0 one.
    """
    # What the previous calibration actually left behind on the real device:
    # its trailing summary replies AND its CALIB_RESULT push. Together these
    # hit _poll_for_result's fast path (summary satisfied *and* per_point
    # already known), so it returns instantly -- which is why the grace window
    # from item 2a cannot mask this the way it would for a summary alone.
    stale = (
        '<CAL ID="CALIB_RESULT" CALX1="0.50000" CALY1="0.50000" '
        'LX1="0.99000" LY1="0.99000" LV1="1" RX1="0.99000" RY1="0.99000" RV1="1" />\r\n'
        '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="99.0" VALID_POINTS="5" />\r\n'
    )
    script = [
        # This run's own result, arriving only after a realistic delay.
        (0.6, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="12.5" VALID_POINTS="5" />\r\n'),
    ]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        # Seed the socket with the previous calibration's leftover replies.
        server.send_now(stale * 3)
        time.sleep(0.2)  # let them land in the client's receive buffer

        started = time.monotonic()
        result = Calibration(client=_StubClient(sock), n_points=5, timeout_s=5.0).run()
        elapsed = time.monotonic() - started

        # The stale 99.0 must not be what gets reported...
        assert result.mean_error_px == pytest.approx(12.5)
        # ...and the call must actually have waited for this run's own result
        # rather than returning instantly off the stale queue.
        assert elapsed > 0.4
    finally:
        server.close()


def test_run_ignores_a_retained_result_reported_before_this_calibration_could_finish():
    """SPEC-gui-audit-2026-09-10.md S9, the half a socket drain cannot fix.

    On a *fresh* connection there is nothing stale in the socket, yet Gazepoint
    Control still answers CALIBRATE_RESULT_QUERY with the calibration it
    retained from a previous session -- measured against the real device at
    0.031s after CALIBRATE_START, carrying the previous app instance's own
    error value. A result that arrives before the points could physically have
    been animated must not be accepted as this run's.
    """
    script = [
        # Retained from a previous session: satisfying, but impossibly early.
        (0.05, '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="99.0" VALID_POINTS="2" />\r\n'),
        # This run's real result, once the points have actually been animated.
        (
            1.6,
            '<CAL ID="CALIB_RESULT" CALX1="0.50000" CALY1="0.50000" '
            'LX1="0.50229" LY1="0.50279" LV1="1" RX1="0.51467" RY1="0.50870" RV1="1" />\r\n'
            '<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="12.5" VALID_POINTS="2" />\r\n',
        ),
    ]
    server = _ScriptedServer(script)
    try:
        sock = server.connect_client_socket()
        started = time.monotonic()
        # n_points=2 -> _min_calibration_s == 0.4 * 2 * 1.75 == 1.4s, so the
        # 0.05s reply is rejected and the 1.6s one accepted.
        result = Calibration(client=_StubClient(sock), n_points=2, timeout_s=6.0).run()
        elapsed = time.monotonic() - started

        assert result.mean_error_px == pytest.approx(12.5)  # not the retained 99.0
        assert result.per_point is not None  # this run's own breakdown
        assert elapsed >= 1.4  # waited past the earliest a real result could exist
    finally:
        server.close()
