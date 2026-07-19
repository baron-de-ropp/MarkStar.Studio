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
    "md-include": "#4EC9B0",
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
    "md-include": "#1B8A7A",
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

# --- Gruvbox dark -----------------------------------------------------------
GRUVBOX_DARK = Theme(
    name="gruvbox-dark",
    primary="#83A598",
    secondary="#8EC07C",
    accent="#458588",
    foreground="#EBDBB2",
    background="#282828",
    surface="#32302F",
    panel="#3C3836",
    boost="#32302F",
    warning="#FABD2F",
    error="#FB4934",
    success="#B8BB26",
    dark=True,
    variables={
        "hint-key": "#83A598",
        "search-match": "#504945",
        "tab-active": "#FBF1C7",
        "tab-inactive": "#928374",
        "rule": "#504945",
        "md-marker": "#665C54",
        "md-strong": "#FBF1C7",
        "md-emphasis": "#EBDBB2",
        "md-code": "#FE8019",
        "md-heading": "#FABD2F",
        "md-quote": "#B8BB26",
        "md-link": "#83A598",
        "md-include": "#8EC07C",
        "spell-underline": "#FB4934",
    },
)

# --- Nord -------------------------------------------------------------------
NORD = Theme(
    name="nord",
    primary="#88C0D0",
    secondary="#8FBCBB",
    accent="#5E81AC",
    foreground="#D8DEE9",
    background="#2E3440",
    surface="#3B4252",
    panel="#434C5E",
    boost="#3B4252",
    warning="#EBCB8B",
    error="#BF616A",
    success="#A3BE8C",
    dark=True,
    variables={
        "hint-key": "#88C0D0",
        "search-match": "#434C5E",
        "tab-active": "#ECEFF4",
        "tab-inactive": "#6C7A96",
        "rule": "#434C5E",
        "md-marker": "#4C566A",
        "md-strong": "#ECEFF4",
        "md-emphasis": "#E5E9F0",
        "md-code": "#D08770",
        "md-heading": "#81A1C1",
        "md-quote": "#A3BE8C",
        "md-link": "#88C0D0",
        "md-include": "#8FBCBB",
        "spell-underline": "#BF616A",
    },
)

# --- Popular themes (canonical palettes) ------------------------------------
def make_theme(
    name: str,
    *,
    dark: bool,
    bg: str,
    fg: str,
    surface: str,
    accent: str,
    blue: str,
    green: str,
    yellow: str,
    red: str,
    cyan: str,
    purple: str,
    comment: str,
    selection: str,
) -> Theme:
    """Build a fully-tokenized Theme from a small canonical palette."""
    return Theme(
        name=name,
        primary=accent,
        secondary=cyan,
        accent=accent,
        foreground=fg,
        background=bg,
        surface=surface,
        panel=surface,
        boost=surface,
        warning=yellow,
        error=red,
        success=green,
        dark=dark,
        variables={
            "hint-key": blue,
            "search-match": selection,
            "tab-active": fg,
            "tab-inactive": comment,
            "rule": comment,
            "md-marker": comment,
            "md-strong": fg,
            "md-emphasis": fg,
            "md-code": yellow,
            "md-heading": blue,
            "md-quote": green,
            "md-link": cyan,
            "md-include": purple,
            "spell-underline": red,
        },
    )


