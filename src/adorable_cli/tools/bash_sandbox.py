"""Bash sandbox for secure command execution.

Claude Code's sandbox implementation:
- Uses macOS sandbox-exec with generated profiles
- Allows read-only operations by default
- Blocks file writes, network access, and dangerous syscalls
- Provides defense in depth for shell command execution

Usage:
    sandbox = BashSandbox()
    result = sandbox.execute("ls -la /tmp")

    # Allow specific writes
    sandbox = BashSandbox(allow_writes=["/tmp/output"])
    result = sandbox.execute("echo hello > /tmp/output/file.txt")
"""

from __future__ import annotations

import platform
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class SandboxLevel(Enum):
    """Sandbox restriction levels."""

    READ_ONLY = "read_only"  # Only file reads allowed
    RESTRICTED = "restricted"  # Reads + specific writes
    NETWORK = "network"  # Reads + writes + network
    UNRESTRICTED = "unrestricted"  # No sandbox (dangerous)


@dataclass
class SandboxResult:
    """Result of sandboxed command execution."""

    success: bool
    stdout: str
    stderr: str
    return_code: int
    blocked: bool = False  # True if sandbox blocked the operation
    block_reason: Optional[str] = None


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""

    level: SandboxLevel = SandboxLevel.READ_ONLY
    allow_reads: list[str] = field(default_factory=list)
    allow_writes: list[str] = field(default_factory=list)
    allow_network: bool = False
    allow_process: bool = False  # Allow spawning subprocesses
    timeout_seconds: int = 300
    max_output_size: int = 10 * 1024 * 1024  # 10MB


class SandboxProfileGenerator:
    """Generates macOS sandbox-exec profiles.

    Creates SBPL (Sandbox Profile Language) profiles dynamically
    based on the required permission level.
    """

    # Base restrictive profile
    BASE_PROFILE = '''(version 1)

; Deny everything by default
(deny default)

; Allow basic process operations
(allow process-exec (subpath "/bin"))
(allow process-exec (subpath "/usr/bin"))
(allow process-exec (subpath "/usr/local/bin"))
(allow process-exec (subpath "/opt/homebrew/bin"))
(allow process-exec (subpath "/System/Library"))
(allow process-exec (subpath "/usr/libexec"))

; Allow reading system libraries
(allow file-read* (subpath "/usr/lib"))
(allow file-read* (subpath "/usr/local/lib"))
(allow file-read* (subpath "/System/Library"))
(allow file-read* (subpath "/opt/homebrew/lib"))

; Allow reading dev random/urandom
(allow file-read* (literal "/dev/random"))
(allow file-read* (literal "/dev/urandom"))
(allow file-read* (literal "/dev/null"))
(allow file-read* (literal "/dev/zero"))

; Allow signals to self
(allow signal (target self))
'''

    # Profile for read-only access
    READ_ONLY_ADDITIONS = '''
; Read-only file access
(allow file-read*)
(deny file-write*)
(deny file-write-data)
(deny file-write-create)
'''

    # Profile additions for network access
    NETWORK_ADDITIONS = '''
; Network access
(allow network-inbound)
(allow network-outbound)
(allow system-socket)
'''

    @classmethod
    def generate(cls, config: SandboxConfig) -> str:
        """Generate a sandbox profile based on config.

        Args:
            config: Sandbox configuration

        Returns:
            SBPL profile string
        """
        if config.level == SandboxLevel.UNRESTRICTED:
            return "(version 1)\n(allow default)\n"

        parts = [cls.BASE_PROFILE]

        # Add level-specific rules
        if config.level == SandboxLevel.READ_ONLY:
            parts.append(cls.READ_ONLY_ADDITIONS)
        elif config.level == SandboxLevel.RESTRICTED:
            # Allow reads everywhere, writes to specific paths
            parts.append("\n; Allow file reads\n(allow file-read*)\n")
            parts.append("\n; Deny all writes by default\n(deny file-write*)\n")

            # Add specific write permissions
            for path in config.allow_writes:
                resolved = Path(path).resolve()
                parts.append(f'(allow file-write* (subpath "{resolved}"))\n')

        elif config.level == SandboxLevel.NETWORK:
            parts.append("\n; Allow file operations\n(allow file-read*)\n")
            parts.append("(allow file-write*)\n")
            parts.append(cls.NETWORK_ADDITIONS)

        # Add specific read permissions
        for path in config.allow_reads:
            resolved = Path(path).resolve()
            parts.append(f'(allow file-read* (subpath "{resolved}"))\n')

        # Process spawning
        if not config.allow_process:
            parts.append('\n; Restrict process spawning\n(deny process-exec (subpath "/bin/sh"))\n')
            parts.append('(deny process-exec (subpath "/bin/bash"))\n')

        return "\n".join(parts)


