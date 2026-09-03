"""Theme sound assets: each theme's declared hit/miss cue must exist and be a
short, valid PCM WAV. Kept Qt-free (unlike GuiFeedback itself, which needs a
running QApplication/audio device and is verified live via qt-mcp instead —
see SPEC-2026-09-02.md item 4)."""

from __future__ import annotations

import wave

import pytest

from src.engine.config import CONFIG_ROOT, load_theme

THEMES = ["space", "forest"]
CUES = ["hit", "miss"]


@pytest.mark.parametrize("theme_name", THEMES)
def test_theme_declares_hit_and_miss_sounds(theme_name: str):
    theme = load_theme(theme_name)
    for cue in CUES:
        assert theme["sounds"][cue]


@pytest.mark.parametrize("theme_name", THEMES)
@pytest.mark.parametrize("cue", CUES)
def test_theme_sound_file_is_a_short_valid_wav(theme_name: str, cue: str):
    theme = load_theme(theme_name)
    path = CONFIG_ROOT / theme["sounds"][cue]
    assert path.exists(), path

    with wave.open(str(path), "rb") as wav:
        duration_s = wav.getnframes() / wav.getframerate()
        assert wav.getsampwidth() == 2  # 16-bit PCM
        assert 0 < duration_s <= 2.0  # short UI cue, not a full music clip
