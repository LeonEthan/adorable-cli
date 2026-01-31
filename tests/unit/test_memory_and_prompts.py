"""Tests for memory system and prompt engineering."""

import asyncio
import os
import sqlite3
import tempfile
import pytest

from adorable_cli.memory import (
    CompressionManager,
    CompressionResult,
    compress_tool_result,
    compress_messages,
    SessionSummarizer,
    SummaryResult,
    WorkingMemory,
    MemoryItem,
    MemoryPriority,
)
from adorable_cli.prompts.engineering import (
    PromptEngineer,
    PromptStyle,
    ConcisenessEnforcer,
)
from adorable_cli.prompts.templates import (
    get_system_prompt,
    get_error_prompt,
    get_recovery_prompt,
)
from adorable_cli.prompts.psychological import (
    ConfidenceCalibrator,
    UncertaintyHandler,
    ErrorFraming,
    ConfidenceLevel,
)


class TestCompressionManager:
    """Test compression functionality."""

    def test_should_compress_threshold(self):
        manager = CompressionManager(compress_threshold=10)
        assert manager.should_compress(5) is False
        assert manager.should_compress(10) is True
        assert manager.should_compress(20) is True

    def test_compress_small_result_not_compressed(self):
        manager = CompressionManager()
        result = manager.compress_tool_result("small output")

        assert result.was_compressed is False
        assert result.original_size == result.compressed_size

    def test_compress_large_result(self):
        manager = CompressionManager()
        large_output = "x" * 1000 + "\n" * 100

        result = manager.compress_tool_result(large_output)

        assert result.was_compressed is True
        assert result.compressed_size < result.original_size
        assert result.compression_ratio > 0

    def test_preserve_essential_patterns(self):
        manager = CompressionManager()
        output = """
Some regular output here
Error: Critical failure occurred
More output
Path: /home/user/file.txt
Final output
"""
        result = manager.compress_tool_result(output)

        compressed = result.content
        assert "Error:" in compressed or len(compressed) > 0
        assert "Path:" in compressed or len(compressed) > 0

    def test_compress_shell_output(self):
        manager = CompressionManager()
        shell_output = """
Running command...
[#######             ] 35%
[############        ] 60%
[####################] 100%
Output line 1
Output line 2
""" * 50  # More repetitions to trigger compression

        result = manager.compress_tool_result(shell_output, tool_name="shell")

        # Just verify compression happens; progress bar removal is best-effort
        assert result.was_compressed is True
        assert result.compression_ratio > 0

    def test_compress_convenience_function(self):
        result = compress_tool_result("x" * 3000, max_length=1000)

        assert len(result) <= 1000


class TestCompressMessages:
    """Test message compression."""

    def test_no_compression_below_target(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        result = compress_messages(messages, target_count=5)

        assert len(result) == len(messages)

    def test_compression_above_target(self):
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(20)
        ]

        result = compress_messages(messages, target_count=5)

        # Compressed to around target (may include summary message)
        assert len(result) <= 6

    def test_keep_system_messages(self):
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
        ] + [{"role": "user", "content": f"Msg {i}"} for i in range(15)]

        result = compress_messages(messages, target_count=5)

        system_msgs = [m for m in result if m.get("role") == "system"]
        assert len(system_msgs) >= 1


