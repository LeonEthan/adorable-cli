"""Tests for file edit safety system."""

import tempfile
from pathlib import Path

import pytest

from adorable_cli.tools.file_safety import (
    EditOperation,
    EditResult,
    EditTool,
    EditValidator,
    FileCache,
    FileState,
    MultiEdit,
    MultiEditResult,
    MultiEditTool,
    ValidationResult,
    WriteTool,
    create_edit_tools,
)


class TestFileState:
    """Test FileState."""

    def test_from_path(self, tmp_path):
        """Create FileState from existing file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        state = FileState.from_path(file_path)
        assert state is not None
        assert state.content == "Hello World"
        assert state.path == file_path
        assert len(state.content_hash) == 16

    def test_from_nonexistent_path(self, tmp_path):
        """Handle non-existent file."""
        state = FileState.from_path(tmp_path / "nonexistent.txt")
        assert state is None

    def test_is_stale(self, tmp_path):
        """Detect external changes."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Original")

        state = FileState.from_path(file_path)
        assert not state.is_stale()

        # Modify file
        file_path.write_text("Modified")
        assert state.is_stale()

    def test_has_changed(self, tmp_path):
        """Check content changes."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Original")

        state = FileState.from_path(file_path)
        assert not state.has_changed("Original")
        assert state.has_changed("Different")


class TestFileCache:
    """Test FileCache."""

    def test_read_and_cache(self, tmp_path):
        """Read and cache a file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Content")

        cache = FileCache()
        state = cache.read_and_cache(file_path)

        assert state.content == "Content"
        assert cache.is_cached(file_path)
        assert cache.get_cached(file_path) == state

    def test_invalidate(self, tmp_path):
        """Invalidate cached state."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Content")

        cache = FileCache()
        cache.read_and_cache(file_path)
        assert cache.is_cached(file_path)

        cache.invalidate(file_path)
        assert not cache.is_cached(file_path)

    def test_update_cache(self, tmp_path):
        """Update cache after writing."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Original")

        cache = FileCache()
        cache.read_and_cache(file_path)

        cache.update_cache(file_path, "New Content")
        cached = cache.get_cached(file_path)
        assert cached.content == "New Content"


