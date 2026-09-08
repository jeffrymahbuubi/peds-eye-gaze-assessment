"""Retint wiremd-rendered wireframe HTML into the WTMH Clinical Teal palette.

wiremd's built-in styles (sketch/clean/wireframe/material/tailwind/brutal/none)
are fixed CSS presets -- there is no `--palette`/custom-color CLI flag, so a
brand palette has to be applied as a post-render pass over the generated
HTML's embedded <style> block. This script is that pass: run it after every
`wiremd *.md --style clean -o *.html` re-render (see docs/specs/
SPEC-ui-setup-task-selection.md S9 for the full palette table and rationale).

Usage:
    python tools/apply_wtmh_wireframe_theme.py docs/wireframes/setup.html docs/wireframes/tasks.html
"""

from __future__ import annotations

import sys
from pathlib import Path

# (old, new) exact literal substrings from wiremd's "clean" style CSS output.
# Each old string must appear in the file -- a zero-count replacement raises,
# so a future wiremd upgrade that changes this CSS text will fail loudly
# instead of silently no-op'ing.
REPLACEMENTS: list[tuple[str, str]] = [
    # -- shared structural block (tabs) --
    (
        ".wmd-tab-header { display: inline-block; padding: 8px 16px; border: none; "
        "border-bottom: 2px solid transparent; margin-bottom: -2px; font-size: 14px; "
        "font-weight: 500; color: #888; background: transparent; cursor: pointer; "
        "font-family: inherit; transition: color 0.15s; }",
        ".wmd-tab-header { display: inline-block; padding: 8px 16px; border: none; "
        "border-bottom: 2px solid transparent; margin-bottom: -2px; font-size: 14px; "
        "font-weight: 500; color: #5C7684; background: transparent; cursor: pointer; "
        "font-family: inherit; transition: color 0.15s; }",
    ),
    (
        ".wmd-tab-header:hover { color: #333; }",
        ".wmd-tab-header:hover { color: #122B3A; }",
    ),
    (
        ".wmd-tab-header.wmd-active { border-bottom-color: currentColor; color: #333; font-weight: 600; }",
        ".wmd-tab-header.wmd-active { border-bottom-color: currentColor; color: #1A6F95; font-weight: 600; }",
    ),
    # -- body / type --
    (
        "body.wmd-root {\n"
        "  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;\n"
        "  background: #ffffff;\n"
        "  color: #1a1a1a;\n"
        "  padding: 40px;\n"
        "  margin: 0;\n"
        "  line-height: 1.6;\n"
        "}",
        "body.wmd-root {\n"
        "  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;\n"
        "  background: #F5F9FB;\n"
        "  color: #122B3A;\n"
        "  padding: 40px;\n"
        "  margin: 0;\n"
        "  line-height: 1.6;\n"
        "}",
    ),
    (
        ".wmd-h1, .wmd-h2, .wmd-h3, .wmd-h4, .wmd-h5, .wmd-h6 {\n"
        "  font-weight: 600;\n"
        "  margin: 1.5em 0 0.75em;\n"
        "  color: #000;\n"
        "  letter-spacing: -0.02em;\n"
        "}",
        ".wmd-h1, .wmd-h2, .wmd-h3, .wmd-h4, .wmd-h5, .wmd-h6 {\n"
        "  font-weight: 600;\n"
        "  margin: 1.5em 0 0.75em;\n"
        "  color: #122B3A;\n"
        "  letter-spacing: -0.02em;\n"
        "}",
    ),
    (
        ".wmd-h1 { font-size: 2.5em; border-bottom: 2px solid #e0e0e0; padding-bottom: 0.3em; }",
        ".wmd-h1 { font-size: 2.5em; border-bottom: 2px solid #DBE6EC; padding-bottom: 0.3em; }",
    ),
    (
        ".wmd-paragraph {\n  margin: 0.75em 0;\n  color: #4a4a4a;\n}",
        ".wmd-paragraph {\n  margin: 0.75em 0;\n  color: #5C7684;\n}",
    ),
    # -- buttons: base = ghost (transparent, bordered, ink text) --
    (
        ".wmd-button {\n"
        "  display: inline-block;\n"
        "  padding: 10px 20px;\n"
        "  margin: 6px;\n"
        "  background: #f5f5f5;\n"
        "  border: 1px solid #d0d0d0;\n"
        "  border-radius: 6px;\n"
        "  font-family: inherit;\n"
        "  font-size: 14px;\n"
        "  font-weight: 500;\n"
        "  cursor: pointer;\n"
        "  transition: all 0.2s;\n"
        "}",
        ".wmd-button {\n"
        "  display: inline-block;\n"
        "  padding: 10px 20px;\n"
        "  margin: 6px;\n"
        "  background: transparent;\n"
        "  color: #122B3A;\n"
        "  border: 1px solid #DBE6EC;\n"
        "  border-radius: 6px;\n"
        "  font-family: inherit;\n"
        "  font-size: 14px;\n"
        "  font-weight: 500;\n"
        "  cursor: pointer;\n"
        "  transition: all 0.2s;\n"
        "}",
    ),
    (
        ".wmd-button:hover {\n  background: #e8e8e8;\n  border-color: #b0b0b0;\n}",
        ".wmd-button:hover {\n  background: #DCF0F5;\n  border-color: #1F7A9C;\n}",
    ),
    (
        ".wmd-button-primary, .wmd-button.wmd-primary {\n"
        "  background: #0066cc;\n"
        "  color: #fff;\n"
        "  border-color: #0052a3;\n"
        "}\n"
        "\n"
        ".wmd-button-primary:hover, .wmd-button.wmd-primary:hover {\n"
        "  background: #0052a3;\n"
        "}",
        ".wmd-button-primary, .wmd-button.wmd-primary {\n"
        "  background: linear-gradient(90deg, #2FA8C4, #1A6F95);\n"
        "  color: #fff;\n"
        "  border-color: #1A6F95;\n"
        "}\n"
        "\n"
        ".wmd-button-primary:hover, .wmd-button.wmd-primary:hover {\n"
        "  background: #1A6F95;\n"
        "}",
    ),
    (
        ".wmd-button-secondary, .wmd-button.wmd-secondary {\n"
        "  background: #fff;\n"
        "  border: 2px solid #d0d0d0;\n"
        "}",
        ".wmd-button-secondary, .wmd-button.wmd-secondary {\n"
        "  background: #DCF0F5;\n"
        "  color: #0F5670;\n"
        "  border: 2px solid #DCF0F5;\n"
        "}",
    ),
    (
        ".wmd-button-danger, .wmd-button.wmd-danger {\n"
        "  background: #dc3545;\n"
        "  color: #fff;\n"
        "  border-color: #c82333;\n"
        "}",
        ".wmd-button-danger, .wmd-button.wmd-danger {\n"
        "  background: #E15353;\n"
        "  color: #fff;\n"
        "  border-color: #C23E3E;\n"
        "}",
    ),
    # -- badges: functional colors kept, inactive states -> neutral gray --
    (
        ".wmd-badge {\n"
        "  display: inline-block;\n"
        "  padding: 2px 10px;\n"
        "  margin: 0 2px;\n"
        "  border-radius: 12px;\n"
        "  font-size: 11px;\n"
        "  font-weight: 600;\n"
        "  letter-spacing: 0.02em;\n"
        "  background: #e5e7eb;\n"
        "  color: #374151;\n"
        "}",
        ".wmd-badge {\n"
        "  display: inline-block;\n"
        "  padding: 2px 10px;\n"
        "  margin: 0 2px;\n"
        "  border-radius: 12px;\n"
        "  font-size: 11px;\n"
        "  font-weight: 600;\n"
        "  letter-spacing: 0.02em;\n"
        "  background: #E6EDF1;\n"
        "  color: #5C7684;\n"
        "}",
    ),
    (
        ".wmd-badge-primary { background: #dbeafe; color: #1d4ed8; }\n"
        ".wmd-badge-success { background: #d1fae5; color: #065f46; }\n"
        ".wmd-badge-warning { background: #fef3c7; color: #92400e; }\n"
        ".wmd-badge-error { background: #fee2e2; color: #991b1b; }",
        ".wmd-badge-primary { background: #DCF0F5; color: #0F5670; }\n"
        ".wmd-badge-success { background: #2F9E6E; color: #ffffff; }\n"
        "/* warning/error badges here mark INACTIVE states (\"not connected\", \"none\") --\n"
        "   per the WTMH palette these read as neutral, not alarm colors. */\n"
        ".wmd-badge-warning { background: #E6EDF1; color: #5C7684; }\n"
        ".wmd-badge-error { background: #E6EDF1; color: #5C7684; }\n"
        "/* reserved for a real danger state (e.g. a future \"SIGNAL LOST\" badge) --\n"
        "   unused by setup.md/tasks.md today. */\n"
        ".wmd-badge-danger { background: #E15353; color: #ffffff; }",
    ),
    # -- inputs --
    (
        ".wmd-input, .wmd-textarea, .wmd-select {\n"
        "  display: block;\n"
        "  width: 100%;\n"
        "  max-width: 400px;\n"
        "  padding: 10px 12px;\n"
        "  margin: 6px 0;\n"
        "  font-family: inherit;\n"
        "  font-size: 14px;\n"
        "  background: #fff;\n"
        "  border: 1px solid #d0d0d0;\n"
        "  border-radius: 6px;\n"
        "  transition: border-color 0.2s;\n"
        "}",
        ".wmd-input, .wmd-textarea, .wmd-select {\n"
        "  display: block;\n"
        "  width: 100%;\n"
        "  max-width: 400px;\n"
        "  padding: 10px 12px;\n"
        "  margin: 6px 0;\n"
        "  font-family: inherit;\n"
        "  font-size: 14px;\n"
        "  background: #FFFFFF;\n"
        "  color: #122B3A;\n"
        "  border: 1px solid #DBE6EC;\n"
        "  border-radius: 6px;\n"
        "  transition: border-color 0.2s;\n"
        "}",
    ),
    (
        ".wmd-input:focus, .wmd-textarea:focus, .wmd-select:focus {\n"
        "  outline: none;\n"
        "  border-color: #0066cc;\n"
        "  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);\n"
        "}",
        ".wmd-input:focus, .wmd-textarea:focus, .wmd-select:focus {\n"
        "  outline: none;\n"
        "  border-color: #1F7A9C;\n"
        "  box-shadow: 0 0 0 3px rgba(31, 122, 156, 0.15);\n"
        "}",
    ),
    (
        "  opacity: 0.6;\n  cursor: not-allowed;\n  background: #f5f5f5;\n  border-color: #e0e0e0;\n}",
        "  opacity: 0.6;\n  cursor: not-allowed;\n  background: #E6EDF1;\n  border-color: #DBE6EC;\n}",
    ),
    # -- containers (card/hero/modal) --
    (
        ".wmd-container-hero, .wmd-container-card, .wmd-container-modal {\n"
        "  background: #fafafa;\n"
        "  border: 1px solid #e0e0e0;\n"
        "  border-radius: 8px;\n"
        "  padding: 32px;\n"
        "  margin: 24px 0;\n"
        "}",
        ".wmd-container-hero, .wmd-container-card, .wmd-container-modal {\n"
        "  background: #F5F9FB;\n"
        "  border: 1px solid #DBE6EC;\n"
        "  border-radius: 8px;\n"
        "  padding: 32px;\n"
        "  margin: 24px 0;\n"
        "}\n"
        "\n"
        "/* alerts (::: alert ...) get no dedicated rule from wiremd's \"clean\" style at\n"
        "   all -- confirmed by reading src/renderer/styles.ts and the rendered output,\n"
        "   the warning/info/success word after \"alert\" isn't captured as a CSS class\n"
        "   either, so per-severity coloring isn't available. One consistent\n"
        "   informational card treatment is used for all of them instead. */\n"
        ".wmd-container-alert {\n"
        "  background: #DCF0F5;\n"
        "  border: 1px solid #BFE3ED;\n"
        "  border-left: 4px solid #1F7A9C;\n"
        "  border-radius: 6px;\n"
        "  padding: 16px 20px;\n"
        "  margin: 16px 0;\n"
        "  color: #122B3A;\n"
        "}",
    ),
    (
        ".wmd-container-hero {\n"
        "  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);",
        ".wmd-container-hero {\n"
        "  background: linear-gradient(135deg, #F5F9FB 0%, #DCF0F5 100%);",
    ),
    (
        ".wmd-container-card {\n  background: #fff;\n  box-shadow: 0 2px 8px rgba(0,0,0,0.08);\n}",
        ".wmd-container-card {\n  background: #FFFFFF;\n  box-shadow: 0 2px 8px rgba(18,43,58,0.08);\n}",
    ),
    (
        ".wmd-container-modal {\n"
        "  max-width: 500px;\n"
        "  margin: 40px auto;\n"
        "  background: #fff;\n"
        "  box-shadow: 0 4px 16px rgba(0,0,0,0.15);\n"
        "}",
        ".wmd-container-modal {\n"
        "  max-width: 500px;\n"
        "  margin: 40px auto;\n"
        "  background: #FFFFFF;\n"
        "  box-shadow: 0 4px 16px rgba(18,43,58,0.15);\n"
        "}",
    ),
    # -- nav bar -> Titlebar surface (also home of the WTMH logo, injected below) --
    (
        ".wmd-nav {\n"
        "  background: #fff;\n"
        "  border: 1px solid #e0e0e0;\n"
        "  border-radius: 8px;\n"
        "  padding: 16px 24px;\n"
        "  margin: 24px 0;\n"
        "  box-shadow: 0 1px 3px rgba(0,0,0,0.05);\n"
        "}",
        ".wmd-nav {\n"
        "  background: #12374A;\n"
        "  border: 1px solid #1B4A61;\n"
        "  border-radius: 8px;\n"
        "  padding: 16px 24px;\n"
        "  margin: 24px 0;\n"
        "  box-shadow: 0 1px 3px rgba(0,0,0,0.2);\n"
        "}",
    ),
    (
        ".wmd-nav-item {\n"
        "  display: inline-block;\n"
        "  color: #4a4a4a;\n"
        "  text-decoration: none;\n"
        "  font-weight: 500;\n"
        "  padding: 8px 16px;\n"
        "  background: #f8f9fa;\n"
        "  border: 1px solid #dee2e6;\n"
        "  border-radius: 6px;\n"
        "  transition: all 0.2s;\n"
        "}",
        ".wmd-nav-item {\n"
        "  display: inline-flex;\n"
        "  align-items: center;\n"
        "  color: #CFE6EE;\n"
        "  text-decoration: none;\n"
        "  font-weight: 500;\n"
        "  padding: 8px 16px;\n"
        "  background: rgba(255,255,255,0.08);\n"
        "  border: 1px solid rgba(255,255,255,0.16);\n"
        "  border-radius: 6px;\n"
        "  transition: all 0.2s;\n"
        "}",
    ),
    (
        ".wmd-nav-item:hover {\n"
        "  background: #e9ecef;\n"
        "  border-color: #adb5bd;\n"
        "  transform: translateY(-1px);\n"
        "  box-shadow: 0 2px 4px rgba(0,0,0,0.1);\n"
        "}",
        ".wmd-nav-item:hover {\n"
        "  background: rgba(255,255,255,0.16);\n"
        "  border-color: rgba(255,255,255,0.32);\n"
        "  transform: translateY(-1px);\n"
        "  box-shadow: 0 2px 4px rgba(0,0,0,0.2);\n"
        "}",
    ),
    (
        ".wmd-nav-item.wmd-active {\n"
        "  background: #343a40;\n"
        "  color: #fff;\n"
        "  border-color: #343a40;\n"
        "}",
        ".wmd-nav-item.wmd-active {\n"
        "  background: rgba(255,255,255,0.08);\n"
        "  color: #ffffff;\n"
        "  border-color: transparent;\n"
        "  border-bottom: 3px solid #2FA8C4;\n"
        "}\n"
        "\n"
        ".wmd-brand-logo {\n"
        "  height: 28px;\n"
        "  width: auto;\n"
        "  margin-right: 4px;\n"
        "  vertical-align: middle;\n"
        "}",
    ),
    # -- brand label (the title text sitting on the dark titlebar) --
    # NOTE: dropping the `:eye:` icon prefix in _nav.md changed which wiremd
    # node type this text becomes -- it is now .wmd-brand, not .wmd-nav-item,
    # and .wmd-brand has no color rule of its own in wiremd's "clean" style
    # (it silently inherited the page's dark ink color against our now-dark
    # titlebar background -- nearly invisible until this was added).
    (
        ".wmd-brand {\n"
        "  font-weight: 600;\n"
        "  font-size: 1.25em;\n"
        "  margin-right: auto;\n"
        "}",
        ".wmd-brand {\n"
        "  font-weight: 600;\n"
        "  font-size: 1.25em;\n"
        "  margin-right: auto;\n"
        "  color: #CFE6EE;\n"
        "  display: inline-flex;\n"
        "  align-items: center;\n"
        "}",
    ),
    # -- sidebar / grid-item-card (unused by setup.md/tasks.md today, retinted for consistency) --
    (
        "  background: #f0f8ff;\n  border: 2px solid #4682B4;\n  border-radius: 8px;\n}",
        "  background: #DCF0F5;\n  border: 2px solid #1F7A9C;\n  border-radius: 8px;\n}",
    ),
    (
        ".wmd-grid-item-card {\n"
        "  background: #fff;\n"
        "  border: 1px solid #e0e0e0;\n"
        "  border-radius: 8px;\n"
        "  padding: 24px;\n"
        "  transition: box-shadow 0.2s;\n"
        "}",
        ".wmd-grid-item-card {\n"
        "  background: #FFFFFF;\n"
        "  border: 1px solid #DBE6EC;\n"
        "  border-radius: 8px;\n"
        "  padding: 24px;\n"
        "  transition: box-shadow 0.2s;\n"
        "}",
    ),
    # -- blockquote (the "Design note" callouts) --
    (
        ".wmd-blockquote {\n"
        "  border-left: 3px solid #0066cc;\n"
        "  padding-left: 20px;\n"
        "  margin: 20px 0;\n"
        "  color: #4a4a4a;\n"
        "}",
        ".wmd-blockquote {\n"
        "  border-left: 3px solid #1F7A9C;\n"
        "  padding-left: 20px;\n"
        "  margin: 20px 0;\n"
        "  color: #5C7684;\n"
        "}",
    ),
    # -- separator (the "---" rules used throughout setup.md) --
    (
        ".wmd-separator {\n  border: none;\n  border-top: 1px solid #e0e0e0;\n  margin: 32px 0;\n}",
        ".wmd-separator {\n  border: none;\n  border-top: 1px solid #DBE6EC;\n  margin: 32px 0;\n}",
    ),
]

FAVICON_LINK = '  <link rel="icon" href="../../configs/assets/branding/WTMH.ico">\n'
LOGO_IMG = (
    '<img src="../../configs/assets/branding/wtmh_logo.png" alt="WTMH logo" '
    'class="wmd-brand-logo">'
)


def apply_theme(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    for old, new in REPLACEMENTS:
        count = text.count(old)
        if count == 0:
            raise ValueError(f"{path}: expected CSS block not found (wiremd output changed?):\n{old[:80]}...")
        text = text.replace(old, new)

    if "WTMH.ico" not in text:
        text = text.replace("  <style>", FAVICON_LINK + "  <style>", 1)

    if "wmd-brand-logo" not in text or "<img" not in text.split("wmd-nav-content")[1].split("</div>")[0]:
        # Insert the logo as the first child of the nav bar's content row.
        marker = '<div class="wmd-nav-content">\n'
        if marker not in text:
            raise ValueError(f"{path}: nav content marker not found")
        text = text.replace(marker, marker + "    " + LOGO_IMG + "\n", 1)

    path.write_text(text, encoding="utf-8")
    print(f"themed: {path}")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    for arg in argv:
        apply_theme(Path(arg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
