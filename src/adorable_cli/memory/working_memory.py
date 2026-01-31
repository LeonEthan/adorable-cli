"""Working memory for high-priority context items.

Claude Code's working memory system:
- Maintains high-priority items during agent execution
- Automatically manages capacity with priority-based eviction
- Tracks active todos, key findings, and user directives
- Persists critical items across turns
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MemoryPriority(Enum):
    """Priority levels for memory items."""

    CRITICAL = 4  # User directives, safety constraints
    HIGH = 3      # Active todos, key decisions
    MEDIUM = 2    # Important findings, context
    LOW = 1       # General information


@dataclass
class MemoryItem:
    """A single item in working memory."""

    content: str
    priority: MemoryPriority
    category: str = "general"  # e.g., "todo", "finding", "directive"
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: Optional[float] = None  # Time-to-live (None = permanent)
    source: str = ""  # Where this item came from
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if this item has exceeded its TTL."""
        if self.ttl_seconds is None:
            return False
        return time.time() - self.timestamp > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "priority": self.priority.value,
            "category": self.category,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryItem:
        """Create from dictionary."""
        return cls(
            content=data["content"],
            priority=MemoryPriority(data.get("priority", 2)),
            category=data.get("category", "general"),
            timestamp=data.get("timestamp", time.time()),
            ttl_seconds=data.get("ttl_seconds"),
            source=data.get("source", ""),
            metadata=data.get("metadata", {}),
        )


