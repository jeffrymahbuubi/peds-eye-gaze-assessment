# SPEC-compiled-release — Windows executable builds of the dashboard (v1.0.0)

**Status: v1.0.0 BUILT, smoke-tested, tagged.** One-folder windowed
PyInstaller build via `tools/pyinstaller/build_exe.py`, published to
`compiled/PedsEyeGaze-1.0.0/` (+ `.zip`). This SPEC is the cumulative record
for every future release build too — append a §5 entry per version.

**Created:** 2026-09-17
**Last updated:** 2026-09-17

## 1. Origin / what was asked

User, 2026-09-17: "I need the Version 1.0.0 of the custom software compiled
now. This is Windows environment. Usually I use auto-py-to-exe. Create a
dedicated folder called `compiled` to contain the compiled executable app."

## 2. Decisions (`AskUserQuestion`, 2026-09-17)

| Fork | Decision | Why |
|---|---|---|
| Git relation | **Commit + push + tag `v1.0.0`**, build from the tagged commit | An exe must be traceable to an exact commit; `BUILD_INFO.txt` records commit + dirty flag |
| Layout | **One-folder** (`PedsEyeGaze.exe` + `_internal/`) | PySide6 starts faster; `local_state.json`/`sessions/` persist beside the exe; fewer AV false positives. One-file would unpack ~140 MB per launch and lose saved host/port |
| Tool | **PyInstaller spec + build script, plus an auto-py-to-exe JSON** | auto-py-to-exe is a browser GUI over the same engine — it cannot be driven from this session, but its config can be written so the user's usual workflow still works |
| Console | **Windowed, log to file** | No black console for physicians; a crash still leaves `logs/app-<ts>.log` |
| Physical size / viewing distance | Config-only (from the parity SPEC's same-day decision) | No new Setup-page UI in the release |

## 3. What had to change in the app for a frozen build

Read before touching packaging — each is a real behaviour difference
between "run from source" and "double-click an exe":

1. **Working directory.** `sessions/`, `_diagnostics/`, and `output_root`
   are CWD-relative; a shortcut launches with whatever CWD Windows gives
   it. `src/main.py::prepare_frozen_environment()` `chdir`s to the exe's
   folder when `sys.frozen`. From source it is a no-op.
2. **No console.** A windowed PyInstaller exe starts with
   `sys.stdout`/`sys.stderr` = `None`, so any `print` raises. The same
   function opens `logs/app-<timestamp>.log`, points both streams at it
   (line-buffered) and installs `qInstallMessageHandler` so Qt warnings
   land there too.
3. **No arguments = dashboard.** From source `python -m src.main` with no
   flags prints "Nothing to do"; the exe defaults `argv` to `["--dashboard"]`
   when frozen and given nothing. Explicit flags still win (`--gui`,
   `--replay` work from the exe).
4. **`CONFIG_ROOT`.** From source it is `<repo>/configs` via `__file__`;
   frozen, `__file__` would point inside `_internal/`. `src/engine/config.py`
   now resolves `<exe folder>/configs` when frozen, and the build script
   copies `configs/` there (minus `local_state.json` and caches) — so the
   YAML is where a therapist can find it, and icons/sounds/logo resolve
   through the same root. `configs/` is deliberately **not** in the spec's
   `datas`.
5. **Entry script.** `src/main.py` uses package-relative imports, so
   PyInstaller gets `tools/pyinstaller/launcher.py` (`from src.main import
   main`) with `pathex=[repo root]`.
6. **Version.** `pyproject.toml`, `src/__init__.__version__` and the README
   title bumped 0.1.0 → 1.0.0; the dashboard window title now reads
   "Pediatric Eye-Gaze Assessment v1.0.0" so a screenshot identifies the
   build.

Tests: `tests/test_frozen_bootstrap.py` (5) pin 1–4 by monkeypatching
`sys.frozen`/`sys.executable` — no PyInstaller needed in the suite.

## 4. Build recipe

```
tools/pyinstaller/
  launcher.py          entry shim
  peds_eye_gaze.spec   Analysis/EXE/COLLECT; windowed; WTMH.ico; excludes below
  build_exe.py         runs PyInstaller -> copies configs/ -> BUILD_INFO.txt -> compiled/<name>-<ver>/ -> .zip
  auto-py-to-exe.json  same options for the GUI tool (import it from the repo root)
```

Excludes: `pandas`, `matplotlib`, `cv2`, `pytest`, `PyInstaller`, `tkinter`,
`mcp`, `qt_mcp` (the dev venv carries the qt-mcp probe and `mcp`; neither
belongs in a release) and ~30 unused `PySide6.Qt*` modules. What still ships
from Qt: Core, Gui, Widgets, Multimedia(+Widgets), Network, OpenGL, Svg, plus
Qml/Quick/Pdf/VirtualKeyboard pulled in transitively by the multimedia and
platform plugins — 141 MB total. `upx` off (AV heuristics).

`compiled/` and `build/` are gitignored; PyInstaller ≥ 6.10 is installed
into `dev/.venv` (not a project dependency — `mcp` stayed pinned at 1.29.1
after the install, the qt-mcp footgun did not recur).

## 5. Releases

### 5.1 v1.0.0 — 2026-09-17

- **Commit:** see the git tag `v1.0.0` (the parity work `4387319` plus this
  SPEC's packaging commit). `BUILD_INFO.txt` inside the folder carries the
  exact hash and `git_dirty: no`.
- **Output:** `compiled/PedsEyeGaze-1.0.0/` (141 MB) and
  `compiled/PedsEyeGaze-1.0.0-win64.zip`. Python 3.12.14, PySide6 6.11.2,
  PyInstaller 6.22.3, Windows 11.
- **Smoke tests (a pre-tag build of the identical tree, then repeated on
  the tagged build):**
  - Headless from `C:\`: `PedsEyeGaze.exe --task click_static --replay
    <fixture> --subject FROZENTEST` → exit 0; the log shows
    `cwd=…\compiled\PedsEyeGaze-1.0.0`; `sessions/replay_click_static_FROZENTEST/`
    with all six files appeared **beside the exe**, not in `C:\`; 32 trials
    / 24 hits — the bundled YAML, numpy and recorder all work.
  - GUI, no arguments, launched from `C:\`: window title
    "Pediatric Eye-Gaze Assessment v1.0.0", `logs/app-<ts>.log` created
    with no Qt warnings; `_internal/PySide6/plugins/` carries platforms,
    styles, imageformats, multimedia, iconengines.
  - PyInstaller's warn file lists no missing module of ours.
- **Not exercised:** a full Connect → Calibrate → Run → Results pass from
  the exe against a device (the code path is identical to source, which was
  live-validated the same day for the parity work), and running on a PC
  without a Python install (the whole point of the bundle — worth one check
  on the clinic machine; `logs/` will say what went wrong if anything).

## 6. Log

- **2026-09-17 — v1.0.0 built, via `/sparc:orchestrator`.** Decisions §2;
  app changes §3 (+5 tests); tooling §4; smoke tests §5.1. README gained a
  "Building the Windows executable" section. Committed with the version
  bump, tagged `v1.0.0`, pushed with tags.
