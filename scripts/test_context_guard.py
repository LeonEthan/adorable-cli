#!/usr/bin/env python3
"""
Context Guard test script.

This script verifies the pre-hook that keeps model context within window by:
- Building the main Agent and optionally the VLM Agent
- Submitting a very long input to trigger budgeting logic
- Or invoking the pre-hook directly on a synthetic run_input

All comments are in English by request.
"""

from __future__ import annotations

import argparse
import os
import sys
from types import SimpleNamespace
from pathlib import Path


def _add_src_to_path() -> None:
    """Ensure `src/` is on sys.path for local runs without installation."""
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))


_add_src_to_path()

from adorable_cli.main import build_agent, CONFIG_FILE  # noqa: E402
from adorable_cli.hooks.context_guard import (
    ensure_context_within_window,
    estimate_tokens,
    get_context_window,
)  # noqa: E402


def load_config_to_env() -> None:
    """Load `~/.adorable/config` KEY=VALUE pairs into environment if present."""
    cfg_path = CONFIG_FILE
    try:
        if Path(cfg_path).exists():
            for line in Path(cfg_path).read_text().splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass


def make_very_long_input(repeat: int) -> str:
    base = "Please read and process the following instructions carefully. "
    long_chunk = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Curabitur dignissim, sapien in sollicitudin commodo, "
        "nibh lacus placerat sem, a luctus orci turpis vitae nulla. "
    )
    return base + (long_chunk * max(1, repeat))


def run_direct_hook_test(window: int | None, margin: str | None, avg_run: int, repeat: int) -> int:
    # Optional tuning via env
    if window:
        os.environ['ADORABLE_CONTEXT_WINDOW'] = str(window)
    if margin:
        os.environ['ADORABLE_CTX_MARGIN'] = str(margin)
    os.environ['ADORABLE_CTX_AVG_RUN_TOKENS'] = str(avg_run)

    agent = build_agent()

    class RunInput:
        def __init__(self, text: str):
            self.input_content = text

    ri = RunInput(make_very_long_input(repeat))
    session = SimpleNamespace(session_state={})

    print('Before length:', len(ri.input_content))
    print('Before num_history_runs:', getattr(agent, 'num_history_runs', None))
    print('Before add_history_to_context:', getattr(agent, 'add_history_to_context', None))

    ensure_context_within_window(agent=agent, run_input=ri, session=session)

    print('After length:', len(ri.input_content))
    print('After startswith compressed tag:', ri.input_content.startswith('[Input compressed to fit model context]'))
    print('After num_history_runs:', getattr(agent, 'num_history_runs', None))
    print('After add_history_to_context:', getattr(agent, 'add_history_to_context', None))

    # Budget-based check using the same estimator
    model_id = getattr(getattr(agent, 'model', None), 'id', '') or ''
    context_window = get_context_window(model_id)
    max_output = int(getattr(getattr(agent, 'model', None), 'max_tokens', 2048))
    # Parse margin from env (fallback to 1024)
    m_env = os.environ.get('ADORABLE_CTX_MARGIN', '1024').strip()
    try:
        margin_tokens = int(m_env)
    except Exception:
        margin_tokens = 1024
    budget = context_window - max_output - margin_tokens

    # Rough system parts
    system_parts = []
    system_parts.append(str(getattr(agent, 'description', '')))
    instr = getattr(agent, 'instructions', None)
    if isinstance(instr, (list, tuple)):
        system_parts.extend([str(x) for x in instr])
    else:
        system_parts.append(str(instr))

    est = estimate_tokens(["\n".join(system_parts), ri.input_content], model_id)
    ok = est <= budget
    print(f'Estimated tokens: {est} / Budget: {budget} (window={context_window}, max_output={max_output}, margin={margin_tokens})')
    print('Within budget:', ok)
    return 0 if ok else 1


def run_agent_call_test(window: int | None, margin: str | None, avg_run: int, repeat: int) -> int:
    # Optional tuning via env
    if window:
        os.environ['ADORABLE_CONTEXT_WINDOW'] = str(window)
    if margin:
        os.environ['ADORABLE_CTX_MARGIN'] = str(margin)
    os.environ['ADORABLE_CTX_AVG_RUN_TOKENS'] = str(avg_run)

    agent = build_agent()

    very_long_input = make_very_long_input(repeat)
    print('Sending very long input... length=', len(very_long_input))
    try:
        resp = agent.run(very_long_input, stream=False)
        content = getattr(resp, 'content', '')
        print('\n--- Response (truncated) ---')
        print(content[:1000] + ('...\n[truncated]' if len(content) > 1000 else ''))
        return 0
    except Exception as e:
        print('Run failed with exception:', type(e).__name__, str(e))
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Test the Context Guard pre-hook.')
    parser.add_argument('--mode', choices=['direct', 'run'], default='direct', help='Test mode: direct hook or full agent.run call')
    parser.add_argument('--window', type=int, default=None, help='Override context window (tokens)')
    parser.add_argument('--margin', type=str, default=None, help='Safety margin tokens or percentage (e.g., 1024 or 5%)')
    parser.add_argument('--avg-run', type=int, default=512, help='Average tokens per history run for budgeting')
    parser.add_argument('--repeat', type=int, default=3000, help='Repeat factor for long input construction')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode env vars')

    args = parser.parse_args(argv)

    # Load config and set model defaults if missing
    load_config_to_env()
    os.environ.setdefault('ADORABLE_MODEL_ID', 'gpt-5-mini')

    if args.debug:
        os.environ.setdefault('AGNO_DEBUG', '1')
        os.environ.setdefault('AGNO_DEBUG_LEVEL', '1')

    if args.mode == 'direct':
        return run_direct_hook_test(args.window, args.margin, args.avg_run, args.repeat)
    else:
        return run_agent_call_test(args.window, args.margin, args.avg_run, args.repeat)


if __name__ == '__main__':
    raise SystemExit(main())