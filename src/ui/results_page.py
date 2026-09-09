"""Dedicated "3 · Results" tab (SPEC-result-logic.md §8.2/§8.3).

Reached via the persistent top-nav "Results" button or a completed task
card's "Analyze" button (``tasks_page.py``) -- shows the most recently
analyzed task's rolled-up result, modeled on a colleague's reference UI
(``resources/images/diki-ui-3.png``)'s 4-category metrics table (Data
quality / Fixation / Saccade / Selection) plus a verbatim Session Log panel.

Supersedes the earlier design where this page auto-showed between a task
run finishing and returning to Tasks (see the SPEC's §3 vs. §8) -- a task
run now always returns straight to Tasks; this page is only ever shown on
request. Reuses ``src.data.exporter``'s already-tested, Qt-free aggregation
functions rather than recomputing anything here -- this widget only formats
and displays their output.

Inherits the ``wtmhDashboard``-scoped stylesheet from ``DashboardWindow``'s
central widget (no separate ``setStyleSheet`` call needed here).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..data.exporter import compute_fixation_saccade_metrics, load_metadata, summarize
from .tasks_page import TASK_INFO


def _fmt(value: Any, suffix: str = "", ndigits: int | None = None) -> str:
    if value is None:
        return "—"
    if ndigits is not None and isinstance(value, float):
        value = round(value, ndigits)
    return f"{value}{suffix}"


def _pct(ratio: float | None, ndigits: int = 0) -> str:
    return _fmt(ratio * 100 if ratio is not None else None, "%", ndigits)


class ResultsPage(QWidget):
    backRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        header_row = QHBoxLayout()
        title = QLabel("3 · Results")
        title.setObjectName("wtmhPageTitle")
        header_row.addWidget(title)
        header_row.addStretch(1)
        self._back_button = QPushButton("← Back to Tasks")
        self._back_button.setObjectName("wtmhGhost")
        self._back_button.clicked.connect(self.backRequested)
        header_row.addWidget(self._back_button)
        outer.addLayout(header_row)

        self._empty_label = QLabel("No results yet — run a task, then click Analyze.")
        self._empty_label.setObjectName("wtmhMuted")
        outer.addWidget(self._empty_label)

        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        outer.addWidget(self._content)
        self._content.setVisible(False)

        self._session_title = QLabel("")
        self._session_title.setObjectName("wtmhSectionTitle")
        content_layout.addWidget(self._session_title)

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("wtmhMuted")
        content_layout.addWidget(self._subtitle)

        self._warning_banner = QFrame()
        self._warning_banner.setObjectName("wtmhAlertWarning")
        warning_layout = QVBoxLayout(self._warning_banner)
        self._warning_label = QLabel("")
        self._warning_label.setWordWrap(True)
        warning_layout.addWidget(self._warning_label)
        content_layout.addWidget(self._warning_banner)
        self._warning_banner.setVisible(False)

        self._data_quality_rows = self._add_category_card(content_layout, "Data quality", [
            "Valid samples", "On-screen samples", "Effective rate", "Calibration error (raw)", "Longest gap",
        ])
        self._fixation_rows = self._add_category_card(content_layout, "Fixation", [
            "Mean duration", "Median duration", "Rate",
        ])
        self._saccade_rows = self._add_category_card(content_layout, "Saccade", [
            "Mean amplitude", "Mean direction", "Latency (to first fixation)",
        ])
        self._selection_rows = self._add_category_card(content_layout, "Selection", [
            "Hit rate", "Median RT", "Mean attempts", "Mean revisits", "Trials needing re-attempt",
        ])

        log_card = QFrame()
        log_card.setObjectName("wtmhCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 14, 16, 14)
        log_title = QLabel("Session Log")
        log_title.setObjectName("wtmhSectionTitle")
        log_layout.addWidget(log_title)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Consolas", 9))
        self._log_view.setFixedHeight(140)
        log_layout.addWidget(self._log_view)
        content_layout.addWidget(log_card)

    @staticmethod
    def _add_category_card(parent_layout: QVBoxLayout, title: str, metrics: list[str]) -> dict[str, QLabel]:
        card = QFrame()
        card.setObjectName("wtmhCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("wtmhSectionTitle")
        layout.addWidget(title_label)

        form = QFormLayout()
        form.setVerticalSpacing(8)
        layout.addLayout(form)

        rows: dict[str, QLabel] = {}
        for metric in metrics:
            value_label = QLabel("—")
            form.addRow(metric, value_label)
            rows[metric] = value_label

        parent_layout.addWidget(card)
        return rows

    def populate(self, session_dir: str | Path, task_id: str, subject_id: str = "") -> None:
        """Compute (via ``exporter``) and display the result for one session.

        Safe to call on any session directory ``exporter``'s functions can
        read, including an empty/aborted run -- both already degrade to
        ``None``/zero rather than raising, so no extra guarding is needed here.
        """
        session_dir = Path(session_dir)
        self._empty_label.setVisible(False)
        self._content.setVisible(True)

        summary = summarize(session_dir)
        fix = compute_fixation_saccade_metrics(session_dir)
        try:
            metadata = load_metadata(session_dir)
        except (OSError, ValueError):
            metadata = {}

        task_name = TASK_INFO.get(task_id, (task_id, ""))[0]
        self._session_title.setText(f"{task_name} — {summary['n_trials']} trials")
        self._subtitle.setText(
            f"Subject: {subject_id or '—'}    Session: {session_dir.name}"
        )

        if fix["valid_ratio"] is not None and fix["valid_ratio"] < 0.8:
            self._warning_label.setText(
                f"! valid share {fix['valid_ratio'] * 100:.0f}% below the 80% floor"
            )
            self._warning_banner.setVisible(True)
        else:
            self._warning_banner.setVisible(False)

        self._data_quality_rows["Valid samples"].setText(_pct(fix["valid_ratio"]))
        self._data_quality_rows["On-screen samples"].setText(_pct(fix["on_screen_ratio"]))
        self._data_quality_rows["Effective rate"].setText(_fmt(fix["effective_rate_hz"], " Hz", 1))
        self._data_quality_rows["Calibration error (raw)"].setText(
            _fmt(metadata.get("calibration_error_px"), " px", 1)
        )
        self._data_quality_rows["Longest gap"].setText(_fmt(fix["longest_gap_s"], " s", 2))

        self._fixation_rows["Mean duration"].setText(_fmt(fix["mean_fixation_duration_s"], " s", 2))
        self._fixation_rows["Median duration"].setText(_fmt(fix["median_fixation_duration_s"], " s", 2))
        self._fixation_rows["Rate"].setText(_fmt(fix["fixation_rate_per_min"], " /min", 1))

        # Amplitude/direction need fixation-centroid tracking this codebase
        # doesn't capture yet (SPEC-result-logic.md §8.4's "needs genuinely
        # new tracking" gap class) -- left as "—" deliberately, not a bug.
        self._saccade_rows["Latency (to first fixation)"].setText(
            _fmt(summary["mean_time_to_first_fixation_ms"], " ms", 0)
        )

        self._selection_rows["Hit rate"].setText(_pct(summary["hit_rate"]))
        self._selection_rows["Median RT"].setText(_fmt(summary["median_reaction_time_ms"], " ms", 0))
        self._selection_rows["Mean attempts"].setText(_fmt(summary["mean_attempts"], "", 2))
        # Mean revisits needs on-target entry/exit tracking this codebase
        # doesn't capture yet -- same deliberate gap as amplitude/direction.
        self._selection_rows["Trials needing re-attempt"].setText(
            _fmt(summary["n_trials_needing_reattempt"])
        )

        log_path = session_dir / "session.log"
        self._log_view.setPlainText(log_path.read_text(encoding="utf-8") if log_path.exists() else "—")
