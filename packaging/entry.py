"""PyInstaller entry point — a plain script that launches the app.

PyInstaller freezes a script, not a console-script entry point, so this thin
launcher stands in for the ``markstar`` command (markstar.app:main).
"""

from markstar.app import main

if __name__ == "__main__":
    main()
