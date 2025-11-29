"""
Simplified context guard to keep model context within reasonable limits.

Uses conservative fixed limits and relies on agno's built-in context management.
For advanced tuning, use environment variables:
- ADORABLE_CONTEXT_WINDOW: Override context window size
- ADORABLE_CTX_MARGIN: Safety margin in tokens (default: 2048)
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover
    tiktoken = None  # type: ignore


# Fixed conservative limits
DEFAULT_CONTEXT_WINDOW = 64_000
DEFAULT_MARGIN = 2_048
DEFAULT_MAX_OUTPUT = 2_048


def _estimate_tokens(text: str) -> int:
    """Simple token estimation using tiktoken or character heuristic."""
    if not text:
        return 0
    
    # Try tiktoken for accuracy
    if tiktoken is not None:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            pass
    
    # Fallback: ~4 chars per token (conservative)
    return len(text) // 4


def _get_context_window() -> int:
    """Get context window from env or use conservative default."""
    try:
        val = os.environ.get("ADORABLE_CONTEXT_WINDOW")
        if val:
            return int(val)
    except Exception:
        pass
    return DEFAULT_CONTEXT_WINDOW


def _get_margin() -> int:
    """Get safety margin from env or use conservative default."""
    try:
        val = os.environ.get("ADORABLE_CTX_MARGIN")
        if val:
            return int(val)
    except Exception:
        pass
    return DEFAULT_MARGIN


def _read_input_text(run_input: Any) -> str:
    """Extract text from run input."""
    for attr in ("input_content", "input", "text"):
        val = getattr(run_input, attr, None)
        if isinstance(val, str):
            return val
    return ""


def _compress_input(text: str, max_chars: int) -> str:
    """Compress input by keeping head and tail."""
    if len(text) <= max_chars:
        return text
    
    half = max_chars // 2
    head = text[:half]
    tail = text[-half:]
    return f"[Input compressed to fit context]\n{head}\n...\n{tail}"


def ensure_context_within_window(
    agent: Optional[Any] = None,
    team: Optional[Any] = None,
    run_input: Any = None,
    session: Optional[Any] = None,
    **_: Any,
) -> None:
    """Simple pre-hook to prevent context overflow.
    
    Strategy:
    1. Check if input is too large
    2. Reduce history runs if needed
    3. Compress input as last resort
    
    Relies on agno for most context management.
    """
    agent = agent or team
    if agent is None or run_input is None:
        return
    
    # Get configuration
    context_window = _get_context_window()
    margin = _get_margin()
    max_output = DEFAULT_MAX_OUTPUT
    
    # Reserve space for output and safety margin
    budget = context_window - max_output - margin
    if budget <= 0:
        return
    
    # Estimate current input size
    input_text = _read_input_text(run_input)
    input_tokens = _estimate_tokens(input_text)
    
    # Save original settings for restoration
    try:
        prev: Dict[str, Any] = {
            "num_history_runs": getattr(agent, "num_history_runs", None),
        }
        setattr(agent, "_ctx_guard_prev", prev)
    except Exception:
        pass
    
    # If input alone is within budget, let agno handle it
    if input_tokens <= budget * 0.6:  # Leave 40% for system/history
        return
    
    # Reduce history if enabled
    history_runs = int(getattr(agent, "num_history_runs", 0) or 0)
    if history_runs > 0:
        # Conservatively reduce history
        new_runs = max(0, min(history_runs - 1, 2))  # Keep max 2 runs
        try:
            setattr(agent, "num_history_runs", new_runs)
        except Exception:
            pass
    
    # Compress input if still too large
    max_input_tokens = int(budget * 0.7)  # 70% for input
    if input_tokens > max_input_tokens:
        max_chars = max_input_tokens * 4  # Conservative char estimate
        compressed = _compress_input(input_text, max_chars)
        for attr in ("input_content", "input", "text"):
            if hasattr(run_input, attr):
                try:
                    setattr(run_input, attr, compressed)
                    break
                except Exception:
                    continue


def restore_context_settings(
    agent: Optional[Any] = None,
    team: Optional[Any] = None,
    **_: Any,
) -> None:
    """Post-hook to restore agent settings after run."""
    agent = agent or team
    if agent is None:
        return
    
    try:
        prev = getattr(agent, "_ctx_guard_prev", None)
        if isinstance(prev, dict):
            # Restore saved values
            for key, val in prev.items():
                if val is not None:
                    try:
                        setattr(agent, key, val)
                    except Exception:
                        pass
            # Clean up
            delattr(agent, "_ctx_guard_prev")
    except Exception:
        pass
