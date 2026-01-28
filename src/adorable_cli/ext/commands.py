import yaml
from pathlib import Path
from typing import Dict, Optional

from adorable_cli.console import console

class CustomCommand:
    def __init__(self, name: str, prompt: str, description: str = ""):
        self.name = name
        self.prompt = prompt
        self.description = description

class CommandsLoader:
    def __init__(self, commands_dir: Path):
        self.commands_dir = commands_dir

    def load_commands(self) -> Dict[str, CustomCommand]:
        """
        Load custom commands from markdown files.
        Returns a dict mapping command name (without slash) to CustomCommand object.
        """
        commands = {}
        if not self.commands_dir.exists():
            return commands

        for file_path in self.commands_dir.glob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                frontmatter, body = self._parse_frontmatter(content)
                
                # Command name defaults to filename stem if not in frontmatter
                cmd_name = frontmatter.get("command", file_path.stem).strip().lstrip("/")
                description = frontmatter.get("description", "")
                
                # Append body to prompt if prompt is in frontmatter, or just use body
                prompt = frontmatter.get("prompt", "")
                if body:
                    prompt = f"{prompt}\n{body}".strip()
                
                if cmd_name and prompt:
                    commands[cmd_name] = CustomCommand(cmd_name, prompt, description)
                    # console.print(f"[success]Loaded command: /{cmd_name}[/success]") # Too noisy?
            except Exception as e:
                console.print(f"[error]Failed to load command {file_path.name}: {e}[/error]")

        return commands

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """
        Simple frontmatter parser.
        """
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    return meta, parts[2].strip()
                except yaml.YAMLError:
                    pass
        return {}, content.strip()
