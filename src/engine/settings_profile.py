"""Saved per-subject, per-task settings profiles.

SPEC-live-settings-panel.md S10. A physician tunes a task to a child during a
throwaway first run; those values must survive into the data-collection runs
that follow, and be recoverable when the same child returns another day.

Keyed **per subject and per task** rather than globally, mirroring the
calibration precedent (``sessions/_calibrations/<subject_id>/``): one child's
tuning silently becoming the next child's starting point is a protocol hazard,
not a convenience.

Every save is its own file (S10.12): ``<subject>/<task_id>/<local date>_<local
time>.json``. Nothing is ever overwritten, so a profile saved on one day is
still there to choose after a different one is saved the next. The pre-S10.12
flat ``<subject>/<task_id>.json`` is read as one more version and never
rewritten. Timestamps are **local** time with their UTC offset -- the date is
the label an operator picks a version by, and a UTC date is the wrong day for
any save before 08:00 in this lab's timezone (S10.12.2).

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

_FILENAME_TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"


def subject_settings_dir(output_root: str | Path, subject_id: str) -> Path:
    return Path(output_root) / SETTINGS_DIRNAME / subject_id


def settings_profile_path(output_root: str | Path, subject_id: str, task_id: str) -> Path:
    """The pre-S10.12 single-file location. Still read, no longer written."""
    return subject_settings_dir(output_root, subject_id) / f"{task_id}.json"


def settings_profile_dir(output_root: str | Path, subject_id: str, task_id: str) -> Path:
    """Where this subject+task's saved versions live -- and where the Load
    Settings file dialog opens, so one folder holds exactly the choice."""
    return subject_settings_dir(output_root, subject_id) / task_id


def parse_saved_at(value: str) -> datetime | None:
    """ISO ``saved_at`` -> aware datetime, or ``None`` if unparseable.

    Legacy profiles carry ``+00:00`` (UTC); S10.12 ones carry the local
    offset. Both parse; a naive string (no offset) is treated as UTC, which
    is what every legacy writer produced.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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


def load_settings_profile_file(path: str | Path) -> dict[str, Any] | None:
    """Parse one saved version, or ``None`` if it isn't a usable profile.

    Missing, empty, malformed, or structurally wrong all return ``None`` --
    the caller falls back to config defaults and the run proceeds. The
    returned dict carries ``subject_id``/``task_id`` as written (so a file
    picked from the wrong folder can be refused, S10.12.4) and ``path``.
    """
    path = Path(path)
    if not path.is_file():
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
        "subject_id": str(data.get("subject_id", "")),
        "task_id": str(data.get("task_id", "")),
        "path": str(path),
    }


def list_settings_profiles(
    output_root: str | Path, subject_id: str, task_id: str
) -> list[Path]:
    """Every usable saved version for this subject+task, **newest first**.

    Ordered by each file's own ``saved_at``, not by filename, so the legacy
    flat file (whose name carries no date) and any hand-renamed file both
    sort where they belong. Unreadable files are simply left out, per this
    module's tolerance rule. A missing folder is "no versions".
    """
    candidates: list[Path] = []
    directory = settings_profile_dir(output_root, subject_id, task_id)
    try:
        candidates.extend(p for p in directory.iterdir() if p.suffix == ".json")
    except OSError:
        pass
    legacy = settings_profile_path(output_root, subject_id, task_id)
    if legacy.is_file():
        candidates.append(legacy)

    dated: list[tuple[datetime, Path]] = []
    for path in candidates:
        profile = load_settings_profile_file(path)
        if profile is None:
            continue
        when = parse_saved_at(profile["saved_at"])
        if when is None:
            # Unparseable timestamp: keep the file reachable, sorted last.
            when = datetime.min.replace(tzinfo=timezone.utc)
        dated.append((when, path))
    # Secondary key: filename, so two saves within one second (``<stem>.json``
    # then ``<stem>_2.json``, same ``saved_at``) still come back newest first.
    dated.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    return [path for _when, path in dated]


def load_settings_profile(
    output_root: str | Path, subject_id: str, task_id: str
) -> dict[str, Any] | None:
    """Return the **newest** saved profile, or ``None`` if there isn't one.

    This is the automatic path (S10.3): a fresh sitting starts from the most
    recent save. Choosing an older version is the Tasks page's Load Settings
    (S10.12), which goes through :func:`load_settings_profile_file` directly.
    """
    versions = list_settings_profiles(output_root, subject_id, task_id)
    if not versions:
        return None
    return load_settings_profile_file(versions[0])


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
    """Write a **new** version for this subject+task; earlier ones are kept.

    Called only from an explicit user action -- never automatically at the end
    of a run (S10.5.2, decided with the user): an exploratory or abandoned run
    must not be able to overwrite a profile that was working. S10.12 extends
    that to every save: nothing overwrites anything, so a same-second
    collision gets a numeric suffix rather than replacing the earlier file.

    ``calibration`` records the calibration these settings were tuned under
    (S10.5.5). It is **descriptive only** -- nothing reads it back to change
    behaviour. The reason to keep it is that settings tuned under a poor
    calibration may be compensating for bad tracking rather than suiting the
    child, and re-applying them under a good calibration would be wrong;
    without this, nothing in the profile would say which case it was.
    """
    now = datetime.now().astimezone()
    directory = settings_profile_dir(output_root, subject_id, task_id)
    directory.mkdir(parents=True, exist_ok=True)
    stem = now.strftime(_FILENAME_TIME_FORMAT)
    path = directory / f"{stem}.json"
    suffix = 2
    while path.exists():
        path = directory / f"{stem}_{suffix}.json"
        suffix += 1
    payload = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "subject_id": subject_id,
        "task_id": task_id,
        "saved_at": now.isoformat(timespec="seconds"),
        "live": dict(live),
        "structural": dict(structural or {}),
        "calibration": dict(calibration or {}),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
