"""Secure Python tools extension

Based on composition (Toolkit + Agno PythonTools) for secure Python code execution, return value is str.
"""

import time
from pathlib import Path
from typing import Any, Optional

from agno.tools.python import PythonTools
from agno.tools.toolkit import Toolkit

from .security_config import security_config


class SecurePythonTools(Toolkit):
    """Secure Python tools - composed over Agno PythonTools with added security controls, return value is str"""

    def __init__(self, base_dir: Optional[Path] = None, **kwargs):
        self.config = security_config.config["python"]
        self.execution_config = security_config.config["execution"]
        self.pipx_python = security_config.pipx_python_path
        self.safe_globals = self._create_safe_globals()
        self.safe_locals: dict[str, Any] = {}
        self.python = PythonTools(
            base_dir=base_dir, safe_globals=self.safe_globals, safe_locals=self.safe_locals
        )
        super().__init__(tools=[self.execute_python_code], **kwargs)
        self.base_dir = base_dir

    def _create_safe_globals(self) -> dict[str, Any]:
        """Create a safe global environment"""
        def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
            base = name.split(".")[0]
            if base not in self.config["safe_modules"]:
                raise ImportError(f"Module '{name}' not allowed")
            return __import__(name, globals, locals, fromlist, level)
        safe_globals = {
            # Builtins for common safe operations
            "__builtins__": {
                "abs": abs,
                "all": all,
                "any": any,
                "bin": bin,
                "bool": bool,
                "chr": chr,
                "divmod": divmod,
                "enumerate": enumerate,
                "filter": filter,
                "float": float,
                "hex": hex,
                "int": int,
                "len": len,
                "list": list,
                "map": map,
                "max": max,
                "min": min,
                "oct": oct,
                "ord": ord,
                "pow": pow,
                "range": range,
                "reversed": reversed,
                "round": round,
                "sorted": sorted,
                "str": str,
                "sum": sum,
                "tuple": tuple,
                "type": type,
                "zip": zip,
                # Safe print
                "print": print,
                # Allow standard imports for safe modules
                "__import__": restricted_import,
            },
            # Mathematical constants
            "pi": 3.141592653589793,
            "e": 2.718281828459045,
        }

        # Import safe modules
        for module_name in self.config["safe_modules"]:
            try:
                module = restricted_import(module_name)
                safe_globals[module_name] = module
            except ImportError:
                # Module not found; skip
                pass

        return safe_globals

    def _validate_code_safety(self, code: str) -> tuple[bool, str]:
        """Validate code safety"""
        lines = code.split("\n")

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Check dangerous functions
            for func in self.config["dangerous_functions"]:
                if f"{func}(" in line:
                    return False, f"Dangerous function '{func}' found at line {line_num}"

            # Check dangerous imports
            dangerous_imports = self.config["dangerous_modules"]
            for module in dangerous_imports:
                patterns = [
                    f"import {module}",
                    f"from {module}",
                    f"import {module} as",
                ]
                for pattern in patterns:
                    if pattern in line:
                        return False, f"Dangerous module '{module}' import found at line {line_num}"

            # Check file operations
            if not self.config["allow_file_operations"]:
                if any(op in line for op in ["open(", "file(", "with open"]):
                    return False, f"File operation not allowed at line {line_num}"

        return True, "Code safety validation passed"

    def execute_python_code(self, code: str, variable_to_return: Optional[str] = None) -> str:
        """Securely execute Python code — composition calling Agno PythonTools"""
        # Audit mode
        if self.execution_config["audit_mode"]:
            return f"[AUDIT MODE] Would execute Python code:\n{code}"
        # Security validation
        is_safe, safety_msg = self._validate_code_safety(code)
        if not is_safe:
            return f"Error: Security validation failed: {safety_msg}"
        # Execute using Agno PythonTools
        output = self.python.run_python_code(code, variable_to_return=variable_to_return)
        # Record execution log
        if self.execution_config["log_executions"]:
            self._log_text_output(code, output)
        return output

    def _wrap_code_with_security(self, code: str) -> str:
        """Wrap code with security"""
        return f"""
import sys
import warnings
import signal

# Set timeout
def timeout_handler(signum, frame):
    raise TimeoutError("Execution timeout")

signal.alarm({self.execution_config["max_execution_time"]})

# User code
try:
{self._indent_code(code, "    ")}
except Exception as e:
    print(f"Error: {{e}}")
finally:
    signal.alarm(0)
"""

    def _indent_code(self, code: str, indent: str) -> str:
        """Indent code"""
        return "\n".join(indent + line if line.strip() else line for line in code.split("\n"))

    def _log_text_output(self, code: str, output: str) -> None:
        """Record execution log (text output)"""
        log_entry = {
            "timestamp": time.time(),
            "type": "python",
            "code": code[:200] + "..." if len(code) > 200 else code,
            "success": not str(output).startswith("Error:"),
            "output_length": len(output),
            "error_length": 0 if not str(output).startswith("Error:") else len(output),
        }
        log_file = Path.home() / ".adorable" / "python_execution.log"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"{log_entry}\n")


def create_secure_python_tools(base_dir: Optional[Path] = None) -> SecurePythonTools:
    """Create secure Python tools instance"""
    return SecurePythonTools(base_dir=base_dir)
