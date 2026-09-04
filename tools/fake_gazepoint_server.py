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
    print("[fake-server] client connected")
    while True:
        try:
            chunk = conn.recv(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        if not chunk:
            print("[fake-server] client disconnected")
            break
        buffer += chunk.decode("ascii", errors="ignore")
        while "\r\n" in buffer:
            line, buffer = buffer.split("\r\n", 1)
            print(f"[fake-server] recv: {line}")
            if 'ID="CALIBRATE_RESULT_SUMMARY"' in line and "<GET" in line:
                ack = (
                    f'<ACK ID="CALIBRATE_RESULT_SUMMARY" AVE_ERROR="{AVE_ERROR}" '
                    f'VALID_POINTS="{N_POINTS}" />\r\n'
                )
                conn.sendall(ack.encode("ascii"))
                print(f"[fake-server] sent: {ack.strip()}")


def main() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", PORT))
    listener.listen(1)
    print(f"[fake-server] listening on 127.0.0.1:{PORT} (Ctrl+C to stop)")
    try:
        while True:
            conn, _addr = listener.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        listener.close()


if __name__ == "__main__":
    main()
