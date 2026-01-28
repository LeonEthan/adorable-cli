from __future__ import annotations

from types import SimpleNamespace

from typer.testing import CliRunner


def test_attach_list_sessions(monkeypatch):
    from adorable_cli.main import app

    class FakeClient:
        def __init__(self, base_url: str, *args, **kwargs) -> None:
            self.base_url = base_url

        async def aget_config(self, headers=None):
            return SimpleNamespace(agents=[SimpleNamespace(id="agent-1")])

        async def get_sessions(
            self,
            session_type=None,
            component_id=None,
            user_id=None,
            session_name=None,
            limit=20,
            page=1,
            sort_by="created_at",
            sort_order="desc",
            db_id=None,
            table=None,
            headers=None,
        ):
            return SimpleNamespace(
                data=[
                    SimpleNamespace(session_id="s1", session_name="First"),
                    SimpleNamespace(session_id="s2", session_name=None),
                ]
            )

    monkeypatch.setattr("agno.client.AgentOSClient", FakeClient)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "attach",
            "localhost:7777",
            "--list-sessions",
            "--user-id",
            "u1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "s1  First" in result.output
    assert "s2" in result.output

