"""Session summarization for long-term context management.

Claude Code's summarization system:
- Generates session summaries using a fast/cheap model
- Stores summaries in SQLite for persistent context
- Uses plain text (not JSON) to avoid parsing failures
- Summaries feed back into context for long sessions
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional


@dataclass
class SummaryResult:
    """Result of a summarization operation."""

    summary: str
    session_id: str
    message_count: int
    generated_at: float
    model_used: str = "default"
    tokens_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SummaryResult:
        """Create from dictionary."""
        return cls(**data)


class SessionSummarizer:
    """Manages session summaries for long-term context.

    Key design decisions (from Claude Code):
    1. Plain text summaries (not JSON) - avoids parsing failures
    2. Fast/cheap model for summarization - cost efficient
    3. SQLite storage - persistent across restarts
    4. Incremental updates - can update existing summaries

    Example:
        summarizer = SessionSummarizer(db_path="~/.adorable/memory.db")
        result = await summarizer.summarize_session(
            session_id="abc123",
            messages=conversation_history,
            model=fast_model
        )
    """

    def __init__(
        self,
        db_path: str = "~/.adorable/memory.db",
        summary_model: Optional[str] = None,
    ):
        self.db_path = Path(db_path).expanduser()
        self.summary_model = summary_model
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create summary tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    message_count INTEGER NOT NULL,
                    generated_at REAL NOT NULL,
                    model_used TEXT,
                    tokens_used INTEGER DEFAULT 0
                )
            """)

            # Table for incremental summary history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS summary_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    message_range_start INTEGER NOT NULL,
                    message_range_end INTEGER NOT NULL,
                    generated_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES session_summaries(session_id)
                )
            """)

            conn.commit()

    async def summarize_session(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        model: Optional[Any] = None,
    ) -> SummaryResult:
        """Generate a summary of the session.

        Args:
            session_id: Unique session identifier
            messages: List of conversation messages
            model: Optional model to use for summarization (fast/cheap preferred)

        Returns:
            SummaryResult with the generated summary
        """
        if not messages:
            return SummaryResult(
                summary="No messages to summarize.",
                session_id=session_id,
                message_count=0,
                generated_at=time.time(),
            )

        # Build the summary prompt
        prompt = self._build_summary_prompt(messages)

        # Generate summary
        if model:
            summary_text = await self._generate_with_model(prompt, model)
        else:
            # Fallback: extractive summary without model
            summary_text = self._generate_extractive_summary(messages)

        result = SummaryResult(
            summary=summary_text,
            session_id=session_id,
            message_count=len(messages),
            generated_at=time.time(),
            model_used=self.summary_model or "extractive",
        )

        # Store in database
        self._store_summary(result)

        return result

    def _build_summary_prompt(self, messages: list[dict[str, Any]]) -> str:
        """Build a prompt for session summarization."""
        from adorable_cli.agent.prompts import SESSION_SUMMARY_PROMPT

        # Format messages for the prompt
        formatted_messages = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                # Handle content blocks
                text_parts = [
                    c.get("text", "") for c in content
                    if c.get("type") == "text"
                ]
                content = " ".join(text_parts)
            formatted_messages.append(f"{role}: {content[:500]}")

        conversation_text = "\n".join(formatted_messages[-50:])  # Last 50 messages

        return f"""{SESSION_SUMMARY_PROMPT}

Conversation History (last {len(formatted_messages)} messages):

{conversation_text}

