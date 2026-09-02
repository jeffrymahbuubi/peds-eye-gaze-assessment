"""Tests for OpenGaze REC parsing, deterministic replay, and the live client's
disconnect/reconnect handling (gap D from HANDOVER_GAZEPOINT.md §6)."""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest

from src.inputs.gazepoint_client import (
    GazepointClient,
    ReplayGazeSource,
    enable_command,
    parse_attrs,
    parse_rec,
    rec_to_sample,
)


class FakeGazepointServer:
    """Minimal loopback stand-in for Gazepoint Control's TCP server.

    Accepts one client at a time, ignores whatever it sends (the ENABLE_SEND_*
    subscription commands), and lets the test push REC lines or forcibly drop
    the connection to simulate a real disconnect.
    """

    def __init__(self) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self._listener.settimeout(0.2)
        self.port = self._listener.getsockname()[1]
        self._conn: socket.socket | None = None
        self._received = bytearray()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            conn.settimeout(0.2)
            self._conn = conn
            threading.Thread(target=self._drain, args=(conn,), daemon=True).start()

    def _drain(self, conn: socket.socket) -> None:
        """Continuously record whatever the client sends (SET/GET commands)."""
        while not self._stop.is_set():
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

    def wait_for_connection(self, timeout_s: float = 2.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._conn is not None:
                return
            time.sleep(0.02)
        raise TimeoutError("client never connected")

    def send_rec(self, x: float, y: float) -> None:
        assert self._conn is not None
        line = f'<REC FPOGX="{x}" FPOGY="{y}" FPOGV="1" BPOGX="{x}" BPOGY="{y}" BPOGV="1" />\n'
        self._conn.sendall(line.encode("ascii"))

    def drop_connection(self) -> None:
        assert self._conn is not None
        self._conn.close()
        self._conn = None

    def close(self) -> None:
        self._stop.set()
        if self._conn is not None:
            self._conn.close()
        self._listener.close()
        self._thread.join(timeout=1.0)


@pytest.fixture
def fake_server():
    server = FakeGazepointServer()
    yield server
    server.close()

REC_LINE = (
    '<REC TIME="123.456" FPOGX="0.5124" FPOGY="0.4231" FPOGS="10.1" '
    'FPOGD="0.234" FPOGID="45" FPOGV="1" BPOGX="0.5200" BPOGY="0.4100" '
    'BPOGV="1" LPMM="3.1" RPMM="3.2" />'
)


def test_parse_rec_extracts_attributes():
    attrs = parse_rec(REC_LINE)
    assert attrs is not None
    assert attrs["FPOGID"] == "45"
    assert attrs["BPOGX"] == "0.5200"


def test_parse_rec_ignores_non_rec_lines():
    assert parse_rec('<ACK ID="ENABLE_SEND_POG_FIX" STATE="1" />') is None
    assert parse_rec("") is None


def test_rec_to_sample_prefers_best_pog_when_valid():
    sample = rec_to_sample(parse_rec(REC_LINE), t_ns=1000)
    assert sample.t_ns == 1000
    assert sample.x == pytest.approx(0.52)
    assert sample.y == pytest.approx(0.41)
    assert sample.valid is True
    assert sample.fixation_id == 45
    assert sample.fix_duration_s == pytest.approx(0.234)
    assert sample.pupil_left == pytest.approx(3.1)


def test_rec_to_sample_falls_back_to_fpog_when_best_invalid():
    line = REC_LINE.replace('BPOGV="1"', 'BPOGV="0"')
    sample = rec_to_sample(parse_rec(line), t_ns=5)
    assert sample.x == pytest.approx(0.5124)
    assert sample.y == pytest.approx(0.4231)


def test_rec_to_sample_marks_invalid_when_no_valid_pog():
    line = REC_LINE.replace('BPOGV="1"', 'BPOGV="0"').replace('FPOGV="1"', 'FPOGV="0"')
    sample = rec_to_sample(parse_rec(line), t_ns=5)
    assert sample.valid is False
    assert sample.fixation_id is None


def test_parse_attrs_returns_tag_and_dict_for_any_record_type():
    assert parse_attrs('<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="19.43" VALID_POINTS="5" />') == (
        "ACK",
        {"ID": "CALIBRATE_RESULT_SUMMARY", "AVE_ERROR": "19.43", "VALID_POINTS": "5"},
    )
    assert parse_attrs('<CAL ID="CALIB_START_PT" PT="1" />') == ("CAL", {"ID": "CALIB_START_PT", "PT": "1"})


def test_parse_attrs_returns_none_for_blank_or_malformed():
    assert parse_attrs("") is None
    assert parse_attrs("not a tag") is None


def test_enable_command_format():
    cmd = enable_command("ENABLE_SEND_POG_FIX", True)
    assert cmd == b'<SET ID="ENABLE_SEND_POG_FIX" STATE="1" />\r\n'


def test_replay_source_time_indexed(tmp_path: Path):
    fixture = tmp_path / "g.jsonl"
    lines = [
        {"t_ns": 0, "x": 0.1, "y": 0.1, "valid": True},
        {"t_ns": 500_000_000, "x": 0.9, "y": 0.9, "valid": True},
    ]
    fixture.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")

    src = ReplayGazeSource(fixture, loop=False)
    assert src.sample_at(0.0).x == pytest.approx(0.1)
    assert src.sample_at(0.2).x == pytest.approx(0.1)  # before second sample
    assert src.sample_at(0.6).x == pytest.approx(0.9)  # after second sample
    assert src.duration_s == pytest.approx(0.5)


def test_replay_source_parses_raw_rec_records(tmp_path: Path):
    fixture = tmp_path / "g.jsonl"
    rec = {
        "TIME": 0.0,
        "FPOGX": 0.3,
        "FPOGY": 0.7,
        "FPOGV": 1,
        "FPOGID": 2,
        "BPOGV": 0,
    }
    fixture.write_text(json.dumps(rec), encoding="utf-8")
    src = ReplayGazeSource(fixture, loop=False)
    sample = src.sample_at(0.0)
    assert sample.x == pytest.approx(0.3)
    assert sample.fixation_id == 2


def test_replay_source_empty_raises(tmp_path: Path):
    fixture = tmp_path / "empty.jsonl"
    fixture.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        ReplayGazeSource(fixture)


def _wait_until(predicate, timeout_s: float = 2.0, interval_s: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return predicate()


def test_connect_only_sends_enabled_records(fake_server):
    """Gap C: the `enable` dict passed to GazepointClient must actually gate
    which ENABLE_SEND_* commands go out -- this is what app.py's
    gazepoint.enable.* YAML wiring depends on."""
    enable = {
        "time": True,
        "pog_fix": True,
        "pog_best": False,
        "pupil_left": False,
        "pupil_right": False,
        "cursor": True,
    }
    client = GazepointClient(enable=enable)
    client.connect(host="127.0.0.1", port=fake_server.port)
    try:
        assert _wait_until(lambda: "ENABLE_SEND_DATA" in fake_server.received_text())
        sent = fake_server.received_text()
        assert "ENABLE_SEND_TIME" in sent
        assert "ENABLE_SEND_POG_FIX" in sent
        assert "ENABLE_SEND_CURSOR" in sent
        # PUPILMM gates both pupil_left and pupil_right (see the module-level
        # comment on _ENABLE_RECORDS); both are disabled here, so it must be
        # absent entirely.
        assert "ENABLE_SEND_PUPILMM" not in sent
        assert "ENABLE_SEND_POG_BEST" not in sent
        # The master switch is unconditional, regardless of per-field config.
        assert "ENABLE_SEND_DATA" in sent
    finally:
        client.stop()


def test_is_live_true_for_socket_mode_false_for_replay(tmp_path: Path):
    fixture = tmp_path / "g.jsonl"
    fixture.write_text('{"t_ns": 0, "x": 0.5, "y": 0.5, "valid": true}', encoding="utf-8")

    live_client = GazepointClient()
    assert live_client.is_live is True

    replay_client = GazepointClient(replay_path=fixture)
    assert replay_client.is_live is False


def test_client_reports_connected_after_connect(fake_server):
    client = GazepointClient(reconnect_interval_s=0.1)
    client.connect(host="127.0.0.1", port=fake_server.port)
    try:
        assert client.is_connected() is True
    finally:
        client.stop()


def test_client_detects_disconnect_and_stops_updating(fake_server):
    """A dropped connection must be surfaced via is_connected(), not just a
    thread that silently exits (the original gap D bug)."""
    client = GazepointClient(reconnect_interval_s=0.1)
    client.connect(host="127.0.0.1", port=fake_server.port)
    client.start_streaming()
    try:
        fake_server.wait_for_connection()
        fake_server.send_rec(0.3, 0.4)
        assert _wait_until(lambda: client.latest() is not None)
        assert client.latest().x == pytest.approx(0.3)

        fake_server.drop_connection()
        assert _wait_until(lambda: client.is_connected() is False)
    finally:
        client.stop()


def test_client_reconnects_and_resumes_streaming(fake_server):
    client = GazepointClient(reconnect_interval_s=0.1)
    client.connect(host="127.0.0.1", port=fake_server.port)
    client.start_streaming()
    try:
        fake_server.wait_for_connection()
        fake_server.drop_connection()
        assert _wait_until(lambda: client.is_connected() is False)

        # Server keeps accepting; the reader thread should reconnect on its own.
        fake_server.wait_for_connection()
        assert _wait_until(lambda: client.is_connected() is True)

        fake_server.send_rec(0.7, 0.8)
        assert _wait_until(lambda: client.latest() is not None and client.latest().x == pytest.approx(0.7))
    finally:
        client.stop()


def test_client_stop_is_prompt_during_reconnect_wait(fake_server):
    client = GazepointClient(reconnect_interval_s=5.0)
    client.connect(host="127.0.0.1", port=fake_server.port)
    client.start_streaming()
    fake_server.wait_for_connection()
    fake_server.drop_connection()
    assert _wait_until(lambda: client.is_connected() is False)

    start = time.monotonic()
    client.stop()
    # stop() must not block for the (long) reconnect interval.
    assert time.monotonic() - start < 2.5
