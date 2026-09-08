"""WTMH Clinical Teal palette + Qt stylesheet for the Setup/Tasks dashboard.

Same palette applied to the `docs/wireframes/` mockup (SPEC-ui-setup-task-
selection.md S9) and its `tools/apply_wtmh_wireframe_theme.py` retint pass --
this module is that palette's real-app counterpart. Hex values are quoted
directly from S9's mapping table, not re-derived.

Scoped to ``QWidget#wtmhDashboard`` and its descendants only (matching
``operator_panel.py``'s established pattern), so it can never leak into
``TaskCanvas`` or an embedded ``TaskRunView`` -- Qt stylesheets apply to the
widget they're set on plus descendants, never siblings.
"""

from __future__ import annotations

ACCENT = "#1F7A9C"
ACCENT_GRADIENT_START = "#2FA8C4"
ACCENT_GRADIENT_END = "#1A6F95"
TITLEBAR_BG = "#12374A"
TITLEBAR_TEXT = "#CFE6EE"
SOFT_ACCENT = "#DCF0F5"
SOFT_ACCENT_TEXT = "#0F5670"
BACKGROUND = "#F5F9FB"
PANEL_BG = "#FFFFFF"
BORDER = "#DBE6EC"
INK = "#122B3A"
MUTED = "#5C7684"
DANGER = "#E15353"
SUCCESS = "#2F9E6E"
NEUTRAL_BADGE_BG = "#E6EDF1"

STYLESHEET = f"""
QWidget#wtmhDashboard {{ background: {BACKGROUND}; color: {INK}; }}
QWidget#wtmhDashboard QLabel {{ color: {INK}; }}
QWidget#wtmhDashboard QCheckBox {{ color: {INK}; }}

QWidget#wtmhTitleBar {{ background: {TITLEBAR_BG}; }}
QWidget#wtmhTitleBar QLabel {{ color: {TITLEBAR_TEXT}; }}
QLabel#wtmhBrandTitle {{ font-size: 15px; font-weight: 600; }}

QPushButton#wtmhNavButton {{
    color: {TITLEBAR_TEXT};
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}}
QPushButton#wtmhNavButton:hover {{ background: rgba(255,255,255,0.16); }}
QPushButton#wtmhNavButton[active="true"] {{
    background: rgba(255,255,255,0.08);
    border-bottom: 3px solid {ACCENT_GRADIENT_START};
}}

QLabel#wtmhSectionTitle {{ font-size: 18px; font-weight: 600; color: {INK}; }}
QLabel#wtmhMuted {{ color: {MUTED}; }}

QPushButton#wtmhPrimary {{
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_GRADIENT_START}, stop:1 {ACCENT_GRADIENT_END});
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
}}
QPushButton#wtmhPrimary:hover {{ background: {ACCENT_GRADIENT_END}; }}
QPushButton#wtmhPrimary:disabled {{
    background: {SOFT_ACCENT};
    color: {SOFT_ACCENT_TEXT};
}}

QPushButton#wtmhSecondary {{
    color: {SOFT_ACCENT_TEXT};
    background: {SOFT_ACCENT};
    border: 2px solid {SOFT_ACCENT};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton#wtmhSecondary:hover {{ border-color: {ACCENT}; }}

QPushButton#wtmhGhost {{
    color: {INK};
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 16px;
}}
QPushButton#wtmhGhost:hover {{ background: {SOFT_ACCENT}; border-color: {ACCENT}; }}
QPushButton#wtmhGhost:disabled {{ color: {MUTED}; border-color: {BORDER}; }}

QFrame#wtmhCard {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QFrame#wtmhAlertInfo, QFrame#wtmhAlertWarning, QFrame#wtmhAlertSuccess, QFrame#wtmhAlertError {{
    border-radius: 6px;
    padding: 4px;
}}
QFrame#wtmhAlertInfo, QFrame#wtmhAlertWarning {{
    background: {SOFT_ACCENT};
    border-left: 4px solid {ACCENT};
}}
QFrame#wtmhAlertSuccess {{
    background: #E3F5EC;
    border-left: 4px solid {SUCCESS};
}}
QFrame#wtmhAlertError {{
    background: #FBE7E7;
    border-left: 4px solid {DANGER};
}}

QLabel#wtmhBadgeNeutral {{
    background: {NEUTRAL_BADGE_BG};
    color: {MUTED};
    border-radius: 9px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#wtmhBadgeSuccess {{
    background: {SUCCESS};
    color: white;
    border-radius: 9px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#wtmhBadgeAccent {{
    background: {SOFT_ACCENT};
    color: {SOFT_ACCENT_TEXT};
    border-radius: 9px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}

QWidget#wtmhDashboard QLineEdit,
QWidget#wtmhDashboard QTextEdit,
QWidget#wtmhDashboard QComboBox,
QWidget#wtmhDashboard QDateEdit,
QWidget#wtmhDashboard QSpinBox {{
    background: {PANEL_BG};
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
}}
QWidget#wtmhDashboard QLineEdit:focus,
QWidget#wtmhDashboard QTextEdit:focus,
QWidget#wtmhDashboard QComboBox:focus,
QWidget#wtmhDashboard QDateEdit:focus,
QWidget#wtmhDashboard QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
"""
