"""Gazepoint OpenGaze API client (TCP) + offline replay source.

The GP3HD's *Gazepoint Control* application exposes a TCP server (default
``127.0.0.1:4242``) that speaks a small XML protocol. Clients send
``<SET ID="ENABLE_SEND_..." STATE="1" />`` records to subscribe to data fields,
then receive a stream of ``<REC ... />`` records — one per gaze sample.

This module provides:

* :func:`parse_rec` — parse a ``<REC .../>`` line into an attribute dict.
* :func:`rec_to_sample` — convert that dict into a normalized :class:`GazeSample`.
* :class:`ReplayGazeSource` — deterministic, thread-free playback of a
  ``.jsonl`` fixture, used by the headless pipeline and unit tests.
* :class:`GazepointClient` — the live TCP client (plan section 5.1). It can also
  drive a *paced* replay when no hardware is attached, so the full GUI can be
  developed with no tracker present.

All output coordinates are normalized (0-1); pixel conversion is the canvas's
responsibility.
"""

from __future__ import annotations

import json
import re
import socket
import threading
import time
from collections.abc import Iterable
from pathlib import Path

from ..data.schema import GazeSample

_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')

# OpenGaze SET records used to subscribe to the fields we need (plan 5.1).
#
# NOTE: rec_to_sample() reads LPMM/RPMM (pupil diameter in millimeters), which
# is gated by ENABLE_SEND_PUPILMM (API manual §5.16) -- not by
# ENABLE_SEND_PUPIL_LEFT/RIGHT, which instead gate the pixel-based LPD/RPD
# fields (§5.9/5.10) that this client does not read. Both config keys map to
# the one PUPILMM enable so `gazepoint.enable.pupil_left`/`pupil_right` in
# configs/default.yaml keep working as independent on/off switches.
_ENABLE_RECORDS = {
    "time": "ENABLE_SEND_TIME",
    "pog_fix": "ENABLE_SEND_POG_FIX",
    "pog_best": "ENABLE_SEND_POG_BEST",
    "pupil_left": "ENABLE_SEND_PUPILMM",
    "pupil_right": "ENABLE_SEND_PUPILMM",
    "cursor": "ENABLE_SEND_CURSOR",
}


def enable_command(record_id: str, state: bool = True) -> bytes:
    """Build an OpenGaze SET command as bytes."""
    return f'<SET ID="{record_id}" STATE="{1 if state else 0}" />\r\n'.encode("ascii")


_TAG_RE = re.compile(r"^<(\w+)\b")


def parse_attrs(line: str) -> tuple[str, dict[str, str]] | None:
    """Parse any OpenGaze line (``<REC.../>``, ``<ACK.../>``, ``<CAL.../>``, ...)
    into ``(tag, attrs)``. Returns ``None`` for blank or malformed lines.

    Shared by :func:`parse_rec` (data records) and calibration's result
    polling (ACK/CAL records), which otherwise need the same attribute
    grammar.
    """
    stripped = line.strip()
    tag_match = _TAG_RE.match(stripped)
    if not tag_match:
        return None
    return tag_match.group(1), {k: v for k, v in _ATTR_RE.findall(stripped)}


def parse_rec(line: str) -> dict[str, str] | None:
    """Parse a single ``<REC .../>`` line into an attribute dict.

    Returns ``None`` for lines that are not REC records (ACK, CAL, blank).
    """
    parsed = parse_attrs(line)
    if parsed is None or parsed[0] != "REC":
        return None
    return parsed[1]


def _to_float(attrs: dict[str, str], key: str) -> float | None:
    raw = attrs.get(key)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _to_bool(attrs: dict[str, str], key: str) -> bool:
    return attrs.get(key, "0") == "1"


