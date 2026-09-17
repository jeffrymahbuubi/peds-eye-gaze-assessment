"""Gazepoint Analysis export layout -- ``all_gaze.csv`` / ``fixations.csv``.

Reproduces what Gazepoint Analysis writes when you press Export, from our
own recorder's raw ``<REC>`` stream, so a session folder from this app can
be read by anything built for Gazepoint's export (``gp3tools`` etc.) and so
the derived columns Analysis computes at export time -- ``SACCADE_MAG``,
``SACCADE_DIR``, and the one-row-per-fixation file -- exist here without
Gazepoint Analysis in the loop (SPEC-gazepoint-analysis-export-parity.md).

Every rule in this module was fitted to, and is golden-tested against, a
real Analysis v7.3.0 export (``tests/fixtures/gazepoint_analysis_sample/``),
not the manual alone:

* ``SACCADE_MAG`` = pixel distance between consecutive fixation POGs, scaled
  by the **full tracked monitor** size (never the canvas -- SPEC S4.2);
  ``SACCADE_DIR`` = ``atan2(-dy, dx)`` in degrees, 0-360, screen-up
  positive. Both are written only on a fixation's row, 0 elsewhere.
* A fixation's row is the **last ``FPOGV=1`` record of its ``FPOGID``**,
  excluding the recording's final record (Analysis never emits it), and
  zero-duration fixations are dropped.

Qt-free by design (this package's standing rule) so it is testable headless
and usable from ``analysis/`` scripts.
"""

from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Any

# The 62 columns of a Gazepoint Analysis v7.3.0 ``_all_gaze.csv``, in its
# exact order. ``TIME``/``TIMETICK`` are rendered with their header suffixes
# by :func:`all_gaze_header`; everything else is verbatim.
ALL_GAZE_COLUMNS: tuple[str, ...] = (
    "MEDIA_ID", "MEDIA_NAME", "CNT", "TIME", "TIMETICK",
    "FPOGX", "FPOGY", "FPOGS", "FPOGD", "FPOGID", "FPOGV",
    "BPOGX", "BPOGY", "BPOGV",
    "CX", "CY", "CS", "KB", "KBS", "USER",
    "LPCX", "LPCY", "LPD", "LPS", "LPV",
    "RPCX", "RPCY", "RPD", "RPS", "RPV",
    "BKID", "BKDUR", "BKPMIN",
    "LPMM", "LPMMV", "RPMM", "RPMMV",
    "DIAL", "DIALV", "GSR", "GSR_US", "GSR_US_TONIC", "GSR_US_PHASIC", "GSRV",
    "HR", "HRV", "HRP", "IBI",
    "TTL0", "TTL1", "TTL2", "TTL3", "TTL4", "TTL5", "TTL6", "TTLV",
    "PIXS", "PIXV",
    "AOI", "SACCADE_MAG", "SACCADE_DIR", "VID_FRAME",
)

# What Analysis writes for a field the device did not send (checked against
# the sample: biometrics read 0 / validity 0 without the kit, KB is a single
# space when idle, USER/AOI are empty). Anything not listed defaults to "0".
_ABSENT_DEFAULTS: dict[str, str] = {
    "MEDIA_NAME": "",
    "KB": " ",
    "USER": "",
    "AOI": "",
    "FPOGX": "0.00000", "FPOGY": "0.00000", "FPOGS": "0.00000", "FPOGD": "0.00000",
    "BPOGX": "0.00000", "BPOGY": "0.00000",
    "CX": "0.00000", "CY": "0.00000",
    "LPCX": "0.00000", "LPCY": "0.00000", "LPD": "0.00000", "LPS": "0.00000",
    "RPCX": "0.00000", "RPCY": "0.00000", "RPD": "0.00000", "RPS": "0.00000",
    "BKDUR": "0.00000",
    "LPMM": "0.00000", "RPMM": "0.00000",
    "DIAL": "0.00000",
    "GSR_US": "0.00000", "GSR_US_TONIC": "0.00000", "GSR_US_PHASIC": "0.00000",
    "TTL0": "0.000",
    "PIXS": "0.00000",
    "SACCADE_MAG": "0.00000", "SACCADE_DIR": "0.00000",
}

# API attribute names that differ from the export column name.
_API_ALIASES: dict[str, str] = {
    "TIMETICK": "TIME_TICK",
    "IBI": "HRIBI",
}

ALL_GAZE_FILENAME = "all_gaze.csv"
FIXATIONS_FILENAME = "fixations.csv"


def all_gaze_header(start_wallclock: datetime, tick_frequency: int | None) -> list[str]:
    """Column names as Analysis writes them: ``TIME(<recording start>)`` and
    ``TIMETICK(f=<Hz>)`` carry their context in the header."""
    stamp = start_wallclock.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
    header = []
    for name in ALL_GAZE_COLUMNS:
        if name == "TIME":
            header.append(f"TIME({stamp})")
        elif name == "TIMETICK":
            header.append(f"TIMETICK(f={tick_frequency if tick_frequency else 0})")
        else:
            header.append(name)
    return header


