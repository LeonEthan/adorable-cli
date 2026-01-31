"""Tests for context management (normalizer and assembler)."""

import json
from pathlib import Path

import pytest

from adorable_cli.context.normalizer import (
    NormalizerConfig,
    SizeCalculator,
    TruncationStrategy,
    create_message_normalizer,
    create_tool_result_normalizer,
    normalize_to_size,
)
from adorable_cli.context.assembler import (
    ClaudeMdLoader,
    ContextAssembler,
    ContextItem,
    PriorityLevel,
    build_context_for_turn,
)


class TestSizeCalculator:
    """Test the size calculator."""

    def test_calculate_string(self):
        """Calculate size of a string."""
        calc = SizeCalculator()
        size = calc.calculate("hello world")
        assert size > 0
        assert size == len('"hello world"'.encode())

    def test_calculate_dict(self):
        """Calculate size of a dict."""
        calc = SizeCalculator()
        obj = {"key": "value", "number": 123}
        size = calc.calculate(obj)
        assert size > 0

    def test_calculate_nested(self):
        """Calculate size of nested structure."""
        calc = SizeCalculator()
        obj = {"outer": {"inner": [1, 2, 3]}}
        size = calc.calculate(obj)
        assert size > 0

    def test_is_within_budget(self):
        """Check if object is within budget."""
        calc = SizeCalculator()
        obj = {"test": "data"}

        assert calc.is_within_budget(obj, 10000)
        assert not calc.is_within_budget(obj, 1)

    def test_estimate_size_non_serializable(self):
        """Estimate size for non-serializable objects."""
        calc = SizeCalculator()
        # Custom object
        class CustomObj:
            def __repr__(self):
                return "custom"

        size = calc._estimate_size(CustomObj())
        assert size > 0


class TestNormalizeToSize:
    """Test the normalize_to_size function."""

    def test_already_within_budget(self):
        """Return unchanged if already within budget."""
        obj = {"key": "value"}
        result = normalize_to_size(obj, max_bytes=10000)
        assert result == obj

    def test_truncate_list(self):
        """Truncate a large list."""
        obj = {"items": [f"item {i}" for i in range(200)]}
        result = normalize_to_size(obj, max_bytes=500)

        # Should have fewer items
        assert len(result["items"]) < 200

    def test_truncate_string(self):
        """Truncate a long string."""
        obj = {"text": "x" * 10000}
        result = normalize_to_size(obj, max_bytes=500)

        # String should be shorter
        assert len(result["text"]) < 10000

    def test_reduce_depth(self):
        """Reduce nesting depth."""
        obj = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        result = normalize_to_size(obj, max_bytes=100, max_depth=3)

        # Deep structure should be summarized
        assert "<" in str(result) or len(str(result)) < len(str(obj))

    def test_preserve_keys(self):
        """Preserve specified keys during truncation."""
        config = NormalizerConfig(
            max_bytes=200,
            max_dict_keys=2,
            preserve_keys={"important"},
        )
        obj = {
            "important": "keep this",
            "a": "1",
            "b": "2",
            "c": "3",
        }
        result = normalize_to_size(obj, config=config)

        # Important key should be preserved
        assert "important" in result

    def test_circular_reference(self):
        """Handle circular references."""
        obj = {"name": "test"}
        obj["self"] = obj

        result = normalize_to_size(obj, max_bytes=1000)
        # Should not crash
        assert "circular" in str(result).lower() or "test" in str(result)

    def test_truncate_tail_strategy(self):
        """Use tail truncation strategy."""
        config = NormalizerConfig(
            max_bytes=1000,
            max_list_items=10,
            list_strategy=TruncationStrategy.TRUNCATE_TAIL,
        )
        obj = {"items": list(range(100))}
        result = normalize_to_size(obj, config=config)

        # Should keep some from head and tail
        items = result["items"]
        assert 0 in items  # From head
        assert 99 in items  # From tail


class TestMessageNormalizer:
    """Test the message normalizer factory."""

    def test_create_normalizer(self):
        """Create a message normalizer."""
        normalizer = create_message_normalizer(max_context_tokens=1000)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = normalizer(messages)
        assert isinstance(result, list)

    def test_truncate_long_messages(self):
        """Truncate messages that are too long."""
        normalizer = create_message_normalizer(max_context_tokens=100)
        messages = [
            {"role": "user", "content": "x" * 1000},
        ]
        result = normalizer(messages)
        # Should be shorter
        total_length = sum(len(str(m)) for m in result)
        assert total_length < 1000


