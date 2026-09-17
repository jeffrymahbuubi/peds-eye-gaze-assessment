"""Build the compiled Windows app into ``compiled/PedsEyeGaze-<version>/``.

Usage (from the repo root, with the app venv active or via its python)::

    python tools/pyinstaller/build_exe.py            # build + zip
    python tools/pyinstaller/build_exe.py --no-zip

What it does, in order:

1. ``PyInstaller tools/pyinstaller/peds_eye_gaze.spec`` (one-folder,
   windowed) into ``build/pyinstaller/``.
2. Copies ``configs/`` next to the exe -- minus ``local_state.json`` (a
   per-machine file) and ``__pycache__`` -- because ``src/engine/config.py``
   resolves ``CONFIG_ROOT`` to ``<exe folder>/configs`` when frozen.
3. Writes ``BUILD_INFO.txt`` (version, git commit, dirty flag, build time,
   Python/PySide6/PyInstaller versions) so an exe is traceable to a commit.
4. Moves the folder to ``compiled/PedsEyeGaze-<version>/`` (replacing any
   previous build of the same version) and zips it as
   ``compiled/PedsEyeGaze-<version>-win64.zip``.

``compiled/`` and ``build/`` are gitignored: the exe is an artifact, the
tag is the record.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SPEC = HERE / "peds_eye_gaze.spec"
APP_NAME = "PedsEyeGaze"
BUILD_ROOT = REPO_ROOT / "build" / "pyinstaller"
COMPILED_ROOT = REPO_ROOT / "compiled"

sys.path.insert(0, str(REPO_ROOT))
from src import __version__  # noqa: E402


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_pyinstaller() -> Path:
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--distpath", str(BUILD_ROOT / "dist"),
        "--workpath", str(BUILD_ROOT / "work"),
        str(SPEC),
    ]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    out = BUILD_ROOT / "dist" / APP_NAME
    if not (out / f"{APP_NAME}.exe").exists():
        raise SystemExit(f"PyInstaller produced no exe at {out}")
    return out


def copy_configs(app_dir: Path) -> None:
    src = REPO_ROOT / "configs"
    dst = app_dir / "configs"
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns("local_state.json", "__pycache__", "*.pyc"),
    )
    print(f"+ copied configs/ -> {dst.relative_to(REPO_ROOT)}", flush=True)


def write_build_info(app_dir: Path) -> None:
    import PyInstaller
    import PySide6

    dirty = _git("status", "--porcelain", "--untracked-files=no")
    lines = [
        f"app: {APP_NAME}",
        f"version: {__version__}",
        f"git_commit: {_git('rev-parse', 'HEAD')}",
        f"git_describe: {_git('describe', '--tags', '--always')}",
        f"git_dirty: {'yes' if dirty else 'no'}",
        f"built_at: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"python: {platform.python_version()}",
        f"pyside6: {PySide6.__version__}",
        f"pyinstaller: {PyInstaller.__version__}",
        f"platform: {platform.platform()}",
        "",
        "Run: PedsEyeGaze.exe (opens the dashboard). Command-line modes:",
        "  PedsEyeGaze.exe --task click_static --gui",
        "  PedsEyeGaze.exe --task click_static --replay <fixture.jsonl>",
        "Data: sessions/ next to the exe. Logs: logs/. Config: configs/*.yaml.",
    ]
    (app_dir / "BUILD_INFO.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("+ BUILD_INFO.txt:", " | ".join(lines[1:5]), flush=True)


def publish(app_dir: Path, zip_it: bool) -> Path:
    COMPILED_ROOT.mkdir(exist_ok=True)
    target = COMPILED_ROOT / f"{APP_NAME}-{__version__}"
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(app_dir), str(target))
    print(f"+ published -> {target.relative_to(REPO_ROOT)}", flush=True)
    if zip_it:
        archive = shutil.make_archive(
            str(COMPILED_ROOT / f"{APP_NAME}-{__version__}-win64"), "zip",
            root_dir=COMPILED_ROOT, base_dir=target.name,
        )
        print(f"+ zipped -> {Path(archive).relative_to(REPO_ROOT)}", flush=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-zip", action="store_true", help="Skip the .zip archive.")
    args = parser.parse_args()
    app_dir = run_pyinstaller()
    copy_configs(app_dir)
    write_build_info(app_dir)
    target = publish(app_dir, zip_it=not args.no_zip)
    size_mb = sum(p.stat().st_size for p in target.rglob("*") if p.is_file()) / 1e6
    print(f"done: {target} ({size_mb:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