def base_column(header_name: str) -> str:
    """``TIME(2026/09/10 11:34:58.548)`` -> ``TIME``; other names unchanged."""
    paren = header_name.find("(")
    return header_name if paren < 0 else header_name[:paren]


def rec_to_all_gaze_row(
    attrs: dict[str, str],
    *,
    time_s: float,
    media_name: str,
) -> dict[str, str]:
    """One ``all_gaze.csv`` row from a parsed ``<REC>`` attribute dict.

    ``time_s`` is the recording-relative time Analysis puts in ``TIME`` (the
    caller subtracts the first record's device ``TIME``; the API's own origin
    is Control's last init/calibration, which is not what the export uses).
    Values the device sent are written verbatim -- the API already formats
    them the way the export does -- so this never re-rounds real data.
    """
    row: dict[str, str] = {}
    for name in ALL_GAZE_COLUMNS:
        if name == "MEDIA_ID":
            row[name] = "0"
        elif name == "MEDIA_NAME":
            row[name] = media_name
        elif name == "TIME":
            row[name] = f"{time_s:.5f}"
        elif name in ("AOI", "SACCADE_MAG", "SACCADE_DIR", "VID_FRAME"):
            row[name] = _ABSENT_DEFAULTS.get(name, "0")
        else:
            raw = attrs.get(_API_ALIASES.get(name, name))
            row[name] = raw if raw not in (None, "") else _ABSENT_DEFAULTS.get(name, "0")
    return row


# -- reading back ----------------------------------------------------------


