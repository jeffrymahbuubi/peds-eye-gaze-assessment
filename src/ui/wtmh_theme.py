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

from ..engine.config import CONFIG_ROOT

# S12 fix: Qt's QSS "zero-size box + border" triangle trick does not
# reliably render as a triangle for ::up-arrow/::down-arrow subcontrols in
# this Qt/PySide6 build -- confirmed via a pixel-level zoomed widget grab
# that it painted a solid filled rectangle instead, under both the default
# "windowsvista" style and "Fusion" (SPEC-ui-setup-task-selection.md S12).
# Real PNG assets (generated once via a scratch script, committed here) are
# the standard, actually-reliable fix. CONFIG_ROOT is already absolute
# (Path(__file__).resolve()...), so this path is never CWD-dependent --
# important because QSS `url()` on a stylesheet string (not loaded from a
# .qss file) resolves relative paths against the process's current working
# directory, not this module's location.
_ICONS_DIR = (CONFIG_ROOT / "assets" / "icons").as_posix()

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
# Muted left-border for static info/warning banners -- deliberately NOT the
# same vivid ACCENT used for primary-button gradients/focus rings, so a
# banner never reads as a clickable CTA (SPEC-ui-setup-task-selection.md
# S11.1 critique point 3). Warning gets its own amber tint (S11.3 finding:
# info/warning previously shared identical styling with no way to tell them
# apart).
BANNER_BORDER = "#8FB4C2"
WARNING_BG = "#FBF0DC"
WARNING_BORDER = "#D9A441"

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

/* S16: two-tier title scale -- wtmhPageTitle for "1 · Setup"/"2 · Tasks"
   (largest), wtmhSectionTitle for card titles (one tier down, and now
   also applied to Setup's 4 previously-unstyled card titles). Previously
   both tiers shared wtmhSectionTitle at 18px, so a page title and a card
   title were pixel-identical. margin-bottom gives every card title some
   breathing room before its first content row, in one shared rule
   instead of touching each card-builder call site. */
QLabel#wtmhPageTitle {{ font-size: 22px; font-weight: 700; color: {INK}; }}
QLabel#wtmhSectionTitle {{
    font-size: 16px;
    font-weight: 600;
    color: {INK};
    margin-bottom: 6px;
}}
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
QPushButton#wtmhSecondary:disabled {{
    color: {MUTED};
    background: {NEUTRAL_BADGE_BG};
    border: 2px solid {NEUTRAL_BADGE_BG};
}}

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
QFrame#wtmhAlertInfo {{
    background: {SOFT_ACCENT};
    border-left: 4px solid {BANNER_BORDER};
}}
QFrame#wtmhAlertWarning {{
    background: {WARNING_BG};
    border-left: 4px solid {WARNING_BORDER};
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
QLabel#wtmhBadgeDanger {{
    background: #FBE7E7;
    color: {DANGER};
    border-radius: 9px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}

QWidget#wtmhDashboard QLineEdit,
QWidget#wtmhDashboard QTextEdit,
QWidget#wtmhDashboard QComboBox,
QWidget#wtmhDashboard QDateEdit,
QWidget#wtmhDashboard QSpinBox,
QWidget#wtmhDashboard QDoubleSpinBox {{
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
QWidget#wtmhDashboard QSpinBox:focus,
QWidget#wtmhDashboard QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}

/* Custom chevron + dropdown chrome, replacing the native OS arrow
   (S11.1 critique point 4). Drawn via a real PNG asset (see _ICONS_DIR
   above) -- an earlier zero-size/border "CSS triangle" version rendered as
   a solid filled rectangle instead of a triangle in this Qt/PySide6 build
   (S12), so a real image is used instead of a QSS-only trick. */
QWidget#wtmhDashboard QComboBox {{ padding-right: 22px; }}
QWidget#wtmhDashboard QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid {BORDER};
}}
QWidget#wtmhDashboard QComboBox::down-arrow {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    image: url({_ICONS_DIR}/chevron-down.png);
    width: 16px;
    height: 16px;
    margin-right: 4px;
}}

