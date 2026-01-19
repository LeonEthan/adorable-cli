import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from adorable_cli.evals.runner import EvalRunner
from adorable_cli.evals.types import EvalSuite

@pytest.mark.asyncio
async def test_runner_execution(tmp_path, monkeypatch):
    runner = EvalRunner()
    
    # Mock suite
    suite_file = tmp_path / "test_suite.yaml"
    suite_file.write_text("""
name: Test Suite
cases:
  - input: hello
    expected: world
  - input: foo
    expected_contains: bar
""", encoding="utf-8")
    
    suite = runner.load_suite(suite_file)
    assert suite.name == "Test Suite"
    assert len(suite.cases) == 2
    
    # Mock build_component
    mock_agent = MagicMock()
    
    # Mock arun response
    # Scenario: first call returns "world" (pass), second returns "baz" (fail, expects "bar")
    response1 = MagicMock()
    response1.content = "world"
    
    response2 = MagicMock()
    response2.content = "baz"
    
    mock_agent.arun = AsyncMock(side_effect=[response1, response2])
    
    monkeypatch.setattr("adorable_cli.evals.runner.build_component", lambda team=None: mock_agent)
    
    report = await runner.run_suite(suite)
    
    assert report.total == 2
    assert report.passed == 1
    assert report.failed == 1
    assert report.results[0].success is True
    assert report.results[1].success is False
