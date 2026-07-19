"""MarkStar themes and the semantic color-token system.

Every non-structural color in the app resolves through a **named token** rather
than a hardcoded hex value, so a theme is the single place colors are defined.
Tokens live in each ``Theme``'s ``variables`` dict and are read at runtime with
``token(app, name)`` (for Rich-markup strings) or as ``$name`` in Textual CSS.

Token catalogue (define the same keys in every theme):
    hint-key       shortcut-key color in hint strips / footer
    search-match   background of non-focused search hits
    tab-active     active tab chip text
    tab-inactive   inactive tab chip text
    rule           thin divider rules
    md-marker      dimmed Markdown markers (** * ` ~~ #)
    md-strong      bold text color        (weight added in code)
    md-emphasis    italic text color      (slant added in code)
    md-code        inline code / code fence
    md-heading     heading text
    md-quote       blockquote text
"""

from __future__ import annotations

from textual.theme import Theme

# --- Dark (default): VS Code Dark+–inspired ---------------------------------
_DARK_VARS = {
    "hint-key": "#3794FF",
    "search-match": "#515C6A",
    "tab-active": "#C8C8C8",
    "tab-inactive": "#7A7A7A",
    "rule": "#3A3A3A",
    "md-marker": "#6A6A6A",
    "md-strong": "#E6E6E6",
    "md-emphasis": "#D4D4D4",
    "md-code": "#CE9178",
    "md-heading": "#569CD6",
    "md-quote": "#7BA88B",
    "md-link": "#4E9CD6",
    "spell-underline": "#D16969",
}

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
    variables=_DARK_VARS,
)

# --- Light: warm parchment (easy on the eyes for long writing) --------------
_LIGHT_VARS = {
    "hint-key": "#0B66C3",
    "search-match": "#BFDBFA",
    "tab-active": "#33302B",
    "tab-inactive": "#A79E8B",
    "rule": "#DBD1BF",
    "md-marker": "#B3A98F",
    "md-strong": "#2A2622",
    "md-emphasis": "#3A3733",
    "md-code": "#A3573B",
    "md-heading": "#1A6FB0",
    "md-quote": "#5E7C5E",
    "md-link": "#0B66C3",
    "spell-underline": "#C0392B",
}

MARKSTAR_LIGHT = Theme(
    name="markstar-light",
    primary="#0B66C3",
    secondary="#2C7BD6",
    accent="#C98A3B",
    foreground="#3A3733",
    background="#FBF7EC",
    surface="#F3ECDD",
    panel="#EFE7D5",
    boost="#F3ECDD",
    warning="#B8860B",
    error="#C1432E",
    success="#4F8A4F",
    dark=False,
    variables=_LIGHT_VARS,
)

ALL_THEMES = [VSCODE_DARK, MARKSTAR_LIGHT]
THEME_NAMES = [t.name for t in ALL_THEMES]
DEFAULT_THEME_NAME = "vscode-dark"


def token(app, name: str, fallback: str = "#808080") -> str:
    """Resolve a theme color token to a hex string for use in Rich markup.

    Resolution order: the active theme's variables → the base (vscode-dark)
    theme's variables → ``fallback``. The base-theme step lets any theme be
    *partial* — it only needs to override the tokens it wants to change — and
    means call sites don't have to repeat hex fallbacks. In CSS use ``$name``.
    """
    try:
        val = app.theme_variables.get(name)
        if val:
            return val
    except Exception:
        pass
    return VSCODE_DARK.variables.get(name, fallback)
