from __future__ import annotations

from dataclasses import dataclass

from agno.tools.file import FileTools
from agno.tools.python import PythonTools
from agno.tools.shell import ShellTools


@dataclass(frozen=True)
class ToolPolicy:
    allow_shell: bool = True
    allow_file_write: bool = True
    allow_python: bool = True
    confirm_file_write: bool = False

    @classmethod
    def from_mode(cls, mode: str | None) -> "ToolPolicy":
        normalized = (mode or "").strip().lower()
        if normalized in {"read-only", "readonly", "read_only", "ro"}:
            return cls(allow_shell=False, allow_file_write=False, allow_python=False, confirm_file_write=False)
        if normalized in {"confirm", "ask"}:
            return cls(confirm_file_write=True)
        return cls()


_FILE_WRITE_TOOL_NAMES = {
    "save_file",
    "write_file",
    "append_file",
    "delete_file",
    "remove_file",
    "move_file",
    "copy_file",
    "create_directory",
    "delete_directory",
    "remove_directory",
    "make_directory",
    "mkdir",
    "rmdir",
}


def apply_tool_policy(agent: object, policy: ToolPolicy) -> None:
    current_tools = getattr(agent, "tools", []) or []
    tools = list(current_tools)

    if not policy.allow_shell:
        tools = [t for t in tools if not isinstance(t, ShellTools)]
    if not policy.allow_python:
        tools = [t for t in tools if not isinstance(t, PythonTools)]

    for tk in tools:
        functions = getattr(tk, "functions", None)
        if not isinstance(functions, dict):
            continue

        if isinstance(tk, ShellTools):
            f = functions.get("run_shell_command")
            if f is not None:
                try:
                    setattr(f, "requires_confirmation", True)
                except Exception:
                    pass

        if isinstance(tk, FileTools):
            if not policy.allow_file_write:
                for name in list(functions.keys()):
                    if name in _FILE_WRITE_TOOL_NAMES:
                        functions.pop(name, None)
            elif policy.confirm_file_write:
                for name in _FILE_WRITE_TOOL_NAMES:
                    f = functions.get(name)
                    if f is None:
                        continue
                    try:
                        setattr(f, "requires_confirmation", True)
                    except Exception:
                        pass

    if isinstance(current_tools, list):
        current_tools[:] = tools
        return
    try:
        setattr(agent, "tools", tools)
    except Exception:
        return
