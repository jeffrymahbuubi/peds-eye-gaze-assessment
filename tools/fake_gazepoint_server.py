"""Minimal fake OpenGaze TCP server for testing against a live socket
connection without a real GP3HD attached.

Accepts a connection the same way Gazepoint Control does, and answers
``CALIBRATE_RESULT_SUMMARY`` queries with a fixed, immediately-valid result
-- enough for ``Calibration.run()`` to complete and for ``AssessmentApp`` to
auto-save ``calibration.json`` (SPEC-2026-09-02.md item 7, Goal 1). Once
``ENABLE_SEND_DATA`` is set, streams a fixed-position ``REC`` at
``REC_RATE_HZ`` (SPEC-ui-setup-task-selection.md S24.4 QA: enough for the
Operator Panel's device-sample-rate meter to show a real, non-placeholder
number) -- not a moving gaze signal (use ``--replay`` with ``tools/
make_replay_fixture.py`` output for that instead).

Usage::

    python tools/fake_gazepoint_server.py [port]   # default 4242

Then point ``configs/default.yaml``'s ``gazepoint.host`` at ``127.0.0.1``
(it has ``git update-index --skip-worktree`` set, so this is a free local
edit -- see README.md's "Editing a config file locally without it showing
up in git status" section) and run the app *without* ``--replay``, e.g.::

    python -m src.main --task click_static --gui --subject DEMO01

Ctrl+C to stop. Remember to point ``gazepoint.host`` back at the real
device's address afterward.
"""

from __future__ import annotations

import socket
import sys
import threading
import time

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4242
N_POINTS = 5
AVE_ERROR = "8.42"
REC_RATE_HZ = 20.0

# Canned replies for the connect-time device-info GET queries
# (SPEC-ui-setup-task-selection.md S23). Deliberately reproduces the real
# GP3HD audit's exact reported values (S24) -- NONE/0 placeholders and a
# sub-150 rate -- so this fake server doubles as a QA fixture for S24.1's
# placeholder filter and S24.3's rate-warning banner, not just the happy
# path. Keyed by GET ID.
DEVICE_INFO_REPLIES = {
    "PRODUCT_ID": '<ACK ID="PRODUCT_ID" VALUE="NONE" BUS="USB2" RATE="60" />\r\n',
    "SERIAL_ID": '<ACK ID="SERIAL_ID" VALUE="0" />\r\n',
    "CAMERA_SIZE": '<ACK ID="CAMERA_SIZE" WIDTH="752" HEIGHT="480" />\r\n',
    "API_ID": '<ACK ID="API_ID" VALUE="2.8" />\r\n',
}


def send_rec_loop(conn: socket.socket, stop_event: threading.Event) -> None:
    """Streams a fixed-position, always-valid REC at REC_RATE_HZ until the
    connection drops or stop_event is set (SPEC S24.4 QA support)."""
    t0 = time.monotonic()
    interval_s = 1.0 / REC_RATE_HZ
    while not stop_event.wait(interval_s):
        elapsed = time.monotonic() - t0
        line = (
            f'<REC TIME="{elapsed:.3f}" FPOGX="0.5" FPOGY="0.5" FPOGV="1" '
            f'BPOGX="0.5" BPOGY="0.5" BPOGV="1" LPMM="3.0" RPMM="3.0" />\r\n'
        )
        try:
            conn.sendall(line.encode("ascii"))
        except OSError:
            return


def handle_client(conn: socket.socket) -> None:
    conn.settimeout(0.2)
    buffer = ""
    stop_rec = threading.Event()
    rec_thread: threading.Thread | None = None
    print("[fake-server] client connected", flush=True)
    try:
        while True:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                print("[fake-server] client disconnected", flush=True)
                break
            buffer += chunk.decode("ascii", errors="ignore")
            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                print(f"[fake-server] recv: {line}", flush=True)
                if 'ID="CALIBRATE_RESULT_SUMMARY"' in line and "<GET" in line:
                    ack = (
                        f'<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="{AVE_ERROR}" '
                        f'VALID_POINTS="{N_POINTS}" />\r\n'
                    )
                    conn.sendall(ack.encode("ascii"))
                    print(f"[fake-server] sent: {ack.strip()}", flush=True)
                    continue
                if 'ID="ENABLE_SEND_DATA"' in line and 'STATE="1"' in line and rec_thread is None:
                    rec_thread = threading.Thread(
                        target=send_rec_loop, args=(conn, stop_rec), daemon=True
                    )
                    rec_thread.start()
                    print(f"[fake-server] streaming REC at {REC_RATE_HZ:.0f} Hz", flush=True)
                    continue
                if "<GET" in line:
                    for query_id, reply in DEVICE_INFO_REPLIES.items():
                        if f'ID="{query_id}"' in line:
                            conn.sendall(reply.encode("ascii"))
                            print(f"[fake-server] sent: {reply.strip()}", flush=True)
                            break
    finally:
        stop_rec.set()
        if rec_thread is not None:
            rec_thread.join(timeout=1.0)


def main() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", PORT))
    listener.listen(1)
    # A blocking accept() with no timeout can't be interrupted by Ctrl+C on
    # Windows -- CPython only checks for a pending KeyboardInterrupt between
    # bytecode instructions, and a C-level blocking socket call doesn't
    # return control to the interpreter until it has something to report.
    # With nothing ever connecting, accept() would simply never return and
    # Ctrl+C would appear to do nothing. Polling with a short timeout (same
    # pattern already used for the per-client socket in handle_client)
    # gives the interpreter a chance to service the signal every 0.5s.
    listener.settimeout(0.5)
    print(f"[fake-server] listening on 127.0.0.1:{PORT} (Ctrl+C to stop)", flush=True)
    try:
        while True:
            try:
                conn, _addr = listener.accept()
            except TimeoutError:
                continue
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        print("[fake-server] stopping", flush=True)
    finally:
        listener.close()


if __name__ == "__main__":
    main()
