import pytest
from pathlib import Path
from agno.tools import Toolkit
from adorable_cli.ext.tools import ToolsLoader
from adorable_cli.ext.commands import CommandsLoader

class MockTool(Toolkit):
    def __init__(self):
        super().__init__(name="mock_tool")
    
    def mock_func(self):
        return "mock"

@pytest.fixture
def temp_config_dir(tmp_path):
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    return tmp_path

def test_load_tools(temp_config_dir):
    tools_dir = temp_config_dir / "tools"
    
    # Create a dummy python file with a tool
    tool_file = tools_dir / "my_tool.py"
    tool_file.write_text("""
from agno.tools import Toolkit

class MyCustomTool(Toolkit):
    def __init__(self):
        super().__init__(name="custom_tool")
    
    def say_hello(self):
        return "hello"
""")
    
    loader = ToolsLoader(tools_dir)
    tools = loader.load_tools()
    
    assert len(tools) == 1
    assert tools[0].name == "custom_tool"

def test_load_commands(temp_config_dir):
    commands_dir = temp_config_dir / "commands"
    
    # Create a dummy command file
    cmd_file = commands_dir / "hello.md"
    cmd_file.write_text("""---
description: Say hello
---
Hello from custom command!
""")
    
    loader = CommandsLoader(commands_dir)
    commands = loader.load_commands()
    
    assert "hello" in commands
    assert commands["hello"].description == "Say hello"
    assert commands["hello"].prompt == "Hello from custom command!"

def test_load_command_frontmatter_prompt(temp_config_dir):
    commands_dir = temp_config_dir / "commands"
    
    cmd_file = commands_dir / "greet.md"
    cmd_file.write_text("""---
command: greeting
prompt: How are you?
---
""")
    
    loader = CommandsLoader(commands_dir)
    commands = loader.load_commands()
    
    assert "greeting" in commands
    assert commands["greeting"].prompt == "How are you?"
