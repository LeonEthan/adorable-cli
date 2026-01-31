"""Tests for the streaming JSON parser.

Tests cover:
1. Basic incremental parsing
2. Recovery strategies for common LLM JSON issues
3. Partial object extraction
4. Multiple concatenated JSON objects
5. Edge cases and error conditions
"""

import pytest

from adorable_cli.utils.streaming_json import (
    IncrementalJSONParser,
    JSONParseError,
    RecoveryStrategy,
    StreamingJSONParser,
    extract_complete_objects,
    parse_partial_json,
)


class TestStreamingJSONParser:
    """Test the core StreamingJSONParser class."""

    def test_empty_buffer(self):
        """Empty buffer should not parse."""
        parser = StreamingJSONParser()
        assert parser.try_parse() is None
        assert not parser.is_complete()

    def test_complete_object(self):
        """Parse a complete JSON object."""
        parser = StreamingJSONParser()
        parser.feed('{"key": "value"}')

        assert parser.is_complete()
        result = parser.try_parse()
        assert result == {"key": "value"}

    def test_incremental_feeding(self):
        """Feed JSON in chunks."""
        parser = StreamingJSONParser()

        # Feed in small chunks
        chunks = ['{"na', 'me": "', 'test", ', '"val', 'ue": 123}']
        for chunk in chunks:
            parser.feed(chunk)

        assert parser.is_complete()
        result = parser.try_parse()
        assert result == {"name": "test", "value": 123}

    def test_incomplete_object_detection(self):
        """Detect incomplete objects correctly."""
        parser = StreamingJSONParser()
        parser.feed('{"key": "value"')

        assert not parser.is_complete()
        assert parser.could_be_valid()
        assert parser.try_parse() is None

    def test_string_with_braces(self):
        """Handle braces inside strings."""
        parser = StreamingJSONParser()
        parser.feed('{"code": "function() { return 1; }"}')

        assert parser.is_complete()
        result = parser.try_parse()
        assert result == {"code": "function() { return 1; }"}

    def test_nested_objects(self):
        """Handle deeply nested objects."""
        parser = StreamingJSONParser()
        parser.feed('{"a": {"b": {"c": {"d": "deep"}}}}')

        assert parser.is_complete()
        result = parser.try_parse()
        assert result["a"]["b"]["c"]["d"] == "deep"

    def test_arrays(self):
        """Handle arrays."""
        parser = StreamingJSONParser()
        parser.feed('[1, 2, {"key": "value"}, ["nested"]]')

        assert parser.is_complete()
        result = parser.try_parse()
        assert result == [1, 2, {"key": "value"}, ["nested"]]

    def test_escape_sequences(self):
        """Handle escape sequences in strings."""
        parser = StreamingJSONParser()
        parser.feed('{"text": "line1\\nline2\\tescaped quote: \\\"test\\\""}')

        assert parser.is_complete()
        result = parser.try_parse()
        assert "\n" in result["text"]
        assert '\"test\"' in result["text"]

    def test_unicode(self):
        """Handle unicode characters."""
        parser = StreamingJSONParser()
        parser.feed('{"emoji": "🎉", "chinese": "你好"}')

        assert parser.is_complete()
        result = parser.try_parse()
        assert result["emoji"] == "🎉"
        assert result["chinese"] == "你好"


class TestRecoveryStrategies:
    """Test recovery strategies for malformed JSON."""

    def test_close_braces_recovery(self):
        """Recover from missing closing braces."""
        parser = StreamingJSONParser()
        parser.feed('{"a": {"b": "c"}')

        assert not parser.is_complete()

        result = parser.try_parse_recovery(RecoveryStrategy.CLOSE_BRACES)
        assert result == {"a": {"b": "c"}}

    def test_close_brackets_recovery(self):
        """Recover from missing closing brackets."""
        parser = StreamingJSONParser()
        parser.feed('[1, 2, [3, 4]')

        result = parser.try_parse_recovery(RecoveryStrategy.CLOSE_BRACKETS)
        assert result == [1, 2, [3, 4]]

    def test_trailing_comma_recovery(self):
        """Recover from trailing commas."""
        parser = StreamingJSONParser()
        parser.feed('{"a": 1, "b": 2,}')

        result = parser.try_parse_recovery(RecoveryStrategy.REMOVE_TRAILING_COMMA)
        assert result == {"a": 1, "b": 2}

    def test_trailing_comma_in_array(self):
        """Recover from trailing commas in arrays."""
        parser = StreamingJSONParser()
        parser.feed('[1, 2, 3,]')

        result = parser.try_parse_recovery(RecoveryStrategy.REMOVE_TRAILING_COMMA)
        assert result == [1, 2, 3]

    def test_truncate_string_recovery(self):
        """Recover by truncating unterminated string."""
        parser = StreamingJSONParser()
        parser.feed('{"a": "incomplete string')

        result = parser.try_parse_recovery(RecoveryStrategy.TRUNCATE_STRING)
        # Should return empty or minimal object
        assert isinstance(result, dict)

    def test_extract_first_strategy(self):
        """Extract first complete object from partial stream."""
        parser = StreamingJSONParser()
        # Multiple objects, first is complete
        parser.feed('{"complete": true}{"incomplete":')

        result = parser.try_parse_recovery(RecoveryStrategy.EXTRACT_FIRST)
        assert result == {"complete": True}

    def test_all_strategies(self):
        """Try all strategies in order."""
        parser = StreamingJSONParser()
        parser.feed('{"a": 1, "b": {"c": 2')  # Missing closing braces

        result = parser.try_parse_recovery(RecoveryStrategy.ALL)
        assert result == {"a": 1, "b": {"c": 2}}

    def test_recovery_failure(self):
        """Raise error when all strategies fail."""
        parser = StreamingJSONParser()
        parser.feed('not valid json at all {{{')

        with pytest.raises(JSONParseError) as exc_info:
            parser.try_parse_recovery()

        assert "Failed to parse JSON" in str(exc_info.value)