class TestToolResultNormalizer:
    """Test the tool result normalizer."""

    def test_normalize_large_result(self):
        """Normalize a large tool result."""
        normalizer = create_tool_result_normalizer(max_result_bytes=500)
        result = normalizer({"output": "x" * 10000})

        # Should be smaller
        assert len(str(result)) < 10000


class TestPriorityLevel:
    """Test priority levels."""

    def test_priority_order(self):
        """Priority levels are ordered correctly."""
        assert PriorityLevel.CRITICAL.value < PriorityLevel.HIGH.value
        assert PriorityLevel.HIGH.value < PriorityLevel.MEDIUM.value
        assert PriorityLevel.MEDIUM.value < PriorityLevel.LOW.value


class TestContextItem:
    """Test context items."""

    def test_estimate_tokens_string(self):
        """Estimate tokens for string content."""
        item = ContextItem(
            content="Hello world",
            priority=PriorityLevel.HIGH,
            source="user",
        )
        assert item.estimated_tokens > 0
        assert item.estimated_tokens == len("Hello world") // 4

    def test_estimate_tokens_dict(self):
        """Estimate tokens for dict content."""
        item = ContextItem(
            content={"key": "value"},
            priority=PriorityLevel.HIGH,
            source="system",
        )
        assert item.estimated_tokens > 0


class TestContextAssembler:
    """Test the context assembler."""

    def test_empty_assembly(self):
        """Assemble with no items."""
        assembler = ContextAssembler(max_tokens=1000)
        result = assembler.assemble()

        assert len(result.items) == 0
        assert result.total_tokens == 0
        assert not result.truncated

    def test_add_single_item(self):
        """Add a single item."""
        assembler = ContextAssembler(max_tokens=1000)
        assembler.add_item("test", PriorityLevel.HIGH, "system")

        result = assembler.assemble()
        assert len(result.items) == 1

    def test_priority_ordering(self):
        """Items ordered by priority."""
        assembler = ContextAssembler(max_tokens=1000)
        assembler.add_item("low", PriorityLevel.LOW, "system")
        assembler.add_item("critical", PriorityLevel.CRITICAL, "system")
        assembler.add_item("high", PriorityLevel.HIGH, "system")

        result = assembler.assemble()
        priorities = [item.priority for item in result.items]
        assert priorities == [PriorityLevel.CRITICAL, PriorityLevel.HIGH, PriorityLevel.LOW]

    def test_truncation(self):
        """Truncate when exceeding token budget."""
        assembler = ContextAssembler(max_tokens=100)
        # Add items that exceed budget
        for i in range(10):
            assembler.add_item(f"message {i}" * 50, PriorityLevel.LOW, "history")

        result = assembler.assemble()
        assert result.truncated
        assert result.total_tokens <= 96  # 100 - 4 reserved

    def test_system_prompt_priority(self):
        """System prompt has CRITICAL priority."""
        assembler = ContextAssembler(max_tokens=1000)
        assembler.add_system_prompt("You are a helpful assistant")

        result = assembler.assemble()
        assert len(result.items) == 1
        assert result.items[0].priority == PriorityLevel.CRITICAL

    def test_user_message_priority(self):
        """User message has HIGH priority."""
        assembler = ContextAssembler(max_tokens=1000)
        assembler.add_user_message("Hello")

        result = assembler.assemble()
        assert result.items[0].priority == PriorityLevel.HIGH

    def test_tool_result_priority(self):
        """Tool result has MEDIUM priority."""
        assembler = ContextAssembler(max_tokens=1000)
        assembler.add_tool_result({"output": "result"}, "test_tool")

        result = assembler.assemble()
        assert result.items[0].priority == PriorityLevel.MEDIUM

    def test_conversation_history_summarization(self):
        """Conversation history can be summarized."""
        assembler = ContextAssembler(max_tokens=200)
        # Add a long conversation history
        history = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        assembler.add_conversation_history(history, can_summarize=True)

        result = assembler.assemble()
        # Should be summarized (fewer items than original)
        history_item = result.items[0]
        assert isinstance(history_item.content, list)
        assert len(history_item.content) < 20

    def test_to_messages(self):
        """Convert to message format."""
        assembler = ContextAssembler(max_tokens=1000)
        assembler.add_system_prompt("System prompt")
        assembler.add_user_message("User message")

        messages = assembler.to_messages()
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_model_specific_limits(self):
        """Use model-specific token limits."""
        # Claude model
        assembler = ContextAssembler(model_id="claude-3-opus")
        assert assembler.max_tokens == 200_000

        # GPT model
        assembler = ContextAssembler(model_id="gpt-4o")
        assert assembler.max_tokens == 128_000

        # Unknown model (default)
        assembler = ContextAssembler(model_id="unknown-model")
        assert assembler.max_tokens == 128_000

    def test_clear(self):
        """Clear all items."""
        assembler = ContextAssembler(max_tokens=1000)
        assembler.add_item("test", PriorityLevel.HIGH, "system")
        assembler.clear()

        result = assembler.assemble()
        assert len(result.items) == 0

    def test_chaining(self):
        """Method chaining works."""
        assembler = ContextAssembler(max_tokens=1000)
        result = (
            assembler.add_system_prompt("System")
            .add_user_message("User")
            .add_assistant_message("Assistant")
            .assemble()
        )
        assert len(result.items) == 3


