"""The compiled-exe bootstrap in ``src.main`` (SPEC-compiled-release.md).

Runs from source with ``sys.frozen``/``sys.executable`` monkeypatched -- the
real bundle is smoke-tested by hand (see the SPEC), these pin the behaviour
the bundle depends on without needing PyInstaller in the test run.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from src import __version__
from src import main as entry
from src.engine import config as config_module


def test_not_frozen_from_source_is_a_no_op(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert entry.is_frozen() is False
    assert entry.prepare_frozen_environment() is None
    assert Path.cwd() == tmp_path
    assert not (tmp_path / "logs").exists()


def test_frozen_chdirs_to_exe_folder_and_logs_there(tmp_path: Path, monkeypatch):
    exe_dir = tmp_path / "PedsEyeGaze-x"
    exe_dir.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "PedsEyeGaze.exe"))
    old_out, old_err = sys.stdout, sys.stderr
    try:
        log_path = entry.prepare_frozen_environment()
        print("hello from the app")
        assert Path.cwd() == exe_dir.resolve()
        assert log_path is not None and log_path.parent == exe_dir / "logs"
        assert sys.stdout is sys.stderr  # both mirrored into the same file
    finally:
        sys.stdout.close()
        sys.stdout, sys.stderr = old_out, old_err
        os.chdir(tmp_path)
    text = log_path.read_text(encoding="utf-8")
    assert "=== start" in text and "hello from the app" in text


def test_frozen_config_root_is_beside_the_exe(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "PedsEyeGaze.exe"))
    assert config_module._config_root() == tmp_path.resolve() / "configs"
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert config_module._config_root() == config_module.CONFIG_ROOT


def test_frozen_no_args_means_dashboard(monkeypatch):
    """Double-clicking the exe must open the dashboard, not the 'Nothing to
    do' headless error -- captured by intercepting the parsed args."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(entry, "prepare_frozen_environment", lambda: None)
    seen: dict[str, list[str]] = {}
    real_parser = entry.build_parser()

    class _Spy:
        def parse_args(self, argv):
            seen["argv"] = list(argv)
            raise SystemExit(0)

    monkeypatch.setattr(entry, "build_parser", lambda: _Spy())
    monkeypatch.setattr(sys, "argv", ["PedsEyeGaze.exe"])
    with pytest.raises(SystemExit):
        entry.main()
    assert seen["argv"] == ["--dashboard"]
    # Explicit arguments still win.
    with pytest.raises(SystemExit):
        entry.main(["--task", "click_static", "--gui"])
    assert seen["argv"] == ["--task", "click_static", "--gui"]
    assert real_parser.parse_args(["--dashboard"]).dashboard is True


def test_version_is_1_0_0_everywhere():
    root = Path(__file__).resolve().parents[1]
    assert __version__ == "1.0.0"
    assert 'version = "1.0.0"' in (root / "pyproject.toml").read_text(encoding="utf-8")
