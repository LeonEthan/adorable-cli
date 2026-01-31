from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency fallback
    yaml = None


@dataclass(frozen=True)
class CommandDefinition:
    name: str
    prompt: str
    description: str | None = None
    source_path: Path | None = None


class CommandsLoader:
    """Load custom slash commands from a directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def load_commands(self) -> dict[str, CommandDefinition]:
        if not self.directory.exists():
            return {}

        commands: dict[str, CommandDefinition] = {}
        for path in sorted(self.directory.iterdir()):
            if path.is_dir() or path.name.startswith("."):
                continue

            items = []
            if path.suffix.lower() in {".json", ".yaml", ".yml"}:
                items = self._load_structured(path)
            else:
                cmd = self._load_text_command(path)
                if cmd is not None:
                    items = [cmd]

            for cmd in items:
                commands[cmd.name] = cmd

        return commands

    def _load_text_command(self, path: Path) -> CommandDefinition | None:
        try:
            prompt = path.read_text(encoding="utf-8").strip()
        except Exception:
            return None
        if not prompt:
            return None
        return CommandDefinition(name=path.stem, prompt=prompt, source_path=path)

    def _load_structured(self, path: Path) -> list[CommandDefinition]:
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:
            return []

        data: Any = None
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(raw)
            except Exception:
                return []
        else:
            if yaml is None:
                return []
            try:
                data = yaml.safe_load(raw)
            except Exception:
                return []

        return self._coerce_structured_data(data, path)

    def _coerce_structured_data(self, data: Any, path: Path) -> list[CommandDefinition]:
        if data is None:
            return []

        if isinstance(data, dict) and isinstance(data.get("commands"), list):
            items = data.get("commands") or []
        elif isinstance(data, list):
            items = data
        else:
            items = [data]

        commands: list[CommandDefinition] = []
        for item in items:
            cmd = self._command_from_mapping(item, path)
            if cmd is not None:
                commands.append(cmd)
        return commands

    def _command_from_mapping(self, mapping: Any, path: Path) -> CommandDefinition | None:
        if not isinstance(mapping, dict):
            return None

        name = str(mapping.get("name") or mapping.get("command") or path.stem).strip()
        prompt = mapping.get("prompt")
        if prompt is None:
            prompt = mapping.get("text") or mapping.get("instruction") or mapping.get("template")

        if isinstance(prompt, list):
            prompt = "\n".join(str(line) for line in prompt)
        if prompt is None:
            return None

        prompt_text = str(prompt).strip()
        if not name or not prompt_text:
            return None

        description = mapping.get("description") or mapping.get("desc")
        if description is not None:
            description = str(description).strip() or None

        return CommandDefinition(
            name=name,
            prompt=prompt_text,
            description=description,
            source_path=path,
        )
