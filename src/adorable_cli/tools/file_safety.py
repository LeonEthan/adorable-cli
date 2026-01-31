"""File editing safety system with read-before-edit enforcement.

Implements Claude Code's four-phase editing pipeline:
1. Validation - checks file state and edit parameters
2. Preparation - prepares the edit operation
3. Application - performs the string replacement
4. Verification - confirms the result

Also provides MultiEditTool for atomic batch operations with conflict detection.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from adorable_cli.utils.errors import FileSafetyError


@dataclass
class FileState:
    """Cached state of a file for read-before-edit enforcement.

    Tracks the state at read time to detect external changes.
    """

    path: Path
    content: str
    mtime_ns: int
    size_bytes: int
    content_hash: str
    read_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_path(cls, path: Path) -> Optional["FileState"]:
        """Create FileState by reading the file from disk."""
        try:
            stat = path.stat()
            content = path.read_text(encoding="utf-8")
            return cls(
                path=path,
                content=content,
                mtime_ns=stat.st_mtime_ns,
                size_bytes=stat.st_size,
                content_hash=hashlib.sha256(content.encode()).hexdigest()[:16],
            )
        except (IOError, OSError):
            return None

    def is_stale(self) -> bool:
        """Check if the file has been modified since read."""
        try:
            current_stat = self.path.stat()
            return current_stat.st_mtime_ns != self.mtime_ns
        except (IOError, OSError):
            return True

    def has_changed(self, expected_content: str) -> bool:
        """Check if file content differs from expected."""
        return self.content != expected_content

    def verify_content_hash(self, content: str) -> bool:
        """Verify content matches the stored hash."""
        current_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return current_hash == self.content_hash


@dataclass
class EditOperation:
    """A single edit operation.

    Uses exact string matching with zero ambiguity.
    """

    old_text: str
    new_text: str
    expected_replacements: int = 1

    def __post_init__(self):
        # Normalize line endings
        self.old_text = self.old_text.replace("\r\n", "\n")
        self.new_text = self.new_text.replace("\r\n", "\n")


@dataclass
class EditResult:
    """Result of an edit operation."""

    success: bool
    path: Path
    replacements_made: int
    original_content: str
    new_content: str
    error_message: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of edit validation."""

    is_valid: bool
    error_message: Optional[str] = None
    old_text_occurrences: int = 0
    can_proceed: bool = False


class FileCache:
    """Cache for file states to enforce read-before-edit."""

    def __init__(self):
        self._cache: dict[Path, FileState] = {}

    def read_and_cache(self, path: Path) -> FileState:
        """Read a file and cache its state."""
        path = path.resolve()
        state = FileState.from_path(path)
        if state is None:
            raise FileNotFoundError(f"File not found: {path}")
        self._cache[path] = state
        return state

    def get_cached(self, path: Path) -> Optional[FileState]:
        """Get cached file state if available."""
        return self._cache.get(path.resolve())

    def is_cached(self, path: Path) -> bool:
        """Check if a file is cached."""
        return path.resolve() in self._cache

    def invalidate(self, path: Path) -> None:
        """Invalidate cached state for a file."""
        self._cache.pop(path.resolve(), None)

    def update_cache(self, path: Path, content: str) -> None:
        """Update cache after writing (for subsequent edits)."""
        path = path.resolve()
        try:
            stat = path.stat()
            self._cache[path] = FileState(
                path=path,
                content=content,
                mtime_ns=stat.st_mtime_ns,
                size_bytes=len(content.encode()),
                content_hash=hashlib.sha256(content.encode()).hexdigest()[:16],
            )
        except (IOError, OSError):
            pass


