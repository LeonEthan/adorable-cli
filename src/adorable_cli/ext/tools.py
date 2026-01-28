import hashlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import List

from agno.tools import Toolkit
from adorable_cli.console import console

class ToolsLoader:
    def __init__(self, tools_dir: Path):
        self.tools_dir = tools_dir

    def load_tools(self) -> List[Toolkit]:
        """
        Load all Toolkit subclasses found in python files within tools_dir.
        """
        tools = []
        if not self.tools_dir.exists():
            return tools

        for file_path in self.tools_dir.glob("*.py"):
            if file_path.name.startswith("__") or file_path.name.startswith("."):
                continue

            try:
                digest = hashlib.md5(str(file_path).encode("utf-8")).hexdigest()[:8]
                module_name = f"adorable_ext_tools_{file_path.stem}_{digest}"
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, Toolkit)
                            and obj is not Toolkit
                        ):
                            try:
                                # Instantiate the tool
                                tool_instance = obj()
                                tools.append(tool_instance)
                                console.print(f"[success]Loaded tool: {name} from {file_path.name}[/success]")
                            except Exception as e:
                                console.print(f"[error]Failed to instantiate tool {name}: {e}[/error]")
            except Exception as e:
                console.print(f"[error]Failed to load module {file_path.name}: {e}[/error]")

        return tools
