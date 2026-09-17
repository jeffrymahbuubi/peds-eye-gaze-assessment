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

# Canned replies for the connect-time device-info GET queries
# (SPEC-ui-setup-task-selection.md S23) -- keyed by GET ID.
_DEVICE_INFO_REPLIES = {
    "PRODUCT_ID": '<ACK ID="PRODUCT_ID" VALUE="GP3HD" BUS="USB3" RATE="150" />\n',
    "SERIAL_ID": '<ACK ID="SERIAL_ID" VALUE="GP3HD-TEST-0001" />\n',
    "CAMERA_SIZE": '<ACK ID="CAMERA_SIZE" WIDTH="752" HEIGHT="480" />\n',
    "API_ID": '<ACK ID="API_ID" VALUE="2.0" />\n',
    # SPEC-gui-audit-2026-09-10.md item 5 -- the tracked-screen region.
    "SCREEN_SIZE": '<ACK ID="SCREEN_SIZE" X="0" Y="0" WIDTH="1920" HEIGHT="1080" />\n',
    # all_gaze.csv's TIMETICK(f=..) header (SPEC-gazepoint-analysis-export-parity.md S5.1).
    "TIME_TICK_FREQUENCY": '<ACK ID="TIME_TICK_FREQUENCY" FREQ="10000000" />\n',
}


