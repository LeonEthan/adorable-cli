"""Tests for the parallel tool execution engine."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from adorable_cli.models.messages import ToolUseBlock
from adorable_cli.tools.executor import (
    ExecutionContext,
    ParallelToolExecutor,
    ToolCategory,
    ToolExecutionGroup,
    ToolRegistry,
    execute_tools_simple,
)


class MockTool:
    """Mock tool for testing."""

    def __init__(self, delay: float = 0, result: Any = None, should_error: bool = False):
        self.delay = delay
        self.result = result
        self.should_error = should_error
        self.call_count = 0

    async def __call__(self, **kwargs: Any) -> Any:
        self.call_count += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.should_error:
            raise RuntimeError("Mock error")
        return self.result or {"result": "ok", "args": kwargs}


class TestToolRegistry:
    """Test the tool registry."""

    def test_register_tool(self):
        """Register a tool and retrieve it."""
        registry = ToolRegistry()
        mock_tool = MockTool()

        registry.register("test_tool", mock_tool)

        assert registry.get("test_tool") is mock_tool
        assert registry.list_tools() == ["test_tool"]

    def test_default_categories(self):
        """Test default tool categorization."""
        registry = ToolRegistry()

        # Register tools with default categories
        registry.register("read_file", MockTool())
        registry.register("save_file", MockTool())
        registry.register("run_shell_command", MockTool())

        assert registry.categorize("read_file") == ToolCategory.READ_ONLY
        assert registry.categorize("save_file") == ToolCategory.WRITE
        assert registry.categorize("run_shell_command") == ToolCategory.SHELL

    def test_custom_category(self):
        """Register tool with custom category."""
        registry = ToolRegistry()
        mock_tool = MockTool()

        registry.register("custom_tool", mock_tool, category=ToolCategory.DANGEROUS)

        assert registry.categorize("custom_tool") == ToolCategory.DANGEROUS
        assert registry.is_dangerous("custom_tool", {})

    def test_is_read_only(self):
        """Test read-only detection."""
        registry = ToolRegistry()

        registry.register("list_files", MockTool())
        registry.register("write_file", MockTool())

        assert registry.is_read_only("list_files")
        assert not registry.is_read_only("write_file")

    def test_is_dangerous_shell_pattern(self):
        """Test dangerous shell pattern detection."""
        registry = ToolRegistry()

        # Register shell tool
        registry.register("run_shell_command", MockTool())

        # Check dangerous patterns
        dangerous_input = {"command": "rm -rf /"}
        safe_input = {"command": "ls -la"}

        assert registry.is_dangerous("run_shell_command", dangerous_input)
        assert not registry.is_dangerous("run_shell_command", safe_input)

    def test_requires_read_before_edit(self):
        """Test read-before-edit enforcement detection."""
        registry = ToolRegistry()

        registry.register("save_file", MockTool())
        registry.register("read_file", MockTool())

        assert registry.requires_read_before_edit("save_file")
        assert not registry.requires_read_before_edit("read_file")


class TestParallelToolExecutor:
    """Test the parallel tool executor."""

    @pytest.mark.asyncio
    async def test_execute_single_tool(self):
        """Execute a single tool."""
        registry = ToolRegistry()
        mock_tool = MockTool(result={"data": "test"})
        registry.register("test_tool", mock_tool)

        context = ExecutionContext()
        executor = ParallelToolExecutor(registry, context)

        tool_call = ToolUseBlock(id="tool-1", name="test_tool", input={"arg": "value"})

        results = []
        async for event in executor.execute_batch([tool_call]):
            if hasattr(event, "result"):
                results.append(event)

        assert len(results) == 1
        assert results[0].tool_name == "test_tool"
        assert results[0].is_error is False

    @pytest.mark.asyncio
    async def test_execute_parallel_read_only(self):
        """Execute read-only tools in parallel."""
        registry = ToolRegistry()

        # Create tools with delays
        tool1 = MockTool(delay=0.1, result={"file": "1"})
        tool2 = MockTool(delay=0.1, result={"file": "2"})
        tool3 = MockTool(delay=0.1, result={"file": "3"})

        registry.register("read_file", tool1)
        registry.register("list_files", tool2)
        registry.register("search_files", tool3)

        context = ExecutionContext()
        executor = ParallelToolExecutor(registry, context, max_parallel=10)

        tool_calls = [
            ToolUseBlock(id="t1", name="read_file", input={"path": "/tmp/1"}),
            ToolUseBlock(id="t2", name="list_files", input={"path": "/tmp"}),
            ToolUseBlock(id="t3", name="search_files", input={"query": "test"}),
        ]

        start = asyncio.get_event_loop().time()
        results = []

        async for event in executor.execute_batch(tool_calls):
            if hasattr(event, "result"):
                results.append(event)

        elapsed = asyncio.get_event_loop().time() - start

        # Should complete in ~0.1s (parallel) not 0.3s (serial)
        assert elapsed < 0.25
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_execute_sequential_write(self):
        """Execute write tools sequentially."""
        registry = ToolRegistry()

        execution_order = []

        async def make_tool(name: str):
            async def tool(**kwargs):
                execution_order.append(name)
                await asyncio.sleep(0.05)
                return {"tool": name}
            return tool

        registry.register("write_file", await make_tool("write1"))
        registry.register("save_file", await make_tool("write2"))

        context = ExecutionContext()
        executor = ParallelToolExecutor(registry, context)

        tool_calls = [
            ToolUseBlock(id="t1", name="write_file", input={}),
            ToolUseBlock(id="t2", name="save_file", input={}),
        ]

        async for event in executor.execute_batch(tool_calls):
            pass

        # Both tools should have executed
        assert len(execution_order) == 2

    @pytest.mark.asyncio
    async def test_execute_with_error(self):
        """Handle tool execution errors."""
        registry = ToolRegistry()
        mock_tool = MockTool(should_error=True)
        registry.register("error_tool", mock_tool)

        context = ExecutionContext()
        executor = ParallelToolExecutor(registry, context)

        tool_call = ToolUseBlock(id="tool-1", name="error_tool", input={})

        results = []
        async for event in executor.execute_batch([tool_call]):
            if hasattr(event, "is_error"):
                results.append(event)

        assert len(results) == 1
        assert results[0].is_error is True
        assert "Mock error" in results[0].error_message

    @pytest.mark.asyncio
    async def test_execute_with_confirmation(self):
        """Execute dangerous tool with confirmation."""
        registry = ToolRegistry()
        mock_tool = MockTool(result={"deleted": True})
        registry.register("delete_file", mock_tool, category=ToolCategory.DANGEROUS)

        context = ExecutionContext()
        executor = ParallelToolExecutor(registry, context, enable_confirmations=True)

        tool_call = ToolUseBlock(id="tool-1", name="delete_file", input={"path": "/tmp/x"})

        # Confirmation callback that approves
        async def confirm(tool_call):
            return True

        results = []
        async for event in executor.execute_batch([tool_call], confirm):
            if hasattr(event, "result"):
                results.append(event)

        assert len(results) == 1
        assert results[0].is_error is False

    @pytest.mark.asyncio
    async def test_execute_confirmation_declined(self):
        """Handle declined confirmation."""
        registry = ToolRegistry()
        mock_tool = MockTool(result={"deleted": True})
        registry.register("delete_file", mock_tool, category=ToolCategory.DANGEROUS)

        context = ExecutionContext()
        executor = ParallelToolExecutor(registry, context, enable_confirmations=True)

        tool_call = ToolUseBlock(id="tool-1", name="delete_file", input={})

        # Confirmation callback that declines
        async def decline(tool_call):
            return False

        results = []
        async for event in executor.execute_batch([tool_call], decline):
            if hasattr(event, "result"):
                results.append(event)

        assert len(results) == 1
        assert results[0].is_error is True
        assert "declined" in results[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_file_safety_validation(self):
        """Test read-before-edit enforcement."""
        registry = ToolRegistry()
        mock_tool = MockTool()
        registry.register("save_file", mock_tool)

        context = ExecutionContext()
        # Don't cache the file first

        executor = ParallelToolExecutor(registry, context)

        tool_call = ToolUseBlock(
            id="tool-1",
            name="save_file",
            input={"file_path": "/tmp/not_read.txt"},
        )

        results = []
        async for event in executor.execute_batch([tool_call]):
            if hasattr(event, "result"):
                results.append(event)

        assert len(results) == 1
        assert results[0].is_error is True
        assert "must be read before editing" in results[0].error_message

    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        """Handle missing tool."""
        registry = ToolRegistry()
        context = ExecutionContext()
        executor = ParallelToolExecutor(registry, context)

        tool_call = ToolUseBlock(id="tool-1", name="nonexistent", input={})

        results = []
        async for event in executor.execute_batch([tool_call]):
            if hasattr(event, "result"):
                results.append(event)

        assert len(results) == 1
        assert results[0].is_error is True
        assert "not found" in results[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """Test progress reporting."""
        registry = ToolRegistry()
        mock_tool = MockTool()
        registry.register("test_tool", mock_tool)

        context = ExecutionContext()
        executor = ParallelToolExecutor(registry, context)

        progress_updates = []

        def on_progress(tool_use_id, percent, message):
            progress_updates.append((tool_use_id, percent, message))

        executor.on_progress(on_progress)

        tool_call = ToolUseBlock(id="tool-1", name="test_tool", input={})

        async for event in executor.execute_batch([tool_call]):
            pass

        # Should have progress updates
        assert len(progress_updates) >= 1
        assert any(p[1] == 100.0 for p in progress_updates)


class TestToolExecutionGroup:
    """Test tool execution grouping."""

    def test_group_read_only_tools(self):
        """Group consecutive read-only tools."""
        registry = ToolRegistry()
        registry.register("read_file", MockTool())
        registry.register("list_files", MockTool())
        registry.register("write_file", MockTool())

        tool_calls = [
            ToolUseBlock(id="t1", name="read_file", input={}),
            ToolUseBlock(id="t2", name="list_files", input={}),
            ToolUseBlock(id="t3", name="write_file", input={}),
        ]

        groups = ToolExecutionGroup.create_groups(tool_calls, registry)

        assert len(groups) == 2
        assert len(groups[0].tools) == 2  # read_file + list_files
        assert groups[0].parallel is True
        assert len(groups[1].tools) == 1  # write_file
        assert groups[1].parallel is False

    def test_group_write_tools_separate(self):
        """Each write tool gets its own group."""
        registry = ToolRegistry()
        registry.register("write_file", MockTool())
        registry.register("save_file", MockTool())

        tool_calls = [
            ToolUseBlock(id="t1", name="write_file", input={}),
            ToolUseBlock(id="t2", name="save_file", input={}),
        ]

        groups = ToolExecutionGroup.create_groups(tool_calls, registry)

        assert len(groups) == 2
        assert all(not g.parallel for g in groups)

    def test_group_empty(self):
        """Handle empty tool calls."""
        registry = ToolRegistry()
        groups = ToolExecutionGroup.create_groups([], registry)
        assert len(groups) == 0


class TestExecuteToolsSimple:
    """Test the convenience function."""

    @pytest.mark.asyncio
    async def test_simple_execution(self):
        """Execute tools with simple interface."""
        registry = ToolRegistry()
        registry.register("read_file", MockTool(result={"content": "test"}))

        context = ExecutionContext()
        tool_calls = [ToolUseBlock(id="t1", name="read_file", input={"path": "/tmp"})]

        results = await execute_tools_simple(tool_calls, registry, context)

        assert len(results) == 1
        assert results[0].is_error is False

    @pytest.mark.asyncio
    async def test_simple_error(self):
        """Handle errors in simple execution."""
        registry = ToolRegistry()
        registry.register("error_tool", MockTool(should_error=True))

        context = ExecutionContext()
        tool_calls = [ToolUseBlock(id="t1", name="error_tool", input={})]

        results = await execute_tools_simple(tool_calls, registry, context)

        assert len(results) == 1
        assert results[0].is_error is True


class TestExecutionContext:
    """Test execution context."""

    def test_file_cache(self):
        """Test file caching."""
        context = ExecutionContext()

        context.cache_file(Path("/tmp/test.txt"), "content")
        assert context.get_cached_file(Path("/tmp/test.txt")) == "content"
        assert context.get_cached_file(Path("/tmp/other.txt")) is None

    def test_cwd_default(self):
        """Default working directory."""
        context = ExecutionContext()
        assert context.cwd == Path.cwd()

    def test_custom_cwd(self):
        """Custom working directory."""
        context = ExecutionContext(cwd=Path("/tmp"))
        assert context.cwd == Path("/tmp")