class EditValidator:
    """Validates edit operations before application."""

    def __init__(self, file_cache: FileCache):
        self.file_cache = file_cache

    def validate(
        self,
        path: Path,
        operation: EditOperation,
        allow_create: bool = False,
    ) -> ValidationResult:
        """Validate an edit operation.

        Performs the following checks:
        1. File must have been read first (read-before-edit)
        2. File must not have changed externally
        3. Old text must exist in the file
        4. Expected replacements must match actual occurrences
        """
        path = path.resolve()

        # Phase 0: Check for line number prefixes in old_text
        line_number_check = self._check_line_number_prefix(operation.old_text)
        if line_number_check:
            return ValidationResult(
                is_valid=False,
                error_message=line_number_check,
            )

        # Phase 1: Check if file was read
        cached_state = self.file_cache.get_cached(path)
        if cached_state is None:
            if not allow_create or path.exists():
                return ValidationResult(
                    is_valid=False,
                    error_message=f"File {path} must be read with read_file before editing. "
                    "This ensures you have the current file content.",
                )
            # File doesn't exist and allow_create is True - will be created
            cached_state = None

        # Phase 2: Check for external changes
        if cached_state is not None and cached_state.is_stale():
            return ValidationResult(
                is_valid=False,
                error_message=f"File {path} has been modified externally since it was read. "
                "Re-read the file before editing.",
            )

        # Phase 3: Check if old text exists
        if cached_state is not None:
            content = cached_state.content
            occurrences = content.count(operation.old_text)

            if occurrences == 0:
                # Try to find similar text for helpful error
                suggestion = self._find_similar(content, operation.old_text)
                msg = f"The text to replace was not found in {path}."
                if suggestion:
                    msg += f"\nDid you mean:\n{suggestion}"
                return ValidationResult(
                    is_valid=False,
                    error_message=msg,
                    old_text_occurrences=0,
                )

            # Phase 4: Check expected replacements
            if occurrences != operation.expected_replacements:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Expected {operation.expected_replacements} occurrence(s) of the text "
                    f"but found {occurrences}. Use expected_replacements={occurrences} "
                    f"if this is correct, or check your old_text for accuracy.",
                    old_text_occurrences=occurrences,
                )

            return ValidationResult(
                is_valid=True,
                old_text_occurrences=occurrences,
                can_proceed=True,
            )

        # New file creation
        return ValidationResult(is_valid=True, can_proceed=True)

    def _find_similar(self, content: str, target: str, max_distance: int = 10) -> Optional[str]:
        """Find similar text in content for error suggestions."""
        # Simple similarity: look for lines containing similar words
        target_words = set(target.lower().split())
        best_match = None
        best_score = 0

        for line in content.split("\n"):
            line_words = set(line.lower().split())
            if target_words & line_words:
                score = len(target_words & line_words)
                if score > best_score:
                    best_score = score
                    best_match = line.strip()

        return best_match if best_score > 0 else None

    def _check_line_number_prefix(self, old_text: str) -> Optional[str]:
        r"""Check if old_text contains line number prefixes.

        Claude Code outputs line numbers in read_file (e.g., "2\tconsole.log(...)")
        but edit_file requires the actual text without line numbers. This detects
        common line number patterns and provides a helpful error message.

        Patterns detected:
        - ^\d+\t  (e.g., "2\tcontent")
        - ^\s*\d+:\s*  (e.g., "2: content" or "  10:  content")
        - ^\s*\d+\s+  (e.g., "2  content" or "  10 content")

        Returns:
            Error message if line number prefix detected, None otherwise
        """
        if not old_text:
            return None

        # Split into lines to check each line
        lines = old_text.split('\n')
        problematic_lines = []

        for i, line in enumerate(lines, 1):
            if not line.strip():
                continue

            # Pattern 1: Number followed by tab (Claude Code read_file format)
            if re.match(r'^\d+\t', line):
                problematic_lines.append((i, line[:50]))
                continue

            # Pattern 2: Number followed by colon and optional spaces
            if re.match(r'^\s*\d+:\s*', line):
                problematic_lines.append((i, line[:50]))
                continue

            # Pattern 3: Number followed by spaces (at start of line)
            if re.match(r'^\s*\d+\s+', line) and not re.match(r'^\s*\d+\.\d+', line):
                # Exclude decimal numbers like "3.14"
                problematic_lines.append((i, line[:50]))
                continue

        if problematic_lines:
            examples = "\n".join([
                f"  Line {ln}: '{text}...'" for ln, text in problematic_lines[:3]
            ])
            return (
                f"The old_text appears to contain line number prefixes.\n"
                f"Detected problematic lines:\n{examples}\n\n"
                f"The read_file tool adds line numbers for display, but edit_file "
                f"requires the actual file content WITHOUT line numbers.\n\n"
                f"Please remove:\n"
                f"  - The line number (e.g., '2', '10')\n"
                f"  - The tab character or space after it\n\n"
                f"For example, change:\n"
                f"  '2\\tconsole.log(\"hello\")'\n"
                f"To:\n"
                f"  'console.log(\"hello\")'"
            )

        return None