class WorkingMemory:
    """Manages high-priority working memory for the agent.

    Claude Code uses working memory to maintain critical context
    across turns without exceeding token limits. Items are
    automatically evicted based on priority when capacity is reached.

    Key features:
    - Priority-based storage (CRITICAL items never auto-evicted)
    - TTL support for temporary items
    - Category-based retrieval
    - Automatic cleanup of expired items

    Example:
        memory = WorkingMemory(max_items=20)

        # Add critical user directive
        memory.add(
            "Always use TypeScript strict mode",
            priority=MemoryPriority.CRITICAL,
            category="directive"
        )

        # Add active todo
        memory.add(
            "Implement user authentication",
            priority=MemoryPriority.HIGH,
            category="todo",
            ttl_seconds=3600  # 1 hour
        )

        # Get formatted context for prompt injection
        context = memory.get_context_string()
    """

    def __init__(
        self,
        max_items: int = 20,
        max_critical_items: int = 10,
    ):
        self.max_items = max_items
        self.max_critical_items = max_critical_items
        self._items: list[MemoryItem] = []

    def add(
        self,
        content: str,
        priority: MemoryPriority = MemoryPriority.MEDIUM,
        category: str = "general",
        ttl_seconds: Optional[float] = None,
        source: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> MemoryItem:
        """Add an item to working memory.

        If capacity is exceeded, lowest priority non-critical items
        are evicted first.

        Args:
            content: The content to remember
            priority: Priority level
            category: Category for grouping
            ttl_seconds: Optional time-to-live
            source: Source of this item
            metadata: Additional metadata

        Returns:
            The created MemoryItem
        """
        item = MemoryItem(
            content=content,
            priority=priority,
            category=category,
            ttl_seconds=ttl_seconds,
            source=source,
            metadata=metadata or {},
        )

        # Remove expired items first
        self._cleanup_expired()

        # Check if we need to evict
        while len(self._items) >= self.max_items:
            if not self._evict_lowest_priority():
                # Can't evict anything (all critical), remove oldest critical
                self._items.pop(0)

        # Check critical item limit
        if priority == MemoryPriority.CRITICAL:
            critical_count = sum(
                1 for i in self._items
                if i.priority == MemoryPriority.CRITICAL
            )
            if critical_count >= self.max_critical_items:
                # Remove oldest critical item
                for i, existing in enumerate(self._items):
                    if existing.priority == MemoryPriority.CRITICAL:
                        self._items.pop(i)
                        break

        self._items.append(item)

        # Keep sorted by priority (highest first), then timestamp
        self._items.sort(
            key=lambda x: (-x.priority.value, x.timestamp)
        )

        return item

    def get(
        self,
        category: Optional[str] = None,
        min_priority: Optional[MemoryPriority] = None,
    ) -> list[MemoryItem]:
        """Get items from working memory.

        Args:
            category: Filter by category
            min_priority: Minimum priority level

        Returns:
            List of matching memory items
        """
        self._cleanup_expired()

        results = self._items

        if category:
            results = [i for i in results if i.category == category]

        if min_priority:
            results = [
                i for i in results
                if i.priority.value >= min_priority.value
            ]

        return results

    def get_context_string(
        self,
        max_items: Optional[int] = None,
        categories: Optional[list[str]] = None,
    ) -> str:
        """Get formatted context string for prompt injection.

        Args:
            max_items: Maximum number of items to include
            categories: Only include these categories

        Returns:
            Formatted context string
        """
        self._cleanup_expired()

        items = self._items

        if categories:
            items = [i for i in items if i.category in categories]

        if max_items:
            items = items[:max_items]

        if not items:
            return ""

        parts = ["## Working Memory"]

        # Group by category
        by_category: dict[str, list[MemoryItem]] = {}
        for item in items:
            if item.category not in by_category:
                by_category[item.category] = []
            by_category[item.category].append(item)

        for category, cat_items in by_category.items():
            parts.append(f"\n### {category.title()}")
            for item in cat_items:
                priority_marker = {
                    MemoryPriority.CRITICAL: "🔴",
                    MemoryPriority.HIGH: "🟠",
                    MemoryPriority.MEDIUM: "🟡",
                    MemoryPriority.LOW: "🟢",
                }.get(item.priority, "⚪")

                parts.append(f"{priority_marker} {item.content}")

        return "\n".join(parts)

    def remove(self, content_substring: str) -> bool:
        """Remove items containing the given substring.

        Returns:
            True if any items were removed
        """
        original_len = len(self._items)
        self._items = [
            i for i in self._items
            if content_substring not in i.content
        ]
        return len(self._items) < original_len

    def remove_by_category(self, category: str) -> int:
        """Remove all items in a category.

        Returns:
            Number of items removed
        """
        original_len = len(self._items)
        self._items = [i for i in self._items if i.category != category]
        return original_len - len(self._items)

    def clear(self) -> None:
        """Clear all items from working memory."""
        self._items.clear()

    def _cleanup_expired(self) -> None:
        """Remove expired items."""
        self._items = [i for i in self._items if not i.is_expired()]

    def _evict_lowest_priority(self) -> bool:
        """Evict the lowest priority non-critical item.

        Returns:
            True if an item was evicted
        """
        # Find lowest priority non-critical item
        for priority in [MemoryPriority.LOW, MemoryPriority.MEDIUM, MemoryPriority.HIGH]:
            for i, item in enumerate(self._items):
                if item.priority == priority:
                    self._items.pop(i)
                    return True
        return False

    def update_todo(
        self,
        content: str,
        completed: bool = False,
        priority: MemoryPriority = MemoryPriority.HIGH,
    ) -> MemoryItem:
        """Add or update a todo item.

        If a todo with similar content exists, updates it.
        """
        # Remove existing similar todos
        self._items = [
            i for i in self._items
            if not (i.category == "todo" and content in i.content)
        ]

        if not completed:
            return self.add(
                content=content,
                priority=priority,
                category="todo",
                ttl_seconds=None,  # Todos persist until completed
            )
        else:
            # Add as completed (lower priority, short TTL)
            return self.add(
                content=f"✓ {content}",
                priority=MemoryPriority.LOW,
                category="completed",
                ttl_seconds=300,  # 5 minutes
            )

    def add_finding(
        self,
        content: str,
        priority: MemoryPriority = MemoryPriority.MEDIUM,
        source: str = "",
    ) -> MemoryItem:
        """Add a key finding from analysis."""
        return self.add(
            content=content,
            priority=priority,
            category="finding",
            source=source,
        )

    def add_directive(
        self,
        content: str,
        source: str = "user",
    ) -> MemoryItem:
        """Add a critical user directive."""
        return self.add(
            content=content,
            priority=MemoryPriority.CRITICAL,
            category="directive",
            source=source,
            ttl_seconds=None,  # Directives persist
        )

    def get_active_todos(self) -> list[MemoryItem]:
        """Get all active todo items."""
        return self.get(category="todo")

    def get_directives(self) -> list[MemoryItem]:
        """Get all critical directives."""
        return self.get(
            category="directive",
            min_priority=MemoryPriority.CRITICAL,
        )

    def to_list(self) -> list[dict[str, Any]]:
        """Convert to list of dictionaries for serialization."""
        return [item.to_dict() for item in self._items]

    @classmethod
    def from_list(cls, data: list[dict[str, Any]], **kwargs) -> WorkingMemory:
        """Create from list of dictionaries."""
        memory = cls(**kwargs)
        for item_data in data:
            item = MemoryItem.from_dict(item_data)
            if not item.is_expired():
                memory._items.append(item)
        return memory

    def __len__(self) -> int:
        """Return number of items in memory."""
        self._cleanup_expired()
        return len(self._items)

    def __contains__(self, content: str) -> bool:
        """Check if content is in memory."""
        return any(content in item.content for item in self._items)
