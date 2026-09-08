"""Minimal fake OpenGaze TCP server for testing against a live socket
connection without a real GP3HD attached.

Accepts a connection the same way Gazepoint Control does, and answers
``CALIBRATE_RESULT_SUMMARY`` queries with a fixed, immediately-valid result
-- enough for ``Calibration.run()`` to complete and for ``AssessmentApp`` to
auto-save ``calibration.json`` (SPEC-2026-09-02.md item 7, Goal 1). Sends no
``REC`` gaze data, so the on-screen cursor stays "no gaze" -- this is for
exercising the *connection/calibration* path, not for simulating a moving
gaze signal (use ``--replay`` with ``tools/make_replay_fixture.py`` output
for that instead).

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

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4242
N_POINTS = 5
AVE_ERROR = "8.42"


def handle_client(conn: socket.socket) -> None:
    conn.settimeout(0.2)
    buffer = ""
    print("[fake-server] client connected", flush=True)
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