class EditTool:
    """Tool for safe file editing.

    Implements Claude Code's read-before-edit pattern with
    exact string matching and validation.
    """

    def __init__(self, file_cache: Optional[FileCache] = None):
        self.file_cache = file_cache or FileCache()
        self.validator = EditValidator(self.file_cache)

    def read_file(self, path: Path) -> str:
        """Read a file and cache its state.

        Must be called before editing a file.
        """
        state = self.file_cache.read_and_cache(path)
        return state.content

    def edit_file(
        self,
        path: Path,
        old_text: str,
        new_text: str,
        expected_replacements: int = 1,
        dry_run: bool = False,
    ) -> EditResult:
        """Edit a file with safety checks.

        Args:
            path: Path to the file
            old_text: Text to replace
            new_text: Replacement text
            expected_replacements: Expected number of occurrences (safety check)
            dry_run: If True, don't actually write changes

        Returns:
            EditResult with success status and details
        """
        path = path.resolve()

        # Phase 1: Validation
        operation = EditOperation(old_text, new_text, expected_replacements)
        validation = self.validator.validate(path, operation)

        if not validation.is_valid:
            return EditResult(
                success=False,
                path=path,
                replacements_made=0,
                original_content="",
                new_content="",
                error_message=validation.error_message,
            )

        # Get current content
        cached_state = self.file_cache.get_cached(path)
        if cached_state:
            original_content = cached_state.content
        else:
            # New file
            original_content = ""

        # Phase 2: Preparation
        new_content = original_content.replace(operation.old_text, operation.new_text)
        replacements_made = original_content.count(operation.old_text)

        if dry_run:
            return EditResult(
                success=True,
                path=path,
                replacements_made=replacements_made,
                original_content=original_content,
                new_content=new_content,
            )

        # Phase 3: Application
        try:
            path.write_text(new_content, encoding="utf-8")
        except (IOError, OSError) as e:
            return EditResult(
                success=False,
                path=path,
                replacements_made=0,
                original_content=original_content,
                new_content=new_content,
                error_message=f"Failed to write file: {e}",
            )

        # Phase 4: Verification
        try:
            written_content = path.read_text(encoding="utf-8")
            if written_content != new_content:
                return EditResult(
                    success=False,
                    path=path,
                    replacements_made=replacements_made,
                    original_content=original_content,
                    new_content=new_content,
                    error_message="Verification failed: written content doesn't match expected",
                )
        except (IOError, OSError) as e:
            return EditResult(
                success=False,
                path=path,
                replacements_made=replacements_made,
                original_content=original_content,
                new_content=new_content,
                error_message=f"Failed to verify write: {e}",
            )

        # Update cache for subsequent edits
        self.file_cache.update_cache(path, new_content)

        return EditResult(
            success=True,
            path=path,
            replacements_made=replacements_made,
            original_content=original_content,
            new_content=new_content,
        )


@dataclass
class MultiEdit:
    """A single edit in a MultiEdit batch."""

    path: Path
    old_text: str
    new_text: str
    expected_replacements: int = 1


@dataclass
class MultiEditResult:
    """Result of a MultiEdit operation."""

    success: bool
    edit_results: list[EditResult]
    rolled_back: bool
    error_message: Optional[str] = None