/* The popup list is a separate top-level QAbstractItemView, not a
   layout-tree descendant of QWidget#wtmhDashboard -- Qt forwards a
   QComboBox's own effective stylesheet down into its popup, so this rule
   still needs to be declared here even though it never leaked in from the
   rules above. Without it the popup falls back to the OS/Qt default
   palette, which on this app's Windows setup renders white text on a white
   background (SPEC-ui-setup-task-selection.md S11.2 finding A -- the Sex
   dropdown bug). Same root-cause family as the QCheckBox fix in S10.

   S13: this rule alone only styles the QListView itself -- the native
   popup FRAME wrapping it (Qt's undocumented QComboBoxPrivateContainer,
   a QFrame with no public class/object-name selector) draws its own
   heavy default border independently, especially visible after S12's
   switch to the Fusion style. QSS can't reach that frame directly, so
   setup_page.py additionally calls
   ``sex_combo.view().setFrameShape(QFrame.Shape.NoFrame)`` in code to
   remove the native frame decoration, leaving this rule's own border/
   radius as the only visible one. */
QWidget#wtmhDashboard QComboBox QAbstractItemView {{
    background: {PANEL_BG};
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}
QWidget#wtmhDashboard QComboBox QAbstractItemView::item {{
    padding: 9px 12px;
    border-radius: 4px;
}}
QWidget#wtmhDashboard QComboBox QAbstractItemView::item:hover {{
    background: {SOFT_ACCENT};
    outline: none;
    border: none;
}}
/* S16: an explicit transparent border (not just outline: none) --
   Fusion's own PE_FrameFocusRect primitive can still paint a bare focus
   outline around the current item on a fresh popup open even with
   outline suppressed; giving it a real border color to paint instead
   (rather than relying on outline suppression alone) is the fix being
   tried here -- verified live, see SPEC-ui-setup-task-selection.md
   §16.3 for the actual result. */
QWidget#wtmhDashboard QComboBox QAbstractItemView::item:focus {{
    background: {SOFT_ACCENT};
    outline: 0;
    border: 1px solid transparent;
}}
QWidget#wtmhDashboard QComboBox QAbstractItemView::item:selected {{
    background: {ACCENT};
    color: white;
    outline: none;
    border: none;
}}

/* Themed spin-box steppers, replacing native OS up/down arrows (S12).
   Arrows are real PNG assets (see _ICONS_DIR above), each given its own
   "padding"-origin, centered subcontrol box -- without an explicit
   subcontrol-origin/position, Qt falls back to its platform style's own
   tiny built-in icon-metric box, which would clip even a real image down
   small. A 1px border between up-button and down-button (previously
   absent) gives the visible separator the critique asked for. */
QWidget#wtmhDashboard QSpinBox::up-button, QWidget#wtmhDashboard QDoubleSpinBox::up-button,
QWidget#wtmhDashboard QSpinBox::down-button, QWidget#wtmhDashboard QDoubleSpinBox::down-button {{
    background: {SOFT_ACCENT};
    width: 18px;
    border-left: 1px solid {BORDER};
}}
QWidget#wtmhDashboard QSpinBox::up-button, QWidget#wtmhDashboard QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: 5px;
    border-bottom: 1px solid {BORDER};
}}
QWidget#wtmhDashboard QSpinBox::down-button, QWidget#wtmhDashboard QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: 5px;
}}
QWidget#wtmhDashboard QSpinBox::up-arrow, QWidget#wtmhDashboard QDoubleSpinBox::up-arrow {{
    subcontrol-origin: padding;
    subcontrol-position: center;
    image: url({_ICONS_DIR}/spin-up.png);
    width: 12px;
    height: 12px;
}}
QWidget#wtmhDashboard QSpinBox::down-arrow, QWidget#wtmhDashboard QDoubleSpinBox::down-arrow {{
    subcontrol-origin: padding;
    subcontrol-position: center;
    image: url({_ICONS_DIR}/spin-down.png);
    width: 12px;
    height: 12px;
}}

/* Custom checkbox check style, replacing the native OS indicator. */
QWidget#wtmhDashboard QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {PANEL_BG};
}}
QWidget#wtmhDashboard QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QWidget#wtmhDashboard QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    image: url({_ICONS_DIR}/checkmark.png);
}}

/* Themed slider, matching the accent gradient rather than native OS chrome
   -- used by TaskSettingsDialog's SliderSpinRow controls. */
QWidget#wtmhDashboard QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}
QWidget#wtmhDashboard QSlider::sub-page:horizontal {{
    background: {ACCENT_GRADIENT_START};
    border-radius: 2px;
}}
QWidget#wtmhDashboard QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
"""
