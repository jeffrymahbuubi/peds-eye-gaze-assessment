"""Gazepoint Analysis export parity (SPEC-gazepoint-analysis-export-parity.md).

The golden tests run our derivation over a real Gazepoint Analysis v7.3.0
export and compare against the vendor's own output columns -- proof against
Analysis itself, not against our reading of the manual.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.data.analysis_export import (
    ALL_GAZE_COLUMNS,
    all_gaze_header,
    annotate_saccades,
    base_column,
    compute_saccade_metrics,
    finalize_all_gaze,
    fixation_row_indices,
    read_all_gaze,
    rec_to_all_gaze_row,
    saccade_amplitude_deg,
    saccade_mag_dir,
)
from src.data.exporter import write_session_metrics
from src.data.recorder import SessionRecorder
from src.data.schema import SessionMetadata

SAMPLE_DIR = Path(__file__).parent / "fixtures" / "gazepoint_analysis_sample"
# The monitor the sample was recorded on -- fitted to 0.0002 px over every
# saccade (SPEC S4); an exact fit, not a guess.
SAMPLE_SCREEN = (3440, 1440)


@pytest.fixture(scope="module")
def sample():
    header, rows = read_all_gaze(SAMPLE_DIR / "all_gaze.csv")
    _fix_header, fixation_rows = read_all_gaze(SAMPLE_DIR / "fixations.csv")
    return header, rows, fixation_rows


# -- golden tests against the vendor's own export ---------------------------


def test_header_matches_vendor_column_for_column(sample):
    header, _rows, _fix = sample
    assert [base_column(h) for h in header] == list(ALL_GAZE_COLUMNS)
    assert len(ALL_GAZE_COLUMNS) == 62


def test_fixation_rows_match_vendor_fixations_file(sample):
    _header, rows, fixation_rows = sample
    ours = [rows[i]["CNT"] for i in fixation_row_indices(rows)]
    theirs = [r["CNT"] for r in fixation_rows]
    assert ours == theirs
    assert len(ours) == 16


def test_saccade_mag_dir_reproduce_vendor_columns_exactly(sample):
    _header, rows, fixation_rows = sample
    expected = {r["CNT"]: (float(r["SACCADE_MAG"]), float(r["SACCADE_DIR"])) for r in fixation_rows}
    indices = annotate_saccades(rows, *SAMPLE_SCREEN)
    assert len(indices) == len(expected)
    for i in indices:
        row = rows[i]
        mag, direction = expected[row["CNT"]]
        assert float(row["SACCADE_MAG"]) == pytest.approx(mag, abs=0.01)
        assert float(row["SACCADE_DIR"]) == pytest.approx(direction, abs=0.01)
    # Non-fixation rows carry 0, as in the vendor file.
    fixation_set = set(indices)
    assert all(rows[i]["SACCADE_MAG"] == "0.00000" for i in range(len(rows)) if i not in fixation_set)


def test_first_fixation_has_no_saccade(sample):
    _header, rows, _fix = sample
    indices = annotate_saccades(rows, *SAMPLE_SCREEN)
    assert rows[indices[0]]["SACCADE_MAG"] == "0.00000"


def test_canvas_size_would_bias_the_result(sample):
    """SPEC S4.2: scaling by anything but the monitor is wrong -- a narrower
    canvas (side HUD column) shrinks horizontal amplitudes and rotates
    direction. Pinned so nobody 'fixes' the scale to the canvas later."""
    _header, rows, fixation_rows = sample
    narrower = (SAMPLE_SCREEN[0] - 300, SAMPLE_SCREEN[1])
    indices = annotate_saccades(rows, *narrower)
    expected = {r["CNT"]: float(r["SACCADE_MAG"]) for r in fixation_rows}
    mismatches = sum(
        1 for i in indices[1:] if abs(float(rows[i]["SACCADE_MAG"]) - expected[rows[i]["CNT"]]) > 1.0
    )
    assert mismatches > 0


# -- unit behaviour --------------------------------------------------------


def test_saccade_mag_dir_conventions():
    # Pure rightward jump on a 1000x500 monitor: 0.1 of width = 100 px, 0 deg.
    assert saccade_mag_dir((0.5, 0.5), (0.6, 0.5), 1000, 500) == pytest.approx((100.0, 0.0))
    # Upward (smaller y) is 90 deg, screen-up positive.
    assert saccade_mag_dir((0.5, 0.5), (0.5, 0.3), 1000, 500) == pytest.approx((100.0, 90.0))
    # Downward is 270, not -90.
    assert saccade_mag_dir((0.5, 0.5), (0.5, 0.7), 1000, 500) == pytest.approx((100.0, 270.0))


def test_all_gaze_header_carries_start_and_tick_frequency():
    header = all_gaze_header(datetime(2026, 9, 10, 11, 34, 58, 548000), 1_000_000_000)
    assert header[3] == "TIME(2026/09/10 11:34:58.548)"
    assert header[4] == "TIMETICK(f=1000000000)"
    assert base_column(header[3]) == "TIME"


def test_rec_to_all_gaze_row_verbatim_and_defaults():
    attrs = {
        "CNT": "7", "TIME": "12.5", "TIME_TICK": "123", "FPOGX": "0.51295", "FPOGY": "0.21609",
        "FPOGV": "1", "FPOGID": "4", "FPOGD": "0.24249", "BPOGX": "0.5", "BPOGY": "0.4",
        "BPOGV": "1", "LPMM": "3.1", "LPMMV": "1", "BKID": "2", "BKDUR": "0.15", "HRIBI": "0.8",
    }
    row = rec_to_all_gaze_row(attrs, time_s=0.5, media_name="click_static")
    assert list(row) == list(ALL_GAZE_COLUMNS)
    assert row["FPOGX"] == "0.51295"           # verbatim, never re-rounded
    assert row["TIMETICK"] == "123"            # API name TIME_TICK -> column TIMETICK
    assert row["IBI"] == "0.8"                 # API name HRIBI -> column IBI
    assert row["TIME"] == "0.50000"            # recording-relative, not the device origin
    assert row["MEDIA_ID"] == "0" and row["MEDIA_NAME"] == "click_static"
    assert row["KB"] == " " and row["USER"] == "" and row["AOI"] == ""
    assert row["GSR"] == "0" and row["DIAL"] == "0.00000" and row["TTL0"] == "0.000"
    assert row["SACCADE_MAG"] == "0.00000" and row["VID_FRAME"] == "0"


def _metadata() -> SessionMetadata:
    return SessionMetadata(subject_id="P001", session_id="2026-09-17_P001_click_static_run1", started_ns=0)


def _rec(cnt: int, t: float, x: float, y: float, fid: int, fd: float, valid: int = 1) -> dict[str, str]:
    return {
        "CNT": str(cnt), "TIME": f"{t:.5f}", "FPOGX": f"{x:.5f}", "FPOGY": f"{y:.5f}",
        "FPOGS": "0.00000", "FPOGD": f"{fd:.5f}", "FPOGID": str(fid), "FPOGV": str(valid),
        "BPOGX": f"{x:.5f}", "BPOGY": f"{y:.5f}", "BPOGV": "1", "LPMM": "3.0", "RPMM": "3.0",
    }


def _record_two_fixations(tmp_path: Path) -> Path:
    """Fixation 1 at (0.2, 0.5), fixation 2 at (0.7, 0.5), plus a trailing
    record Analysis would ignore. Device TIME starts at 100 s to prove the
    recording-relative origin."""
    meta = _metadata()
    with SessionRecorder(meta, output_root=tmp_path) as rec:
        rec.open_all_gaze(media_name="click_static", tick_frequency=1000)
        recs = [
            _rec(0, 100.00, 0.2, 0.5, 1, 0.0),
            _rec(1, 100.01, 0.2, 0.5, 1, 0.01),
            _rec(2, 100.02, 0.2, 0.5, 1, 0.02),
            _rec(3, 100.03, 0.7, 0.5, 2, 0.0),
            _rec(4, 100.04, 0.7, 0.5, 2, 0.01),
            _rec(5, 100.05, 0.7, 0.5, 2, 0.02),
            _rec(6, 100.06, 0.7, 0.5, 2, 0.03),
        ]
        for i, attrs in enumerate(recs):
            rec.record_raw(i * 10_000_000, attrs)
        rec.write_trials([])
    return tmp_path / meta.session_id


def test_recorder_writes_all_gaze_with_recording_relative_time(tmp_path: Path):
    session_dir = _record_two_fixations(tmp_path)
    header, rows = read_all_gaze(session_dir / "all_gaze.csv")
    assert [base_column(h) for h in header] == list(ALL_GAZE_COLUMNS)
    assert header[4] == "TIMETICK(f=1000)"
    assert len(rows) == 7
    assert rows[0]["TIME"] == "0.00000"
    assert rows[6]["TIME"] == "0.06000"
    assert rows[3]["MEDIA_NAME"] == "click_static"
    assert (session_dir / "gaze_stream.csv").read_text(encoding="utf-8").splitlines()[0].startswith("t_ns,")


def test_recorder_without_all_gaze_writes_nothing_extra(tmp_path: Path):
    meta = _metadata()
    with SessionRecorder(meta, output_root=tmp_path) as rec:
        rec.record_raw(0, _rec(0, 0.0, 0.5, 0.5, 1, 0.0))  # no-op when not opened
        rec.write_trials([])
    assert not (tmp_path / meta.session_id / "all_gaze.csv").exists()


def test_finalize_fills_saccades_and_writes_fixations(tmp_path: Path):
    session_dir = _record_two_fixations(tmp_path)
    fixations_path = finalize_all_gaze(session_dir, 1000, 500)
    assert fixations_path is not None and fixations_path.exists()
    _h, fixation_rows = read_all_gaze(fixations_path)
    # Fixation 1's last valid row is CNT 2; fixation 2's is CNT 5 (CNT 6 is
    # the final record, never emitted -- vendor rule).
    assert [r["CNT"] for r in fixation_rows] == ["2", "5"]
    assert fixation_rows[0]["SACCADE_MAG"] == "0.00000"
    assert float(fixation_rows[1]["SACCADE_MAG"]) == pytest.approx(500.0)   # 0.5 * 1000 px
    assert float(fixation_rows[1]["SACCADE_DIR"]) == pytest.approx(0.0)
    # all_gaze.csv itself now carries the same values on the same row.
    _h2, rows = read_all_gaze(session_dir / "all_gaze.csv")
    assert float(rows[5]["SACCADE_MAG"]) == pytest.approx(500.0)
    assert rows[4]["SACCADE_MAG"] == "0.00000"


def test_finalize_is_a_no_op_without_all_gaze(tmp_path: Path):
    meta = _metadata()
    with SessionRecorder(meta, output_root=tmp_path) as rec:
        rec.write_trials([])
    assert finalize_all_gaze(tmp_path / meta.session_id, 1920, 1080) is None


def test_saccade_metrics_px_only_without_geometry(tmp_path: Path):
    session_dir = _record_two_fixations(tmp_path)
    finalize_all_gaze(session_dir, 1000, 500)
    metrics = compute_saccade_metrics(session_dir, {})
    assert metrics["n_saccades"] == 1
    assert metrics["mean_amplitude_px"] == 500.0
    assert metrics["median_amplitude_px"] == 500.0
    assert metrics["mean_direction_deg"] == 0.0
    assert metrics["mean_amplitude_deg"] is None


def test_saccade_metrics_degrees_when_geometry_known(tmp_path: Path):
    session_dir = _record_two_fixations(tmp_path)
    finalize_all_gaze(session_dir, 1000, 500)
    geometry = {
        "screen_width_px": 1000, "screen_height_px": 500,
        "screen_physical_width_mm": 500.0, "screen_physical_height_mm": 250.0,
        "viewing_distance_mm": 650.0,
    }
    metrics = compute_saccade_metrics(session_dir, geometry)
    # 500 px of a 1000 px / 500 mm screen = 250 mm chord at 650 mm.
    expected = saccade_amplitude_deg(
        500.0, 0.0, screen_w_px=1000, screen_h_px=500, physical_w_mm=500.0,
        physical_h_mm=250.0, viewing_distance_mm=650.0,
    )
    assert metrics["mean_amplitude_deg"] == pytest.approx(expected, abs=1e-3)
    assert expected == pytest.approx(21.77, abs=0.01)


def test_saccade_metrics_empty_without_fixations_file(tmp_path: Path):
    assert compute_saccade_metrics(tmp_path)["n_saccades"] == 0


def test_session_metrics_carry_saccade_block(tmp_path: Path):
    session_dir = _record_two_fixations(tmp_path)
    finalize_all_gaze(session_dir, 1000, 500)
    payload = json.loads(write_session_metrics(session_dir).read_text(encoding="utf-8"))
    assert payload["saccades"]["n_saccades"] == 1
    assert payload["saccades"]["mean_amplitude_px"] == 500.0
