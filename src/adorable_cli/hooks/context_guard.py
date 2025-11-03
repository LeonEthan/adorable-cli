"""
Context Guard hooks to keep the constructed model context within window.

This module provides a pre-hook to estimate token budget before an Agent run
and dynamically adjust history inclusion or lightly compress the input to avoid
context overflow errors. A matching post-hook restores any temporary settings.

Notes:
- Estimation is conservative and does not depend on accessing internal
  context-construction details; it uses simple heuristics to remain robust.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover
    tiktoken = None  # type: ignore


def _get_str(obj: Any) -> str:
    """Safely stringify objects for token estimation."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    try:
        # Avoid importing json to keep dependencies minimal
        return str(obj)
    except Exception:
        return ""


def estimate_tokens(texts: list[str], model_id: str) -> int:
    """Estimate tokens for a list of text segments.

    Tries model-specific tokenizer via tiktoken. Falls back to a
    char-length heuristic (≈ 3.5 chars per token) when tokenizer is
    not available.
    """
    text = "\n".join(texts)
    if not text:
        return 0

    # Prefer tiktoken when available (works for OpenAI-compatible models)
    if tiktoken is not None:
        try:
            enc = None
            # Try an exact encoding first
            try:
                enc = tiktoken.encoding_for_model(model_id)
            except Exception:
                enc = tiktoken.get_encoding("cl100k_base")
            if enc is not None:
                return len(enc.encode(text))
        except Exception:
            pass

    # Heuristic fallback: approx 3.5 chars per token
    return int(len(text) / 3.5) + 1


def get_context_window(model_id: str) -> int:
    """Resolve the context window for the given model.

    Priority:
    1) Environment override `ADORABLE_CONTEXT_WINDOW`
    2) Known model mappings (conservative defaults)
    3) Generic safe default (32k)
    """
    env_val = os.environ.get("ADORABLE_CONTEXT_WINDOW")
    if env_val:
        try:
            return int(env_val)
        except Exception:
            pass

    mid = (model_id or "").lower()
    # Conservative mappings for common models (adjust as needed)
    if any(k in mid for k in ["gpt-4o", "gpt-5"]):
        return 128_000
    if any(k in mid for k in ["gpt-4", "claude-3-", "llama-3-", "mistral"]):
        return 32_000
    if "glm" in mid:
        return 32_000

    # Generic safe default
    return 32_000


def _get_margin_tokens() -> int:
    """Safety margin to cover estimation error and system/tool glue tokens."""
    val = os.environ.get("ADORABLE_CTX_MARGIN", "1024").strip()
    try:
        return int(val)
    except Exception:
        # Support percentage format like "5%" (use 5% of 32k = ~1600)
        if val.endswith("%"):
            try:
                pct = float(val[:-1]) / 100.0
                return int(32_000 * pct)
            except Exception:
                pass
        return 1024


def _avg_tokens_per_run() -> int:
    """Average tokens per history run used for coarse budgeting."""
    val = os.environ.get("ADORABLE_CTX_AVG_RUN_TOKENS", "512").strip()
    try:
        return int(val)
    except Exception:
        return 512


def _get_model_id(agent: Any) -> str:
    """Extract model id from agent.model when available."""
    try:
        model = getattr(agent, "model", None)
        mid = getattr(model, "id", None)
        return str(mid) if mid else ""
    except Exception:
        return ""


def _get_max_output_tokens(agent: Any) -> int:
    """Extract max output tokens from agent.model when available."""
    try:
        model = getattr(agent, "model", None)
        mt = getattr(model, "max_tokens", None)
        if mt is None:
            return 2048
        return int(mt)
    except Exception:
        return 2048


def _mutate_run_input_text(run_input: Any, new_text: str) -> None:
    """Try to update the run input content across common attribute names."""
    for attr in ("input_content", "input", "text"):
        if hasattr(run_input, attr):
            try:
                setattr(run_input, attr, new_text)
                return
            except Exception:
                continue


def _read_run_input_text(run_input: Any) -> str:
    for attr in ("input_content", "input", "text"):
        val = getattr(run_input, attr, None)
        if isinstance(val, str):
            return val
    return ""


def _get_input_strategy() -> str:
    """Return input compression strategy.

    Supported: 'tail_head' (default), 'summarize', 'hybrid'.
    """
    val = os.environ.get("ADORABLE_CTX_INPUT_STRATEGY", "tail_head").strip().lower()
    if val in {"tail_head", "summarize", "hybrid"}:
        return val
    return "tail_head"