Summary:"""

    async def _generate_with_model(self, prompt: str, model: Any) -> str:
        """Generate summary using the provided model."""
        try:
            # This would integrate with your actual model
            # For now, return a placeholder that would be replaced
            response = await model.generate(prompt)
            return response.strip()
        except Exception:
            # Fallback to extractive summary on model failure
            return self._generate_extractive_summary_from_prompt(prompt)

    def _generate_extractive_summary(self, messages: list[dict[str, Any]]) -> str:
        """Generate an extractive summary without a model."""
        # Extract key information types
        files_mentioned = set()
        commands_run = set()
        errors_encountered = set()
        decisions_made = []

        for msg in messages:
            content = str(msg.get("content", ""))

            # Look for file operations
            import re
            file_patterns = [
                r'(?:read|edited|created|deleted|modified)\s+(?:file\s+)?[`"\']?(\S+\.(?:py|js|ts|json|md|txt|yml|yaml))[`"\']?',
                r'(?:file|path)\s*:?\s*[`"\']?(\S+\.(?:py|js|ts|json|md|txt))[`"\']?',
            ]
            for pattern in file_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                files_mentioned.update(matches)

            # Look for shell commands
            shell_patterns = [
                r'(?:ran|executed|command)\s*:?\s*[`"\']?(\S+[^`"\']*)[`"\']?',
                r'`([^`]+)`',  # Inline code
            ]
            for pattern in shell_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                commands_run.update(m.strip() for m in matches if len(m.strip()) > 3)

            # Look for errors
            if "error" in content.lower() or "exception" in content.lower():
                lines = content.split("\n")
                for line in lines:
                    if "error" in line.lower() or "exception" in line.lower():
                        errors_encountered.add(line.strip()[:200])

            # Look for decisions/plans
            decision_patterns = [
                r'(?:decided|plan|approach|will|should)\s*:?\s*(.+)',
                r'(?:next\s+step|then)\s*:?\s*(.+)',
            ]
            for pattern in decision_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                decisions_made.extend(m[:200] for m in matches)

        # Build summary
        parts = []
        parts.append("Session Summary:")

        if files_mentioned:
            parts.append(f"\nFiles worked with: {', '.join(sorted(files_mentioned)[:10])}")

        if commands_run:
            parts.append(f"\nCommands executed: {len(commands_run)}")

        if errors_encountered:
            parts.append(f"\nIssues encountered: {len(errors_encountered)}")

        if decisions_made:
            parts.append("\nKey decisions:")
            for decision in decisions_made[-5:]:
                parts.append(f"- {decision}")

        return "\n".join(parts)

    def _generate_extractive_summary_from_prompt(self, prompt: str) -> str:
        """Fallback summary generation from prompt text."""
        lines = prompt.split("\n")

        # Extract files, commands, and key actions mentioned
        files = set()
        commands = set()

        import re
        for line in lines:
            # Find file paths
            file_matches = re.findall(r'\b\w+\.(?:py|js|ts|json|md|txt|yml|yaml)\b', line)
            files.update(file_matches)

            # Find commands in backticks
            cmd_matches = re.findall(r'`([^`]+)`', line)
            commands.update(cmd_matches)

        parts = ["Session Summary (Extractive):"]

        if files:
            parts.append(f"Files: {', '.join(sorted(files))}")
        if commands:
            parts.append(f"Commands: {len(commands)} executed")

        parts.append(f"Total messages: ~{len([l for l in lines if l.startswith(('user:', 'assistant:'))])}")

        return "\n".join(parts)

    def _store_summary(self, result: SummaryResult) -> None:
        """Store summary in database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO session_summaries
                (session_id, summary, message_count, generated_at, model_used, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.session_id,
                    result.summary,
                    result.message_count,
                    result.generated_at,
                    result.model_used,
                    result.tokens_used,
                )
            )
            conn.commit()

    def get_summary(self, session_id: str) -> Optional[SummaryResult]:
        """Retrieve a stored summary."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT * FROM session_summaries WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            if row:
                return SummaryResult(
                    session_id=row[0],
                    summary=row[1],
                    message_count=row[2],
                    generated_at=row[3],
                    model_used=row[4] or "",
                    tokens_used=row[5] or 0,
                )
            return None

    def update_summary(
        self,
        session_id: str,
        additional_messages: list[dict[str, Any]],
        model: Optional[Any] = None,
    ) -> Optional[SummaryResult]:
        """Update an existing summary with new messages.

        This implements incremental summarization for long sessions.
        """
        existing = self.get_summary(session_id)
        if not existing:
            return None

        # Combine existing summary context with new messages
        # Create a synthetic "message" representing the existing summary
        context_message = {
            "role": "system",
            "content": f"Previous session context: {existing.summary}"
        }

        all_messages = [context_message] + additional_messages

        return self.summarize_session(session_id, all_messages, model)

    def list_sessions(self, limit: int = 10) -> list[SummaryResult]:
        """List recent session summaries."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT * FROM session_summaries
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

            return [
                SummaryResult(
                    session_id=row[0],
                    summary=row[1],
                    message_count=row[2],
                    generated_at=row[3],
                    model_used=row[4] or "",
                    tokens_used=row[5] or 0,
                )
                for row in rows
            ]


# Convenience function


async def create_session_summary(
    messages: list[dict[str, Any]],
    session_id: Optional[str] = None,
    db_path: str = "~/.adorable/memory.db",
    model: Optional[Any] = None,
) -> SummaryResult:
    """Create a session summary (convenience function).

    Args:
        messages: Conversation messages to summarize
        session_id: Optional session ID (generated if not provided)
        db_path: Path to SQLite database
        model: Optional model for generation

    Returns:
        SummaryResult with the generated summary
    """
    if session_id is None:
        import uuid
        session_id = str(uuid.uuid4())[:8]

    summarizer = SessionSummarizer(db_path=db_path)
    return await summarizer.summarize_session(session_id, messages, model)
