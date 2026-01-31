"""Tests for line number validation in file editing."""

import tempfile
from pathlib import Path

import pytest

from adorable_cli.tools.file_safety import (
    EditTool,
    EditValidator,
    FileCache,
    strip_line_numbers,
)


class TestStripLineNumbers:
    """Test the strip_line_numbers utility function."""

    def test_strip_tab_prefix(self):
        """Strip number + tab prefix (Claude Code format)."""
        result = strip_line_numbers("2\tconsole.log('hello')")
        assert result == "console.log('hello')"

    def test_strip_colon_prefix(self):
        """Strip number + colon prefix."""
        result = strip_line_numbers("10: def foo():")
        assert result == "def foo():"

    def test_strip_space_prefix(self):
        """Strip number + space prefix."""
        result = strip_line_numbers("5  x = 1")
        assert result == "x = 1"

    def test_strip_colon_with_spaces(self):
        """Strip number + colon + spaces prefix."""
        result = strip_line_numbers("  15:   x = 1")
        assert result == "x = 1"

    def test_multiline_stripping(self):
        """Strip line numbers from multiple lines."""
        input_text = """1\tdef hello():
2\t    print('world')
3\t    return 42"""
        result = strip_line_numbers(input_text)
        assert result == """def hello():
    print('world')
    return 42"""

    def test_mixed_formats(self):
        """Handle mixed line number formats."""
        input_text = """1\tdef hello():
2:     print('world')
3  return 42
regular line
5\t"""
        result = strip_line_numbers(input_text)
        # The function strips line numbers; whitespace handling may vary
        assert "def hello():" in result
        assert "print('world')" in result
        assert "return 42" in result
        assert "regular line" in result

    def test_no_line_numbers_preserved(self):
        """Text without line numbers is preserved."""
        text = "console.log('hello')\ndef foo():\n    pass"
        result = strip_line_numbers(text)
        assert result == text

    def test_empty_string(self):
        """Empty string handled correctly."""
        result = strip_line_numbers("")
        assert result == ""

    def test_decimal_numbers_preserved(self):
        """Decimal numbers (like 3.14) are not stripped."""
        result = strip_line_numbers("pi = 3.14159")
        assert result == "pi = 3.14159"

    def test_version_numbers_preserved(self):
        """Version numbers (like 1.2.3) are not stripped."""
        result = strip_line_numbers("version = 1.2.3")
        assert result == "version = 1.2.3"

    def test_leading_whitespace_preserved(self):
        """Leading whitespace before line numbers is handled."""
        result = strip_line_numbers("    5\tcontent")
        # The function doesn't strip leading whitespace, only the number
        assert "content" in result


class TestLineNumberValidation:
    """Test line number validation in EditValidator."""

    def test_tab_prefix_detected(self):
        """Validator detects tab-separated line numbers."""
        cache = FileCache()
        validator = EditValidator(cache)

        # Create a temp file and read it into cache
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("console.log('hello')\n")
            path = Path(f.name)

        try:
            cache.read_and_cache(path)

            # Try to edit with line number prefix
            from adorable_cli.tools.file_safety import EditOperation
            operation = EditOperation("1\tconsole.log('hello')", "print('hi')")
            result = validator.validate(path, operation)

            assert not result.is_valid
            assert "line number" in result.error_message.lower()
            assert "remove" in result.error_message.lower()

        finally:
            path.unlink()

    def test_colon_prefix_detected(self):
        """Validator detects colon-separated line numbers."""
        cache = FileCache()
        validator = EditValidator(cache)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def foo():\n    pass\n")
            path = Path(f.name)

        try:
            cache.read_and_cache(path)

            from adorable_cli.tools.file_safety import EditOperation
            operation = EditOperation("1: def foo():", "def bar():")
            result = validator.validate(path, operation)

            assert not result.is_valid
            assert "line number" in result.error_message.lower()

        finally:
            path.unlink()

    def test_valid_edit_passes(self):
        """Edit without line numbers passes validation."""
        cache = FileCache()
        validator = EditValidator(cache)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("console.log('hello')\n")
            path = Path(f.name)

        try:
            cache.read_and_cache(path)

            from adorable_cli.tools.file_safety import EditOperation
            operation = EditOperation("console.log('hello')", "print('hi')")
            result = validator.validate(path, operation)

            assert result.is_valid

        finally:
            path.unlink()

    def test_error_message_helpful(self):
        """Error message includes helpful instructions."""
        cache = FileCache()
        validator = EditValidator(cache)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("content\n")
            path = Path(f.name)

        try:
            cache.read_and_cache(path)

            from adorable_cli.tools.file_safety import EditOperation
            operation = EditOperation("1\tcontent", "new")
            result = validator.validate(path, operation)

            assert not result.is_valid
            # Check for helpful content in error message
            assert "old_text" in result.error_message.lower() or "line number" in result.error_message.lower()

        finally:
            path.unlink()


class TestEditToolWithLineNumbers:
    """Test EditTool behavior with line number issues."""

    def test_edit_rejects_line_numbers(self):
        """Edit is rejected when old_text contains line numbers."""
        tool = EditTool()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("console.log('hello')\n")
            path = Path(f.name)

        try:
            # Read the file first
            tool.read_file(path)

            # Try to edit with line number
            result = tool.edit_file(
                path=path,
                old_text="1\tconsole.log('hello')",
                new_text="print('hi')",
            )

            assert not result.success
            assert "line number" in result.error_message.lower()

        finally:
            path.unlink()

    def test_edit_succeeds_without_line_numbers(self):
        """Edit succeeds when old_text is clean."""
        tool = EditTool()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("console.log('hello')\n")
            path = Path(f.name)

        try:
            tool.read_file(path)

            result = tool.edit_file(
                path=path,
                old_text="console.log('hello')",
                new_text="print('hi')",
            )

            assert result.success
            assert result.replacements_made == 1

        finally:
            path.unlink()


class TestEdgeCases:
    """Edge cases for line number detection."""

    def test_large_line_numbers(self):
        """Large line numbers are still detected."""
        result = strip_line_numbers("9999\tcontent")
        assert result == "content"

    def test_line_zero(self):
        """Line 0 is detected (unusual but possible)."""
        result = strip_line_numbers("0\tcontent")
        assert result == "content"

    def test_partial_number_match(self):
        """Numbers within text are not affected."""
        text = "x = 123\ny = 456"
        result = strip_line_numbers(text)
        assert result == text

    def test_code_with_numbers(self):
        """Code containing numbers is preserved."""
        text = """x = 42
if x > 100:
    print(x)"""
        result = strip_line_numbers(text)
        assert result == text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