class TestPartialObjectExtraction:
    """Test extracting complete objects from streams."""

    def test_extract_single_object(self):
        """Extract a single complete object."""
        parser = StreamingJSONParser()
        parser.feed('{"tool": "read_file", "args": {"path": "/tmp/test"}}')

        objects = list(parser.extract_complete_objects())
        assert len(objects) == 1
        assert objects[0]["tool"] == "read_file"

    def test_extract_multiple_objects(self):
        """Extract multiple concatenated objects."""
        parser = StreamingJSONParser()
        parser.feed(
            '{"tool": "tool1"}{"tool": "tool2"}{"tool": "tool3"}'
        )

        objects = list(parser.extract_complete_objects())
        assert len(objects) == 3
        assert [obj["tool"] for obj in objects] == ["tool1", "tool2", "tool3"]

    def test_extract_with_partial_remainder(self):
        """Extract complete objects leaving partial data."""
        parser = StreamingJSONParser()
        parser.feed('{"tool": "complete"}{"tool": "incom')

        objects = list(parser.extract_complete_objects())
        assert len(objects) == 1
        assert objects[0]["tool"] == "complete"

        # Remainder should still be in buffer
        assert "incom" in parser.buffer

    def test_get_partial_object(self):
        """Get partial object from incomplete JSON."""
        parser = StreamingJSONParser()
        parser.feed('{"name": "test", "value": 123, "nested": {"a": 1')

        partial = parser.get_partial_object()
        assert partial is not None
        assert partial.get("name") == "test"
        assert partial.get("value") == 123


class TestIncrementalJSONParser:
    """Test the higher-level IncrementalJSONParser."""

    def test_track_multiple_tools(self):
        """Track multiple concurrent tool calls."""
        parser = IncrementalJSONParser()

        parser.start_tool("tool-1")
        parser.start_tool("tool-2")

        parser.feed("tool-1", '{"path": ')
        parser.feed("tool-1", '"/tmp/file"}')

        parser.feed("tool-2", '{"command": "ls"}')

        assert parser.is_complete("tool-1")
        assert parser.is_complete("tool-2")

        result1 = parser.try_parse("tool-1")
        result2 = parser.try_parse("tool-2")

        assert result1 == {"path": "/tmp/file"}
        assert result2 == {"command": "ls"}

    def test_get_partial_during_streaming(self):
        """Get partial results during streaming."""
        parser = IncrementalJSONParser()
        parser.start_tool("tool-1")

        parser.feed("tool-1", '{"path": "')
        partial = parser.get_partial("tool-1")
        assert partial is not None

        parser.feed("tool-1", '/tmp/file", "recursive": true}')
        assert parser.is_complete("tool-1")

    def test_finalize_with_recovery(self):
        """Finalize uses recovery if needed."""
        parser = IncrementalJSONParser()
        parser.start_tool("tool-1")

        parser.feed("tool-1", '{"path": "/tmp", "recursive": true')
        # Missing closing brace

        result = parser.finalize("tool-1")
        assert result == {"path": "/tmp", "recursive": True}


