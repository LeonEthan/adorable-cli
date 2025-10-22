"""Security configuration management

Manage configuration options for secure execution.
"""


import sys
import yaml
from pathlib import Path
from typing import Optional


class SecurityConfig:
    """Security configuration manager"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".adorable" / "security.yaml"
        self.config = self._load_default_config()
        self._load_user_config()
        self.pipx_python_path = self._detect_pipx_python()
    
    def _detect_pipx_python(self) -> str:
        """Detect Python path in pipx environment"""
        # 1. Check whether current Python is in a pipx environment
        current_exe = Path(sys.executable)
        pipx_root = Path.home() / ".local" / "pipx" / "venvs"
        
        if pipx_root in current_exe.parents:
            return str(current_exe)
        
        # 2. Find the pipx environment for adorable-cli
        adorable_pipx = pipx_root / "adorable-cli"
        if adorable_pipx.exists():
            python_exe = adorable_pipx / "bin" / "python"
            if python_exe.exists():
                return str(python_exe)
        
        # 3. Fall back to current Python
        return sys.executable
    
    def _load_default_config(self) -> dict:
        """Load default configuration"""
        return {
            "execution": {
                "use_pipx_python": True,
                "max_execution_time": 30,
                "max_memory_mb": 512,
                "audit_mode": False,
                "log_executions": True,
                "temp_dir": "/tmp/adorable_secure_exec",
                "cleanup_temp": True,
            },
            "python": {
                # List of safe modules
                "safe_modules": [
                    # Data science
                    "pandas", "numpy", "matplotlib", "seaborn", "scipy", "sklearn",
                    # Standard libraries
                    "json", "csv", "re", "datetime", "collections", "math", 
                    "statistics", "random", "itertools", "pathlib", "typing",
                    "dataclasses", "fractions", "decimal", "string",
                    # Visualization
                    "plotly", "bokeh", "altair",
                ],
                # Dangerous modules blacklist
                "dangerous_modules": [
                    "subprocess", "os.system", "eval", "exec", "compile",
                    "importlib", "__import__", "globals", "locals", "vars",
                    "socket", "urllib", "requests", "http", "ftplib",
                    "shutil", "tempfile", "glob", "fnmatch",
                    "ctypes", "sys", "platform", "pwd", "grp",
                    "pip", "setuptools", "conda", "pkg_resources",
                ],
                # Dangerous functions blacklist
                "dangerous_functions": [
                    "exec", "eval", "compile", "__import__", "open", 
                    "file", "input", "raw_input", "reload", "help",
                ],
                "allow_file_operations": False,
                "allowed_file_paths": ["./data", "./results", "."],
            },
            "shell": {
                # Allowed commands whitelist
                "allowed_commands": [
                    # Text processing
                    "cat", "head", "tail", "grep", "awk", "sed", "sort", 
                    "uniq", "cut", "wc", "tr", "split", "join", "nl",
                    # System information (read-only)
                    "ls", "pwd", "whoami", "date", "uptime", "df", "du",
                    # Compression related
                    "tar", "zip", "unzip", "gzip", "gunzip",
                    # Text display
                    "echo", "printf", "tee",
                ],
                # Blocked commands blacklist
                "blocked_commands": [
                    # System management
                    "rm", "mv", "cp", "chmod", "chown", "sudo", "su",
                    "kill", "killall", "pkill", "systemctl", "service",
                    # Networking
                    "curl", "wget", "nc", "netcat", "ssh", "scp", "rsync",
                    "ping", "traceroute", "nslookup", "dig",
                    # Package management
                    "pip", "pip3", "conda", "apt", "yum", "dnf", "brew",
                    # Development tools
                    "gcc", "g++", "make", "cmake", "python", "python3",
                    # System control
                    "reboot", "shutdown", "halt", "poweroff", "init",
                ],
                "allow_pipes": False,
                "allow_redirection": False,
                "allow_background": False,
            }
        }
    
    def _load_user_config(self):
        """Load user custom configuration"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f) or {}
                self._merge_config(self.config, user_config)
            except Exception:
                pass  # Use default configuration
    
    def _merge_config(self, base: dict, override: dict):
        """Recursively merge configuration"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value


# Global configuration instance
security_config = SecurityConfig()