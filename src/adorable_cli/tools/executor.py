"""Tool execution engine with parallel read-only and serial write semantics.

This module implements Claude Code's tool execution pattern:
- Read-only tools execute in parallel (concurrency limit: 10)
- Write tools execute sequentially for safety
- Dangerous tools require user confirmation
- Progress tracking and error handling throughout

The executor uses async generators to stream progress updates,
allowing real-time UI feedback during tool execution.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Optional, Protocol, runtime_checkable

from adorable_cli.models.events import (
    ToolExecutionProgressEvent,
    ToolExecutionStartEvent,
    ToolResultEvent,
)
from adorable_cli.models.messages import ToolResultBlock, ToolUseBlock
from adorable_cli.utils.errors import ToolError, format_tool_error


class ToolCategory(Enum):
    """Tool categories based on side effects."""

    READ_ONLY = auto()  # Safe to run in parallel, no side effects
    WRITE = auto()  # Modifies state, must run sequentially
    DANGEROUS = auto()  # Destructive operations, requires confirmation
    SHELL = auto()  # Shell commands, special handling


@dataclass
class ToolSpec:
    """Specification for a registered tool."""

    name: str
    category: ToolCategory
    description: str = ""
    confirm_before_run: bool = False
    read_file_before_edit: bool = False
    max_execution_time: float = 60.0  # seconds


@dataclass
class ExecutionResult:
    """Result of tool execution."""

    tool_use_id: str
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass
class ExecutionContext:
    """Context passed to tool executors."""

    cwd: Path = field(default_factory=Path.cwd)
    env: dict[str, str] = field(default_factory=dict)
    file_cache: dict[Path, Any] = field(default_factory=dict)
    dry_run: bool = False

    def get_cached_file(self, path: Path) -> Optional[Any]:
        """Get cached file content if available."""
        return self.file_cache.get(path)

    def cache_file(self, path: Path, content: Any) -> None:
        """Cache file content for read-before-edit enforcement."""
        self.file_cache[path] = content


@runtime_checkable
class ToolCallable(Protocol):
    """Protocol for tool callables."""

    async def __call__(self, **kwargs: Any) -> Any:
        ...


class ToolRegistry:
    """Registry of available tools with metadata."""

    # Default tool categorization (can be extended)
    DEFAULT_CATEGORIES: dict[str, ToolCategory] = {
        # Read-only file operations
        "read_file": ToolCategory.READ_ONLY,
        "read_file_chunk": ToolCategory.READ_ONLY,
        "list_files": ToolCategory.READ_ONLY,
        "search_files": ToolCategory.READ_ONLY,
        "file_exists": ToolCategory.READ_ONLY,
        "get_file_info": ToolCategory.READ_ONLY,
        # Read-only search
        "duckduckgo_search": ToolCategory.READ_ONLY,
        "duckduckgo_news": ToolCategory.READ_ONLY,
        "fetch": ToolCategory.READ_ONLY,
        "grep": ToolCategory.READ_ONLY,
        "find": ToolCategory.READ_ONLY,
        # Read-only Python
        "run_python_code": ToolCategory.READ_ONLY,
        # Write file operations
        "save_file": ToolCategory.WRITE,
        "write_file": ToolCategory.WRITE,
        "replace_file_chunk": ToolCategory.WRITE,
        "edit_file": ToolCategory.WRITE,
        "create_directory": ToolCategory.WRITE,
        # Dangerous operations
        "run_shell_command": ToolCategory.SHELL,
        "delete_file": ToolCategory.DANGEROUS,
        "remove_file": ToolCategory.DANGEROUS,
        "delete_directory": ToolCategory.DANGEROUS,
        "move_file": ToolCategory.DANGEROUS,
        "rename_file": ToolCategory.DANGEROUS,
    }

    # Tools requiring read-before-edit enforcement
    READ_BEFORE_EDIT_TOOLS: set[str] = {
        "save_file",
        "write_file",
        "replace_file_chunk",
        "edit_file",
    }

    # Dangerous command patterns
    DANGEROUS_PATTERNS: list[str] = [
        "rm -rf /",
        "rm -rf ~",
        "rm -rf *",
        "sudo ",
        "chmod -R 000 /",
        "dd if=/dev/zero",
        "> /dev/sda",
        "mkfs.",
        ":(){ :|:& };:",  # Fork bomb
    ]

    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}
        self._specs: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        callable: Callable[..., Any],
        category: Optional[ToolCategory] = None,
        description: str = "",
    ) -> None:
        """Register a tool with the registry."""
        self._tools[name] = callable

        # Determine category
        if category is None:
            category = self.DEFAULT_CATEGORIES.get(name, ToolCategory.WRITE)

        # Determine if confirmation is needed
        confirm = category in (ToolCategory.DANGEROUS, ToolCategory.SHELL)

        self._specs[name] = ToolSpec(
            name=name,
            category=category,
            description=description,
            confirm_before_run=confirm,
            read_file_before_edit=name in self.READ_BEFORE_EDIT_TOOLS,
        )

    def get(self, name: str) -> Optional[Callable[..., Any]]:
        """Get a tool callable by name."""
        return self._tools.get(name)

    def get_spec(self, name: str) -> Optional[ToolSpec]:
        """Get tool specification by name."""
        return self._specs.get(name)

    def categorize(self, tool_name: str) -> ToolCategory:
        """Get the category for a tool."""
        spec = self._specs.get(tool_name)
        if spec:
            return spec.category
        return self.DEFAULT_CATEGORIES.get(tool_name, ToolCategory.WRITE)

    def is_read_only(self, tool_name: str) -> bool:
        """Check if a tool is read-only."""
        return self.categorize(tool_name) == ToolCategory.READ_ONLY

    def is_write(self, tool_name: str) -> bool:
        """Check if a tool modifies state."""
        return self.categorize(tool_name) == ToolCategory.WRITE

    def is_dangerous(self, tool_name: str, tool_input: dict[str, Any]) -> bool:
        """Check if a tool execution is dangerous."""
        spec = self._specs.get(tool_name)
        if spec and spec.category == ToolCategory.DANGEROUS:
            return True

        # Check shell commands for dangerous patterns
        if tool_name in ("run_shell_command", "shell"):
            command = tool_input.get("command", "")
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern in command.lower():
                    return True

        return False

    def requires_read_before_edit(self, tool_name: str) -> bool:
        """Check if tool requires read-before-edit enforcement."""
        spec = self._specs.get(tool_name)
        if spec:
            return spec.read_file_before_edit
        return tool_name in self.READ_BEFORE_EDIT_TOOLS

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())


class ParallelToolExecutor:
    """Executes tools with parallel read-only and serial write semantics.

    Implements Claude Code's execution pattern:
    1. Categorize tools by side effects
    2. Group read-only tools for parallel execution
    3. Execute write tools sequentially
    4. Handle dangerous tools with confirmation

    Example:
        executor = ParallelToolExecutor(registry, context)
        async for event in executor.execute_batch(tool_calls):
            if isinstance(event, ToolExecutionStartEvent):
                print(f"Starting {event.tool_name}")
            elif isinstance(event, ToolResultEvent):
                print(f"Completed: {event.result}")
    """

    def __init__(
        self,
        registry: ToolRegistry,
        context: ExecutionContext,
        max_parallel: int = 10,
        enable_confirmations: bool = True,
    ):
        self.registry = registry
        self.context = context
        self.max_parallel = max_parallel
        self.enable_confirmations = enable_confirmations

        # Progress callbacks
        self._progress_callbacks: list[Callable[[str, float, str], None]] = []

    def on_progress(
        self, callback: Callable[[str, float, str], None]
    ) -> "ParallelToolExecutor":
        """Register a progress callback.

        Args:
            callback: Function(tool_use_id, percent, message) -> None
        """
        self._progress_callbacks.append(callback)
        return self

    def _notify_progress(self, tool_use_id: str, percent: float, message: str) -> None:
        """Notify all progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                callback(tool_use_id, percent, message)
            except Exception:
                pass  # Don't let callbacks break execution

    async def execute_batch(
        self,
        tool_calls: list[ToolUseBlock],
        confirmation_callback: Optional[
            Callable[[ToolUseBlock], asyncio.Future[bool]]
        ] = None,
    ) -> AsyncGenerator[
        ToolExecutionStartEvent | ToolExecutionProgressEvent | ToolResultEvent, None
    ]:
        """Execute a batch of tool calls with proper parallelism.

        Args:
            tool_calls: List of tool calls to execute
            confirmation_callback: Async function to confirm dangerous tools

        Yields:
            Tool execution events (start, progress, result)
        """
        if not tool_calls:
            return

        # Categorize tool calls
        read_only_calls: list[ToolUseBlock] = []
        write_calls: list[ToolUseBlock] = []
        dangerous_calls: list[ToolUseBlock] = []

        for tool_call in tool_calls:
            tool_name = tool_call.name
            if self.registry.is_dangerous(tool_name, tool_call.input):
                dangerous_calls.append(tool_call)
            elif self.registry.is_read_only(tool_name):
                read_only_calls.append(tool_call)
            else:
                write_calls.append(tool_call)

        # Execute dangerous calls with confirmation
        for tool_call in dangerous_calls:
            async for event in self._execute_with_confirmation(
                tool_call, confirmation_callback
            ):
                yield event

        # Execute read-only calls in parallel
        if read_only_calls:
            async for event in self._execute_parallel(read_only_calls):
                yield event

        # Execute write calls sequentially
        for tool_call in write_calls:
            async for event in self._execute_single(tool_call):
                yield event

    async def _execute_with_confirmation(
        self,
        tool_call: ToolUseBlock,
        confirmation_callback: Optional[
            Callable[[ToolUseBlock], asyncio.Future[bool]]
        ],
    ) -> AsyncGenerator[
        ToolExecutionStartEvent | ToolExecutionProgressEvent | ToolResultEvent, None
    ]:
        """Execute a tool with user confirmation."""
        if not self.enable_confirmations or confirmation_callback is None:
            # Auto-decline if no confirmation mechanism
            yield ToolResultEvent(
                tool_use_id=tool_call.id,
                tool_name=tool_call.name,
                result=None,
                is_error=True,
                error_message="Confirmation required but no callback provided",
            )
            return

        # Request confirmation
        confirmed = await confirmation_callback(tool_call)

        if not confirmed:
            yield ToolResultEvent(
                tool_use_id=tool_call.id,
                tool_name=tool_call.name,
                result=None,
                is_error=True,
                error_message="User declined to run this tool",
            )
            return

        # Execute after confirmation
        async for event in self._execute_single(tool_call):
            yield event

    async def _execute_parallel(
        self, tool_calls: list[ToolUseBlock]
    ) -> AsyncGenerator[
        ToolExecutionStartEvent | ToolExecutionProgressEvent | ToolResultEvent, None
    ]:
        """Execute read-only tools in parallel with concurrency limit."""
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def execute_with_limit(
            tool_call: ToolUseBlock,
        ) -> list[ToolResultEvent]:
            async with semaphore:
                events: list[ToolResultEvent] = []
                async for event in self._execute_single(tool_call):
                    if isinstance(event, ToolResultEvent):
                        events.append(event)
                return events

        # Create tasks for all tool calls
        tasks = [execute_with_limit(tc) for tc in tool_calls]

        # Execute and yield results as they complete
        pending = set(asyncio.create_task(t) for t in tasks)

        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                try:
                    events = await task
                    for event in events:
                        yield event
                except Exception as e:
                    # Handle task errors
                    pass

    async def _execute_single(
        self, tool_call: ToolUseBlock
    ) -> AsyncGenerator[
        ToolExecutionStartEvent | ToolExecutionProgressEvent | ToolResultEvent, None
    ]:
        """Execute a single tool call."""
        tool_use_id = tool_call.id
        tool_name = tool_call.name
        tool_input = tool_call.input

        start_time = time.time()

        # Yield start event
        yield ToolExecutionStartEvent(
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            turn_id=None,  # Will be set by caller
        )

        # Validate read-before-edit for file operations
        if self.registry.requires_read_before_edit(tool_name):
            is_valid, error = self._validate_file_edit(tool_input)
            if not is_valid:
                yield ToolResultEvent(
                    tool_use_id=tool_use_id,
                    tool_name=tool_name,
                    result=None,
                    is_error=True,
                    error_message=error,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )
                return

        # Get the tool callable
        tool_callable = self.registry.get(tool_name)
        if tool_callable is None:
            yield ToolResultEvent(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                result=None,
                is_error=True,
                error_message=f"Tool not found: {tool_name}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
            return

        # Execute with timeout and error handling
        try:
            spec = self.registry.get_spec(tool_name)
            timeout = spec.max_execution_time if spec else 60.0

            # Report progress
            self._notify_progress(tool_use_id, 0.0, "Starting execution")
            yield ToolExecutionProgressEvent(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                progress_percent=0.0,
                message="Starting execution",
            )

            # Execute the tool
            is_async_callable = asyncio.iscoroutinefunction(tool_callable) or inspect.iscoroutinefunction(
                getattr(tool_callable, "__call__", None)
            )
            if is_async_callable:
                result = await asyncio.wait_for(tool_callable(**tool_input), timeout=timeout)
            else:
                # Run sync function in thread pool
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool_callable(**tool_input)),
                    timeout=timeout,
                )
                if inspect.isawaitable(result):
                    result = await asyncio.wait_for(result, timeout=timeout)

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Report completion
            self._notify_progress(tool_use_id, 100.0, "Complete")

            yield ToolResultEvent(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                result=result,
                is_error=False,
                execution_time_ms=execution_time_ms,
            )

        except asyncio.TimeoutError:
            execution_time_ms = int((time.time() - start_time) * 1000)
            yield ToolResultEvent(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                result=None,
                is_error=True,
                error_message=f"Tool execution timed out after {timeout}s",
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            formatted_error = format_tool_error(tool_name, tool_input, e)

            yield ToolResultEvent(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                result=None,
                is_error=True,
                error_message=formatted_error,
                execution_time_ms=execution_time_ms,
            )

    def _validate_file_edit(self, tool_input: dict[str, Any]) -> tuple[bool, str]:
        """Validate read-before-edit for file operations.

        Returns:
            (is_valid, error_message)
        """
        file_path = tool_input.get("file_path") or tool_input.get("path")
        if not file_path:
            return True, ""  # No file path, skip validation

        path = Path(file_path)
        if not path.is_absolute():
            path = self.context.cwd / path

        cached = self.context.get_cached_file(path)
        if cached is None:
            return (
                False,
                f"File {path} must be read before editing. "
                "Use read_file first.",
            )

        return True, ""


class ToolExecutionGroup:
    """A group of tools that can be executed together.

    Read-only tools are grouped for parallel execution.
    Write tools are in their own group for sequential execution.
    """

    def __init__(self, tools: list[ToolUseBlock], parallel: bool = False):
        self.tools = tools
        self.parallel = parallel

    @classmethod
    def create_groups(
        cls,
        tool_calls: list[ToolUseBlock],
        registry: ToolRegistry,
    ) -> list["ToolExecutionGroup"]:
        """Create execution groups from tool calls.

        Groups consecutive read-only tools together.
        Write tools get their own group.
        """
        if not tool_calls:
            return []

        groups: list[ToolExecutionGroup] = []
        current_read_group: list[ToolUseBlock] = []

        for tool_call in tool_calls:
            tool_name = tool_call.name

            if registry.is_read_only(tool_name):
                current_read_group.append(tool_call)
            else:
                # Flush current read group
                if current_read_group:
                    groups.append(ToolExecutionGroup(current_read_group, parallel=True))
                    current_read_group = []

                # Write tool gets its own group
                groups.append(ToolExecutionGroup([tool_call], parallel=False))

        # Flush final read group
        if current_read_group:
            groups.append(ToolExecutionGroup(current_read_group, parallel=True))

        return groups


# Convenience function for simple tool execution
async def execute_tools_simple(
    tool_calls: list[ToolUseBlock],
    registry: ToolRegistry,
    context: ExecutionContext,
    max_parallel: int = 10,
) -> list[ToolResultBlock]:
    """Execute tools and return results (non-streaming).

    Convenience function for when you just need the results
    without progress tracking.

    Args:
        tool_calls: List of tool calls to execute
        registry: Tool registry
        context: Execution context
        max_parallel: Maximum parallel read-only tools

    Returns:
        List of tool results in the same order as tool_calls
    """
    executor = ParallelToolExecutor(registry, context, max_parallel)
    results: dict[str, ToolResultBlock] = {}

    async for event in executor.execute_batch(tool_calls):
        if isinstance(event, ToolResultEvent):
            results[event.tool_use_id] = ToolResultBlock(
                tool_use_id=event.tool_use_id,
                content=str(event.result) if event.result else "",
                is_error=event.is_error,
            )

    # Return results in original order
    ordered_results = []
    for tc in tool_calls:
        if tc.id in results:
            ordered_results.append(results[tc.id])
        else:
            # Missing result (shouldn't happen)
            ordered_results.append(
                ToolResultBlock(
                    tool_use_id=tc.id,
                    content="",
                    is_error=True,
                )
            )

    return ordered_results