class TestConvenienceFunctions:
    """Test the convenience functions."""

    def test_parse_partial_json(self):
        """Test one-shot partial JSON parsing."""
        result = parse_partial_json('{"a": 1, "b": 2')
        assert result == {"a": 1, "b": 2}

    def test_parse_partial_json_failure(self):
        """Test that parse_partial_json raises on failure."""
        with pytest.raises(JSONParseError):
            parse_partial_json("not json {{{")

    def test_extract_complete_objects_function(self):
        """Test the extract_complete_objects function."""
        text = '{"id": 1}{"id": 2}{"id": 3}'
        objects = extract_complete_objects(text)

        assert len(objects) == 3
        assert [obj["id"] for obj in objects] == [1, 2, 3]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_whitespace_only(self):
        """Handle whitespace-only buffer."""
        parser = StreamingJSONParser()
        parser.feed("   \n\t  ")

        assert not parser.is_complete()
        assert parser.could_be_valid()  # Could become valid

    def test_empty_object(self):
        """Handle empty object."""
        parser = StreamingJSONParser()
        parser.feed("{}")

        assert parser.is_complete()
        assert parser.try_parse() == {}

    def test_empty_array(self):
        """Handle empty array."""
        parser = StreamingJSONParser()
        parser.feed("[]")

        assert parser.is_complete()
        assert parser.try_parse() == []

    def test_just_whitespace_in_string(self):
        """Handle whitespace inside strings."""
        parser = StreamingJSONParser()
        parser.feed('{"text": "   \n\t  "}')

        assert parser.is_complete()
        result = parser.try_parse()
        assert result["text"] == "   \n\t  "

    def test_large_numbers(self):
        """Handle large numbers."""
        parser = StreamingJSONParser()
        parser.feed('{"big": 12345678901234567890, "decimal": 3.14159265359}')

        result = parser.try_parse()
        assert result["big"] == 12345678901234567890
        assert abs(result["decimal"] - 3.14159265359) < 1e-10

    def test_null_true_false(self):
        """Handle JSON literals."""
        parser = StreamingJSONParser()
        parser.feed('{"null": null, "true": true, "false": false}')

        result = parser.try_parse()
        assert result["null"] is None
        assert result["true"] is True
        assert result["false"] is False

    def test_deep_nesting(self):
        """Handle deeply nested structures."""
        parser = StreamingJSONParser()
        deep = '{"a":' * 50 + '"deep"' + "}" * 50
        parser.feed(deep)

        assert parser.is_complete()
        result = parser.try_parse()
        # Navigate to the deepest value
        current = result
        for _ in range(49):
            current = current["a"]
        assert current == "deep"

    def test_reset(self):
        """Test parser reset."""
        parser = StreamingJSONParser()
        parser.feed('{"key": "value"}')
        assert parser.is_complete()

        parser.reset()
        assert not parser.is_complete()
        assert parser.buffer == ""
        assert parser.try_parse() is None

    def test_state_summary(self):
        """Test state summary for debugging."""
        parser = StreamingJSONParser()
        parser.feed('{"a": {"b":')

        summary = parser.get_state_summary()
        assert summary["buffer_length"] == 10
        assert not summary["is_complete"]
        assert summary["brace_depth"] == 2


class TestLLMRealWorldScenarios:
    """Test scenarios based on real LLM output patterns."""

    def test_tool_call_pattern(self):
        """Parse typical tool call from LLM."""
        parser = StreamingJSONParser()

        # Typical streaming pattern
        chunks = [
            '{"tool": "read_file", ',
            '"arguments": {',
            '"file_path": "/tmp/test.py"',
            '}}',
        ]

        for chunk in chunks:
            parser.feed(chunk)

        result = parser.try_parse()
        assert result["tool"] == "read_file"
        assert result["arguments"]["file_path"] == "/tmp/test.py"

    def test_truncated_tool_call(self):
        """Handle truncated tool call (common in LLM streaming)."""
        parser = StreamingJSONParser()
        parser.feed(
            '{"tool": "run_shell_command", "arguments": {"command": "ls -la"'
        )

        # Not complete but could be valid
        assert not parser.is_complete()
        assert parser.could_be_valid()

        # Recovery should work
        result = parser.try_parse_recovery()
        assert result["tool"] == "run_shell_command"

    def test_multiple_tools_in_stream(self):
        """Handle multiple tool calls in one stream."""
        # This happens when LLM batches tool calls
        text = (
            '{"tool": "tool1", "args": {}}'
            '{"tool": "tool2", "args": {}}'
        )

        objects = extract_complete_objects(text)
        assert len(objects) == 2

    def test_complex_nested_tool_args(self):
        """Handle complex nested arguments."""
        parser = StreamingJSONParser()
        parser.feed(
            '{"tool": "edit_file", "arguments": {"'
            'file_path": "/src/main.py", '
            '"edits": [{"old_text": "def foo():", '
            '"new_text": "def foo(bar):"}]}}'
        )

        result = parser.try_parse()
        assert result["tool"] == "edit_file"
        assert len(result["arguments"]["edits"]) == 1

    def test_string_with_special_chars(self):
        """Handle strings with code snippets."""
        parser = StreamingJSONParser()
        code = '''{"code": "function test() {\\n  return \\"hello\\";\\n}"}'''
        parser.feed(code)

        result = parser.try_parse()
        assert "function test()" in result["code"]
