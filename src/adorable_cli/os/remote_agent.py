from __future__ import annotations

from typing import Any, AsyncIterator, Iterable


class RemoteAgent:
    """Minimal remote agent wrapper for AgentOS attach workflow."""

    def __init__(
        self,
        client: Any,
        agent_id: str,
        session_id: str | None = None,
        user_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.client = client
        self.agent_id = agent_id
        self.session_id = session_id
        self.user_id = user_id
        self.headers = headers

    async def arun(self, *args: Any, **kwargs: Any) -> Iterable[Any]:
        """Placeholder async run for compatibility with run_interactive."""
        return []

    async def acontinue_run(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        """Placeholder async continuation for compatibility with run_interactive."""
        if False:  # pragma: no cover - generator placeholder
            yield None