_POPULAR = [
    make_theme("dracula", dark=True, bg="#282a36", fg="#f8f8f2", surface="#44475a",
               accent="#bd93f9", blue="#8be9fd", green="#50fa7b", yellow="#ffb86c",
               red="#ff5555", cyan="#8be9fd", purple="#ff79c6", comment="#6272a4",
               selection="#44475a"),
    make_theme("one-dark", dark=True, bg="#282c34", fg="#abb2bf", surface="#21252b",
               accent="#61afef", blue="#61afef", green="#98c379", yellow="#e5c07b",
               red="#e06c75", cyan="#56b6c2", purple="#c678dd", comment="#5c6370",
               selection="#3e4451"),
    make_theme("tokyo-night", dark=True, bg="#1a1b26", fg="#c0caf5", surface="#1f2335",
               accent="#7aa2f7", blue="#7aa2f7", green="#9ece6a", yellow="#e0af68",
               red="#f7768e", cyan="#7dcfff", purple="#bb9af7", comment="#565f89",
               selection="#283457"),
    make_theme("catppuccin-mocha", dark=True, bg="#1e1e2e", fg="#cdd6f4", surface="#313244",
               accent="#cba6f7", blue="#89b4fa", green="#a6e3a1", yellow="#f9e2af",
               red="#f38ba8", cyan="#94e2d5", purple="#cba6f7", comment="#6c7086",
               selection="#45475a"),
    make_theme("catppuccin-latte", dark=False, bg="#eff1f5", fg="#4c4f69", surface="#ccd0da",
               accent="#8839ef", blue="#1e66f5", green="#40a02b", yellow="#df8e1d",
               red="#d20f39", cyan="#179299", purple="#8839ef", comment="#9ca0b0",
               selection="#bcc0cc"),
    make_theme("solarized-dark", dark=True, bg="#002b36", fg="#839496", surface="#073642",
               accent="#268bd2", blue="#268bd2", green="#859900", yellow="#b58900",
               red="#dc322f", cyan="#2aa198", purple="#6c71c4", comment="#586e75",
               selection="#073642"),
    make_theme("solarized-light", dark=False, bg="#fdf6e3", fg="#657b83", surface="#eee8d5",
               accent="#268bd2", blue="#268bd2", green="#859900", yellow="#b58900",
               red="#dc322f", cyan="#2aa198", purple="#6c71c4", comment="#93a1a1",
               selection="#eee8d5"),
    make_theme("monokai", dark=True, bg="#272822", fg="#f8f8f2", surface="#3e3d32",
               accent="#f92672", blue="#66d9ef", green="#a6e22e", yellow="#fd971f",
               red="#f92672", cyan="#66d9ef", purple="#ae81ff", comment="#75715e",
               selection="#49483e"),
    make_theme("night-owl", dark=True, bg="#011627", fg="#d6deeb", surface="#0b2942",
               accent="#82aaff", blue="#82aaff", green="#22da6e", yellow="#addb67",
               red="#ef5350", cyan="#7fdbca", purple="#c792ea", comment="#637777",
               selection="#1d3b53"),
    make_theme("ayu-dark", dark=True, bg="#0d1017", fg="#bfbdb6", surface="#10141c",
               accent="#e6b450", blue="#59c2ff", green="#aad94c", yellow="#ffb454",
               red="#d95757", cyan="#39bae6", purple="#d2a6ff", comment="#5a6673",
               selection="#163051"),
    make_theme("ayu-mirage", dark=True, bg="#242936", fg="#cccac2", surface="#1f2430",
               accent="#ffcc66", blue="#73d0ff", green="#d5ff80", yellow="#ffd173",
               red="#ff6666", cyan="#5ccfe6", purple="#dfbfff", comment="#6c7380",
               selection="#2b4768"),
    make_theme("ayu-light", dark=False, bg="#fcfcfc", fg="#5c6166", surface="#f8f9fa",
               accent="#f29718", blue="#399ee6", green="#86b300", yellow="#fa8d3e",
               red="#e65050", cyan="#55b4d4", purple="#a37acc", comment="#8a8d92",
               selection="#dbe7f7"),
    make_theme("github-dark", dark=True, bg="#0d1117", fg="#e6edf3", surface="#161b22",
               accent="#2f81f7", blue="#79c0ff", green="#3fb950", yellow="#d29922",
               red="#ff7b72", cyan="#39c5cf", purple="#d2a8ff", comment="#8b949e",
               selection="#2d4f76"),
    make_theme("github-light", dark=False, bg="#ffffff", fg="#1f2328", surface="#f6f8fa",
               accent="#0969da", blue="#0550ae", green="#1a7f37", yellow="#953800",
               red="#cf222e", cyan="#1b7c83", purple="#8250df", comment="#6e7781",
               selection="#ddf4ff"),
    make_theme("material-palenight", dark=True, bg="#292d3e", fg="#a6accd", surface="#333747",
               accent="#ab47bc", blue="#82aaff", green="#c3e88d", yellow="#ffcb6b",
               red="#f07178", cyan="#89ddff", purple="#c792ea", comment="#676e95",
               selection="#444267"),
    make_theme("synthwave-84", dark=True, bg="#262335", fg="#ffffff", surface="#241b2f",
               accent="#ff7edb", blue="#36f9f6", green="#72f1b8", yellow="#fede5d",
               red="#fe4450", cyan="#36f9f6", purple="#ff7edb", comment="#848bbd",
               selection="#413e4e"),
]

ALL_THEMES = [VSCODE_DARK, MARKSTAR_LIGHT, GRUVBOX_DARK, NORD, *_POPULAR]
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