class FakeGazepointServer:
    """Minimal loopback stand-in for Gazepoint Control's TCP server.

    Accepts one client at a time, ignores whatever it sends (the ENABLE_SEND_*
    subscription commands), and lets the test push REC lines or forcibly drop
    the connection to simulate a real disconnect.
    """

    def __init__(self, reply_to_device_info_queries: bool = True) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self._listener.settimeout(0.2)
        self.port = self._listener.getsockname()[1]
        self._conn: socket.socket | None = None
        self._received = bytearray()
        self._reply_to_device_info_queries = reply_to_device_info_queries
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
        """Continuously record whatever the client sends (SET/GET commands),
        optionally replying to the connect-time device-info GET queries."""
        buffer = ""
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
            if not self._reply_to_device_info_queries:
                continue
            buffer += chunk.decode("ascii", errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                parsed = parse_attrs(line)
                if parsed is None:
                    continue
                tag, attrs = parsed
                reply = _DEVICE_INFO_REPLIES.get(attrs.get("ID", "")) if tag == "GET" else None
                if reply is not None:
                    try:
                        conn.sendall(reply.encode("ascii"))
                    except OSError:
                        return

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


@pytest.fixture
def silent_fake_server():
    """A fake server that accepts a connection but never replies to
    anything -- exercises the device-info query's timeout/None-fields path.
    """
    server = FakeGazepointServer(reply_to_device_info_queries=False)
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


def test_connect_sends_the_export_parity_records_when_enabled(fake_server):
    """SPEC-gazepoint-analysis-export-parity.md S5.2: the raw-field keys map
    to their own ENABLE_SEND_* commands, and the pixel-pupil keys are the
    PUPIL_LEFT/RIGHT switches -- not PUPILMM, which the mm keys own."""
    enable = {
        "counter": True, "time_tick": True, "kb": True, "user_data": True,
        "pupil_left_px": True, "pupil_right_px": True, "blink": True, "pix": True,
        "pupil_left": False, "pupil_right": False,
    }
    client = GazepointClient(enable=enable)
    client.connect(host="127.0.0.1", port=fake_server.port)
    try:
        assert _wait_until(lambda: "ENABLE_SEND_DATA" in fake_server.received_text())
        sent = fake_server.received_text()
        for record_id in (
            "ENABLE_SEND_COUNTER", "ENABLE_SEND_TIME_TICK", "ENABLE_SEND_KB",
            "ENABLE_SEND_USER_DATA", "ENABLE_SEND_PUPIL_LEFT", "ENABLE_SEND_PUPIL_RIGHT",
            "ENABLE_SEND_BLINK", "ENABLE_SEND_PIX",
        ):
            assert f'ID="{record_id}"' in sent, record_id
        assert "ENABLE_SEND_PUPILMM" not in sent
        # Biometrics-kit switches are never sent (excluded by decision).
        for record_id in ("ENABLE_SEND_DIAL", "ENABLE_SEND_GSR", "ENABLE_SEND_HR", "ENABLE_SEND_TTL"):
            assert record_id not in sent
    finally:
        client.stop()


def test_drain_raw_yields_every_rec_once_at_device_rate(fake_server):
    """all_gaze.csv needs every <REC>, not the one-per-frame view latest()
    gives: three records pushed faster than any GUI tick must all be drained,
    verbatim, oldest first, and a second drain must be empty."""
    client = GazepointClient(reconnect_interval_s=0.1)
    client.connect(host="127.0.0.1", port=fake_server.port)
    client.start_streaming()
    try:
        fake_server.wait_for_connection()
        for x in (0.1, 0.2, 0.3):
            fake_server.send_rec(x, 0.5)
        assert _wait_until(lambda: len(client._raw_queue) >= 3)
        drained = client.drain_raw()
        assert [attrs["FPOGX"] for _t, attrs in drained] == ["0.1", "0.2", "0.3"]
        assert all(isinstance(t, int) and t > 0 for t, _attrs in drained)
        assert client.drain_raw() == []
    finally:
        client.stop()


def test_replay_queues_raw_records_only_for_raw_fixtures(tmp_path: Path):
    raw_fixture = tmp_path / "raw.jsonl"
    raw_fixture.write_text(
        '{"TIME": "0.0", "FPOGX": "0.4", "FPOGY": "0.4", "FPOGV": "1", "CNT": "0"}\n'
        '{"TIME": "0.5", "FPOGX": "0.6", "FPOGY": "0.6", "FPOGV": "1", "CNT": "1"}\n',
        encoding="utf-8",
    )
    client = GazepointClient(replay_path=raw_fixture)
    client.start_streaming()
    try:
        assert _wait_until(lambda: len(client._raw_queue) >= 1, timeout_s=2.0)
        drained = client.drain_raw()
        assert drained and drained[0][1]["CNT"] == "0"
        # One queue entry per distinct fixture record, not per 60 Hz poll.
        assert len(drained) <= 2
    finally:
        client.stop()

    normalized_fixture = tmp_path / "norm.jsonl"
    normalized_fixture.write_text('{"t_ns": 0, "x": 0.5, "y": 0.5, "valid": true}', encoding="utf-8")
    client = GazepointClient(replay_path=normalized_fixture)
    client.start_streaming()
    try:
        time.sleep(0.1)
        assert client.drain_raw() == []
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


def test_connect_populates_device_info_from_get_replies(fake_server):
    """SPEC-ui-setup-task-selection.md S23: a successful connect should query
    PRODUCT_ID/SERIAL_ID/CAMERA_SIZE/API_ID and expose them via device_info."""
    client = GazepointClient()
    client.connect(host="127.0.0.1", port=fake_server.port)
    try:
        info = client.device_info
        assert info is not None
        assert info.model == "GP3HD"
        assert info.bus == "USB3"
        assert info.rate_hz == 150
        assert info.serial == "GP3HD-TEST-0001"
        assert info.camera_width == 752
        assert info.camera_height == 480
        assert info.api_version == "2.0"
        assert info.screen_x == 0
        assert info.screen_y == 0
        assert info.screen_width == 1920
        assert info.screen_height == 1080
        assert info.tick_frequency == 10_000_000
    finally:
        client.stop()


def test_device_info_fields_stay_none_when_queries_go_unanswered(silent_fake_server):
    """A device that never answers a GET must not fail the connection --
    every device_info field should just stay None."""
    client = GazepointClient()
    client.connect(host="127.0.0.1", port=silent_fake_server.port)
    try:
        assert client.is_connected() is True
        info = client.device_info
        assert info is not None
        assert info.model is None
        assert info.serial is None
        assert info.rate_hz is None
        assert info.camera_width is None
        assert info.api_version is None
        assert info.screen_width is None
        assert info.screen_height is None
    finally:
        client.stop()


def test_device_info_none_before_any_connect():
    client = GazepointClient()
    assert client.device_info is None


def test_device_info_none_in_replay_mode(tmp_path: Path):
    fixture = tmp_path / "g.jsonl"
    fixture.write_text('{"t_ns": 0, "x": 0.5, "y": 0.5, "valid": true}', encoding="utf-8")
    client = GazepointClient(replay_path=fixture)
    client.connect()
    assert client.device_info is None
