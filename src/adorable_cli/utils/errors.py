"""Error formatting utilities for LLM comprehension.

Claude Code's error formatting pipeline creates error messages tailored
for LLM comprehension with actionable suggestions, stdout/stderr preservation,
and context-aware hints for shell, validation, permission, and filesystem errors.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class ToolError:
    """Structured error information for tools."""

    tool_name: str
    error_type: str
    message: str
    suggestion: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    context: dict[str, Any] = None

    def __post_init__(self):
        if self.context is None:
            self.context = {}


def format_tool_error(tool_name: str, tool_input: dict[str, Any], error: Exception) -> str:
    """Format an error for LLM comprehension.

    Creates actionable error messages with context-aware suggestions.

    Args:
        tool_name: Name of the tool that failed
        tool_input: Input arguments to the tool
        error: The exception that occurred

    Returns:
        Formatted error message suitable for LLM consumption
    """
    error_type = type(error).__name__
    error_message = str(error)

    # Categorize the error
    if isinstance(error, FileNotFoundError):
        return _format_file_not_found_error(tool_name, tool_input, error)
    elif isinstance(error, PermissionError):
        return _format_permission_error(tool_name, tool_input, error)
    elif isinstance(error, subprocess.CalledProcessError):
        return _format_shell_error(tool_name, tool_input, error)
    elif isinstance(error, TimeoutError):
        return _format_timeout_error(tool_name, tool_input, error)
    elif isinstance(error, ValueError):
        return _format_validation_error(tool_name, tool_input, error)
    elif isinstance(error, ConnectionError):
        return _format_connection_error(tool_name, tool_input, error)

    # Generic error formatting
    return _format_generic_error(tool_name, tool_input, error_type, error_message)


def _format_file_not_found_error(
    tool_name: str, tool_input: dict[str, Any], error: FileNotFoundError
) -> str:
    """Format file not found errors with helpful suggestions."""
    file_path = tool_input.get("file_path") or tool_input.get("path") or str(error.filename)

    parts = [
        f"Error: File not found: {file_path}",
        "",
        "Possible causes:",
    ]

    path = Path(file_path)
    if not path.is_absolute():
        parts.append(f"  - Relative path '{file_path}' may not exist in current directory")
        parts.append(f"  - Current working directory: {Path.cwd()}")

    if "." in file_path:
        parts.append(f"  - File extension may be incorrect")
        parts.append(f"  - Check if the file has a different extension")

    parts.append("")
    parts.append("Suggested actions:")
    parts.append(f"  1. Use list_files to see files in the directory")
    parts.append(f"  2. Use search_files to find the correct filename")
    parts.append(f"  3. Check if the file needs to be created first")

    return "\n".join(parts)


def _format_permission_error(
    tool_name: str, tool_input: dict[str, Any], error: PermissionError
) -> str:
    """Format permission errors with actionable suggestions."""
    file_path = tool_input.get("file_path") or tool_input.get("path") or str(error.filename)

    parts = [
        f"Error: Permission denied: {file_path}",
        "",
        "Possible causes:",
        "  - File is read-only",
        "  - Directory is not writable",
        "  - Insufficient permissions to access the file",
        "",
        "Suggested actions:",
    ]

    if tool_name in ("write_file", "save_file", "edit_file"):
        parts.append(f"  1. Check if the file is locked by another process")
        parts.append(f"  2. Verify you have write permission to the directory")
        parts.append(f"  3. Use a different output location")
    else:
        parts.append(f"  1. Check file permissions with stat")
        parts.append(f"  2. Try running with elevated permissions if appropriate")
        parts.append(f"  3. Choose a different file or directory")

    return "\n".join(parts)


def _format_shell_error(
    tool_name: str, tool_input: dict[str, Any], error: subprocess.CalledProcessError
) -> str:
    """Format shell command errors with stdout/stderr preservation."""
    command = tool_input.get("command", "unknown command")

    parts = [
        f"Error: Command failed: {command}",
        f"Exit code: {error.returncode}",
    ]

    if error.stdout:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout
        if stdout.strip():
            parts.append("")
            parts.append("Standard output:")
            parts.append(_indent(_truncate(stdout, 2000)))

    if error.stderr:
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr
        if stderr.strip():
            parts.append("")
            parts.append("Standard error:")
            parts.append(_indent(_truncate(stderr, 2000)))

    parts.append("")
    parts.append("Suggested actions:")

    # Analyze stderr for common patterns
    stderr_text = ""
    if error.stderr:
        stderr_text = error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr

    if "command not found" in stderr_text.lower():
        parts.append("  - Command not found in PATH")
        parts.append("  - Check if the tool is installed")
        parts.append("  - Use 'which <command>' to verify location")
    elif "permission denied" in stderr_text.lower():
        parts.append("  - Permission denied to execute command")
        parts.append("  - Check file permissions")
    elif "no such file" in stderr_text.lower():
        parts.append("  - Referenced file or directory doesn't exist")
        parts.append("  - Check the path and try again")
    else:
        parts.append("  1. Verify the command syntax")
        parts.append("  2. Check if all required arguments are provided")
        parts.append("  3. Ensure dependent tools/files are available")

    return "\n".join(parts)


def _format_timeout_error(
    tool_name: str, tool_input: dict[str, Any], error: TimeoutError
) -> str:
    """Format timeout errors with helpful context."""
    parts = [
        f"Error: Tool '{tool_name}' timed out",
        "",
        "The operation took longer than expected and was terminated.",
        "",
        "Possible causes:",
        "  - Operation is processing a large amount of data",
        "  - Network request is hanging",
        "  - Infinite loop or deadlock in the operation",
        "",
        "Suggested actions:",
        "  1. Try with a more specific/smaller input",
        "  2. Check if the resource is responsive",
        "  3. Break the operation into smaller steps",
    ]

    return "\n".join(parts)


def _format_validation_error(
    tool_name: str, tool_input: dict[str, Any], error: ValueError
) -> str:
    """Format validation errors with parameter hints."""
    error_message = str(error)

    parts = [
        f"Error: Invalid input for '{tool_name}'",
        f"Details: {error_message}",
        "",
        "Input provided:",
    ]

    # Show relevant input parameters
    for key, value in tool_input.items():
        if key in error_message.lower():
            parts.append(f"  - {key}: {value} (may be invalid)")
        else:
            parts.append(f"  - {key}: {value}")

    parts.append("")
    parts.append("Suggested actions:")
    parts.append("  1. Check the tool's required parameters")
    parts.append("  2. Verify parameter types and formats")
    parts.append("  3. Ensure all required fields are provided")

    return "\n".join(parts)


def _format_connection_error(
    tool_name: str, tool_input: dict[str, Any], error: ConnectionError
) -> str:
    """Format connection errors for network operations."""
    url = tool_input.get("url", tool_input.get("endpoint", "unknown"))

    parts = [
        f"Error: Connection failed to {url}",
        f"Details: {str(error)}",
        "",
        "Possible causes:",
        "  - Network connectivity issues",
        "  - Server is not responding",
        "  - URL is incorrect or unreachable",
        "  - Firewall or proxy blocking the connection",
        "",
        "Suggested actions:",
        "  1. Verify the URL is correct",
        "  2. Check network connectivity",
        "  3. Try again later if the server may be down",
        "  4. Check if a proxy or VPN is required",
    ]

    return "\n".join(parts)


def _format_generic_error(
    tool_name: str, tool_input: dict[str, Any], error_type: str, error_message: str
) -> str:
    """Format generic errors with helpful structure."""
    parts = [
        f"Error in '{tool_name}': {error_type}",
        f"Message: {error_message}",
    ]

    # Add input context (but truncate if too large)
    if tool_input:
        parts.append("")
        parts.append("Tool input:")
        for key, value in tool_input.items():
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            parts.append(f"  {key}: {value_str}")

    parts.append("")
    parts.append("Suggested actions:")
    parts.append("  1. Review the error message above")
    parts.append("  2. Check the tool input parameters")
    parts.append("  3. Try a different approach or input")

    return "\n".join(parts)


def _indent(text: str, spaces: int = 2) -> str:
    """Indent text with spaces."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.split("\n"))


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to maximum length with indicator."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n... [truncated]"


