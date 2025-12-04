from rich.console import Console
from rich.theme import Theme

_APP_THEME = Theme(
    {
        "header": "bold orange3",
        "muted": "grey58",
        "tip": "bold dark_orange",
        "panel_border": "blue",
        "rule_light": "grey37",
        "panel_title": "bold white",
        "info": "cyan",
        "success": "green",
        "error": "red",
        "warning": "yellow",
        "tool_line": "cyan",
        "tool_name": "magenta",
        "cat_primary": "sandy_brown",
        "cat_secondary": "navajo_white1",
        "cat_accent": "black",
    }
)

console = Console(theme=_APP_THEME)


def configure_console(plain: bool) -> None:
    global console
    if plain:
        console = Console(no_color=True)
    else:
        console = Console(theme=_APP_THEME)