def rec_to_sample(attrs: dict[str, str], t_ns: int) -> GazeSample:
    """Convert parsed REC attributes to a normalized :class:`GazeSample`.

    Uses the *best* POG (BPOG) as the pointer when valid, otherwise falls back
    to the fixation POG (FPOG). ``t_ns`` is the capture timestamp to stamp on
    the sample (callers pass the receive time for live data).
    """
    bpogv = _to_bool(attrs, "BPOGV")
    fpogv = _to_bool(attrs, "FPOGV")

    if bpogv and "BPOGX" in attrs:
        x = _to_float(attrs, "BPOGX")
        y = _to_float(attrs, "BPOGY")
        valid = True
    else:
        x = _to_float(attrs, "FPOGX")
        y = _to_float(attrs, "FPOGY")
        valid = fpogv

    fix_id = attrs.get("FPOGID")
    fixation_id = int(fix_id) if (fix_id not in (None, "") and fpogv) else None

    return GazeSample(
        t_ns=t_ns,
        x=x if x is not None else 0.0,
        y=y if y is not None else 0.0,
        valid=bool(valid and x is not None and y is not None),
        fixation_id=fixation_id,
        fix_duration_s=_to_float(attrs, "FPOGD"),
        pupil_left=_to_float(attrs, "LPMM"),
        pupil_right=_to_float(attrs, "RPMM"),
    )


def _load_replay_records(path: str | Path) -> list[tuple[float, dict]]:
    """Load a replay ``.jsonl`` file into ``(offset_s, record)`` pairs.

    Each line may be either a raw REC attribute dict (containing e.g. ``FPOGX``)
    or a pre-normalized sample dict with keys ``t_ns``/``x``/``y``/``valid``.
    ``offset_s`` is the sample's time relative to the first sample.
    """
    records: list[tuple[float, dict]] = []
    base_time: float | None = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rec = json.loads(line)
        # Determine a relative time offset in seconds.
        if "t_ns" in rec:
            t = rec["t_ns"] / 1e9
        elif "TIME" in rec:
            t = float(rec["TIME"])
        else:
            t = None
        if t is not None:
            if base_time is None:
                base_time = t
            offset = t - base_time
        else:
            # No timestamp: fall back to index-based ordering downstream.
            offset = float(len(records))
        records.append((offset, rec))
    return records


def _record_to_sample(rec: dict, t_ns: int) -> GazeSample:
    """Turn a replay record (raw REC or normalized) into a GazeSample."""
    if "FPOGX" in rec or "BPOGX" in rec:
        return rec_to_sample({k: str(v) for k, v in rec.items()}, t_ns)
    return GazeSample(
        t_ns=t_ns,
        x=float(rec.get("x", 0.0)),
        y=float(rec.get("y", 0.0)),
        valid=bool(rec.get("valid", True)),
        fixation_id=rec.get("fixation_id"),
        fix_duration_s=rec.get("fix_duration_s"),
        pupil_left=rec.get("pupil_left"),
        pupil_right=rec.get("pupil_right"),
    )


class ReplayGazeSource:
    """Deterministic, thread-free playback of a gaze fixture.

    The engine advances a virtual clock; :meth:`sample_at` returns the most
    recent sample whose offset is <= the elapsed virtual time. This makes the
    whole pipeline reproducible (no wall-clock, no threads) for tests and the
    ``--replay`` headless demo.
    """

    def __init__(self, path: str | Path, loop: bool = True) -> None:
        self._records = _load_replay_records(path)
        if not self._records:
            raise ValueError(f"Replay fixture is empty: {path}")
        self._loop = loop
        self._duration = self._records[-1][0]

    @property
    def duration_s(self) -> float:
        return self._duration

    def sample_at(self, elapsed_s: float) -> GazeSample:
        """Return the sample active at ``elapsed_s`` seconds into playback."""
        if self._loop and self._duration > 0:
            elapsed_s = elapsed_s % (self._duration + 1e-6)
        # Records are time-ordered; find last with offset <= elapsed.
        idx = 0
        for i, (offset, _rec) in enumerate(self._records):
            if offset <= elapsed_s:
                idx = i
            else:
                break
        offset, rec = self._records[idx]
        t_ns = int(elapsed_s * 1e9)
        return _record_to_sample(rec, t_ns)

    def iter_samples(self, base_ns: int = 0) -> Iterable[GazeSample]:
        """Iterate all fixture samples with absolute timestamps from ``base_ns``."""
        for offset, rec in self._records:
            yield _record_to_sample(rec, base_ns + int(offset * 1e9))


