# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the compiled dashboard (one-folder, windowed).

Run through ``tools/pyinstaller/build_exe.py`` rather than directly: the
script sets the work/dist paths, copies ``configs/`` next to the exe (the
app resolves CONFIG_ROOT there when frozen -- ``src/engine/config.py``),
stamps BUILD_INFO.txt and moves the result into ``compiled/``.
"""

from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parents[1]

APP_NAME = "PedsEyeGaze"
ICON = REPO_ROOT / "configs" / "assets" / "branding" / "WTMH.ico"

a = Analysis(
    [str(SPEC_DIR / "launcher.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    # configs/ is deliberately NOT bundled here -- build_exe.py copies it
    # beside the exe so therapists can edit the YAML (CONFIG_ROOT points
    # there in a frozen build).
    datas=[],
    hiddenimports=[
        # Imported at module level by src/app.py, listed to be explicit.
        "PySide6.QtMultimedia",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Analysis-only / dev-only packages the GUI never imports.
        "pandas",
        "matplotlib",
        "cv2",
        "pytest",
        "PyInstaller",
        "tkinter",
        "mcp",
        "qt_mcp",
        # Qt modules this app does not use (keeps the bundle small).
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtQuick3D",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtRemoteObjects",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtWebSockets",
        "PySide6.QtWebChannel",
        "PySide6.QtLocation",
        "PySide6.QtPositioning",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtUiTools",
        "PySide6.QtScxml",
        "PySide6.QtStateMachine",
        "PySide6.QtTextToSpeech",
        "PySide6.QtHttpServer",
        "PySide6.QtGraphs",
        "PySide6.QtGraphsWidgets",
        "PySide6.QtSpatialAudio",
        "PySide6.QtAsyncio",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed; src.main mirrors stdout/stderr + Qt messages into logs/
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