class MultiEditTool:
    """Tool for atomic batch file editing.

    Validates all edits before applying any.
    If any edit fails, none are applied.

    Also detects conflicts between edits (overlapping changes).
    """

    def __init__(self, file_cache: Optional[FileCache] = None):
        self.file_cache = file_cache or FileCache()
        self.edit_tool = EditTool(self.file_cache)

    def add_read_file(self, path: Path) -> str:
        """Read and cache a file for editing."""
        return self.edit_tool.read_file(path)

    def edit_files(
        self,
        edits: list[MultiEdit],
        dry_run: bool = False,
    ) -> MultiEditResult:
        """Apply multiple edits atomically.

        Args:
            edits: List of edits to apply
            dry_run: If True, validate but don't apply

        Returns:
            MultiEditResult with results for all edits
        """
        if not edits:
            return MultiEditResult(
                success=True,
                edit_results=[],
                rolled_back=False,
            )

        # Phase 1: Validate all edits
        validations: list[tuple[MultiEdit, ValidationResult]] = []
        for edit in edits:
            operation = EditOperation(
                edit.old_text,
                edit.new_text,
                edit.expected_replacements,
            )
            validation = self.edit_tool.validator.validate(edit.path, operation)
            validations.append((edit, validation))

        # Check for validation failures
        failures = [
            (edit, val) for edit, val in validations if not val.is_valid
        ]
        if failures:
            error_msgs = [
                f"{edit.path}: {val.error_message}"
                for edit, val in failures
            ]
            return MultiEditResult(
                success=False,
                edit_results=[],
                rolled_back=False,
                error_message="Validation failed for some edits:\n" + "\n".join(error_msgs),
            )

        # Phase 2: Check for conflicts
        conflicts = self._detect_conflicts(edits)
        if conflicts:
            return MultiEditResult(
                success=False,
                edit_results=[],
                rolled_back=False,
                error_message="Conflicts detected between edits:\n" + "\n".join(conflicts),
            )

        # Phase 3: Prepare all edits
        prepared_edits: list[tuple[MultiEdit, str, str]] = []  # edit, original, new
        current_contents: dict[Path, str] = {}
        for edit in edits:
            if edit.path in current_contents:
                original = current_contents[edit.path]
            else:
                cached = self.file_cache.get_cached(edit.path)
                original = cached.content if cached else ""

            new_content = original.replace(edit.old_text, edit.new_text)
            prepared_edits.append((edit, original, new_content))
            current_contents[edit.path] = new_content

        if dry_run:
            # Return dry-run results
            edit_results = [
                EditResult(
                    success=True,
                    path=edit.path,
                    replacements_made=original.count(edit.old_text),
                    original_content=original,
                    new_content=new_content,
                )
                for edit, original, new_content in prepared_edits
            ]
            return MultiEditResult(
                success=True,
                edit_results=edit_results,
                rolled_back=False,
            )

        # Phase 4: Apply all edits (with rollback on failure)
        applied: list[tuple[Path, str]] = []  # path, original_content
        edit_results: list[EditResult] = []

        try:
            for edit, original, new_content in prepared_edits:
                # Store original for potential rollback
                if edit.path not in [p for p, _ in applied]:
                    applied.append((edit.path, original))

                # Write the file
                edit.path.write_text(new_content, encoding="utf-8")

                # Update cache
                self.file_cache.update_cache(edit.path, new_content)

                edit_results.append(
                    EditResult(
                        success=True,
                        path=edit.path,
                        replacements_made=original.count(edit.old_text),
                        original_content=original,
                        new_content=new_content,
                    )
                )

        except (IOError, OSError) as e:
            # Rollback on failure
            for path, original_content in applied:
                try:
                    path.write_text(original_content, encoding="utf-8")
                except (IOError, OSError):
                    pass  # Best effort rollback

            return MultiEditResult(
                success=False,
                edit_results=edit_results,
                rolled_back=True,
                error_message=f"Failed during application: {e}. All changes rolled back.",
            )

        return MultiEditResult(
            success=True,
            edit_results=edit_results,
            rolled_back=False,
        )

    def _detect_conflicts(self, edits: list[MultiEdit]) -> list[str]:
        """Detect conflicts between edits.

        Conflicts include:
        - Two edits to the same file with overlapping text ranges
        - One edit's old_text contains another edit's old_text
        """
        conflicts: list[str] = []

        # Group edits by path
        by_path: dict[Path, list[MultiEdit]] = {}
        for edit in edits:
            if edit.path not in by_path:
                by_path[edit.path] = []
            by_path[edit.path].append(edit)

        # Check for conflicts within each path
        for path, path_edits in by_path.items():
            if len(path_edits) < 2:
                continue

            # Get current content
            cached = self.file_cache.get_cached(path)
            if not cached:
                continue

            content = cached.content

            # Find positions of each edit
            positions: list[tuple[MultiEdit, int, int]] = []  # edit, start, end
            for edit in path_edits:
                idx = content.find(edit.old_text)
                if idx >= 0:
                    positions.append((edit, idx, idx + len(edit.old_text)))

            # Check for overlaps
            for i, (edit1, start1, end1) in enumerate(positions):
                for edit2, start2, end2 in positions[i + 1 :]:
                    # Check if ranges overlap
                    if start1 < end2 and start2 < end1:
                        conflicts.append(
                            f"Edits overlap in {path}: "
                            f"'{edit1.old_text[:30]}...' and '{edit2.old_text[:30]}...'"
                        )

        return conflicts


