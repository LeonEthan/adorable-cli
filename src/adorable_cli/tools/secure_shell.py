"""Secure Shell tools extension

Based on composition (Toolkit + Agno ShellTools) for secure Shell command execution, return value is str.
"""

import shlex
import re

import time
from pathlib import Path
from typing import Optional

from agno.tools.toolkit import Toolkit
from agno.tools.shell import ShellTools
from .security_config import security_config



class SecureShellTools(Toolkit):
    """Secure Shell tools - composed over Agno ShellTools with added security controls, return value is str"""
    
    def __init__(self, base_dir: Optional[Path] = None, **kwargs):
        self.shell = ShellTools(base_dir=base_dir)
        self.config = security_config.config["shell"]
        self.execution_config = security_config.config["execution"]
        super().__init__(tools=[self.run_shell_command], **kwargs)
        self.base_dir = base_dir
    
    def _validate_command_safety(self, command: str) -> tuple[bool, str]:
        """Validate command safety"""
        # Parse command
        try:
            args = shlex.split(command)
            if not args:
                return False, "Empty command"
            
            main_cmd = args[0]
            
            # Check allowed commands
            if main_cmd not in self.config["allowed_commands"]:
                return False, f"Command '{main_cmd}' is not in allowed list"
            
            # Check blocked commands
            if main_cmd in self.config["blocked_commands"]:
                return False, f"Command '{main_cmd}' is blocked"
            
            # Check pipes
            if "|" in command and not self.config["allow_pipes"]:
                return False, "Pipe operations are not allowed"
            
            # Check redirection
            if (">" in command or "<" in command) and not self.config["allow_redirection"]:
                return False, "Redirection operations are not allowed"
            
            # Check background execution
            if "&" in command and not self.config["allow_background"]:
                return False, "Background execution is not allowed"
            
            # Check dangerous patterns
            dangerous_patterns = [
                r';\s*rm\s+', r'&&\s*rm\s+', r'\|\|\s*rm\s+',
                r'rm\s+-rf\s+/', r'chmod\s+777', r'sudo\s+',
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    return False, f"Dangerous command pattern detected: {pattern}"
            
            return True, "Command validation passed"
            
        except ValueError as e:
            return False, f"Command parsing error: {str(e)}"
    
    def run_shell_command(self, command: str, tail: int = 100) -> str:
        """Securely run Shell command — composition calling Agno ShellTools"""
        # Audit mode
        if self.execution_config["audit_mode"]:
            return f"[AUDIT MODE] Would execute shell command: {command}"
        # Security validation
        is_safe, safety_msg = self._validate_command_safety(command)
        if not is_safe:
            return f"Error: Security validation failed: {safety_msg}"
        # Execute using Agno ShellTools
        output = self.shell.run_shell_command(shlex.split(command), tail=tail)
        # Record execution log
        if self.execution_config["log_executions"]:
            self._log_text_output(command, output)
        return output
    
    def _log_text_output(self, command: str, output: str) -> None:
        """Record execution log (text output)"""
        log_entry = {
            "timestamp": time.time(),
            "type": "shell",
            "command": command,
            "success": not str(output).startswith("Error:"),
            "output_length": len(output),
            "error_length": 0 if not str(output).startswith("Error:") else len(output),
        }
        log_file = Path.home() / ".adorable" / "shell_execution.log"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'a') as f:
            f.write(f"{log_entry}\n")


def create_secure_shell_tools(base_dir: Optional[Path] = None) -> SecureShellTools:
    """Create secure Shell tools instance"""
    return SecureShellTools(base_dir=base_dir)