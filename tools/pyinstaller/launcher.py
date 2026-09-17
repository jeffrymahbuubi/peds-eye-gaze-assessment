"""PyInstaller entry script for the compiled app.

``src/main.py`` uses package-relative imports, so it cannot be handed to
PyInstaller directly as a script; this shim imports it as a package and
runs ``main()`` -- with no arguments the exe opens the dashboard (see
``src.main.main``).
"""

from src.main import main

if __name__ == "__main__":
    raise SystemExit(main())