class TestEditValidator:
    """Test EditValidator."""

    def test_validate_success(self, tmp_path):
        """Validate a valid edit."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        cache = FileCache()
        cache.read_and_cache(file_path)

        validator = EditValidator(cache)
        operation = EditOperation("Hello", "Hi")
        result = validator.validate(file_path, operation)

        assert result.is_valid
        assert result.can_proceed
        assert result.old_text_occurrences == 1

    def test_validate_not_read(self, tmp_path):
        """Fail if file not read first."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        cache = FileCache()
        validator = EditValidator(cache)
        operation = EditOperation("Hello", "Hi")
        result = validator.validate(file_path, operation)

        assert not result.is_valid
        assert "must be read" in result.error_message

    def test_validate_stale(self, tmp_path):
        """Fail if file changed externally."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        cache = FileCache()
        cache.read_and_cache(file_path)

        # Modify file externally
        file_path.write_text("Modified Content")

        validator = EditValidator(cache)
        operation = EditOperation("Hello", "Hi")
        result = validator.validate(file_path, operation)

        assert not result.is_valid
        assert "modified externally" in result.error_message

    def test_validate_text_not_found(self, tmp_path):
        """Fail if old text not found."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        cache = FileCache()
        cache.read_and_cache(file_path)

        validator = EditValidator(cache)
        operation = EditOperation("Not Found", "Hi")
        result = validator.validate(file_path, operation)

        assert not result.is_valid
        assert "not found" in result.error_message

    def test_validate_wrong_replacements(self, tmp_path):
        """Fail if expected replacements don't match."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello Hello Hello")

        cache = FileCache()
        cache.read_and_cache(file_path)

        validator = EditValidator(cache)
        operation = EditOperation("Hello", "Hi", expected_replacements=1)
        result = validator.validate(file_path, operation)

        assert not result.is_valid
        assert "Expected 1 occurrence" in result.error_message
        assert result.old_text_occurrences == 3


class TestEditTool:
    """Test EditTool."""

    def test_read_file(self, tmp_path):
        """Read and cache file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Content")

        tool = EditTool()
        content = tool.read_file(file_path)

        assert content == "Content"
        assert tool.file_cache.is_cached(file_path)

    def test_edit_file_success(self, tmp_path):
        """Successful file edit."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        tool = EditTool()
        tool.read_file(file_path)

        result = tool.edit_file(file_path, "Hello", "Hi")

        assert result.success
        assert result.replacements_made == 1
        assert file_path.read_text() == "Hi World"

    def test_edit_file_not_read(self, tmp_path):
        """Fail if file not read first."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        tool = EditTool()
        # Don't read first

        result = tool.edit_file(file_path, "Hello", "Hi")

        assert not result.success
        assert "must be read" in result.error_message
        assert file_path.read_text() == "Hello World"  # Unchanged

    def test_edit_file_wrong_replacements(self, tmp_path):
        """Fail with wrong expected_replacements."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello Hello Hello")

        tool = EditTool()
        tool.read_file(file_path)

        result = tool.edit_file(file_path, "Hello", "Hi", expected_replacements=1)

        assert not result.success
        assert "Expected 1 occurrence" in result.error_message

    def test_edit_file_dry_run(self, tmp_path):
        """Dry run doesn't modify file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        tool = EditTool()
        tool.read_file(file_path)

        result = tool.edit_file(file_path, "Hello", "Hi", dry_run=True)

        assert result.success
        assert file_path.read_text() == "Hello World"  # Unchanged

    def test_edit_file_multiple_replacements(self, tmp_path):
        """Edit with multiple replacements."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello Hello Hello")

        tool = EditTool()
        tool.read_file(file_path)

        result = tool.edit_file(file_path, "Hello", "Hi", expected_replacements=3)

        assert result.success
        assert result.replacements_made == 3
        assert file_path.read_text() == "Hi Hi Hi"


class TestMultiEditTool:
    """Test MultiEditTool."""

    def test_single_edit(self, tmp_path):
        """Apply single edit."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        tool = MultiEditTool()
        tool.add_read_file(file_path)

        edits = [MultiEdit(file_path, "Hello", "Hi")]
        result = tool.edit_files(edits)

        assert result.success
        assert len(result.edit_results) == 1
        assert file_path.read_text() == "Hi World"

    def test_multiple_edits_different_files(self, tmp_path):
        """Edit multiple files."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Hello from file1")
        file2.write_text("Hello from file2")

        tool = MultiEditTool()
        tool.add_read_file(file1)
        tool.add_read_file(file2)

        edits = [
            MultiEdit(file1, "Hello", "Hi"),
            MultiEdit(file2, "Hello", "Hi"),
        ]
        result = tool.edit_files(edits)

        assert result.success
        assert file1.read_text() == "Hi from file1"
        assert file2.read_text() == "Hi from file2"

    def test_multiple_edits_same_file(self, tmp_path):
        """Edit same file multiple times."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World Foo Bar")

        tool = MultiEditTool()
        tool.add_read_file(file_path)

        edits = [
            MultiEdit(file_path, "Hello", "Hi"),
            MultiEdit(file_path, "Foo", "Baz"),
        ]
        result = tool.edit_files(edits)

        assert result.success
        assert file_path.read_text() == "Hi World Baz Bar"

    def test_validation_failure_all_rejected(self, tmp_path):
        """If any edit invalid, all rejected."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        tool = MultiEditTool()
        tool.add_read_file(file_path)

        edits = [
            MultiEdit(file_path, "Hello", "Hi"),  # Valid
            MultiEdit(file_path, "NotFound", "X"),  # Invalid
        ]
        result = tool.edit_files(edits)

        assert not result.success
        assert "Validation failed" in result.error_message
        assert file_path.read_text() == "Hello World"  # Unchanged

    def test_conflict_detection(self, tmp_path):
        """Detect overlapping edits."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World Foo Bar")

        tool = MultiEditTool()
        tool.add_read_file(file_path)

        # These edits overlap in "Hello World Foo"
        edits = [
            MultiEdit(file_path, "Hello World", "Hi"),
            MultiEdit(file_path, "World Foo", "Universe"),
        ]
        result = tool.edit_files(edits)

        assert not result.success
        assert "Conflicts detected" in result.error_message
        assert "overlap" in result.error_message

    def test_dry_run(self, tmp_path):
        """Dry run validates but doesn't apply."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello World")

        tool = MultiEditTool()
        tool.add_read_file(file_path)

        edits = [MultiEdit(file_path, "Hello", "Hi")]
        result = tool.edit_files(edits, dry_run=True)

        assert result.success
        assert file_path.read_text() == "Hello World"  # Unchanged

    def test_empty_edits(self):
        """Handle empty edit list."""
        tool = MultiEditTool()
        result = tool.edit_files([])

        assert result.success
        assert len(result.edit_results) == 0


class TestWriteTool:
    """Test WriteTool."""

    def test_write_new_file(self, tmp_path):
        """Write to new file."""
        file_path = tmp_path / "new.txt"

        tool = WriteTool()
        result = tool.write_file(file_path, "New Content")

        assert result.success
        assert file_path.read_text() == "New Content"

    def test_write_creates_directories(self, tmp_path):
        """Create parent directories."""
        file_path = tmp_path / "subdir" / "nested" / "file.txt"

        tool = WriteTool()
        result = tool.write_file(file_path, "Content")

        assert result.success
        assert file_path.exists()
        assert file_path.read_text() == "Content"

    def test_overwrite_existing_requires_read(self, tmp_path):
        """Overwrite existing requires read first."""
        file_path = tmp_path / "existing.txt"
        file_path.write_text("Original")

        tool = WriteTool()
        result = tool.write_file(file_path, "New Content")

        assert not result.success
        assert "must be read" in result.error_message
        assert file_path.read_text() == "Original"

    def test_overwrite_after_read(self, tmp_path):
        """Overwrite after reading."""
        file_path = tmp_path / "existing.txt"
        file_path.write_text("Original")

        tool = WriteTool()
        tool.read_file(file_path)

        result = tool.write_file(file_path, "New Content")

        assert result.success
        assert file_path.read_text() == "New Content"

    def test_allow_overwrite_flag(self, tmp_path):
        """allow_overwrite bypasses read requirement."""
        file_path = tmp_path / "existing.txt"
        file_path.write_text("Original")

        tool = WriteTool()
        # Don't read
        result = tool.write_file(file_path, "New Content", allow_overwrite=True)

        assert result.success
        assert file_path.read_text() == "New Content"


class TestCreateEditTools:
    """Test create_edit_tools factory."""

    def test_creates_all_tools(self):
        """Factory creates all tools."""
        tools = create_edit_tools()

        assert "file_cache" in tools
        assert "read_file" in tools
        assert "edit_file" in tools
        assert "write_file" in tools
        assert "multi_edit" in tools
        assert "add_read_file" in tools

    def test_shared_cache(self, tmp_path):
        """All tools share the same cache."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Content")

        tools = create_edit_tools()

        # Read with one tool
        tools["read_file"](file_path)

        # Cache should be shared
        assert tools["file_cache"].is_cached(file_path)

        # Edit should work with shared cache
        result = tools["edit_file"](file_path, "Content", "New")
        assert result.success


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_file(self, tmp_path):
        """Handle empty file."""
        file_path = tmp_path / "empty.txt"
        file_path.write_text("")

        tool = EditTool()
        tool.read_file(file_path)

        result = tool.edit_file(file_path, "anything", "X")
        assert not result.success  # Can't replace what's not there

    def test_unicode_content(self, tmp_path):
        """Handle unicode content."""
        file_path = tmp_path / "unicode.txt"
        file_path.write_text("Hello 🎉 你好")

        tool = EditTool()
        tool.read_file(file_path)

        result = tool.edit_file(file_path, "🎉", "✨")

        assert result.success
        assert "✨" in file_path.read_text()

    def test_multiline_edit(self, tmp_path):
        """Edit multiple lines."""
        file_path = tmp_path / "multiline.txt"
        file_path.write_text("line1\nline2\nline3")

        tool = EditTool()
        tool.read_file(file_path)

        result = tool.edit_file(file_path, "line1\nline2", "new1\nnew2")

        assert result.success
        assert file_path.read_text() == "new1\nnew2\nline3"

    def test_special_characters(self, tmp_path):
        """Handle special regex characters."""
        file_path = tmp_path / "special.txt"
        file_path.write_text("Price: $5.00 [SALE]")

        tool = EditTool()
        tool.read_file(file_path)

        result = tool.edit_file(file_path, "$5.00", "$3.00")

        assert result.success
        assert "$3.00" in file_path.read_text()