def read_all_gaze(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    """Load an ``all_gaze.csv`` (ours or a Gazepoint Analysis one).

    Returns the header as written plus rows keyed by *base* column name, so
    ``row["TIME"]`` works whatever the header suffix. A trailing empty
    column (Analysis ends every line with a comma) is dropped.
    """
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header and header[-1] == "":
            header = header[:-1]
        keys = [base_column(h) for h in header]
        rows = []
        for values in reader:
            if not values:
                continue
            # A vendor row also ends with the trailing empty column; zip stops
            # at the shorter (keys), which drops it.
            rows.append(dict(zip(keys, values, strict=False)))
    return header, rows


# -- the derivation ----------------------------------------------------------


def fixation_row_indices(rows: list[dict[str, str]]) -> list[int]:
    """Indices of the rows Analysis puts in ``_fixations.csv``.

    Rule, fitted to the sample and golden-tested: the recording's final
    record is never considered; for each ``FPOGID`` take the last row with
    ``FPOGV == 1``; drop fixations whose ``FPOGD`` is 0. Order follows first
    appearance of each id.
    """
    last_valid: dict[str, int] = {}
    for index, row in enumerate(rows[:-1]):
        if row.get("FPOGV") == "1":
            fid = row.get("FPOGID", "")
            last_valid[fid] = index
    return [i for i in last_valid.values() if _to_float(rows[i].get("FPOGD")) > 0.0]


def saccade_mag_dir(
    prev_xy: tuple[float, float],
    cur_xy: tuple[float, float],
    screen_w_px: float,
    screen_h_px: float,
) -> tuple[float, float]:
    """Analysis's ``SACCADE_MAG`` (px) and ``SACCADE_DIR`` (deg) for the jump
    from ``prev_xy`` to ``cur_xy`` (both normalized to the tracked monitor).

    Direction is measured counter-clockwise from +x with screen-up positive,
    in [0, 360). The monitor size is the only correct scale here -- see
    SPEC-gazepoint-analysis-export-parity.md S4.2 for why the canvas is not.
    """
    dx = (cur_xy[0] - prev_xy[0]) * screen_w_px
    dy = (cur_xy[1] - prev_xy[1]) * screen_h_px
    magnitude = math.hypot(dx, dy)
    direction = math.degrees(math.atan2(-dy, dx)) % 360.0
    return magnitude, direction


def annotate_saccades(
    rows: list[dict[str, str]], screen_w_px: float, screen_h_px: float
) -> list[int]:
    """Fill ``SACCADE_MAG``/``SACCADE_DIR`` in place on each fixation row
    (from the previous fixation's POG; the first fixation keeps 0) and zero
    them everywhere else. Returns the fixation row indices."""
    for row in rows:
        row["SACCADE_MAG"] = _ABSENT_DEFAULTS["SACCADE_MAG"]
        row["SACCADE_DIR"] = _ABSENT_DEFAULTS["SACCADE_DIR"]
    indices = fixation_row_indices(rows)
    prev: tuple[float, float] | None = None
    for index in indices:
        row = rows[index]
        cur = (_to_float(row.get("FPOGX")), _to_float(row.get("FPOGY")))
        if prev is not None:
            magnitude, direction = saccade_mag_dir(prev, cur, screen_w_px, screen_h_px)
            row["SACCADE_MAG"] = f"{magnitude:.5f}"
            row["SACCADE_DIR"] = f"{direction:.5f}"
        prev = cur
    return indices


def finalize_all_gaze(
    session_dir: str | Path, screen_w_px: float, screen_h_px: float
) -> Path | None:
    """Post-pass at session close: fill the saccade columns in
    ``all_gaze.csv`` and write ``fixations.csv`` next to it.

    A post-pass because a fixation's saccade columns describe the jump *into*
    it, which is only known once the previous fixation is complete -- exactly
    why Analysis computes these at export time rather than live. Returns the
    ``fixations.csv`` path, or ``None`` if there is no ``all_gaze.csv``.
    """
    session_dir = Path(session_dir)
    all_gaze_path = session_dir / ALL_GAZE_FILENAME
    if not all_gaze_path.exists():
        return None
    header, rows = read_all_gaze(all_gaze_path)
    indices = annotate_saccades(rows, screen_w_px, screen_h_px)
    keys = [base_column(h) for h in header]
    _write_rows(all_gaze_path, header, keys, rows)
    fixations_path = session_dir / FIXATIONS_FILENAME
    _write_rows(fixations_path, header, keys, [rows[i] for i in indices])
    return fixations_path


def _write_rows(path: Path, header: list[str], keys: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for row in rows:
            writer.writerow([row.get(k, "") for k in keys])


# -- session-level aggregates ----------------------------------------------


def saccade_amplitude_deg(
    magnitude_px: float,
    direction_deg: float,
    *,
    screen_w_px: float,
    screen_h_px: float,
    physical_w_mm: float,
    physical_h_mm: float,
    viewing_distance_mm: float,
) -> float:
    """Convert one saccade to degrees of visual angle, per-axis mm scaling so
    non-square pixels are handled, then ``2 * atan(chord / 2d)``."""
    dx_px = magnitude_px * math.cos(math.radians(direction_deg))
    dy_px = magnitude_px * math.sin(math.radians(direction_deg))
    chord_mm = math.hypot(dx_px * physical_w_mm / screen_w_px, dy_px * physical_h_mm / screen_h_px)
    return math.degrees(2.0 * math.atan(chord_mm / (2.0 * viewing_distance_mm)))


def compute_saccade_metrics(session_dir: str | Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Aggregate ``fixations.csv``'s saccade columns for ``session_metrics.json``.

    Amplitude in px always (the vendor-comparable quantity); degrees only
    when ``metadata`` carries the full geometry (screen px, physical mm,
    viewing distance) -- never guessed. Direction is a circular mean.
    """
    empty: dict[str, Any] = {
        "n_saccades": 0,
        "mean_amplitude_px": None,
        "median_amplitude_px": None,
        "mean_amplitude_deg": None,
        "mean_direction_deg": None,
    }
    path = Path(session_dir) / FIXATIONS_FILENAME
    if not path.exists():
        return empty
    _header, rows = read_all_gaze(path)
    saccades = [
        (_to_float(r.get("SACCADE_MAG")), _to_float(r.get("SACCADE_DIR")))
        for r in rows
        if _to_float(r.get("SACCADE_MAG")) > 0.0
    ]
    if not saccades:
        return empty
    magnitudes = sorted(m for m, _ in saccades)
    n = len(magnitudes)
    median = magnitudes[n // 2] if n % 2 else (magnitudes[n // 2 - 1] + magnitudes[n // 2]) / 2
    sin_sum = sum(math.sin(math.radians(d)) for _, d in saccades)
    cos_sum = sum(math.cos(math.radians(d)) for _, d in saccades)
    mean_direction = math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0

    mean_deg: float | None = None
    geometry = _geometry_from_metadata(metadata or {})
    if geometry is not None:
        mean_deg = sum(saccade_amplitude_deg(m, d, **geometry) for m, d in saccades) / n

    return {
        "n_saccades": n,
        "mean_amplitude_px": round(sum(magnitudes) / n, 2),
        "median_amplitude_px": round(median, 2),
        "mean_amplitude_deg": round(mean_deg, 3) if mean_deg is not None else None,
        "mean_direction_deg": round(mean_direction, 2),
    }


def _geometry_from_metadata(metadata: dict[str, Any]) -> dict[str, float] | None:
    keys = {
        "screen_w_px": "screen_width_px",
        "screen_h_px": "screen_height_px",
        "physical_w_mm": "screen_physical_width_mm",
        "physical_h_mm": "screen_physical_height_mm",
        "viewing_distance_mm": "viewing_distance_mm",
    }
    geometry: dict[str, float] = {}
    for arg, field in keys.items():
        value = metadata.get(field)
        if value is None or float(value) <= 0:
            return None
        geometry[arg] = float(value)
    return geometry


def _to_float(raw: str | None) -> float:
    try:
        return float(raw) if raw not in (None, "") else 0.0
    except ValueError:
        return 0.0