class GazepointClient:
    """Live Gazepoint TCP client with a background reader thread.

    Interface follows plan section 5.1. When ``replay_path`` is given, no socket
    is opened; a background thread paces the fixture in real time so the GUI
    behaves as if a tracker were attached.
    """

    def __init__(
        self,
        enable: dict[str, bool] | None = None,
        replay_path: str | Path | None = None,
        reconnect_interval_s: float = 1.0,
    ) -> None:
        self._enable = enable or {k: True for k in _ENABLE_RECORDS}
        self._replay_path = replay_path
        self._reconnect_interval_s = reconnect_interval_s
        self._host = "127.0.0.1"
        self._port = 4242
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest: GazeSample | None = None
        # Replay mode has no socket to lose, so it's always "connected".
        self._connected = replay_path is not None

    # -- connection --------------------------------------------------------

    def connect(self, host: str = "127.0.0.1", port: int = 4242) -> None:
        self._host = host
        self._port = port
        if self._replay_path is not None:
            return  # replay mode needs no socket
        self._open_socket()

    def _open_socket(self) -> None:
        """Open (or reopen) the TCP socket and (re-)subscribe to data fields.

        Raises ``OSError`` on failure; caller decides whether that's fatal
        (initial :meth:`connect`) or something to retry (the reader thread's
        reconnect loop, see :meth:`_reconnect`).
        """
        sock = socket.create_connection((self._host, self._port), timeout=5.0)
        try:
            sock.settimeout(1.0)
            for key, enabled in self._enable.items():
                record_id = _ENABLE_RECORDS.get(key)
                if record_id and enabled:
                    sock.sendall(enable_command(record_id, True))
            # Master switch: individual ENABLE_SEND_* calls above only select
            # which fields appear in each REC; the server won't stream any REC
            # records at all until ENABLE_SEND_DATA is set (API manual §3.1).
            sock.sendall(enable_command("ENABLE_SEND_DATA", True))
        except OSError:
            sock.close()
            raise
        self._sock = sock
        self._connected = True

    def is_connected(self) -> bool:
        """Whether the socket is currently connected and streaming.

        False while a live connection is down and the background thread is
        retrying — callers should treat this distinctly from "gaze lost"
        (no face detected), since a stale last-known sample would otherwise
        look identical to a live, valid gaze that just isn't moving.
        """
        return self._connected

    @property
    def is_live(self) -> bool:
        """Whether this client is backed by a real socket, not a replay fixture.

        A replay source's ``GazeSample.t_ns`` values are relative to its own
        virtual playback clock, not wall time, so comparing them against
        ``time.time_ns()`` (e.g. for latency measurement) is only meaningful
        when this is True.
        """
        return self._replay_path is None

    def start_streaming(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        target = self._run_replay if self._replay_path is not None else self._run_socket
        self._thread = threading.Thread(target=target, name="gazepoint-reader", daemon=True)
        self._thread.start()

    def latest(self) -> GazeSample | None:
        with self._lock:
            return self._latest

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    # -- reader loops ------------------------------------------------------

    def _set_latest(self, sample: GazeSample) -> None:
        with self._lock:
            self._latest = sample

    def _run_socket(self) -> None:
        buffer = ""
        while not self._stop_event.is_set():
            if self._sock is None:
                # Disconnected: block (in small increments) until reconnected
                # or a stop is requested, then resume reading.
                if not self._reconnect():
                    break
                continue
            try:
                chunk = self._sock.recv(4096)
            except TimeoutError:
                continue
            except OSError:
                chunk = b""
            if not chunk:
                # Either a clean close (empty recv) or a socket error above —
                # both mean the stream is down; drop the buffer (a partial
                # line can't be completed by a fresh connection) and go
                # through the same reconnect path.
                buffer = ""
                self._on_disconnected()
                continue
            buffer += chunk.decode("ascii", errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                attrs = parse_rec(line)
                if attrs is not None:
                    self._set_latest(rec_to_sample(attrs, time.time_ns()))

    def _on_disconnected(self) -> None:
        self._connected = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _reconnect(self) -> bool:
        """Wait out the retry interval, then attempt one reconnect.

        Returns False if a stop was requested while waiting (caller should
        exit the reader loop); True otherwise, whether or not the attempt
        itself succeeded — a failed attempt just leaves ``_sock`` as
        ``None`` so the next loop iteration retries after another wait.
        """
        if self._stop_event.wait(self._reconnect_interval_s):
            return False
        try:
            self._open_socket()
        except OSError:
            pass
        return True

    def _run_replay(self) -> None:
        source = ReplayGazeSource(self._replay_path, loop=True)
        start = time.monotonic()
        while not self._stop_event.is_set():
            elapsed = time.monotonic() - start
            self._set_latest(source.sample_at(elapsed))
            time.sleep(1.0 / 60.0)
