from __future__ import annotations

from pathlib import Path
from typing import Any

from adorable_cli.ext._python_loader import load_objects_from_directory


class ToolsLoader:
    """Load external tools from a directory of Python modules."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def load_tools(self) -> list[Any]:
        return load_objects_from_directory(self.directory)