def _compress_text(text: str, cap_chars: int, strategy: str) -> str:
    """Compress input text according to strategy while preserving intent."""
    if cap_chars <= 0 or cap_chars >= len(text):
        return text

    # Default head/tail preservation
    if strategy == "tail_head":
        head = text[: cap_chars // 2]
        tail = text[-(cap_chars // 2) :]
        return "[Input compressed to fit model context]\n" + head + "\n...\n" + tail

    # Hybrid: try to preserve first fenced code block if present
    if strategy == "hybrid":
        block_start = text.find("```")
        block_end = -1
        preserved = ""
        if block_start != -1:
            block_end = text.find("```", block_start + 3)
            if block_end != -1:
                preserved = text[block_start : block_end + 3]
        remaining = max(0, cap_chars - len(preserved))
        if remaining <= 0:
            return "[Input compressed to fit model context]\n" + preserved
        head = text[: remaining // 2]
        tail = text[-(remaining // 2) :]
        return "[Input compressed to fit model context]\n" + head + "\n" + preserved + "\n...\n" + tail

    # Summarize (placeholder): fallback to head/tail due to no external calls
    head = text[: cap_chars // 2]
    tail = text[-(cap_chars // 2) :]
    note = "[Input compressed (summary fallback) to fit model context]"
    return note + "\n" + head + "\n...\n" + tail


def assemble_context_preview(agent: Any, session: Any, run_input: Any) -> list[str]:
    """Assemble a coarse preview of context parts for budgeting.

    This does not attempt to faithfully reconstruct Agno's final context.
    Instead, it collects the major static parts (system prompt & instructions),
    the current input, and a rough placeholder for history based on configured
    `num_history_runs`.
    """
    system_parts: list[str] = []
    system_parts.append(_get_str(getattr(agent, "description", "")))
    instr = getattr(agent, "instructions", None)
    if isinstance(instr, (list, tuple)):
        system_parts.extend([_get_str(x) for x in instr])
    else:
        system_parts.append(_get_str(instr))

    # Session state may be joined into system context by Agno when enabled.
    # Avoid stringifying the entire dict; include only relevant fields (e.g., todos).
    add_ss_ctx = bool(getattr(agent, "add_session_state_to_context", False))
    if add_ss_ctx:
        try:
            ss = getattr(session, "session_state", None)
            if isinstance(ss, dict):
                todos = ss.get("todos")
                if todos is not None:
                    system_parts.append(_get_str(todos))
            # else: do not include arbitrary session_state blob
        except Exception:
            pass

    # If session summaries are enabled and added to context, include summary text
    add_summary = bool(getattr(agent, "add_session_summary_to_context", False))
    enable_summary = bool(getattr(agent, "enable_session_summaries", False))
    if add_summary and enable_summary:
        try:
            summary_text = ""
            # Preferred: Agent.get_session_summary(session=...)
            get_sum = getattr(agent, "get_session_summary", None)
            if callable(get_sum):
                try:
                    summary_text = _get_str(get_sum(session=session) if session is not None else get_sum())
                except TypeError:
                    # Fallback if signature differs
                    summary_text = _get_str(get_sum())
            else:
                # Alternate: agent.session_summary_manager.get_session_summary(...)
                ssm = getattr(agent, "session_summary_manager", None)
                fn = getattr(ssm, "get_session_summary", None)
                if callable(fn):
                    try:
                        summary_text = _get_str(fn(session=session) if session is not None else fn())
                    except TypeError:
                        summary_text = _get_str(fn())
            if summary_text:
                system_parts.append(summary_text)
        except Exception:
            # If any error occurs, skip adding summary to keep guard robust
            pass

    user_text = _read_run_input_text(run_input)
    history_runs = int(getattr(agent, "num_history_runs", 0) or 0)
    add_hist = bool(getattr(agent, "add_history_to_context", False))

    # Try to collect exact history texts when strategy allows
    hist_strategy = os.environ.get("ADORABLE_CTX_HISTORY_STRATEGY", "avg_only").strip().lower()

    def _collect_recent_history_texts(limit: int) -> list[str]:
        texts: list[str] = []
        if limit <= 0:
            return texts
        # Common potential attributes
        for attr in ("history_messages", "messages", "chat_history"):
            msgs = getattr(agent, attr, None)
            if isinstance(msgs, (list, tuple)) and msgs:
                # take last `limit` items
                for m in list(msgs)[-limit:]:
                    # dict-like or object-like content
                    if isinstance(m, dict):
                        c = m.get("content") or m.get("text") or ""
                        texts.append(_get_str(c))
                    else:
                        c = getattr(m, "content", None) or getattr(m, "text", None) or ""
                        texts.append(_get_str(c))
                break
        return texts

    history_preview = ""
    if add_hist and history_runs > 0 and hist_strategy == "exact_when_possible":
        hist_texts = _collect_recent_history_texts(history_runs)
        if hist_texts:
            history_preview = "\n".join(hist_texts)
    if not history_preview:
        # Fallback: placeholder
        history_preview = "[history placeholder x{}]".format(history_runs)

    return [
        "\n".join(system_parts),
        user_text,
        history_preview,
    ]


def _estimate_vlm_image_tokens(run_input: Any) -> int:
    """Estimate image token budget for VLM inputs via env configuration."""
    per_image = 0
    try:
        per_image = int(os.environ.get("ADORABLE_VLM_IMAGE_TOKENS_PER_IMAGE", "0").strip())
    except Exception:
        per_image = 0
    if per_image <= 0:
        return 0
    # Try common attributes for image payload
    images = None
    for attr in ("images", "image_urls", "attachments"):
        val = getattr(run_input, attr, None)
        if val is not None:
            images = val
            break
    count = 0
    if isinstance(images, (list, tuple)):
        if attr == "attachments":
            # Count only image-like attachments
            for it in images:
                kind = None
                if isinstance(it, dict):
                    kind = (it.get("type") or it.get("kind") or "").lower()
                else:
                    kind = str(getattr(it, "type", "") or getattr(it, "kind", "")).lower()
                if "image" in (kind or ""):
                    count += 1
        else:
            count = len(images)
    return count * per_image


def ensure_context_within_window(
    agent: Any,
    run_input: Any,
    session: Optional[Any] = None,
    **_: Any,
) -> None:
    """Pre-hook that keeps the context within the model window.

    Strategy:
    - Estimate total tokens for (system + input + placeholder history).
    - Compare with (context_window - max_output - margin).
    - If over budget, progressively reduce `agent.num_history_runs`.
    - If still over, lightly compress the input by slicing head/tail.
    - Record original settings for later restoration.
    """
    model_id = _get_model_id(agent)
    context_window = get_context_window(model_id)
    max_output = _get_max_output_tokens(agent)
    margin = _get_margin_tokens()

    # Assemble preview
    preview_parts = assemble_context_preview(agent, session, run_input)
    est_tokens = estimate_tokens(preview_parts, model_id) + _estimate_vlm_image_tokens(run_input)

    budget = context_window - max_output - margin
    if budget <= 0:
        # Pathological: keep as-is
        return

    # Save previous settings for post-hook restore on a private agent attribute
    try:
        prev: Dict[str, Any] = {
            "num_history_runs": getattr(agent, "num_history_runs", None),
            "add_history_to_context": getattr(agent, "add_history_to_context", None),
        }
        setattr(agent, "_ctx_guard_prev", prev)
    except Exception:
        pass

    if est_tokens <= budget:
        return  # Already within limits

    # First, reduce history runs until within budget
    avg_per_run = _avg_tokens_per_run()
    cur_runs = int(getattr(agent, "num_history_runs", 0) or 0)
    # If history inclusion is disabled, skip trimming
    add_hist = bool(getattr(agent, "add_history_to_context", False))

    if add_hist and cur_runs > 0:
        while cur_runs > 0:
            # Reduce the estimate by one run and check
            cur_runs -= 1
            setattr(agent, "num_history_runs", cur_runs)
            est_tokens -= avg_per_run
            if est_tokens <= budget:
                return

    # If still over budget, disable history entirely as a last resort
    if add_hist:
        try:
            setattr(agent, "add_history_to_context", False)
            est_tokens -= cur_runs * avg_per_run
        except Exception:
            pass
        if est_tokens <= budget:
            return

    # Light input compression (configurable strategy) to preserve intent
    user_text = _read_run_input_text(run_input)
    if user_text:
        # Keep a balanced slice of the input
        # Target tokens: leave space for system + margin
        # Convert to chars approx; use a conservative cap
        allow_tokens = max(256, budget - estimate_tokens(preview_parts[:1], model_id))
        # chars ≈ tokens * 3.5
        cap_chars = int(allow_tokens * 3.5)
        if cap_chars < len(user_text):
            strategy = _get_input_strategy()
            new_text = _compress_text(user_text, cap_chars, strategy)
            _mutate_run_input_text(run_input, new_text)

            # Re-evaluate after compression; if still close or over budget, lightly shrink once more
            new_preview = assemble_context_preview(agent, session, run_input)
            new_est = estimate_tokens(new_preview, model_id)
            if new_est > budget:
                # Small additional shrink (15%)
                cap_chars2 = max(128, int(cap_chars * 0.85))
                newer_text = _compress_text(_read_run_input_text(run_input), cap_chars2, strategy)
                _mutate_run_input_text(run_input, newer_text)


def restore_context_settings(agent: Any, session: Optional[Any] = None, **_: Any) -> None:
    """Post-hook to restore Agent settings changed by the context guard.

    Uses a private attribute on the agent to avoid polluting session_state.
    """
    try:
        prev = getattr(agent, "_ctx_guard_prev", None)
        if not isinstance(prev, dict):
            return
        # Restore values if present
        for key in ("num_history_runs", "add_history_to_context"):
            if key in prev and prev[key] is not None:
                try:
                    setattr(agent, key, prev[key])
                except Exception:
                    pass
        # Clean up the private attribute
        try:
            delattr(agent, "_ctx_guard_prev")
        except Exception:
            pass
    except Exception:
        return
