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
    load_calibration_result,
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


def test_save_writes_none_mean_error_as_null(tmp_path):
    path = tmp_path / "calibration.json"
    result = CalibrationResult(n_points=5, mean_error_px=None, valid=False)
    save_calibration_result(path, "P001", result)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["mean_error_px"] is None

    saved = load_calibration_result(path)
    assert saved.result.mean_error_px is None
    assert saved.result.valid is False


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