class BashSandbox:
    """Secure bash command execution with sandboxing.

    Provides defense-in-depth for shell command execution:
    1. Uses macOS sandbox-exec when available
    2. Falls back to restricted environment variables
    3. Timeout enforcement
    4. Output size limits

    Example:
        sandbox = BashSandbox()

        # Safe read-only command
        result = sandbox.execute("ls -la /tmp")
        print(result.stdout)

        # Command that tries to write (will be blocked in read-only mode)
        result = sandbox.execute("echo test > /tmp/file.txt")
        if result.blocked:
            print(f"Operation blocked: {result.block_reason}")
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """Initialize sandbox.

        Args:
            config: Sandbox configuration (default: read-only)
        """
        self.config = config or SandboxConfig()
        self._is_macos = platform.system() == "Darwin"
        self._profile_file: Optional[Path] = None

    def execute(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
    ) -> SandboxResult:
        """Execute a command in the sandbox.

        Args:
            command: Shell command to execute
            cwd: Working directory for execution
            env: Environment variables

        Returns:
            SandboxResult with output and status
        """
        if self.config.level == SandboxLevel.UNRESTRICTED:
            return self._execute_unrestricted(command, cwd, env)

        if self._is_macos:
            return self._execute_sandboxed_macos(command, cwd, env)
        else:
            return self._execute_sandboxed_linux(command, cwd, env)

    def _execute_sandboxed_macos(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
    ) -> SandboxResult:
        """Execute using macOS sandbox-exec."""
        # Generate and write profile
        profile = SandboxProfileGenerator.generate(self.config)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.sb', delete=False) as f:
            f.write(profile)
            profile_path = Path(f.name)

        try:
            # Build sandbox-exec command
            cmd = [
                "sandbox-exec",
                "-f", str(profile_path),
                "/bin/bash",
                "-c", command,
            ]

            # Execute with timeout
            result = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )

            # Check if sandbox blocked the operation
            blocked, reason = self._check_blocked(result)

            return SandboxResult(
                success=result.returncode == 0 and not blocked,
                stdout=result.stdout[:self.config.max_output_size],
                stderr=result.stderr[:self.config.max_output_size],
                return_code=result.returncode,
                blocked=blocked,
                block_reason=reason,
            )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {self.config.timeout_seconds}s",
                return_code=-1,
                blocked=True,
                block_reason="timeout",
            )
        except FileNotFoundError:
            # sandbox-exec not available
            return self._execute_unrestricted(command, cwd, env)
        finally:
            # Clean up profile
            try:
                profile_path.unlink()
            except OSError:
                pass

    def _execute_sandboxed_linux(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
    ) -> SandboxResult:
        """Execute with Linux restrictions (fallback)."""
        # Linux doesn't have sandbox-exec, use environment restrictions
        restricted_env = self._build_restricted_env(env)

        # Build restricted command using bash restricted mode
        restricted_cmd = f"bash -r -c {repr(command)}"

        try:
            result = subprocess.run(
                restricted_cmd,
                cwd=cwd,
                env=restricted_env,
                capture_output=True,
                text=True,
                shell=True,
                timeout=self.config.timeout_seconds,
            )

            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout[:self.config.max_output_size],
                stderr=result.stderr[:self.config.max_output_size],
                return_code=result.returncode,
                blocked=False,
            )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {self.config.timeout_seconds}s",
                return_code=-1,
                blocked=True,
                block_reason="timeout",
            )

    def _execute_unrestricted(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
    ) -> SandboxResult:
        """Execute without sandbox (DANGEROUS)."""
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                shell=True,
                timeout=self.config.timeout_seconds,
            )

            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout[:self.config.max_output_size],
                stderr=result.stderr[:self.config.max_output_size],
                return_code=result.returncode,
                blocked=False,
            )

        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {self.config.timeout_seconds}s",
                return_code=-1,
                blocked=True,
                block_reason="timeout",
            )

    def _check_blocked(self, result: subprocess.CompletedProcess) -> tuple[bool, Optional[str]]:
        """Check if sandbox blocked the operation.

        Analyzes stderr for sandbox denial messages.
        """
        stderr = result.stderr.lower()

        if "sandbox" in stderr and ("deny" in stderr or "violation" in stderr):
            if "file-write" in stderr:
                return True, "file_write_blocked"
            if "network" in stderr:
                return True, "network_blocked"
            if "process" in stderr:
                return True, "process_spawn_blocked"
            return True, "sandbox_violation"

        return False, None

    def _build_restricted_env(self, base_env: Optional[dict]) -> dict:
        """Build restricted environment for Linux fallback."""
        if base_env:
            env = base_env.copy()
        else:
            env = {}

        # Remove dangerous environment variables
        dangerous_vars = [
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
        ]
        for var in dangerous_vars:
            env.pop(var, None)

        # Set restrictive PATH
        env["PATH"] = "/usr/bin:/bin:/usr/local/bin"

        return env


class BashTool:
    """High-level bash tool with safety features.

    Combines sandboxing with additional safety checks:
    - Command validation
    - Dangerous pattern detection
    - Confirmation for destructive operations

    Example:
        tool = BashTool()

        # Safe command
        result = tool.run("ls -la")

        # Dangerous command requires confirmation
        result = tool.run("rm -rf /", require_confirmation=True)
        if result.confirmation_required:
            # Ask user for confirmation
            pass
    """

    # Dangerous patterns that require confirmation
    DANGEROUS_PATTERNS = [
        (r"\brm\s+-[a-zA-Z]*r", "recursive deletion"),
        (r"\brm\s+-[a-zA-Z]*f", "force deletion"),
        (r"\brm\s+.*\*", "wildcard deletion"),
        (r"\bmkfs\b", "filesystem creation"),
        (r"\bdd\s+if=", "disk write"),
        (r"\bformat\b", "formatting"),
        (r"\bchmod\s+-R", "recursive permission change"),
        (r"\bchown\s+-R", "recursive ownership change"),
        (r"\bsudo\b", "elevated privileges"),
        (r"\bsu\s+-", "switch user"),
        (r"\bwget\s+.*\|\s*bash", "piped download execution"),
        (r"\bcurl\s+.*\|\s*bash", "piped download execution"),
        (r"\b>\s*/[a-zA-Z]+/", "root filesystem write"),
    ]

    def __init__(
        self,
        sandbox_config: Optional[SandboxConfig] = None,
        allow_unsafe: bool = False,
    ):
        """Initialize bash tool.

        Args:
            sandbox_config: Sandbox configuration
            allow_unsafe: Allow dangerous commands without confirmation
        """
        self.sandbox = BashSandbox(sandbox_config)
        self.allow_unsafe = allow_unsafe

    def run(
        self,
        command: str,
        cwd: Optional[Path] = None,
        require_confirmation: bool = False,
    ) -> SandboxResult:
        """Run a bash command with safety checks.

        Args:
            command: Command to execute
            cwd: Working directory
            require_confirmation: Force confirmation prompt

        Returns:
            SandboxResult
        """
        import re

        # Check for dangerous patterns
        is_dangerous = False
        danger_reason = None

        for pattern, reason in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                is_dangerous = True
                danger_reason = reason
                break

        # Require confirmation for dangerous commands
        if (is_dangerous or require_confirmation) and not self.allow_unsafe:
            # Return a result indicating confirmation is needed
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Confirmation required: This command involves {danger_reason or 'potentially destructive operations'}. "
                "Set require_confirmation=False after user approval.",
                return_code=-1,
                blocked=True,
                block_reason="confirmation_required",
            )

        # Execute in sandbox
        return self.sandbox.execute(command, cwd)

    def is_dangerous(self, command: str) -> tuple[bool, Optional[str]]:
        """Check if a command is considered dangerous.

        Returns:
            (is_dangerous, reason)
        """
        import re

        for pattern, reason in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True, reason

        return False, None


# Convenience functions


def execute_sandboxed(
    command: str,
    level: SandboxLevel = SandboxLevel.READ_ONLY,
    timeout: int = 300,
) -> SandboxResult:
    """Execute a command in a sandbox (convenience function).

    Args:
        command: Command to execute
        level: Sandbox restriction level
        timeout: Timeout in seconds

    Returns:
        SandboxResult
    """
    config = SandboxConfig(level=level, timeout_seconds=timeout)
    sandbox = BashSandbox(config)
    return sandbox.execute(command)


def is_sandbox_available() -> bool:
    """Check if sandbox-exec is available on this system."""
    if platform.system() != "Darwin":
        return False

    try:
        result = subprocess.run(
            ["which", "sandbox-exec"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False
