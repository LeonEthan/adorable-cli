from __future__ import annotations

from typing import Any, AsyncIterator, Optional

from agno.client import AgentOSClient
from agno.models.response import ToolExecution


class RemoteAgent:
    def __init__(
        self,
        *,
        client: AgentOSClient,
        agent_id: str,
        session_id: str | None = None,
        user_id: str | None = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self._client = client
        self._agent_id = agent_id
        self._session_id = session_id
        self._user_id = user_id
        self._headers = headers

    async def arun(
        self,
        message: str,
        *,
        stream: bool = False,
        stream_intermediate_steps: bool = True,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ):
        effective_session_id = session_id if session_id is not None else self._session_id
        effective_user_id = user_id if user_id is not None else self._user_id

        if stream:
            return self._client.run_agent_stream(
                agent_id=self._agent_id,
                message=message,
                session_id=effective_session_id,
                user_id=effective_user_id,
                headers=self._headers,
                stream_events=stream_intermediate_steps,
                **kwargs,
            )
        return await self._client.run_agent(
            agent_id=self._agent_id,
            message=message,
            session_id=effective_session_id,
            user_id=effective_user_id,
            headers=self._headers,
            **kwargs,
        )

    async def acontinue_run(
        self,
        *,
        run_id: str | None = None,
        updated_tools: list[ToolExecution] | None = None,
        stream: bool = False,
        stream_intermediate_steps: bool = True,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ):
        effective_run_id = run_id or ""
        tools = updated_tools or []
        effective_session_id = session_id if session_id is not None else self._session_id
        effective_user_id = user_id if user_id is not None else self._user_id

        if stream:
            return self._client.continue_agent_run_stream(
                agent_id=self._agent_id,
                run_id=effective_run_id,
                tools=tools,
                session_id=effective_session_id,
                user_id=effective_user_id,
                headers=self._headers,
                stream_events=stream_intermediate_steps,
                **kwargs,
            )

        return await self._client.continue_agent_run(
            agent_id=self._agent_id,
            run_id=effective_run_id,
            tools=tools,
            session_id=effective_session_id,
            user_id=effective_user_id,
            headers=self._headers,
            **kwargs,
        )
