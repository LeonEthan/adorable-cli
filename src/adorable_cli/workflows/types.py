from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(frozen=True)
class WorkflowResult:
    workflow_id: str
    output: str
    format: str = "markdown"


RunWorkflowFn = Callable[..., Awaitable[WorkflowResult]]


@dataclass(frozen=True)
class WorkflowSpec:
    workflow_id: str
    description: str
    run: RunWorkflowFn
    requires_component: bool = True