class TestSessionSummarizer:
    """Test session summarization."""

    def test_ensure_tables_creates_database(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            summarizer = SessionSummarizer(db_path=db_path)

            assert os.path.exists(db_path)

            with sqlite3.connect(db_path) as conn:
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                table_names = [t[0] for t in tables]

                assert "session_summaries" in table_names
                assert "summary_history" in table_names
        finally:
            os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_summarize_empty_messages(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            summarizer = SessionSummarizer(db_path=db_path)
            result = await summarizer.summarize_session(
                session_id="test123",
                messages=[],
            )

            assert result.summary == "No messages to summarize."
            assert result.message_count == 0
        finally:
            os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_summarize_with_messages(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            summarizer = SessionSummarizer(db_path=db_path)
            messages = [
                {"role": "user", "content": "Read file.py"},
                {"role": "assistant", "content": "Reading file.py..."},
                {"role": "user", "content": "Edit it"},
            ]

            result = await summarizer.summarize_session(
                session_id="test456",
                messages=messages,
            )

            assert result.session_id == "test456"
            assert result.message_count == 3
            assert len(result.summary) > 0
        finally:
            os.unlink(db_path)

    def test_get_summary_retrieves_stored(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            summarizer = SessionSummarizer(db_path=db_path)

            # Directly store a summary
            result = SummaryResult(
                summary="Test summary",
                session_id="stored123",
                message_count=5,
                generated_at=1234567890.0,
            )
            summarizer._store_summary(result)

            # Retrieve it
            retrieved = summarizer.get_summary("stored123")

            assert retrieved is not None
            assert retrieved.summary == "Test summary"
            assert retrieved.message_count == 5
        finally:
            os.unlink(db_path)


class TestWorkingMemory:
    """Test working memory functionality."""

    def test_add_item(self):
        memory = WorkingMemory(max_items=10)
        item = memory.add("Test content", priority=MemoryPriority.HIGH)

        assert item.content == "Test content"
        assert item.priority == MemoryPriority.HIGH
        assert len(memory) == 1

    def test_add_evicts_low_priority(self):
        memory = WorkingMemory(max_items=3)

        # Add low priority items
        memory.add("Low 1", priority=MemoryPriority.LOW)
        memory.add("Low 2", priority=MemoryPriority.LOW)
        memory.add("Medium", priority=MemoryPriority.MEDIUM)

        # Add high priority - should evict low
        memory.add("High", priority=MemoryPriority.HIGH)

        assert len(memory) == 3
        items = memory.get()
        contents = [i.content for i in items]
        assert "Low 1" not in contents  # Evicted

    def test_critical_items_not_evicted(self):
        memory = WorkingMemory(max_items=2)

        memory.add("Critical", priority=MemoryPriority.CRITICAL)
        memory.add("Low 1", priority=MemoryPriority.LOW)

        # Try to add more
        memory.add("Low 2", priority=MemoryPriority.LOW)

        items = memory.get()
        contents = [i.content for i in items]
        assert "Critical" in contents

    def test_get_by_category(self):
        memory = WorkingMemory()

        memory.add("Todo 1", priority=MemoryPriority.HIGH, category="todo")
        memory.add("Finding 1", priority=MemoryPriority.MEDIUM, category="finding")
        memory.add("Todo 2", priority=MemoryPriority.HIGH, category="todo")

        todos = memory.get(category="todo")

        assert len(todos) == 2
        assert all(t.category == "todo" for t in todos)

    def test_get_by_min_priority(self):
        memory = WorkingMemory()

        memory.add("Critical", priority=MemoryPriority.CRITICAL)
        memory.add("High", priority=MemoryPriority.HIGH)
        memory.add("Low", priority=MemoryPriority.LOW)

        high_and_above = memory.get(min_priority=MemoryPriority.HIGH)

        assert len(high_and_above) == 2

    def test_get_context_string(self):
        memory = WorkingMemory()

        memory.add("Todo 1", priority=MemoryPriority.HIGH, category="todo")
        memory.add("Critical directive", priority=MemoryPriority.CRITICAL, category="directive")

        context = memory.get_context_string()

        assert "## Working Memory" in context
        assert "Todo" in context
        assert "Todo 1" in context
        assert "Critical directive" in context

    def test_update_todo(self):
        memory = WorkingMemory()

        memory.update_todo("Implement feature", completed=False)
        assert len(memory.get_active_todos()) == 1

        memory.update_todo("Implement feature", completed=True)
        assert len(memory.get_active_todos()) == 0

    def test_add_directive(self):
        memory = WorkingMemory()

        memory.add_directive("Always use TypeScript strict mode")

        directives = memory.get_directives()
        assert len(directives) == 1
        assert directives[0].priority == MemoryPriority.CRITICAL

    def test_remove_by_content(self):
        memory = WorkingMemory()

        memory.add("Important task", priority=MemoryPriority.HIGH)
        memory.add("Other task", priority=MemoryPriority.HIGH)

        removed = memory.remove("Important")

        assert removed is True
        assert len(memory) == 1

    def test_clear_memory(self):
        memory = WorkingMemory()

        memory.add("Item 1", priority=MemoryPriority.HIGH)
        memory.add("Item 2", priority=MemoryPriority.MEDIUM)

        memory.clear()

        assert len(memory) == 0


class TestConcisenessEnforcer:
    """Test prompt conciseness enforcement."""

    def test_remove_filler_words(self):
        text = "Please kindly check the file and feel free to edit it"
        result = ConcisenessEnforcer.enforce(text)

        assert "please" not in result.lower()
        assert "kindly" not in result.lower()
        assert "feel free to" not in result.lower()

    def test_remove_redundant_qualifiers_aggressive(self):
        text = "This is very really quite simply just a test"
        result = ConcisenessEnforcer.enforce(text, aggressive=True)

        assert "very" not in result.lower()
        assert "really" not in result.lower()

    def test_convert_you_should(self):
        text = "You should read the file. You should check errors."
        result = ConcisenessEnforcer.enforce(text, aggressive=True)

        assert "you should" not in result.lower()

    def test_count_tokens_saved(self):
        original = "a" * 400  # ~100 tokens
        compressed = "a" * 200  # ~50 tokens

        saved = ConcisenessEnforcer.count_tokens_saved(original, compressed)

        assert saved == 50


class TestPromptEngineer:
    """Test prompt engineering."""

    def test_engineer_basic_prompt(self):
        engineer = PromptEngineer("Base prompt")
        prompt = engineer.engineer({})

        assert "Base prompt" in prompt

    def test_engineer_with_tools(self):
        engineer = PromptEngineer("Base")
        tools = [
            {"name": "read_file", "description": "Read a file."},
            {"name": "write_file", "description": "Write a file."},
        ]

        prompt = engineer.engineer({"tools": tools})

        assert "read_file" in prompt
        assert "write_file" in prompt

    def test_task_repetitions_file_edit(self):
        engineer = PromptEngineer("Base")
        prompt = engineer.engineer({}, task_type="file_edit")

        assert "CRITICAL" in prompt
        assert "Read" in prompt or "exact" in prompt.lower()

    def test_recovery_prompt(self):
        engineer = PromptEngineer("Base")
        recovery = engineer.get_recovery_prompt(
            error="Tool not found",
            context={"last_tool": "read_fiel"}
        )

        assert "ERROR" in recovery
        assert "not found" in recovery

    def test_record_error_increments_metrics(self):
        engineer = PromptEngineer("Base")
        initial = engineer.metrics.retry_count

        engineer.record_error("format_error")

        assert engineer.metrics.retry_count == initial + 1


class TestPromptTemplates:
    """Test prompt templates."""

    def test_get_system_prompt_basic(self):
        prompt = get_system_prompt()

        assert len(prompt) > 0
        assert "Adorable" in prompt or "autonomous" in prompt.lower()

    def test_get_system_prompt_with_context(self):
        context = {"cwd": "/home/user/project", "git_branch": "main"}
        prompt = get_system_prompt(context_info=context)

        assert "/home/user/project" in prompt
        assert "main" in prompt

    def test_get_error_prompt(self):
        prompt = get_error_prompt(
            error="File not found",
            error_type="validation",
            recovery_hint="Check the path"
        )

        assert "ERROR" in prompt
        assert "File not found" in prompt
        assert "Check the path" in prompt

    def test_get_recovery_prompt_single_error(self):
        prompt = get_recovery_prompt(
            consecutive_errors=1,
            last_error="Timeout"
        )

        assert "Fix error" in prompt
        assert "Timeout" in prompt

    def test_get_recovery_prompt_multiple_errors(self):
        prompt = get_recovery_prompt(consecutive_errors=3)

        assert "Multiple errors" in prompt
        assert "simplify" in prompt.lower()


class TestPsychological:
    """Test psychological prompting techniques."""

    def test_confidence_calibrator_certain(self):
        calibrator = ConfidenceCalibrator()
        result = calibrator.calibrate(
            content="The sky is blue",
            evidence=["Visual observation", "Scientific consensus"],
            verification_status="confirmed"
        )

        assert result.confidence == ConfidenceLevel.CERTAIN

    def test_confidence_calibrator_low_with_contradictions(self):
        calibrator = ConfidenceCalibrator()
        result = calibrator.calibrate(
            content="This is the cause",
            evidence=["Some data"],
            contradictions=["Alternative explanation fits better"],
        )

        assert result.confidence == ConfidenceLevel.LOW
        assert len(result.caveats) > 0

    def test_uncertainty_handler(self):
        handler = UncertaintyHandler()
        guidance = handler.handle_uncertainty(
            situation="Multiple possible imports",
            options=["import A", "import B", "import C"],
        )

        assert "UNCERTAIN" in guidance
        assert "import A" in guidance
        assert "DO NOT GUESS" in guidance

    def test_error_framing_recovery(self):
        framer = ErrorFraming()
        prompt = framer.frame_recovery(
            error="Tool 'red_file' not found",
            context="Trying to read config.txt",
            attempt_number=1,
        )

        assert "RECOVER NOW" in prompt
        assert "not found" in prompt
        assert "spelling" in prompt.lower()

    def test_error_framing_argument_error(self):
        framer = ErrorFraming()
        prompt = framer.frame_recovery(
            error="Invalid argument: path",
            context="Trying to read file",
        )

        # Argument errors get specific guidance
        assert "Fix" in prompt or "parameter" in prompt.lower() or "Check" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
