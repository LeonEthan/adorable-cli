"""Execution context management"""

import time
import uuid
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class ExecutionContext:
    """Execution context"""
    work_dir: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    execution_id: str = ""
    user_context: dict[str, Any] = field(default_factory=dict)
    
    @property
    def execution_time(self) -> float:
        """Get execution time"""
        end = self.end_time or time.time()
        return end - self.start_time
    
    @classmethod
    def create(cls, user_context: Optional[dict] = None) -> 'ExecutionContext':
        """Create execution context"""
        return cls(
            execution_id=str(uuid.uuid4())[:8],
            user_context=user_context or {}
        )
    
    def finish(self):
        """Mark execution finished"""
        self.end_time = time.time()