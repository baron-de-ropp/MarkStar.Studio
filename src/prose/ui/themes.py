"""Built-in Prose themes.

Default is a VS Code Dark+–inspired palette (the colors most people mean by
“VS Code dark”), mapped onto Textual’s semantic theme tokens.
"""

from __future__ import annotations

from textual.theme import Theme

# Approximate VS Code “Dark+” (default dark):
#   editor.background #1E1E1E, editor.foreground #D4D4D4,
#   sideBar #252526, focus/accent #007ACC, description #9D9D9D
VSCODE_DARK = Theme(
    name="vscode-dark",
    primary="#007ACC",
    secondary="#3794FF",
    accent="#0E639C",
    foreground="#D4D4D4",
    background="#1E1E1E",
    surface="#252526",
    panel="#2D2D2D",
    boost="#252526",
    warning="#CCA700",
    error="#F44747",
    success="#89D185",
    dark=True,
)

DEFAULT_THEME_NAME = "vscode-dark"
