from pathlib import Path
from typing import List

from agno.tools import Toolkit
from adorable_cli.ext.tools import ToolsLoader

class SkillsLoader(ToolsLoader):
    """
    Loader for skills. Currently behaves identically to ToolsLoader,
    loading Toolkit subclasses from python files.
    """
    def __init__(self, skills_dir: Path):
        super().__init__(skills_dir)
    
    def load_skills(self) -> List[Toolkit]:
        return self.load_tools()
