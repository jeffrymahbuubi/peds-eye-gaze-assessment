"""Saved per-subject, per-task settings profiles.

SPEC-live-settings-panel.md S10. A physician tunes a task to a child during a
throwaway first run; those values must survive into the data-collection runs
that follow, and be recoverable when the same child returns another day.

Keyed **per subject and per task** rather than globally, mirroring the
calibration precedent (``sessions/_calibrations/<subject_id>/``): one child's
tuning silently becoming the next child's starting point is a protocol hazard,
not a convenience.

Kept Qt-free so it can be unit tested headlessly, and deliberately tolerant in
the same way as :mod:`src.engine.local_state`: a missing, empty or malformed
profile is treated as "no profile", never as an error. A saved profile is a
convenience, so a corrupt one must degrade to config defaults rather than
block a session.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SETTINGS_DIRNAME = "_settings"
# Written by setup_page.py's "Save Calibration", not by this module -- named
# here only so ``known_subject_ids`` can look there too.
CALIBRATIONS_DIRNAME = "_calibrations"

# Bumped only if the on-disk shape changes incompatibly. Readers ignore keys
# they do not know (see ``apply_live_values_to_config``), so adding a settings
# field does not need a bump.
PROFILE_SCHEMA_VERSION = 1


def subject_settings_dir(output_root: str | Path, subject_id: str) -> Path:
    return Path(output_root) / SETTINGS_DIRNAME / subject_id


def settings_profile_path(output_root: str | Path, subject_id: str, task_id: str) -> Path:
    return subject_settings_dir(output_root, subject_id) / f"{task_id}.json"


def known_subject_ids(output_root: str | Path) -> list[str]:
    """Every subject ID with something already saved under them, sorted.

    Feeds the Setup page's Subject-ID completer (S10.7.3 B). Unions the
    ``_settings`` and ``_calibrations`` subject directories rather than reading
    only the former: a subject routinely has a saved calibration *before* they
    have a settings profile, and a completer that couldn't offer them yet would
    miss the first -- and most likely -- chance to mistype the ID.

    Deliberately does not scan the dated run directories. Those are named
    ``<date>_<subject>_<task>_run<N>``, so recovering the subject from them
    means parsing a composite name, and any ID containing an underscore parses
    wrong; the two dedicated directories are keyed by subject by construction.

    Tolerant like the rest of this module: a missing or unreadable root is
    simply "no known subjects".
    """
    names: set[str] = set()
    for dirname in (SETTINGS_DIRNAME, CALIBRATIONS_DIRNAME):
        directory = Path(output_root) / dirname
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                names.add(entry.name)
    return sorted(names)


def load_settings_profile(
    output_root: str | Path, subject_id: str, task_id: str
) -> dict[str, Any] | None:
    """Return the saved profile, or ``None`` if there isn't a usable one.

    Missing, empty, malformed, or structurally wrong all return ``None`` --
    the caller falls back to config defaults and the run proceeds.
    """
    path = settings_profile_path(output_root, subject_id, task_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    live = data.get("live")
    structural = data.get("structural")
    calibration = data.get("calibration")
    return {
        "live": live if isinstance(live, dict) else {},
        "structural": structural if isinstance(structural, dict) else {},
        "calibration": calibration if isinstance(calibration, dict) else {},
        "saved_at": str(data.get("saved_at", "")),
        "schema_version": data.get("schema_version"),
    }


def resolve_settings_precedence(
    carried_live: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    structural_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide which settings a run starts from, and say which source won.

    The precedence itself (S10.3): values carried from an earlier run **in this
    sitting** beat a saved profile, because they are the most recent deliberate
    act. A profile applies only when nothing was carried.

    Split out of the dashboard and kept Qt-free so the rule can be tested
    headlessly, and so the Tasks-page badge (S10.7.3 A) and the run that
    follows it resolve through the same code. A badge that reported mere file
    existence would promise the profile while the run actually applied carried
    values -- worse than no badge at all.

    ``source`` is one of ``carried`` / ``profile`` / ``defaults``. Note a
    profile carrying *only* structural overrides still counts as ``profile``,
    while one that turns out to hold nothing at all is ``defaults`` -- the
    source names what the run will really use, not what exists on disk.
    """
    if carried_live:
        return {
            "live_overrides": carried_live,
            "structural_overrides": structural_overrides,
            "source": "carried",
            "saved_at": "",
            "calibration": {},
        }
    if profile:
        live = profile.get("live") or None
        structural = profile.get("structural") or {}
        # An explicit per-task Settings dialog choice this sitting outranks the
        # profile's stored structural block, matching the live-value rule above.
        if structural and not structural_overrides:
            structural_overrides = structural
        if live or structural:
            return {
                "live_overrides": live,
                "structural_overrides": structural_overrides,
                "source": "profile",
                "saved_at": profile.get("saved_at", ""),
                "calibration": profile.get("calibration") or {},
            }
    return {
        "live_overrides": None,
        "structural_overrides": structural_overrides,
        "source": "defaults",
        "saved_at": "",
        "calibration": {},
    }


def save_settings_profile(
    output_root: str | Path,
    subject_id: str,
    task_id: str,
    live: dict[str, Any],
    structural: dict[str, Any] | None = None,
    calibration: dict[str, Any] | None = None,
) -> Path:
    """Write the profile for this subject+task, replacing any previous one.

    Called only from an explicit user action -- never automatically at the end
    of a run (S10.5.2, decided with the user): an exploratory or abandoned run
    must not be able to overwrite a profile that was working.

    ``calibration`` records the calibration these settings were tuned under
    (S10.5.5). It is **descriptive only** -- nothing reads it back to change
    behaviour. The reason to keep it is that settings tuned under a poor
    calibration may be compensating for bad tracking rather than suiting the
    child, and re-applying them under a good calibration would be wrong;
    without this, nothing in the profile would say which case it was.
    """
    path = settings_profile_path(output_root, subject_id, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "subject_id": subject_id,
        "task_id": task_id,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "live": dict(live),
        "structural": dict(structural or {}),
        "calibration": dict(calibration or {}),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
