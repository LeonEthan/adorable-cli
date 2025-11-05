from typing import Any, Dict


def summarize_args(args: Dict[str, Any]) -> str:
    """Create a compact, safe summary string for tool args.

    - Hides common secret keys
    - Truncates long values to keep single-line rendering readable
    - Caps overall summary length
    """
    if not args:
        return ""

    hidden_keys = {"api_key", "token", "password", "secret"}
    parts = []
    for key, value in args.items():
        if key in hidden_keys:
            continue
        sval = str(value)
        if len(sval) > 64:
            sval = sval[:61] + "..."
        parts.append(f"{key}={sval}")

    summary = ", ".join(parts)
    if len(summary) > 100:
        summary = summary[:97] + "..."
    return summary