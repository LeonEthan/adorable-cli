# AGENTS.md

This file is guidance for agentic coding assistants working in this repo.
It summarizes build/lint/test commands and the expected code style.

## Project Summary
- Repo: `adorable-cli`
- Language: Python 3.10+
- Package layout: `src/adorable_cli/`
- CLI entrypoint: `adorable` / `ador`

## Setup
- Install editable: `pip install -e .`
- Install with dev tools: `pip install -e ".[dev]"`
- Recommended: `uv pip install -e .`

## Build & Packaging
- Build sdist/wheel: `python -m build`
- Versioning: `setuptools_scm` (tag-derived)

## Test Commands
- All unit tests: `pytest tests/unit/`
- Specific module: `pytest tests/unit/ui/`
- Single test file: `pytest tests/unit/ui/test_stream_renderer.py`
- Single test case: `pytest tests/unit/ui/test_stream_renderer.py::test_render_stream`
- Verbose: `pytest -v tests/unit/`
- With output: `pytest -s tests/unit/`

## Lint / Format / Types
- Lint (ruff): `ruff check src/`
- Format (black): `black src/`
- Type check (mypy): `mypy src/adorable_cli/`
- Line length: 100 (ruff + black)

## Running the CLI
- Start interactive: `adorable`
- Alias: `ador`
- Configure: `ador config`
- Help: `ador --help`

## Configuration Notes
- Config file: `~/.adorable/config.json` (canonical; legacy `~/.adorable/config` is also maintained)
- Env vars: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `DEEPAGENTS_MODEL_ID`

## Code Style Guidelines

### Formatting
- Follow Black formatting with line length 100.
- Keep diffs minimal; do not reformat unrelated code.
- Use trailing commas where Black expects them (collections, function args).

### Imports
- Group imports in this order: standard library, third-party, local.
- Separate groups with a blank line.
- Prefer explicit imports over wildcard imports.
- Avoid importing unused symbols; keep imports minimal.

### Typing
- Use type hints for public functions and complex logic.
- Prefer `typing` primitives (`list[str]`, `dict[str, Any]`) on Python 3.10+.
- Use `Optional[T]` or `T | None` (preferred) when values may be missing.
- Keep type signatures accurate for async functions and generators.

### Naming
- Files/modules: `snake_case.py`.
- Classes: `PascalCase`.
- Functions/variables: `snake_case`.
- Constants: `UPPER_SNAKE_CASE`.
- CLI options should match existing patterns in `main.py`.

### Error Handling
- Validate inputs at boundaries (CLI options, config loading).
- Raise specific exceptions where possible; avoid bare `except`.
- When catching exceptions, log or surface context without swallowing errors.
- Do not change global error handling patterns in `ui/interactive.py` unless required.

### Logging
- Follow existing logging practices (see CLI debug flags).
- Avoid noisy logs in normal flow; respect debug flags.

### Async Code
- Use `async`/`await` consistently in UI loops.
- Avoid blocking I/O in async paths; use provided helpers.
- In tests, use `@pytest.mark.asyncio` for async tests.

### CLI & UX
- Keep user-facing messages concise and consistent.
- Respect existing confirmation flows for shell operations.
- Avoid adding emojis unless explicitly requested.

### Tests
- Add tests under `tests/unit/` when changing behavior.
- Name tests descriptively and keep them focused.
- Prefer small, deterministic unit tests over heavy integration tests.

### Documentation
- Update README or inline docstrings only when necessary.
- Do not add new docs files unless requested.

## Repository Conventions
- Source code lives under `src/adorable_cli/`.
- Tooling and prompts are in `src/adorable_cli/agent/`.
- UI loop and commands live in `src/adorable_cli/ui/interactive.py`.
- Custom tools are under `src/adorable_cli/tools/`.

## Cursor / Copilot Rules
- No `.cursor/rules`, `.cursorrules`, or `.github/copilot-instructions.md` found.

## When in Doubt
- Prefer minimal, surgical changes.
- Follow patterns already used in nearby files.
- Ask for clarification if requirements are ambiguous.
