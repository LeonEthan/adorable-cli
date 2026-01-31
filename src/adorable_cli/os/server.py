from __future__ import annotations

from typing import Any, Callable


class _AgentOSApp:
    """Minimal AgentOS app wrapper."""

    def __init__(self) -> None:
        self._app = self._build_app()

    @staticmethod
    def _build_app() -> Callable[..., Any]:
        async def app(scope, receive, send):  # type: ignore[override]
            if scope.get("type") != "http":
                return

            path = scope.get("path", "")
            if path == "/status":
                body = b'{"status":"ok"}'
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return

            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"Not Found"})

        return app

    def get_app(self) -> Callable[..., Any]:
        return self._app


def create_agent_os() -> _AgentOSApp:
    return _AgentOSApp()


app = create_agent_os().get_app()
