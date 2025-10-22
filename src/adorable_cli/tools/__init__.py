"""Secure execution tools package - extensions over Agno native tools

Provides secure Python and Shell code execution functionality.
"""

from .secure_python import create_secure_python_tools
from .secure_shell import create_secure_shell_tools
from .security_config import security_config
from .execution_context import ExecutionContext


def create_secure_tools(base_dir=None):
    """Create all secure tools"""
    tools = []
    
    # Add secure Python tools
    python_tools = create_secure_python_tools(base_dir=base_dir)
    tools.append(python_tools)
    
    # Add secure Shell tools  
    shell_tools = create_secure_shell_tools(base_dir=base_dir)
    tools.append(shell_tools)
    
    return tools


__all__ = [
    'create_secure_tools',
    'create_secure_python_tools', 
    'create_secure_shell_tools',
    'security_config',
    'ExecutionContext'
]