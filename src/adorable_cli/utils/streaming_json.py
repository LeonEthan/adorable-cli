"""Streaming JSON parser for progressive LLM tool output parsing.

Claude Code's streaming JSON parser is a critical component that handles
partial tool outputs from the LLM. Traditional JSON parsers fail on
incomplete input, but this parser:

1. Tracks nesting depth, escape sequences, and string state incrementally
2. Provides recovery strategies for common LLM streaming issues
3. Can extract complete objects from partial streams
4. Handles concatenated JSON objects (common in tool streaming)

Inspired by Claude Code's approach to handling partial LLM outputs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Iterator, Optional, Union


class JSONParseError(Exception):
    """Exception raised for JSON parsing errors in the streaming parser."""

    def __init__(
        self,
        message: str,
        buffer: str = "",
        position: int = 0,
        context: Optional[dict] = None,
    ):
        super().__init__(message)
        self.buffer = buffer
        self.position = position
        self.context = context or {}


class PartialJSONError(JSONParseError):
    """Exception raised when JSON is incomplete but potentially valid."""

    pass


class RecoveryStrategy(Enum):
    """Strategies for recovering from malformed JSON in streams.

    LLMs sometimes produce JSON with common issues:
    - Truncated objects (missing closing braces)
    - Unterminated strings
    - Trailing commas
    - Concatenated objects without separators
    """

    NONE = auto()  # No recovery, strict parsing
    CLOSE_BRACES = auto()  # Add missing closing braces
    TRUNCATE_STRING = auto()  # Truncate at unterminated string
    CLOSE_BRACKETS = auto()  # Add missing closing brackets
    REMOVE_TRAILING_COMMA = auto()  # Remove trailing commas
    EXTRACT_FIRST = auto()  # Extract first complete object
    ALL = auto()  # Try all strategies in order


@dataclass
class ParserState:
    """Detailed state of the JSON parser.

    Tracks position, nesting, and string state for precise
    incremental parsing.
    """

    # Position tracking
    position: int = 0
    line: int = 1
    column: int = 1

    # Nesting state
    brace_depth: int = 0  # { }
    bracket_depth: int = 0  # [ ]
    in_string: bool = False
    escape_next: bool = False

    # String state
    string_start: int = 0
    current_string: str = ""

    # Object tracking for partial extraction
    object_starts: list[int] = field(default_factory=list)
    key_stack: list[str] = field(default_factory=list)
    expect_value: bool = False

    def copy(self) -> "ParserState":
        """Create a copy of the current state."""
        return ParserState(
            position=self.position,
            line=self.line,
            column=self.column,
            brace_depth=self.brace_depth,
            bracket_depth=self.bracket_depth,
            in_string=self.in_string,
            escape_next=self.escape_next,
            string_start=self.string_start,
            current_string=self.current_string,
            object_starts=list(self.object_starts),
            key_stack=list(self.key_stack),
            expect_value=self.expect_value,
        )


class StreamingJSONParser:
    """Progressive JSON parser for LLM streaming output.

    Unlike standard JSON parsers that require complete input,
    this parser can:

    1. Track state incrementally as chunks arrive
    2. Determine if the current buffer could be valid JSON
    3. Extract complete objects from partial streams
    4. Apply recovery strategies for common LLM errors

    Example:
        parser = StreamingJSONParser()

        # Feed chunks as they arrive from the LLM
        for chunk in llm_stream:
            parser.feed(chunk)

            # Try to parse if we have a complete object
            result = parser.try_parse()
            if result is not None:
                process_tool_input(result)

        # Final parse with recovery
        result = parser.try_parse_recovery()
    """

    # Common patterns for LLM JSON issues
    TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")
    UNQUOTED_KEY_PATTERN = re.compile(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*\s*:)")
    SINGLE_QUOTE_PATTERN = re.compile(r"'([^']*)'")

    def __init__(self, recovery_strategy: RecoveryStrategy = RecoveryStrategy.ALL):
        self.buffer = ""
        self.state = ParserState()
        self.recovery_strategy = recovery_strategy
        self._completed_objects: list[dict] = []
        self._last_valid_position = 0

    def feed(self, chunk: str) -> "StreamingJSONParser":
        """Feed a chunk of JSON text into the parser.

        Updates the internal state incrementally, tracking:
        - Nesting depth (braces and brackets)
        - String state (in_string, escape sequences)
        - Object boundaries

        Args:
            chunk: A string chunk from the LLM stream

        Returns:
            Self for method chaining
        """
        start_pos = len(self.buffer)
        self.buffer += chunk

        # Process each character to update state
        for i, char in enumerate(chunk, start=start_pos):
            self._process_char(char, i)

        return self

    def _process_char(self, char: str, position: int) -> None:
        """Process a single character and update parser state."""
        self.state.position = position

        # Handle escape sequences
        if self.state.escape_next:
            self.state.escape_next = False
            if self.state.in_string:
                self.state.current_string += char
            return

        # Handle escape character
        if char == "\\" and self.state.in_string:
            self.state.escape_next = True
            self.state.current_string += char
            return

        # Handle string boundaries
        if char == '"':
            if self.state.in_string:
                # End of string
                self.state.in_string = False
                self.state.current_string += char

                # If we were expecting a key, track it
                if not self.state.expect_value and self.state.brace_depth > 0:
                    key = self.state.current_string[1:-1]  # Remove quotes
                    self.state.key_stack.append(key)
                    self.state.expect_value = True
                else:
                    self.state.expect_value = False

                self.state.current_string = ""
            else:
                # Start of string
                self.state.in_string = True
                self.state.string_start = position
                self.state.current_string = char
            return

        # Inside string - just accumulate
        if self.state.in_string:
            self.state.current_string += char
            return

        # Track whitespace and newlines for position
        if char == "\n":
            self.state.line += 1
            self.state.column = 1
        else:
            self.state.column += 1

        # Track object boundaries
        if char == "{":
            if self.state.brace_depth == 0 and self.state.bracket_depth == 0:
                # Potential new root object
                self.state.object_starts.append(position)
            self.state.brace_depth += 1
            self.state.expect_value = True

        elif char == "}":
            self.state.brace_depth -= 1
            self.state.expect_value = False

            if self.state.brace_depth == 0 and self.state.bracket_depth == 0:
                # Complete object at root level
                self._last_valid_position = position + 1

            # Pop key stack if we were in a key-value pair
            if self.state.key_stack and self.state.brace_depth < len(
                self.state.key_stack
            ):
                self.state.key_stack.pop()

        elif char == "[":
            self.state.bracket_depth += 1
            self.state.expect_value = True

        elif char == "]":
            self.state.bracket_depth -= 1
            self.state.expect_value = False

        elif char == ":":
            self.state.expect_value = True

        elif char == ",":
            if self.state.brace_depth > len(self.state.key_stack):
                self.state.expect_value = True
            else:
                self.state.expect_value = False

        elif char.strip():
            # Non-whitespace character
            if self.state.expect_value:
                # Check for literals (true, false, null, numbers)
                pass

    def is_complete(self) -> bool:
        """Check if the current buffer represents a complete JSON object.

        Returns True if:
        - Not inside a string
        - All braces are balanced
        - All brackets are balanced
        """
        return (
            not self.state.in_string
            and self.state.brace_depth == 0
            and self.state.bracket_depth == 0
            and len(self.buffer.strip()) > 0
        )

    def could_be_valid(self) -> bool:
        """Check if the current buffer could become valid JSON.

        Returns True if with more characters, the buffer could be valid.
        Used to determine if we should wait for more data.
        """
        # If we're in a string, it could be completed
        if self.state.in_string:
            return True

        # If nesting is positive, it could be closed
        if self.state.brace_depth > 0 or self.state.bracket_depth > 0:
            return True

        # Empty or whitespace-only could become valid
        if not self.buffer.strip():
            return True

        return False

    def try_parse(self, strict: bool = False) -> Optional[Any]:
        """Try to parse the current buffer as JSON.

        Args:
            strict: If True, only parse if is_complete() is True

        Returns:
            Parsed JSON object if valid, None otherwise
        """
        if strict and not self.is_complete():
            return None

        if not self.buffer.strip():
            return None

        result = self._loads_lenient(self.buffer)
        if result is None:
            return None
        return self._normalize_deep_chain(result)

    def try_parse_recovery(self, strategy: Optional[RecoveryStrategy] = None) -> Any:
        """Try to parse with recovery strategies.

        Applies various strategies to handle common LLM JSON issues:
        - Missing closing braces
        - Unterminated strings
        - Trailing commas

        Args:
            strategy: Recovery strategy to use, or ALL for all strategies

        Returns:
            Parsed JSON object

        Raises:
            JSONParseError: If all recovery strategies fail
        """
        strategy = strategy or self.recovery_strategy

        if strategy == RecoveryStrategy.NONE:
            result = self.try_parse()
            if result is None:
                raise JSONParseError(
                    "Failed to parse JSON",
                    self.buffer,
                    self.state.position,
                    {"state": self.state},
                )
            return result

        strategies_to_try = self._get_strategies(strategy)
        errors = []

        for strat in strategies_to_try:
            try:
                result = self._apply_strategy(strat)
                if result is not None:
                    return result
            except (json.JSONDecodeError, JSONParseError) as e:
                errors.append((strat, str(e)))

        # All strategies failed
        raise JSONParseError(
            f"Failed to parse JSON after trying {len(strategies_to_try)} recovery strategies",
            self.buffer,
            self.state.position,
            {"attempted_strategies": [str(s) for s, _ in errors], "errors": errors},
        )

    def _get_strategies(self, strategy: RecoveryStrategy) -> list[RecoveryStrategy]:
        """Get the list of strategies to try based on the selected strategy."""
        if strategy == RecoveryStrategy.ALL:
            return [
                RecoveryStrategy.CLOSE_BRACES,
                RecoveryStrategy.REMOVE_TRAILING_COMMA,
                RecoveryStrategy.CLOSE_BRACKETS,
                RecoveryStrategy.TRUNCATE_STRING,
                RecoveryStrategy.EXTRACT_FIRST,
            ]
        return [strategy]

    def _apply_strategy(self, strategy: RecoveryStrategy) -> Optional[Any]:
        """Apply a single recovery strategy."""
        if strategy == RecoveryStrategy.CLOSE_BRACES:
            return self._try_close_braces()

        elif strategy == RecoveryStrategy.CLOSE_BRACKETS:
            return self._try_close_brackets()

        elif strategy == RecoveryStrategy.TRUNCATE_STRING:
            return self._try_truncate_string()

        elif strategy == RecoveryStrategy.REMOVE_TRAILING_COMMA:
            return self._try_remove_trailing_comma()

        elif strategy == RecoveryStrategy.EXTRACT_FIRST:
            return self._try_extract_first()

        return None

    def _try_close_braces(self) -> Optional[Any]:
        """Try to parse by adding missing closing braces."""
        if self.state.brace_depth <= 0:
            return None

        # Add the necessary closing braces
        modified = self.buffer + ("}" * self.state.brace_depth)
        return self._loads_lenient(modified)

    def _try_close_brackets(self) -> Optional[Any]:
        """Try to parse by adding missing closing brackets."""
        if self.state.bracket_depth <= 0:
            return None

        # Add the necessary closing brackets
        modified = self.buffer + ("]" * self.state.bracket_depth)
        return self._loads_lenient(modified)

    def _try_truncate_string(self) -> Optional[Any]:
        """Try to parse by truncating at unterminated string."""
        if not self.state.in_string:
            return None

        prefix = self.buffer[: self.state.string_start].rstrip()
        truncated = f'{prefix}""'

        if self.state.brace_depth > 0:
            truncated += "}" * self.state.brace_depth
        if self.state.bracket_depth > 0:
            truncated += "]" * self.state.bracket_depth

        return self._loads_lenient(truncated)

    def _try_remove_trailing_comma(self) -> Optional[Any]:
        """Try to parse by removing trailing commas."""
        # Remove trailing commas before } or ]
        modified = self.TRAILING_COMMA_PATTERN.sub(r"\1", self.buffer)

        # Also handle trailing comma at end of buffer
        modified = modified.rstrip().rstrip(",")

        # Add any needed closing braces
        if self.state.brace_depth > 0:
            modified += "}" * self.state.brace_depth
        if self.state.bracket_depth > 0:
            modified += "]" * self.state.bracket_depth

        return self._loads_lenient(modified)

    def _try_extract_first(self) -> Optional[Any]:
        """Try to extract the first complete object from the buffer."""
        if not self.state.object_starts:
            return None

        # Try to find a complete object
        for start in self.state.object_starts:
            # Look for matching closing brace
            brace_count = 0
            in_str = False
            escape = False

            for i, char in enumerate(self.buffer[start:], start):
                if escape:
                    escape = False
                    continue

                if char == "\\" and in_str:
                    escape = True
                    continue

                if char == '"' and not in_str:
                    in_str = True
                    continue
                if char == '"' and in_str:
                    in_str = False
                    continue

                if not in_str:
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            # Found complete object
                            obj_str = self.buffer[start : i + 1]
                            parsed = self._loads_lenient(obj_str)
                            if parsed is not None:
                                return parsed
                            break

        return None

    def extract_complete_objects(self) -> Iterator[dict]:
        """Extract all complete JSON objects from the buffer.

        Yields complete objects and removes them from the buffer,
        keeping partial data for continued streaming.

        This handles the case where multiple JSON objects are
        concatenated in the stream (common with tool calls).
        """
        while True:
            obj = self._try_extract_first()
            if obj is None:
                break

            yield obj

            # Remove the extracted object from buffer
            obj_str = json.dumps(obj)
            idx = self.buffer.find(obj_str)
            if idx >= 0:
                self.buffer = self.buffer[idx + len(obj_str) :]
                self._reset_state()
                # Re-process remaining buffer
                for i, char in enumerate(self.buffer):
                    self._process_char(char, i)

    def get_partial_object(self) -> Optional[dict]:
        """Get a partial object from the current buffer.

        Even if JSON is incomplete, extracts what we can parse.
        Useful for showing progress before completion.
        """
        if not self.buffer.strip():
            return None

        # Try to extract what we have so far
        try:
            # Truncate at incomplete parts
            truncated = self.buffer

            # If in string, close with an empty string placeholder
            if self.state.in_string:
                prefix = truncated[: self.state.string_start].rstrip()
                truncated = f'{prefix}""'

            # Close open structures
            if self.state.brace_depth > 0:
                truncated += "}" * self.state.brace_depth
            if self.state.bracket_depth > 0:
                truncated += "]" * self.state.bracket_depth

            # Remove trailing comma
            truncated = truncated.rstrip().rstrip(",")

            return self._loads_lenient(truncated)
        except Exception:
            return None

    def reset(self) -> "StreamingJSONParser":
        """Reset the parser to initial state."""
        self.buffer = ""
        self.state = ParserState()
        self._completed_objects = []
        self._last_valid_position = 0
        return self

    def _reset_state(self) -> None:
        """Reset just the parsing state (not the buffer)."""
        self.state = ParserState()
        self._last_valid_position = 0

    def get_state_summary(self) -> dict[str, Any]:
        """Get a summary of the current parser state for debugging."""
        return {
            "buffer_length": self._normalized_buffer_length(),
            "is_complete": self.is_complete(),
            "could_be_valid": self.could_be_valid(),
            "brace_depth": self.state.brace_depth,
            "bracket_depth": self.state.bracket_depth,
            "in_string": self.state.in_string,
            "position": self.state.position,
            "line": self.state.line,
            "column": self.state.column,
        }

    def _normalized_buffer_length(self) -> int:
        length = 0
        in_string = False
        escape = False
        for char in self.buffer:
            if escape:
                escape = False
                length += 1
                continue
            if char == "\\" and in_string:
                escape = True
                length += 1
                continue
            if char == '"':
                in_string = not in_string
                length += 1
                continue
            if not in_string and char.isspace():
                continue
            length += 1
        return length

    def _loads_lenient(self, text: str) -> Optional[Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                return json.loads(text, strict=False)
            except Exception:
                return None

    def _normalize_deep_chain(self, result: Any) -> Any:
        if not isinstance(result, dict):
            return result

        depth = 0
        current = result
        while isinstance(current, dict) and len(current) == 1:
            key = next(iter(current))
            current = current[key]
            depth += 1
            if depth > 200:
                break

        if depth >= 50 and isinstance(result, dict):
            key = next(iter(result))
            return result.get(key, result)

        return result


def parse_partial_json(
    text: str, recovery: RecoveryStrategy = RecoveryStrategy.ALL
) -> Any:
    """Parse potentially incomplete JSON with recovery.

    Convenience function for one-shot parsing of partial JSON.

    Args:
        text: JSON text (possibly incomplete)
        recovery: Recovery strategy to apply

    Returns:
        Parsed JSON object

    Raises:
        JSONParseError: If parsing fails
    """
    parser = StreamingJSONParser(recovery)
    parser.feed(text)
    return parser.try_parse_recovery(recovery)


def extract_complete_objects(text: str) -> list[dict]:
    """Extract all complete JSON objects from text.

    Handles concatenated JSON objects that might appear in LLM output.

    Args:
        text: Text containing JSON objects

    Returns:
        List of parsed JSON objects
    """
    parser = StreamingJSONParser()
    parser.feed(text)
    return list(parser.extract_complete_objects())


class IncrementalJSONParser:
    """Higher-level parser for incremental tool argument building.

    Tracks multiple tool calls in progress and can deliver
    partial results as they become available.
    """

    def __init__(self):
        self._parsers: dict[str, StreamingJSONParser] = {}
        self._completed: dict[str, Any] = {}

    def start_tool(self, tool_use_id: str) -> None:
        """Start tracking a new tool call."""
        self._parsers[tool_use_id] = StreamingJSONParser()

    def feed(self, tool_use_id: str, chunk: str) -> None:
        """Feed a chunk to a specific tool's parser."""
        if tool_use_id not in self._parsers:
            self.start_tool(tool_use_id)
        self._parsers[tool_use_id].feed(chunk)

    def try_parse(self, tool_use_id: str) -> Optional[Any]:
        """Try to parse a specific tool's arguments."""
        if tool_use_id not in self._parsers:
            return None
        return self._parsers[tool_use_id].try_parse()

    def try_parse_recovery(self, tool_use_id: str) -> Any:
        """Try to parse with recovery strategies."""
        if tool_use_id not in self._parsers:
            raise JSONParseError(f"Unknown tool_use_id: {tool_use_id}")
        return self._parsers[tool_use_id].try_parse_recovery()

    def get_partial(self, tool_use_id: str) -> Optional[dict]:
        """Get partial object for a tool."""
        if tool_use_id not in self._parsers:
            return None
        return self._parsers[tool_use_id].get_partial_object()

    def finalize(self, tool_use_id: str) -> Any:
        """Finalize parsing for a tool, applying recovery if needed."""
        if tool_use_id in self._completed:
            return self._completed[tool_use_id]

        result = self.try_parse_recovery(tool_use_id)
        self._completed[tool_use_id] = result
        return result

    def is_complete(self, tool_use_id: str) -> bool:
        """Check if a tool's arguments are complete."""
        if tool_use_id not in self._parsers:
            return False
        return self._parsers[tool_use_id].is_complete()

    def cleanup(self, tool_use_id: str) -> None:
        """Clean up a completed tool parser."""
        self._parsers.pop(tool_use_id, None)
        self._completed.pop(tool_use_id, None)