class WriteTool:
    """Tool for writing new files or overwriting existing ones.

    Requires read-before-edit for existing files.
    """

    def __init__(self, file_cache: Optional[FileCache] = None):
        self.file_cache = file_cache or FileCache()

    def read_file(self, path: Path) -> str:
        """Read and cache a file."""
        return self.file_cache.read_and_cache(path).content

    def write_file(
        self,
        path: Path,
        content: str,
        allow_overwrite: bool = False,
    ) -> EditResult:
        """Write content to a file.

        Args:
            path: Path to write
            content: Content to write
            allow_overwrite: If False, requires file to be read first

        Returns:
            EditResult with operation details
        """
        path = path.resolve()
        path_exists = path.exists()

        # Check read-before-edit for existing files
        if path_exists and not allow_overwrite:
            if not self.file_cache.is_cached(path):
                return EditResult(
                    success=False,
                    path=path,
                    replacements_made=0,
                    original_content="",
                    new_content=content,
                    error_message=f"Existing file {path} must be read with read_file "
                    "before overwriting. This prevents accidental data loss.",
                )

            # Check if file changed
            cached = self.file_cache.get_cached(path)
            if cached and cached.is_stale():
                return EditResult(
                    success=False,
                    path=path,
                    replacements_made=0,
                    original_content="",
                    new_content=content,
                    error_message=f"File {path} has been modified externally. "
                    "Re-read before writing.",
                )

        original = ""
        if path_exists:
            try:
                original = path.read_text(encoding="utf-8")
            except (IOError, OSError):
                pass

        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

            # Update cache
            self.file_cache.update_cache(path, content)

            return EditResult(
                success=True,
                path=path,
                replacements_made=1 if path_exists else 0,
                original_content=original,
                new_content=content,
            )

        except (IOError, OSError) as e:
            return EditResult(
                success=False,
                path=path,
                replacements_made=0,
                original_content=original,
                new_content=content,
                error_message=f"Failed to write file: {e}",
            )


# Line number stripping utility


def strip_line_numbers(text: str) -> str:
    """Strip line number prefixes from text.

    This is useful when the LLM includes line numbers from read_file output
    in the old_text for edit_file. Removes common line number patterns:
    - "2\tcontent" -> "content"
    - "2: content" -> "content"
    - "  10  content" -> "content"

    Args:
        text: Text potentially containing line number prefixes

    Returns:
        Text with line number prefixes removed

    Example:
        >>> strip_line_numbers("2\tconsole.log('hello')")
        "console.log('hello')"
        >>> strip_line_numbers("10: def foo():\\n11:     pass")
        "def foo():\\n    pass"
    """
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        # Pattern 1: Number followed by tab
        if re.match(r'^\d+\t', line):
            cleaned_lines.append(re.sub(r'^\d+\t', '', line))
            continue

        # Pattern 2: Number followed by colon and optional spaces
        if re.match(r'^\s*\d+:\s*', line):
            cleaned_lines.append(re.sub(r'^\s*\d+:\s*', '', line))
            continue

        # Pattern 3: Number followed by spaces (but not decimal numbers)
        match = re.match(r'^(\s*)(\d+)(\s+)(.*)', line)
        if match and not re.match(r'^\d+\.\d+', line):
            # Check if this looks like a line number (reasonable range)
            num = int(match.group(2))
            if 0 < num < 100000:  # Reasonable line number range
                cleaned_lines.append(match.group(4))
                continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


# Convenience functions for common operations


def create_edit_tools(file_cache: Optional[FileCache] = None) -> dict[str, Any]:
    """Create all file editing tools with shared cache.

    Returns dict with:
    - file_cache: The shared FileCache
    - read_file: Function to read and cache files
    - edit_file: Function to edit files safely
    - write_file: Function to write files safely
    - multi_edit: Function for batch edits
    """
    cache = file_cache or FileCache()
    edit_tool = EditTool(cache)
    multi_edit_tool = MultiEditTool(cache)
    write_tool = WriteTool(cache)

    return {
        "file_cache": cache,
        "read_file": edit_tool.read_file,
        "edit_file": edit_tool.edit_file,
        "write_file": write_tool.write_file,
        "multi_edit": multi_edit_tool.edit_files,
        "add_read_file": multi_edit_tool.add_read_file,
    }