class TestClaudeMdLoader:
    """Test the CLAUDE.md loader."""

    def test_load_nonexistent(self, tmp_path):
        """Handle non-existent files."""
        loader = ClaudeMdLoader()
        results = loader.load(tmp_path / "nonexistent")
        assert len(results) == 0

    def test_load_single_file(self, tmp_path):
        """Load a single CLAUDE.md file."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("# Project Context")

        loader = ClaudeMdLoader()
        results = loader.load(tmp_path)

        assert len(results) == 1
        assert "Project Context" in results[md_file]

    def test_load_hierarchical(self, tmp_path):
        """Load CLAUDE.md from parent directories."""
        # Create parent CLAUDE.md
        parent_md = tmp_path / "CLAUDE.md"
        parent_md.write_text("# Parent Context")

        # Create subdirectory with its own CLAUDE.md
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        child_md = subdir / "CLAUDE.md"
        child_md.write_text("# Child Context")

        loader = ClaudeMdLoader()
        results = loader.load(subdir)

        assert len(results) == 1  # Only closest one by default
        assert "Child Context" in results[child_md]

    def test_load_merged(self, tmp_path):
        """Load and merge multiple CLAUDE.md files."""
        # Create parent and child
        parent_md = tmp_path / "CLAUDE.md"
        parent_md.write_text("# Parent")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        child_md = subdir / "CLAUDE.md"
        child_md.write_text("# Child")

        loader = ClaudeMdLoader()
        # Default: override_local=True, should return only closest
        merged = loader.load_merged(subdir)
        assert "Child" in merged
        assert "Parent" not in merged

    def test_alternative_filenames(self, tmp_path):
        """Load alternative CLAUDE.md filenames."""
        md_file = tmp_path / ".claude.md"
        md_file.write_text("# Alternative")

        loader = ClaudeMdLoader()
        results = loader.load(tmp_path)

        assert len(results) == 1

    def test_size_limit(self, tmp_path):
        """Truncate files that are too large."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("x" * 100_000)

        from adorable_cli.context.assembler import ClaudeMdConfig
        config = ClaudeMdConfig(max_size_bytes=1000)
        loader = ClaudeMdLoader(config)
        result = loader.load_merged(tmp_path)

        assert len(result.encode()) < 100_000
        assert "[truncated]" in result


class TestBuildContextForTurn:
    """Test the convenience function."""

    def test_build_basic_context(self, tmp_path):
        """Build basic context."""
        messages = build_context_for_turn(
            user_input="Hello",
            conversation_history=[],
            system_instructions="You are helpful",
            working_dir=tmp_path,
        )

        assert len(messages) >= 2  # System + user
        assert any(m["role"] == "system" for m in messages)
        assert any(m["role"] == "user" and "Hello" in str(m["content"]) for m in messages)

    def test_build_with_history(self, tmp_path):
        """Build context with conversation history."""
        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        messages = build_context_for_turn(
            user_input="Follow up",
            conversation_history=history,
            system_instructions="You are helpful",
            working_dir=tmp_path,
        )

        # Should include history
        assert any("Previous question" in str(m.get("content", "")) for m in messages)

    def test_build_with_claude_md(self, tmp_path):
        """Build context with CLAUDE.md."""
        # Create CLAUDE.md
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("# Use Python 3.11")

        messages = build_context_for_turn(
            user_input="Hello",
            conversation_history=[],
            system_instructions="You are helpful",
            working_dir=tmp_path,
        )

        # Should include CLAUDE.md content
        assert any("Python 3.11" in str(m.get("content", "")) for m in messages)

    def test_build_with_tool_results(self, tmp_path):
        """Build context with tool results."""
        messages = build_context_for_turn(
            user_input="What files?",
            conversation_history=[],
            system_instructions="You are helpful",
            working_dir=tmp_path,
            tool_results=[{"files": ["a.py", "b.py"]}],
        )

        # Should include tool results
        assert any("a.py" in str(m.get("content", "")) for m in messages)
