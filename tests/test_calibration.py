"""Tests for Calibration.run()'s CALIBRATE_RESULT_SUMMARY polling (gap A)."""

from __future__ import annotations

import socket
import threading
import time

import pytest

from src.engine.calibration import Calibration


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


def test_invalid_n_points_raises():
    with pytest.raises(ValueError):
        Calibration(client=None, n_points=7)


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
