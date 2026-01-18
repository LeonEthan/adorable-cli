from __future__ import annotations

import inspect
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class WorkflowResult:
    workflow_id: str
    output: str
    format: str = "markdown"


RunWorkflowFn = Callable[..., Awaitable[WorkflowResult]]


@dataclass(frozen=True)
class WorkflowSpec:
    workflow_id: str
    description: str
    run: RunWorkflowFn


class UnknownWorkflowError(ValueError):
    pass


def list_workflows() -> list[WorkflowSpec]:
    return [
        WorkflowSpec(
            workflow_id="research",
            description="search -> analyze -> write",
            run=run_research_workflow,
        ),
        WorkflowSpec(
            workflow_id="code-review",
            description="diff parse -> run tests -> summarize findings (markdown report)",
            run=run_code_review_workflow,
        ),
    ]


def get_workflow(workflow_id: str) -> WorkflowSpec:
    normalized = (workflow_id or "").strip()
    for wf in list_workflows():
        if wf.workflow_id == normalized:
            return wf
    raise UnknownWorkflowError(f"Unknown workflow: {workflow_id}")


async def run_research_workflow(
    *,
    input_text: str,
    component: Any | None = None,
    offline: bool = False,
    session_id: str | None = None,
    user_id: str | None = None,
) -> WorkflowResult:
    if offline or component is None:
        output = (
            "# Research Workflow\n\n"
            "## Search\n"
            "- Queries:\n"
            "- Sources:\n\n"
            "## Analysis\n"
            "- Key points:\n"
            "- Tradeoffs:\n\n"
            "## Answer\n"
            f"{input_text.strip()}\n"
        )
        return WorkflowResult(workflow_id="research", output=output)

    prompt = (
        "Run the 'research' workflow with these steps:\n"
        "1) Search: find relevant information and cite sources (URLs if web).\n"
        "2) Analyze: distill key points and tradeoffs.\n"
        "3) Write: provide the final answer.\n\n"
        "Output markdown with exactly these headings:\n"
        "## Search\n"
        "## Analysis\n"
        "## Answer\n\n"
        f"User input:\n{input_text.strip()}\n"
    )
    content = await _run_component(component, prompt, session_id=session_id, user_id=user_id)
    return WorkflowResult(workflow_id="research", output=content)


async def run_code_review_workflow(
    *,
    input_text: str | None = None,
    diff_file: Path | None = None,
    run_tests: bool = True,
    tests_cmd: str = "pytest -q",
    timeout_s: float = 900.0,
) -> WorkflowResult:
    diff_text = ""
    if diff_file is not None:
        diff_text = diff_file.read_text(encoding="utf-8", errors="replace")
    elif input_text:
        diff_text = input_text
    else:
        diff_text = _safe_git_diff() or ""

    stats = _parse_unified_diff_stats(diff_text)

    test_section = "## Tests\n- Skipped\n"
    if run_tests:
        test_result = _run_tests_command(tests_cmd=tests_cmd, timeout_s=timeout_s)
        test_section = _render_tests_section(test_result, tests_cmd=tests_cmd)

    report = (
        "# Code Review Report\n\n"
        "## Summary\n"
        f"- Files changed: {len(stats.files)}\n"
        f"- Lines added: {stats.additions}\n"
        f"- Lines removed: {stats.deletions}\n\n"
        "## Changed Files\n"
        + ("\n".join(f"- {p}" for p in stats.files) + "\n\n" if stats.files else "- (none)\n\n")
        + test_section
        + "\n"
        "## Notes\n"
        "- Review the diff for correctness, edge cases, and error handling.\n"
    )
    return WorkflowResult(workflow_id="code-review", output=report)


async def _run_component(
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


@dataclass(frozen=True)
class DiffStats:
    files: list[str]
    additions: int
    deletions: int


def _parse_unified_diff_stats(diff_text: str) -> DiffStats:
    files: list[str] = []
    additions = 0
    deletions = 0

    for line in (diff_text or "").splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                b_path = parts[3]
                if b_path.startswith("b/"):
                    b_path = b_path[2:]
                if b_path not in files:
                    files.append(b_path)
            continue

        if line.startswith("+++ ") or line.startswith("--- "):
            continue

        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1

    return DiffStats(files=files, additions=additions, deletions=deletions)


@dataclass(frozen=True)
class TestRunResult:
    exit_code: int
    stdout: str
    stderr: str


def _run_tests_command(*, tests_cmd: str, timeout_s: float) -> TestRunResult:
    args = shlex.split(tests_cmd)
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return TestRunResult(
            exit_code=int(completed.returncode),
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
    except subprocess.TimeoutExpired as e:
        out = getattr(e, "stdout", "") or ""
        err = getattr(e, "stderr", "") or ""
        return TestRunResult(exit_code=124, stdout=str(out), stderr=str(err))


def _safe_git_diff() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _render_tests_section(
    result: TestRunResult,
    *,
    tests_cmd: str,
    tail_lines: int = 50,
) -> str:
    status = "passed" if result.exit_code == 0 else f"failed (exit {result.exit_code})"
    stdout_tail = "\n".join((result.stdout or "").splitlines()[-tail_lines:])
    stderr_tail = "\n".join((result.stderr or "").splitlines()[-tail_lines:])

    body = f"## Tests\n- Command: `{_escape_inline_code(tests_cmd)}`\n- Status: {status}\n"
    if stdout_tail.strip():
        body += "\n### Stdout (tail)\n```\n" + stdout_tail + "\n```\n"
    if stderr_tail.strip():
        body += "\n### Stderr (tail)\n```\n" + stderr_tail + "\n```\n"
    return body


def _escape_inline_code(text: str) -> str:
    return text.replace("`", "'")