# Specific error types for common scenarios


class FileSafetyError(Exception):
    """Error when file safety check fails (read-before-edit)."""

    def __init__(self, file_path: Path, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"File safety check failed for {file_path}: {reason}")


class ToolNotFoundError(Exception):
    """Error when a requested tool is not found."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Tool not found: {tool_name}")


class ConfirmationRequiredError(Exception):
    """Error when user confirmation is required but not provided."""

    def __init__(self, tool_name: str, reason: str):
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"Confirmation required for {tool_name}: {reason}")


def categorize_error(error: Exception) -> str:
    """Categorize an error for appropriate handling.

    Returns one of: "file", "permission", "shell", "network",
    "timeout", "validation", "unknown"
    """
    if isinstance(error, FileNotFoundError):
        return "file"
    elif isinstance(error, PermissionError):
        return "permission"
    elif isinstance(error, subprocess.CalledProcessError):
        return "shell"
    elif isinstance(error, ConnectionError):
        return "network"
    elif isinstance(error, TimeoutError):
        return "timeout"
    elif isinstance(error, ValueError):
        return "validation"
    elif isinstance(error, FileSafetyError):
        return "safety"
    elif isinstance(error, ToolNotFoundError):
        return "tool"
    else:
        return "unknown"


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error might be resolved by retrying."""
    error_type = categorize_error(error)

    # These errors might be transient
    retryable_types = {"network", "timeout", "shell"}

    if error_type in retryable_types:
        return True

    # Check for specific retryable patterns
    error_msg = str(error).lower()
    retry_patterns = [
        "rate limit",
        "too many requests",
        "temporarily unavailable",
        "connection reset",
        "timeout",
        "try again",
    ]

    return any(pattern in error_msg for pattern in retry_patterns)
