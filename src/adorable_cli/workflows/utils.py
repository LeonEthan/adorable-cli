from __future__ import annotations

import inspect
from typing import Any


async def run_component(
    component: Any,
    message: str,
    *,
    session_id: str | None,
    user_id: str | None,
) -> str:
    resp = component.arun(
        message,
        stream=False,
        stream_intermediate_steps=False,
        session_id=session_id,
        user_id=user_id,
    )
    if inspect.isawaitable(resp):
        resp = await resp

    content = getattr(resp, "content", None)
    if isinstance(content, str) and content.strip():
        return content

    message_text = getattr(resp, "message", None)
    if isinstance(message_text, str) and message_text.strip():
        return message_text

    return str(resp)
